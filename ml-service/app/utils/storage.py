from pathlib import Path


def ensure_path_inside_storage(path: str | Path, storage_root: str | Path) -> Path:
    resolved_path = Path(path).resolve()
    resolved_root = Path(storage_root).resolve()

    try:
        resolved_path.relative_to(resolved_root)
    except ValueError:
        raise ValueError(f"Path is outside shared storage: {resolved_path}")

    return resolved_path