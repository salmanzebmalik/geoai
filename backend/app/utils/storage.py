# backend/app/utils/storage.py

from pathlib import Path
from uuid import UUID


class QueryStorage:
    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir).resolve()
        self.queries_dir = self.base_dir / "queries"
        self.queries_dir.mkdir(parents=True, exist_ok=True)

    def get_query_dir(self, query_id: UUID | str) -> Path:
        query_dir = self.queries_dir / str(query_id)
        query_dir.mkdir(parents=True, exist_ok=True)
        return query_dir

    def get_input_image_path(self, query_id: UUID | str, suffix: str = ".tif") -> Path:
        return self.get_query_dir(query_id) / f"input{suffix}"

    def get_mask_path(self, query_id: UUID | str, suffix: str = ".tif") -> Path:
        return self.get_query_dir(query_id) / f"mask{suffix}"

    def get_geojson_path(self, query_id: UUID | str) -> Path:
        return self.get_query_dir(query_id) / "prediction.geojson"