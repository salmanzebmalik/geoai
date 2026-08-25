import unittest
from unittest.mock import patch

from app.core.config import settings
from app.schemas.segmentation import BoundingBox
from app.utils.raster_budget import (
    estimate_raster_size,
    validate_raster_budget,
    raster_fits_budget,
)

class RasterBudgetTests(unittest.TestCase):
    def setUp(self):
        self.small_bbox = BoundingBox(
            min_lon=7.610,
            max_lon=7.611,
            min_lat=51.950,
            max_lat=51.951,
        )

    @patch.object(
        settings,
        "ortho_resolution_meters_per_pixel",
        0.1,
    )
    @patch.object(settings, "raster_estimate_margin", 1.0)
    def test_estimates_small_ortho_raster(self):
        estimate = estimate_raster_size(
            bbox=self.small_bbox,
            source_type="ortho",
        )

        self.assertGreater(estimate.width_pixels, 600)
        self.assertLess(estimate.width_pixels, 800)
        self.assertGreater(estimate.height_pixels, 1000)
        self.assertLess(estimate.height_pixels, 1300)

    @patch.object(
        settings,
        "ortho_resolution_meters_per_pixel",
        0.1,
    )
    @patch.object(settings, "raster_estimate_margin", 1.1)
    @patch.object(settings, "max_input_raster_pixels", 25_000_000)
    @patch.object(settings, "max_input_raster_side_pixels", 8_000)
    def test_rejects_oversized_ortho_raster(self):
        large_bbox = BoundingBox(
            min_lon=7.60,
            max_lon=7.70,
            min_lat=51.90,
            max_lat=52.00,
        )

        with self.assertRaisesRegex(
            ValueError,
            "Requested area is too large",
        ):
            validate_raster_budget(
                bbox=large_bbox,
                source_type="ortho",
            )

    @patch.object(
        settings,
        "satellite_resolution_meters_per_pixel",
        3.0,
    )
    @patch.object(settings, "raster_estimate_margin", 1.1)
    @patch.object(settings, "max_input_raster_pixels", 25_000_000)
    @patch.object(settings, "max_input_raster_side_pixels", 8_000)
    def test_accepts_small_satellite_raster(self):
        estimate = validate_raster_budget(
            bbox=self.small_bbox,
            source_type="satellite",
        )

        self.assertLess(estimate.total_pixels, 25_000_000)
        
    @patch.object(
        settings,
        "ortho_resolution_meters_per_pixel",
        0.1,
    )
    @patch.object(settings, "raster_estimate_margin", 1.1)
    @patch.object(settings, "max_input_raster_pixels", 25_000_000)
    @patch.object(settings, "max_input_raster_side_pixels", 8_000)
    def test_small_raster_fits_budget(self):
        estimate = estimate_raster_size(
            bbox=self.small_bbox,
            source_type="ortho",
        )

        self.assertTrue(raster_fits_budget(estimate))

    @patch.object(
        settings,
        "ortho_resolution_meters_per_pixel",
        0.1,
    )
    @patch.object(settings, "raster_estimate_margin", 1.1)
    @patch.object(settings, "max_input_raster_pixels", 25_000_000)
    @patch.object(settings, "max_input_raster_side_pixels", 8_000)
    def test_large_raster_does_not_fit_budget(self):
        large_bbox = BoundingBox(
            min_lon=7.60,
            max_lon=7.70,
            min_lat=51.90,
            max_lat=52.00,
        )

        estimate = estimate_raster_size(
            bbox=large_bbox,
            source_type="ortho",
        )

        self.assertFalse(raster_fits_budget(estimate))


if __name__ == "__main__":
    unittest.main()