from dataclasses import dataclass
from math import ceil

from pyproj import Transformer

from app.core.config import settings
from app.schemas.segmentation import BoundingBox, SourceType
from app.utils.crs import best_crs_for_bbox


@dataclass(frozen=True)
class RasterSizeEstimate:
    width_pixels: int
    height_pixels: int
    total_pixels: int
    resolution_meters: float
    projected_crs: str

    @property
    def megapixels(self) -> float:
        return self.total_pixels / 1_000_000


def get_source_resolution(source_type: SourceType) -> float:
    if source_type == "ortho":
        resolution = settings.ortho_resolution_meters_per_pixel
    elif source_type == "satellite":
        resolution = settings.satellite_resolution_meters_per_pixel
    else:
        raise ValueError(f"Unsupported source_type: {source_type}")

    if resolution <= 0:
        raise RuntimeError(
            f"Resolution for source '{source_type}' must be greater than zero"
        )

    return resolution


def estimate_raster_size(
    bbox: BoundingBox,
    source_type: SourceType,
) -> RasterSizeEstimate:
    """Estimate the dimensions of the projected TiTiler crop."""

    resolution = get_source_resolution(source_type)

    if settings.raster_estimate_margin < 1:
        raise RuntimeError("RASTER_ESTIMATE_MARGIN must be at least 1.0")

    projected_crs = best_crs_for_bbox(
        min_lon=bbox.min_lon,
        min_lat=bbox.min_lat,
        max_lon=bbox.max_lon,
        max_lat=bbox.max_lat,
    )

    transformer = Transformer.from_crs(
        "EPSG:4326",
        projected_crs,
        always_xy=True,
    )

    longitudes = (
        bbox.min_lon,
        bbox.min_lon,
        bbox.max_lon,
        bbox.max_lon,
    )
    latitudes = (
        bbox.min_lat,
        bbox.max_lat,
        bbox.min_lat,
        bbox.max_lat,
    )

    x_coordinates, y_coordinates = transformer.transform(
        longitudes,
        latitudes,
    )

    width_meters = max(x_coordinates) - min(x_coordinates)
    height_meters = max(y_coordinates) - min(y_coordinates)

    margin = settings.raster_estimate_margin

    width_pixels = max(
        1,
        ceil((width_meters / resolution) * margin),
    )
    height_pixels = max(
        1,
        ceil((height_meters / resolution) * margin),
    )

    return RasterSizeEstimate(
        width_pixels=width_pixels,
        height_pixels=height_pixels,
        total_pixels=width_pixels * height_pixels,
        resolution_meters=resolution,
        projected_crs=projected_crs,
    )


def validate_raster_budget(
    bbox: BoundingBox,
    source_type: SourceType,
) -> RasterSizeEstimate:
    """Reject raster requests that exceed the configured safety limits."""

    if settings.max_input_raster_pixels <= 0:
        raise RuntimeError(
            "MAX_INPUT_RASTER_PIXELS must be greater than zero"
        )

    if settings.max_input_raster_side_pixels <= 0:
        raise RuntimeError(
            "MAX_INPUT_RASTER_SIDE_PIXELS must be greater than zero"
        )

    estimate = estimate_raster_size(
        bbox=bbox,
        source_type=source_type,
    )

    exceeds_total = (
        estimate.total_pixels > settings.max_input_raster_pixels
    )
    exceeds_side = (
        estimate.width_pixels > settings.max_input_raster_side_pixels
        or estimate.height_pixels > settings.max_input_raster_side_pixels
    )

    if exceeds_total or exceeds_side:
        raise ValueError(
            "Requested area is too large for the current synchronous "
            f"prediction pipeline. Estimated raster: "
            f"{estimate.width_pixels:,} × {estimate.height_pixels:,} "
            f"pixels ({estimate.megapixels:.1f} MP). Current limits: "
            f"{settings.max_input_raster_pixels / 1_000_000:.1f} MP total "
            f"and {settings.max_input_raster_side_pixels:,} pixels per side. "
            "Please select a smaller area."
        )

    return estimate