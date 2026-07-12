from pathlib import Path


def ensure_path_inside_storage(
    path: str | Path,
    storage_root: str | Path,
) -> Path:
    resolved_root = Path(storage_root).resolve()
    requested_path = Path(path)

    if requested_path.is_absolute():
        resolved_path = requested_path.resolve()
    else:
        resolved_path = (resolved_root / requested_path).resolve()

    try:
        resolved_path.relative_to(resolved_root)
    except ValueError:
        raise ValueError(
            f"Path is outside shared storage: {resolved_path}"
        )

    return resolved_path