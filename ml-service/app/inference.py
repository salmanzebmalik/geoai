from app.schemas import GeoJSONFeatureCollection
from app.models.treepipeline import InferencePipeline



_pipeline = InferencePipeline()

# Tree detection 
def run_tree_detection(image_path: str, bbox_coords: tuple):
    mask = _pipeline.get_full_mask(image_path)
    gdf = _pipeline.bbox_to_tree_geojson(bbox_coords, mask)
    if isinstance(gdf, gpd.GeoDataFrame):
        return json.loads(result.to_json())
    return gdf


def run_dummy_building_footprint_prediction() -> GeoJSONFeatureCollection:
    """
    Dummy building footprint prediction.

    For now, this returns fixed vector polygons.
    Later, this function will be replaced with real model inference.
    """





    return GeoJSONFeatureCollection(
        type="FeatureCollection",
        name="predicted_building_footprints",
        features=[
            {
                "type": "Feature",
                "properties": {
                    "building_id": 1,
                    "confidence": 0.91,
                    "source": "model_prediction"
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [120.0, 210.0],
                            [165.0, 210.0],
                            [165.0, 245.0],
                            [120.0, 245.0],
                            [120.0, 210.0]
                        ]
                    ]
                }
            },
            {
                "type": "Feature",
                "properties": {
                    "building_id": 2,
                    "confidence": 0.84,
                    "source": "model_prediction"
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [310.0, 420.0],
                            [348.0, 418.0],
                            [352.0, 455.0],
                            [315.0, 459.0],
                            [310.0, 420.0]
                        ]
                    ]
                }
            }
        ]
    )