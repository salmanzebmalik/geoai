import json
import os
import tempfile
from pathlib import Path
from typing import Any

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

def save_geojson_to_shared_storage(
    query_id: str,
    geojson: dict[str, Any],
    output_dir: str | None = None,
) -> str:
    """
    Save prediction GeoJSON atomically in shared storage.

    Returns the path relative to the shared-storage root, for example:
        queries/<query_id>/prediction.geojson
    """

    storage_root = get_shared_storage_path()

    requested_dir = (
        Path(output_dir)
        if output_dir is not None
        else storage_root / "queries" / query_id
    )

    try:
        safe_output_dir = ensure_path_inside_storage(
            requested_dir,
            storage_root,
        )

        result_path = ensure_path_inside_storage(
            safe_output_dir / "prediction.geojson",
            storage_root,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        ) from e

    safe_output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=safe_output_dir,
            prefix=".prediction.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:

            json.dump(
                geojson,
                temporary_file,
                ensure_ascii=False,
                separators=(",", ":"),
            )

            temporary_file.flush()
            os.fsync(temporary_file.fileno())

            temporary_path = Path(temporary_file.name)

        temporary_path.replace(result_path)

    except Exception as e:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

        raise HTTPException(
            status_code=500,
            detail=f"Failed to save prediction result: {str(e)}",
        ) from e

    return result_path.relative_to(storage_root).as_posix()