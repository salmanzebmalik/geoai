from dataclasses import dataclass
from math import ceil

from pyproj import Transformer

from app.core.config import settings
from app.schemas.segmentation import (
    BoundingBox,
    ModelType,
    SourceType,
)
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


@dataclass(frozen=True)
class RasterBudget:
    max_total_pixels: int
    max_side_pixels: int


class RasterBudgetExceededError(ValueError):
    """Estimated raster exceeds its configured synchronous budget."""

    def __init__(
        self,
        estimate: RasterSizeEstimate,
        budget: RasterBudget,
    ) -> None:
        self.estimate = estimate
        self.budget = budget

        super().__init__(
            "Requested area is too large for the selected "
            "imagery and model combination. Estimated raster: "
            f"{estimate.width_pixels:,} × "
            f"{estimate.height_pixels:,} pixels "
            f"({estimate.megapixels:.1f} MP). Current limits: "
            f"{budget.max_total_pixels / 1_000_000:.1f} MP "
            f"total and {budget.max_side_pixels:,} pixels "
            "per side. Please select a smaller area."
        )


def get_raster_budget(
    source_type: SourceType | None = None,
    model_type: ModelType | None = None,
) -> RasterBudget:
    """
    Return the configured raster budget for an imagery source.
    """

    if source_type == "ortho":
        budget = RasterBudget(
            max_total_pixels=(
                settings.max_ortho_raster_pixels
            ),
            max_side_pixels=(
                settings.max_ortho_raster_side_pixels
            ),
        )

    else:
        # Satellite and requests without a resolved source use the
        # conservative general budget.
        budget = RasterBudget(
            max_total_pixels=(
                settings.max_input_raster_pixels
            ),
            max_side_pixels=(
                settings.max_input_raster_side_pixels
            ),
        )

    if budget.max_total_pixels <= 0:
        raise RuntimeError(
            "Maximum raster pixels must be greater than zero"
        )

    if budget.max_side_pixels <= 0:
        raise RuntimeError(
            "Maximum raster side pixels must be greater than zero"
        )

    return budget


def get_source_resolution(
    source_type: SourceType,
) -> float:
    if source_type == "ortho":
        resolution = (
            settings.ortho_resolution_meters_per_pixel
        )
    elif source_type == "satellite":
        resolution = (
            settings.satellite_resolution_meters_per_pixel
        )
    else:
        raise ValueError(
            f"Unsupported source_type: {source_type}"
        )

    if resolution <= 0:
        raise RuntimeError(
            f"Resolution for source '{source_type}' "
            "must be greater than zero"
        )

    return resolution


def estimate_raster_size(
    bbox: BoundingBox,
    source_type: SourceType,
) -> RasterSizeEstimate:
    """Estimate the dimensions of the projected TiTiler crop."""

    resolution = get_source_resolution(source_type)

    if settings.raster_estimate_margin < 1:
        raise RuntimeError(
            "RASTER_ESTIMATE_MARGIN must be at least 1.0"
        )

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

    width_meters = (
        max(x_coordinates) - min(x_coordinates)
    )
    height_meters = (
        max(y_coordinates) - min(y_coordinates)
    )

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


def raster_fits_budget(
    estimate: RasterSizeEstimate,
    *,
    source_type: SourceType | None = None,
    model_type: ModelType | None = None,
) -> bool:
    """Return whether an estimate fits its configured budget."""

    budget = get_raster_budget(
        source_type=source_type,
        model_type=model_type,
    )

    return (
        estimate.total_pixels
        <= budget.max_total_pixels
        and estimate.width_pixels
        <= budget.max_side_pixels
        and estimate.height_pixels
        <= budget.max_side_pixels
    )


def validate_raster_budget(
    bbox: BoundingBox,
    source_type: SourceType,
    model_type: ModelType | None = None,
) -> RasterSizeEstimate:
    """Reject requests exceeding their synchronous budget."""

    estimate = estimate_raster_size(
        bbox=bbox,
        source_type=source_type,
    )

    budget = get_raster_budget(
        source_type=source_type,
        model_type=model_type,
    )

    if not raster_fits_budget(
        estimate,
        source_type=source_type,
        model_type=model_type,
    ):
        raise RasterBudgetExceededError(
            estimate=estimate,
            budget=budget,
        )

    return estimate