from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


SourceType = Literal["satellite", "ortho", "sentinel"]
ModelType = Literal["tree", "tree_satlas", "tree_unet", "tree_deepforest", "zeroshot"]
MODELS_BY_SOURCE: dict[SourceType, tuple[ModelType, ...]] = {
    "ortho": (
        "tree",
        "tree_deepforest",
        "zeroshot",
    ),
    "satellite": (
        "tree_satlas",
        "tree_unet",
    ),
    # Sentinel-2 is 10 m RGB like the "satellite" source, so the same models
    # apply. Required: upstream's validators do MODELS_BY_SOURCE[source_type],
    # which raises KeyError for a source with no entry.
    "sentinel": (
        "tree_satlas",
        "tree_unet",
    ),
}
VectorFormat = Literal["geojson", "gpkg", "flatgeobuf", "shapefile"]
GeometryType = Literal["Polygon", "MultiPolygon"]


class BoundingBox(BaseModel):
    min_lat: float = Field(..., description="Minimum latitude boundary")
    max_lat: float = Field(..., description="Maximum latitude boundary")
    min_lon: float = Field(..., description="Minimum longitude boundary")
    max_lon: float = Field(..., description="Maximum longitude boundary")


class PredictionRequest(BaseModel):
    bbox: BoundingBox

    # Default keeps your old behavior.
    # Frontend can omit this and tree detection will run.
    model_type: ModelType = "tree"

    # Only used when model_type = "zeroshot".
    # Supply either one keyword or the keywords list below.
    keyword: Optional[str] = None

    # Multiple zero-shot terms are evaluated one after another and merged.
    keywords: List[str] = Field(default_factory=list, max_length=20)

    # The default tree model expects 10 cm orthophoto imagery.
    source_type: SourceType = "ortho"

    # Sentinel-2 only. The crop must be taken from the same imagery the user is
    # looking at, so the frontend sends its current date range and cloud filter
    # rather than letting the backend fall back to its config defaults -- a
    # prediction run against a different window than the map shows would be
    # silently wrong.
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    max_cloud_cover: Optional[float] = None

    @model_validator(mode="after")
    def validate_model_parameters(self) -> "PredictionRequest":
        self.keyword = self.keyword.strip() if self.keyword else None
        self.keywords = list(
            dict.fromkeys(
                term.strip()
                for term in self.keywords
                if term.strip()
            )
        )

        allowed_models = MODELS_BY_SOURCE[self.source_type]

        if self.model_type not in allowed_models:
            allowed_text = ", ".join(allowed_models)

            raise ValueError(
                f"Model '{self.model_type}' is not compatible with "
                f"source '{self.source_type}'. Allowed models for "
                f"'{self.source_type}': {allowed_text}"
            )

        if self.model_type == "zeroshot":
            if not (self.keyword or self.keywords):
                raise ValueError(
                    "keyword or keywords is required when "
                    "model_type is 'zeroshot'"
                )
        else:
            # Keywords have no meaning for the fixed tree models.
            self.keyword = None
            self.keywords = []

        return self

    def requested_keywords(self) -> List[str]:
        return list(
            dict.fromkeys(
                ([self.keyword] if self.keyword else []) + self.keywords
            )
        )


class FetchImageRequest(BaseModel):
    bbox: BoundingBox
    source_type: SourceType = "satellite"

    # Sentinel-2 only; see PredictionRequest above.
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    max_cloud_cover: Optional[float] = None


class RasterEstimateRequest(BaseModel):
    bbox: BoundingBox
    source_type: SourceType = "satellite"
    model_type: Optional[ModelType] = None

    @model_validator(mode="after")
    def validate_model_source(
        self,
    ) -> "RasterEstimateRequest":
        if self.model_type is None:
            return self

        allowed_models = MODELS_BY_SOURCE[self.source_type]

        if self.model_type not in allowed_models:
            allowed_text = ", ".join(allowed_models)

            raise ValueError(
                f"Model '{self.model_type}' is not compatible "
                f"with source '{self.source_type}'. Allowed "
                f"models: {allowed_text}"
            )

        return self


class RasterEstimateResponse(BaseModel):
    source_type: SourceType
    model_type: Optional[ModelType] = None
    width_pixels: int
    height_pixels: int
    total_pixels: int
    megapixels: float
    resolution_meters: float
    projected_crs: str
    allowed: bool
    max_total_pixels: int
    max_side_pixels: int

class ImageInfo(BaseModel):
    image_url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    format: Optional[str] = "tiff"


