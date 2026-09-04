import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_bounds

from app.core.config import settings
from app.schemas.segmentation import ExportOptions
from app.services.annotation_export_service import export_annotations


class AnnotationExportVariantTests(unittest.TestCase):
    def test_raster_exports_support_both_langsam_variants(self):
        original_storage_dir = settings.shared_storage_dir
        try:
            with tempfile.TemporaryDirectory() as directory:
                settings.shared_storage_dir = directory
                for index, variant in enumerate(
                    ("sam2.1_hiera_large", "sam2.1_hiera_tiny"),
                    start=1,
                ):
                    with self.subTest(variant=variant):
                        query_id = f"00000000-0000-0000-0000-{index:012d}"
                        query_dir = Path(directory) / "queries" / query_id
                        query_dir.mkdir(parents=True)
                        self._write_source_raster(query_dir / "input.tiff")

                        manifest = export_annotations(
                            query_id=query_id,
                            annotations=self._annotations(),
                            options=ExportOptions(
                                include_geojson=False,
                                include_annotated_tiff=True,
                                include_mask_tiff=True,
                                include_metadata=True,
                                include_zip=False,
                            ),
                            prediction_metadata={
                                "model_type": "zeroshot",
                                "model_name": f"lang-sam-{variant}",
                                "model_variant": variant,
                                "keywords": ["building"],
                            },
                        )

                        artifact_names = {
                            artifact["name"]
                            for artifact in manifest["artifacts"]
                        }
                        self.assertIn("mask_tiff", artifact_names)
                        self.assertIn("annotated_tiff", artifact_names)
                        self.assertEqual(
                            manifest["prediction"]["model_variant"],
                            variant,
                        )
        finally:
            settings.shared_storage_dir = original_storage_dir

    @staticmethod
    def _write_source_raster(path: Path) -> None:
        data = np.full((3, 10, 10), 100, dtype=np.uint8)
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            width=10,
            height=10,
            count=3,
            dtype="uint8",
            crs="EPSG:4326",
            transform=from_bounds(7.61, 51.95, 7.62, 51.96, 10, 10),
        ) as target:
            target.write(data)

    @staticmethod
    def _annotations() -> dict:
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"class": "building"},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[
                            [7.612, 51.952],
                            [7.618, 51.952],
                            [7.618, 51.958],
                            [7.612, 51.958],
                            [7.612, 51.952],
                        ]],
                    },
                }
            ],
        }


if __name__ == "__main__":
    unittest.main()
