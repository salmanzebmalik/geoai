import unittest

from pydantic import ValidationError

from app.schemas.segmentation import ExportResponse, PredictionRequest
from app.services.satellite_image_service import (
    TiTilerTimeoutError,
)
from app.utils.model_metadata import stored_model_variant

BBOX = {
    "min_lon": 7.61,
    "min_lat": 51.95,
    "max_lon": 7.62,
    "max_lat": 51.96,
}


class PredictionValidationTests(unittest.TestCase):
    def test_prediction_defaults_are_compatible(self):
        request = PredictionRequest(bbox=BBOX)

        self.assertEqual(request.model_type, "tree")
        self.assertEqual(request.source_type, "ortho")

    def test_accepts_supported_combinations(self):
        valid_requests = (
            {
                "source_type": "ortho",
                "model_type": "tree",
            },
            {
                "source_type": "ortho",
                "model_type": "tree_deepforest",
            },
            {
                "source_type": "ortho",
                "model_type": "zeroshot",
                "keyword": "tree",
            },
            {
                "source_type": "satellite",
                "model_type": "tree_satlas",
            },
            {
                "source_type": "satellite",
                "model_type": "tree_unet",
            },
        )

        for parameters in valid_requests:
            with self.subTest(parameters=parameters):
                request = PredictionRequest(
                    bbox=BBOX,
                    **parameters,
                )

                self.assertEqual(
                    request.model_type,
                    parameters["model_type"],
                )

    def test_rejects_unsupported_combinations(self):
        invalid_requests = (
            {
                "source_type": "ortho",
                "model_type": "tree_satlas",
            },
            {
                "source_type": "ortho",
                "model_type": "tree_unet",
            },
            {
                "source_type": "satellite",
                "model_type": "tree",
            },
            {
                "source_type": "satellite",
                "model_type": "tree_deepforest",
            },
            {
                "source_type": "satellite",
                "model_type": "zeroshot",
                "keyword": "tree",
            },
        )

        for parameters in invalid_requests:
            with self.subTest(parameters=parameters):
                with self.assertRaisesRegex(
                    ValidationError,
                    "not compatible",
                ):
                    PredictionRequest(
                        bbox=BBOX,
                        **parameters,
                    )

    def test_removes_keywords_from_fixed_models(self):
        request = PredictionRequest(
            bbox=BBOX,
            source_type="satellite",
            model_type="tree_satlas",
            keyword="tree",
            keywords=["building"],
        )

        self.assertIsNone(request.keyword)
        self.assertEqual(request.keywords, [])

    def test_accepts_both_langsam_variants(self):
        for variant in ("sam2.1_hiera_large", "sam2.1_hiera_tiny"):
            with self.subTest(variant=variant):
                request = PredictionRequest(
                    bbox=BBOX,
                    source_type="ortho",
                    model_type="zeroshot",
                    model_variant=variant,
                    keyword="building",
                )
                self.assertEqual(request.model_variant, variant)

    def test_recovers_variant_from_legacy_model_name(self):
        self.assertEqual(
            stored_model_variant(
                {"model_name": "lang-sam-sam2.1_hiera_tiny"}
            ),
            "sam2.1_hiera_tiny",
        )

    def test_export_response_exposes_model_variant(self):
        response = ExportResponse(
            export_id="00000000-0000-0000-0000-000000000001",
            query_id="00000000-0000-0000-0000-000000000002",
            created_at="2026-09-04T12:00:00Z",
            model_type="zeroshot",
            model_name="lang-sam-sam2.1_hiera_tiny",
            model_variant="sam2.1_hiera_tiny",
            source_feature_count=2,
            exported_feature_count=2,
            output_crs="EPSG:4326",
            artifacts=[],
        )
        self.assertEqual(response.model_variant, "sam2.1_hiera_tiny")


if __name__ == "__main__":
    unittest.main()
