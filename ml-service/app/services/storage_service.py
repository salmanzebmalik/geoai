from fastapi import HTTPException

from app.core.config import get_shared_storage_path
from app.utils.storage import ensure_path_inside_storage


def read_image_from_shared_storage(
    input_image_path: str,
    output_dir: str | None = None,
) -> bytes:
    storage_root = get_shared_storage_path()

    try:
        input_path = ensure_path_inside_storage(
            input_image_path,
            storage_root,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not input_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Input image not found: {input_path}",
        )

    if not input_path.is_file():
        raise HTTPException(
            status_code=400,
            detail=f"Input path is not a file: {input_path}",
        )

    if output_dir is not None:
        try:
            safe_output_dir = ensure_path_inside_storage(
                output_dir,
                storage_root,
            )
            safe_output_dir.mkdir(parents=True, exist_ok=True)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    try:
        image_bytes = input_path.read_bytes()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read input image from shared storage: {str(e)}",
        )

    if len(image_bytes) == 0:
        raise HTTPException(
            status_code=400,
            detail="Input image exists but is empty.",
        )

    return image_bytes