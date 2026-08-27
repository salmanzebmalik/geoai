import unittest
from unittest.mock import patch

from app.core.config import settings
from app.schemas.segmentation import BoundingBox
from app.utils.raster_budget import (
    RasterBudgetExceededError,
    RasterSizeEstimate,
    estimate_raster_size,
    raster_fits_budget,
    validate_raster_budget,
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
    
    @patch.object(
        settings,
        "max_ortho_tree_raster_pixels",
        210_000_000,
    )
    @patch.object(
        settings,
        "max_ortho_tree_raster_side_pixels",
        18_000,
    )
    def test_ortho_tree_uses_tested_large_budget(self):
        estimate = RasterSizeEstimate(
            width_pixels=17_557,
            height_pixels=11_392,
            total_pixels=200_009_344,
            resolution_meters=0.1,
            projected_crs="EPSG:32632",
        )

        self.assertTrue(
            raster_fits_budget(
                estimate,
                source_type="ortho",
                model_type="tree",
            )
        )


    @patch.object(
        settings,
        "max_input_raster_pixels",
        25_000_000,
    )
    @patch.object(
        settings,
        "max_input_raster_side_pixels",
        8_000,
    )
    def test_untested_model_uses_conservative_budget(self):
        estimate = RasterSizeEstimate(
            width_pixels=9_000,
            height_pixels=6_000,
            total_pixels=54_000_000,
            resolution_meters=0.1,
            projected_crs="EPSG:32632",
        )

        self.assertFalse(
            raster_fits_budget(
                estimate,
                source_type="ortho",
                model_type="zeroshot",
            )
        )


    @patch.object(
        settings,
        "max_ortho_tree_raster_pixels",
        210_000_000,
    )
    @patch.object(
        settings,
        "max_ortho_tree_raster_side_pixels",
        18_000,
    )
    def test_oversized_ortho_tree_raises_typed_error(self):
        large_bbox = BoundingBox(
            min_lon=7.54335,
            min_lat=51.92410,
            max_lon=7.70930,
            max_lat=51.98949,
        )

        with self.assertRaises(
            RasterBudgetExceededError
        ):
            validate_raster_budget(
                bbox=large_bbox,
                source_type="ortho",
                model_type="tree",
            )
        
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