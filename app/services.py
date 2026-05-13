from pathlib import Path
from typing import Tuple

from PIL import Image, ImageDraw
from sqlmodel import Session

from app.db_models import SegmentationQuery
from app.schemas import (
    BoundingBox,
    ImageInfo,
    SegmentationClassResult,
    SegmentationPrediction,
    SegmentationRequest,
    SegmentationResponse,
)


STATIC_DIR = Path("static")
IMAGE_DIR = STATIC_DIR / "images"
MASK_DIR = STATIC_DIR / "masks"

IMAGE_WIDTH = 512
IMAGE_HEIGHT = 512


def validate_bbox(bbox: BoundingBox) -> None:
    """
    Validate that the bounding box coordinates are logically and geographically correct.
    """

    if bbox.north <= bbox.south:
        raise ValueError("north must be greater than south")

    if bbox.east <= bbox.west:
        raise ValueError("east must be greater than west")

    if not (-90 <= bbox.north <= 90):
        raise ValueError("north latitude must be between -90 and 90")

    if not (-90 <= bbox.south <= 90):
        raise ValueError("south latitude must be between -90 and 90")

    if not (-180 <= bbox.east <= 180):
        raise ValueError("east longitude must be between -180 and 180")

    if not (-180 <= bbox.west <= 180):
        raise ValueError("west longitude must be between -180 and 180")


def ensure_static_folders_exist() -> None:
    """
    Make sure image and mask folders exist.
    """

    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    MASK_DIR.mkdir(parents=True, exist_ok=True)


def generate_dummy_satellite_image(query_id: str) -> ImageInfo:
    """
    Generate a simple dummy satellite-like image.

    Later, this function will be replaced by real satellite image fetching.
    """

    ensure_static_folders_exist()

    image_path = IMAGE_DIR / f"{query_id}.png"

    image = Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT), color=(90, 130, 90))
    draw = ImageDraw.Draw(image)

    # Vegetation-like patches
    draw.rectangle([0, 0, 260, 512], fill=(70, 140, 70))
    draw.ellipse([300, 40, 500, 220], fill=(80, 160, 80))

    # Building-like blocks
    draw.rectangle([80, 80, 150, 150], fill=(180, 180, 180))
    draw.rectangle([170, 90, 250, 170], fill=(170, 170, 170))
    draw.rectangle([100, 230, 210, 330], fill=(190, 190, 190))
    draw.rectangle([280, 280, 390, 390], fill=(175, 175, 175))

    # Road-like lines
    draw.line([0, 420, 512, 420], fill=(110, 110, 110), width=35)
    draw.line([300, 0, 300, 512], fill=(100, 100, 100), width=30)

    # Water-like patch
    draw.ellipse([360, 330, 520, 510], fill=(70, 120, 180))

    image.save(image_path)

    return ImageInfo(
        image_url=f"/static/images/{query_id}.png",
        width=IMAGE_WIDTH,
        height=IMAGE_HEIGHT
    )


def generate_dummy_segmentation_mask(query_id: str) -> str:
    """
    Generate a dummy segmentation mask image.

    The mask uses transparent background so the frontend can overlay it on the satellite image.

    Later, this function will be replaced by the real ML model output mask.
    """

    ensure_static_folders_exist()

    mask_path = MASK_DIR / f"{query_id}_mask.png"

    mask = Image.new("RGBA", (IMAGE_WIDTH, IMAGE_HEIGHT), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(mask)

    # Buildings: red overlay
    draw.rectangle([80, 80, 150, 150], fill=(255, 0, 0, 120))
    draw.rectangle([170, 90, 250, 170], fill=(255, 0, 0, 120))
    draw.rectangle([100, 230, 210, 330], fill=(255, 0, 0, 120))
    draw.rectangle([280, 280, 390, 390], fill=(255, 0, 0, 120))

    # Vegetation: green overlay
    draw.rectangle([0, 0, 260, 512], fill=(0, 255, 0, 80))
    draw.ellipse([300, 40, 500, 220], fill=(0, 255, 0, 80))

    # Road: gray overlay
    draw.line([0, 420, 512, 420], fill=(100, 100, 100, 130), width=35)
    draw.line([300, 0, 300, 512], fill=(100, 100, 100, 130), width=30)

    # Water: blue overlay
    draw.ellipse([360, 330, 520, 510], fill=(0, 0, 255, 100))

    mask.save(mask_path)

    return f"/static/masks/{query_id}_mask.png"


def run_dummy_segmentation_model(mask_url: str) -> SegmentationPrediction:
    """
    Dummy semantic segmentation model.

    Later this function will:
    1. Load the real satellite image
    2. Run the real segmentation model
    3. Generate a real mask
    4. Calculate real class coverage percentages
    """

    classes = [
        SegmentationClassResult(class_name="building", coverage_percent=28.4),
        SegmentationClassResult(class_name="vegetation", coverage_percent=41.2),
        SegmentationClassResult(class_name="road", coverage_percent=12.7),
        SegmentationClassResult(class_name="water", coverage_percent=3.1),
        SegmentationClassResult(class_name="other", coverage_percent=14.6),
    ]

    return SegmentationPrediction(
        task="semantic_segmentation",
        model_name="default_land_cover_segmentation",
        classes=classes,
        mask_url=mask_url,
        summary="The selected area contains mostly vegetation and buildings."
    )


def create_segmentation_prediction(
    request: SegmentationRequest,
    session: Session
) -> SegmentationResponse:
    """
    Main workflow:
    1. Validate bbox
    2. Create DB row first to get query_id
    3. Generate dummy satellite image
    4. Generate dummy segmentation mask
    5. Generate dummy prediction metadata
    6. Save everything in Supabase
    7. Return response
    """

    validate_bbox(request.bbox)

    # Create a first DB row so we get an official query_id.
    db_query = SegmentationQuery(
        north=request.bbox.north,
        south=request.bbox.south,
        east=request.bbox.east,
        west=request.bbox.west,
        status="processing",
        image_url=None,
        image_width=IMAGE_WIDTH,
        image_height=IMAGE_HEIGHT,
        prediction_result={},
        summary="Segmentation request is being processed.",
    )

    session.add(db_query)
    session.commit()
    session.refresh(db_query)

    query_id = str(db_query.id)

    image = generate_dummy_satellite_image(query_id=query_id)
    mask_url = generate_dummy_segmentation_mask(query_id=query_id)
    prediction = run_dummy_segmentation_model(mask_url=mask_url)

    db_query.status = "completed"
    db_query.image_url = image.image_url
    db_query.image_width = image.width
    db_query.image_height = image.height
    db_query.prediction_result = prediction.model_dump()
    db_query.summary = prediction.summary

    session.add(db_query)
    session.commit()
    session.refresh(db_query)

    return SegmentationResponse(
        query_id=db_query.id,
        status=db_query.status,
        bbox=request.bbox,
        image=image,
        prediction=prediction,
        created_at=db_query.created_at
    )