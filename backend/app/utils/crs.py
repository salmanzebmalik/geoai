# backend/app/utils/crs.py

from pyproj.aoi import AreaOfInterest
from pyproj.database import query_utm_crs_info

# WGS 84 is the only datum we use: it covers the whole world and is what the
# rest of the pipeline already speaks (the bbox and the result GeoJSON are both
# EPSG:4326), so no datum shift is introduced on the way in or out.
DATUM = "WGS 84"


def best_crs_for_bbox(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
) -> str:
    """
    Pick the best projected CRS for a bbox given in EPSG:4326 (lon/lat degrees).

    Returns an "EPSG:<code>" string that can be passed straight to tiTiler's
    bbox endpoint as dst_crs, e.g. "EPSG:32632" for Münster.

    Looks up the UTM zone covering the bbox in the EPSG database, so metres are
    the unit everywhere in the world.
    """

    matches = query_utm_crs_info(
        datum_name=DATUM,
        area_of_interest=AreaOfInterest(
            west_lon_degree=min_lon,
            south_lat_degree=min_lat,
            east_lon_degree=max_lon,
            north_lat_degree=max_lat,
        ),
    )

    if not matches:
        raise ValueError(f"No UTM zone found for bbox: {min_lon},{min_lat},{max_lon},{max_lat}")

    return f"EPSG:{matches[0].code}"
