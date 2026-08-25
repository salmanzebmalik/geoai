from pathlib import Path
from urllib.parse import urlencode

import rasterio
import requests
from rasterio.features import geometry_mask
from rasterio.warp import transform_geom
from shapely.geometry import box as shp_box, mapping

from app.core.config import settings
from app.schemas.segmentation import BoundingBox, ImageInfo, SourceType
from app.utils.crs import best_crs_for_bbox
from app.utils.http import get_http_session

def get_shared_storage_dir() -> Path:
    """
    Return shared storage root.

    This directory must be visible to both:
    - backend service
    - ML service
    """
    path = settings.shared_storage_path
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_query_dir(query_id: str) -> Path:
    query_dir = get_shared_storage_dir() / "queries" / str(query_id)
    query_dir.mkdir(parents=True, exist_ok=True)
    return query_dir


def get_input_image_path(query_id: str) -> Path:
    return get_query_dir(query_id) / "input.tiff"


def bbox_to_titiler_string(bbox: BoundingBox) -> str:
    return f"{bbox.min_lon},{bbox.min_lat},{bbox.max_lon},{bbox.max_lat}"


def build_titiler_request(
    bbox: BoundingBox,
    source_type: SourceType = "satellite",
) -> tuple[str, dict]:
    bbox_string = bbox_to_titiler_string(bbox)
    
    dst_crs = best_crs_for_bbox(
        min_lon=bbox.min_lon,
        min_lat=bbox.min_lat,
        max_lon=bbox.max_lon,
        max_lat=bbox.max_lat,
    )

    # Both default to nearest, which aliases the imagery. "resampling" covers the read,
    # "reproject" the warp into dst_crs; the crop feeds a segmentation model, so smooth
    # edges matter more than the slightly cheaper interpolation.
    resampling = {"resampling": "cubic", "reproject": "cubic"}

    if source_type == "satellite":
        endpoint = f"{settings.titiler_base_url}/cog/bbox/{bbox_string}.tif"
        params = {
            "url": settings.satellite_vrt_path,
            "bidx": [3, 2, 1],
            "rescale": "0,3000",
            "dst_crs": dst_crs,
            **resampling,
        }
        return endpoint, params

    if source_type == "ortho":
        endpoint = f"{settings.titiler_base_url}/mosaicjson/bbox/{bbox_string}.tif"
        params = {
            "url": settings.ortho_mosaic_path,
            "dst_crs": dst_crs,
            **resampling,
        }
        return endpoint, params

    raise ValueError("Invalid source_type. Use 'satellite' or 'ortho'.")


def _write_bbox_masked_crop(
    image_bytes: bytes,
    bbox: BoundingBox,
    out_path: Path,
) -> tuple[int, int]:
    """Store the crop with everything outside the drawn bbox blacked out.

    tiTiler returns the crop as the axis-aligned UTM bounding box of the reprojected
    lon/lat box, so its corners cover ground *outside* the box the user drew. We
    rasterise the bbox polygon (reprojected into the crop's own CRS) and set every
    pixel outside it to 0, so the model doesn't detect features beyond the box. The
    CRS/transform are preserved, so georeferencing downstream is unaffected.

    Returns the (width, height) of the stored image.
    """
    with rasterio.MemoryFile(image_bytes) as memfile, memfile.open() as src:
        profile = src.profile
        data = src.read()
        width, height = src.width, src.height

        if src.crs is not None:
            aoi = transform_geom(
                "EPSG:4326",
                src.crs,
                mapping(shp_box(bbox.min_lon, bbox.min_lat, bbox.max_lon, bbox.max_lat)),
            )
            # invert=False -> True for pixels NOT covered by the AOI polygon
            outside = geometry_mask(
                [aoi],
                out_shape=(height, width),
                transform=src.transform,
                invert=False,
            )
            data[:, outside] = 0

    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(data)

    return width, height


def fetch_satellite_image_from_titiler(
    query_id: str,
    bbox: BoundingBox,
    source_type: SourceType = "satellite",
) -> tuple[str, ImageInfo]:
    """
    Fetch cropped image from tiTiler and save it into shared storage.

    Output:
        storage/queries/{query_id}/input.tiff
    """

    image_path = get_input_image_path(query_id)

    endpoint, params = build_titiler_request(
        bbox=bbox,
        source_type=source_type,
    )

    request_url = endpoint + "?" + urlencode(params, doseq=True)

    print("\n========== tiTiler Request Debug ==========")
    print("URL:", request_url)
    print("Source type:", source_type)
    print("Shared storage root:", get_shared_storage_dir())
    print("Output image path:", image_path)
    print("==========================================\n")

    session = get_http_session()
    session.trust_env = False

    try:
        
        response = session.get(
            request_url,
            timeout=(
                settings.titiler_connect_timeout_seconds,
                settings.titiler_read_timeout_seconds,
            ),
        )

        print("\n========== tiTiler Response Debug ==========")
        print("Status code:", response.status_code)
        print("Content-Type:", response.headers.get("content-type"))
        print("Content-Length:", response.headers.get("content-length"))
        print("Final URL:", response.url)
        print("===========================================\n")

        response.raise_for_status()

    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(
            f"Could not connect to tiTiler at {settings.titiler_base_url}: {e}"
        ) from e

    except requests.exceptions.Timeout as e:
        raise RuntimeError(
            "tiTiler request timed out "
            f"(connect={settings.titiler_connect_timeout_seconds}s, "
            f"read={settings.titiler_read_timeout_seconds}s): "
            f"{request_url}"
        ) from e

    except requests.exceptions.HTTPError as e:
        raise RuntimeError(
            f"tiTiler returned HTTP {response.status_code}: {response.text[:1000]}"
        ) from e

    except requests.exceptions.RequestException as e:
        raise RuntimeError(
            f"Failed to call tiTiler: {e}"
        ) from e

    if not response.content:
        raise RuntimeError("tiTiler returned an empty image.")

    image_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        width, height = _write_bbox_masked_crop(response.content, bbox, image_path)
    except Exception as e:
        raise RuntimeError(
            f"Failed to mask and save the crop from tiTiler: {image_path}. Error: {e}"
        ) from e

    image_info = ImageInfo(
        image_url=str(image_path),
        width=width,
        height=height,
        format="tiff",
    )

    return str(image_path), image_info