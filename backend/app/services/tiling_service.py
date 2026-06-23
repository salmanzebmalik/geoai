from dataclasses import dataclass

from app.schemas.segmentation import BoundingBox


@dataclass(frozen=True)
class TileSpec:
    tile_id: str
    core_bbox: BoundingBox
    inference_bbox: BoundingBox


def _round_bbox_value(value: float) -> float:
    return round(value, 12)


def _make_bbox(
    min_lat: float,
    max_lat: float,
    min_lon: float,
    max_lon: float,
) -> BoundingBox:
    return BoundingBox(
        min_lat=_round_bbox_value(min_lat),
        max_lat=_round_bbox_value(max_lat),
        min_lon=_round_bbox_value(min_lon),
        max_lon=_round_bbox_value(max_lon),
    )


def expand_bbox(
    core_bbox: BoundingBox,
    full_bbox: BoundingBox,
    overlap_deg: float,
) -> BoundingBox:
    """
    Expand the core tile by overlap_deg on all sides,
    but never go outside the original user-selected bbox.
    """

    return _make_bbox(
        min_lat=max(full_bbox.min_lat, core_bbox.min_lat - overlap_deg),
        max_lat=min(full_bbox.max_lat, core_bbox.max_lat + overlap_deg),
        min_lon=max(full_bbox.min_lon, core_bbox.min_lon - overlap_deg),
        max_lon=min(full_bbox.max_lon, core_bbox.max_lon + overlap_deg),
    )


def create_tile_plan(
    bbox: BoundingBox,
    tile_size_deg: float = 0.01,
    overlap_deg: float = 0.001,
    direct_threshold_deg: float = 0.01,
) -> list[TileSpec]:
    """
    Creates a tile plan.

    Small bbox:
        one tile only
        core_bbox == inference_bbox

    Larger bbox:
        core_bbox tiles do NOT overlap
        inference_bbox tiles overlap slightly
    """

    if tile_size_deg <= 0:
        raise ValueError("tile_size_deg must be greater than 0")

    if overlap_deg < 0:
        raise ValueError("overlap_deg cannot be negative")

    lat_span = bbox.max_lat - bbox.min_lat
    lon_span = bbox.max_lon - bbox.min_lon
    max_span = max(lat_span, lon_span)

    # Small bbox: use one direct tile
    if max_span <= direct_threshold_deg:
        return [
            TileSpec(
                tile_id="tile_0000",
                core_bbox=bbox,
                inference_bbox=bbox,
            )
        ]

    tiles: list[TileSpec] = []
    tile_index = 0

    epsilon = 1e-12

    lat = bbox.min_lat

    while lat < bbox.max_lat - epsilon:
        next_lat = min(lat + tile_size_deg, bbox.max_lat)

        lon = bbox.min_lon

        while lon < bbox.max_lon - epsilon:
            next_lon = min(lon + tile_size_deg, bbox.max_lon)

            core_bbox = _make_bbox(
                min_lat=lat,
                max_lat=next_lat,
                min_lon=lon,
                max_lon=next_lon,
            )

            inference_bbox = expand_bbox(
                core_bbox=core_bbox,
                full_bbox=bbox,
                overlap_deg=overlap_deg,
            )

            tiles.append(
                TileSpec(
                    tile_id=f"tile_{tile_index:04d}",
                    core_bbox=core_bbox,
                    inference_bbox=inference_bbox,
                )
            )

            tile_index += 1
            lon = next_lon

        lat = next_lat

    return tiles