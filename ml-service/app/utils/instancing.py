"""instance segmentation"""
import numpy as np
import scipy.ndimage as ndi
from skimage.feature import peak_local_max
from skimage.segmentation import watershed
import geopandas as gpd
from rasterio.features import shapes as rio_shapes
from rasterio.transform import from_bounds
from shapely.geometry import shape

def mask_to_instances(mask, min_distance=7, min_area=20, split_touching=True):
    """Binary/semantic mask (H, W) -> int32 label map (0 background, 1..N instances)."""
    mask = np.asarray(mask) > 0
    if not mask.any():
        return np.zeros(mask.shape, dtype=np.int32)

    if split_touching:
        distance = ndi.distance_transform_edt(mask)
        peaks = peak_local_max(distance, min_distance=min_distance, labels=mask, exclude_border=False)
        seeds = np.zeros(distance.shape, dtype=bool)
        seeds[tuple(peaks.T)] = True
        markers, _ = ndi.label(seeds)
        labels = watershed(-distance, markers, mask=mask)
    else:
        labels, _ = ndi.label(mask)

    if min_area > 0:
        counts = np.bincount(labels.ravel())
        small = np.flatnonzero(counts < min_area)
        small = small[small != 0]
        if small.size:
            labels[np.isin(labels, small)] = 0

    uniq = np.unique(labels)
    uniq = uniq[uniq != 0]
    remap = np.zeros(int(labels.max()) + 1, dtype=np.int32)
    remap[uniq] = np.arange(1, uniq.size + 1)
    return remap[labels].astype(np.int32)


def _area_m2(gdf):
    """True ground area, measured in a metric CRS.

    Measuring in EPSG:3857 overstates area by sec^2(latitude) -- 2.6x at 52 deg N --
    because Web Mercator is conformal, not equal-area. The crop's own UTM CRS is
    already metric, so areas are read straight off it.
    """
    metric = gdf if gdf.crs.is_projected else gdf.to_crs(gdf.estimate_utm_crs())
    return metric.geometry.area


def instances_to_geojson(labels, bounds, crs, class_name="tree", scores=None):
    """Instance label map -> GeoDataFrame with one feature per instance (id, area_m2).

    `bounds`/`crs` come from the input GeoTIFF, so the label grid is georeferenced in
    the raster's own (projected) CRS. Output is reprojected to WGS84, which GeoJSON
    requires and the frontend expects.
    """
    h, w = labels.shape
    transform = from_bounds(*bounds, w, h)

    records = []
    for geom, value in rio_shapes(labels.astype(np.int32), mask=(labels > 0), transform=transform):
        inst_id = int(value)
        records.append({
            "geometry": shape(geom),
            "properties": {
                "instance_id": inst_id,
                "class": class_name,
                "score": None if scores is None else scores.get(inst_id),
            },
        })
    if not records:
        return gpd.GeoDataFrame({"geometry": []}, crs="EPSG:4326")

    gdf = gpd.GeoDataFrame.from_features(records, crs=crs)
    gdf = gdf.dissolve(by="instance_id", as_index=False, aggfunc="first")
    gdf["area_m2"] = _area_m2(gdf)
    return gdf.to_crs("EPSG:4326")