class GeoJSONGeometry(BaseModel):
    type: Literal["Polygon", "MultiPolygon"]

    # Use flexible coordinates because Polygon and MultiPolygon have different nesting.
    coordinates: List[Any]


class GeoJSONFeature(BaseModel):
    type: Literal["Feature"]
    properties: Dict[str, Any]
    geometry: GeoJSONGeometry


class GeoJSONFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"]
    name: Optional[str] = None
    features: List[GeoJSONFeature]


class PredictionOutput(BaseModel):
    prediction_type: str
    model_name: str
    result_url: str
    feature_count: int
    summary: Optional[str] = None


class PredictionResponse(BaseModel):
    query_id: UUID
    status: str
    bbox: BoundingBox
    image: Optional[ImageInfo] = None
    prediction: Optional[PredictionOutput] = None
    created_at: datetime


class PredictionHistoryItem(BaseModel):
    query_id: UUID
    bbox: BoundingBox
    created_at: datetime
    prediction_type: Optional[str] = None
    model_name: Optional[str] = None
    summary: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)


class ExportFilterOptions(BaseModel):
    min_area_m2: Optional[float] = Field(default=None, ge=0)
    max_area_m2: Optional[float] = Field(default=None, ge=0)
    min_confidence: Optional[float] = Field(default=None, ge=0, le=1)
    geometry_types: List[GeometryType] = Field(default_factory=list)
    labels: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_area_range(self) -> "ExportFilterOptions":
        if (
            self.min_area_m2 is not None
            and self.max_area_m2 is not None
            and self.min_area_m2 > self.max_area_m2
        ):
            raise ValueError("min_area_m2 must not exceed max_area_m2")
        self.labels = list(
            dict.fromkeys(label.strip() for label in self.labels if label.strip())
        )
        return self


class ExportOptions(BaseModel):
    include_geojson: bool = True
    include_annotated_tiff: bool = True
    include_mask_tiff: bool = False
    include_metadata: bool = True
    include_zip: bool = True
    overlay_color: str = "#ff0000"
    overlay_opacity: float = Field(default=0.45, ge=0, le=1)
    output_crs: str = "EPSG:4326"
    vector_formats: List[VectorFormat] = Field(
        default_factory=lambda: ["geojson"]
    )
    filters: ExportFilterOptions = Field(default_factory=ExportFilterOptions)

    @field_validator("overlay_color")
    @classmethod
    def validate_overlay_color(cls, value: str) -> str:
        value = value.strip().lower()
        if len(value) != 7 or not value.startswith("#"):
            raise ValueError("overlay_color must use #RRGGBB notation")
        try:
            int(value[1:], 16)
        except ValueError as error:
            raise ValueError("overlay_color must use #RRGGBB notation") from error
        return value

    @field_validator("output_crs")
    @classmethod
    def validate_output_crs(cls, value: str) -> str:
        from rasterio.crs import CRS

        try:
            return CRS.from_user_input(value).to_string()
        except Exception as error:
            raise ValueError(f"Invalid output_crs: {value}") from error

    @model_validator(mode="after")
    def normalize_formats(self) -> "ExportOptions":
        self.vector_formats = list(dict.fromkeys(self.vector_formats))
        if self.include_geojson and "geojson" not in self.vector_formats:
            self.vector_formats.insert(0, "geojson")
        if not self.include_geojson and "geojson" in self.vector_formats:
            self.vector_formats.remove("geojson")
        if not any(
            (
                self.vector_formats,
                self.include_annotated_tiff,
                self.include_mask_tiff,
                self.include_metadata,
                self.include_zip,
            )
        ):
            raise ValueError("At least one export artifact must be selected")
        return self


class ExportRequest(BaseModel):
    query_id: UUID
    options: ExportOptions = Field(default_factory=ExportOptions)


class PredictionExportRequest(PredictionRequest):
    export: ExportOptions = Field(default_factory=ExportOptions)


class ExportArtifact(BaseModel):
    name: str
    media_type: str
    download_url: str


class ExportResponse(BaseModel):
    export_id: UUID
    query_id: UUID
    created_at: datetime
    model_type: Optional[ModelType] = None
    keywords: List[str] = Field(default_factory=list)
    source_feature_count: int
    exported_feature_count: int
    output_crs: str
    artifacts: List[ExportArtifact]


class PredictionExportResponse(BaseModel):
    prediction: PredictionResponse
    export: ExportResponse
