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
from uuid import uuid4

TITILER_DOWNLOAD_CHUNK_SIZE_BYTES = 1024 * 1024

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
    source_path: Path,
    bbox: BoundingBox,
    out_path: Path,
) -> tuple[int, int]:
    """Mask and store a raster crop one block at a time.

    Pixels outside the user-drawn bounding box are set to zero. Processing
    block by block prevents the complete raster and mask from being loaded
    into backend memory at once.

    Returns the width and height of the stored image.
    """

    with rasterio.open(source_path) as src:
        profile = src.profile.copy()
        width = src.width
        height = src.height

        aoi = None

        if src.crs is not None:
            aoi = transform_geom(
                "EPSG:4326",
                src.crs,
                mapping(
                    shp_box(
                        bbox.min_lon,
                        bbox.min_lat,
                        bbox.max_lon,
                        bbox.max_lat,
                    )
                ),
            )

        with rasterio.open(out_path, "w", **profile) as dst:
            for _, window in src.block_windows(1):
                data = src.read(window=window)

                if aoi is not None:
                    outside = geometry_mask(
                        [aoi],
                        out_shape=(
                            int(window.height),
                            int(window.width),
                        ),
                        transform=src.window_transform(window),
                        invert=False,
                    )

                    data[:, outside] = 0

                dst.write(data, window=window)

    return width, height

def _stream_response_to_file(
    response: requests.Response,
    destination: Path,
) -> int:
    """Stream an HTTP response to disk and return the bytes written."""

    bytes_written = 0

    with destination.open("wb") as output_file:
        for chunk in response.iter_content(
            chunk_size=TITILER_DOWNLOAD_CHUNK_SIZE_BYTES
        ):
            if not chunk:
                continue

            output_file.write(chunk)
            bytes_written += len(chunk)

    return bytes_written

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

    image_path.parent.mkdir(parents=True, exist_ok=True)

    transfer_id = uuid4().hex

    download_path = image_path.with_name(
        f".{image_path.name}.{transfer_id}.download.part"
    )
    masked_path = image_path.with_name(
        f".{image_path.name}.{transfer_id}.masked.part"
    )

    response: requests.Response | None = None
    bytes_written = 0

    try:
        try:
            response = session.get(
                request_url,
                stream=True,
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

            bytes_written = _stream_response_to_file(
                response=response,
                destination=download_path,
            )

            print("Downloaded tiTiler bytes:", bytes_written)

        except requests.exceptions.ConnectionError as e:
            raise RuntimeError(
                f"Could not connect to tiTiler at "
                f"{settings.titiler_base_url}: {e}"
            ) from e

        except requests.exceptions.Timeout as e:
            raise RuntimeError(
                "tiTiler request timed out "
                f"(connect={settings.titiler_connect_timeout_seconds}s, "
                f"read={settings.titiler_read_timeout_seconds}s): "
                f"{request_url}"
            ) from e

        except requests.exceptions.HTTPError as e:
            status_code = (
                e.response.status_code
                if e.response is not None
                else "unknown"
            )
            response_preview = (
                e.response.text[:1000]
                if e.response is not None
                else str(e)
            )

            raise RuntimeError(
                f"tiTiler returned HTTP {status_code}: "
                f"{response_preview}"
            ) from e

        except requests.exceptions.RequestException as e:
            raise RuntimeError(
                f"Failed while downloading the crop from tiTiler: {e}"
            ) from e

        except OSError as e:
            raise RuntimeError(
                f"Failed to stream the tiTiler crop to "
                f"{download_path}: {e}"
            ) from e

        finally:
            if response is not None:
                response.close()

        if bytes_written == 0:
            raise RuntimeError("tiTiler returned an empty image.")

        try:
            width, height = _write_bbox_masked_crop(
                source_path=download_path,
                bbox=bbox,
                out_path=masked_path,
            )

            # Atomic publication: input.tiff appears only after masking
            # and writing have completed successfully.
            masked_path.replace(image_path)

        except Exception as e:
            raise RuntimeError(
                f"Failed to mask and save the crop from tiTiler: "
                f"{image_path}. Error: {e}"
            ) from e

    finally:
        download_path.unlink(missing_ok=True)
        masked_path.unlink(missing_ok=True)

    image_info = ImageInfo(
        image_url=str(image_path),
        width=width,
        height=height,
        format="tiff",
    )

    return str(image_path), image_info