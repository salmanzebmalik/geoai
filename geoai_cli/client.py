from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import Request, urlopen


DEFAULT_API_URL = "http://127.0.0.1:8013/api/segmentation"


class APIError(RuntimeError):
    """A user-facing API or connection error."""


class APIClient:
    def __init__(self, base_url: str | None = None, timeout: float = 600.0):
        self.base_url = (
            base_url or os.getenv("GEOAI_API_URL") or DEFAULT_API_URL
        ).rstrip("/")
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("API URL must be an absolute HTTP(S) URL")
        self.timeout = timeout

    def get(self, path: str, query: dict[str, Any] | None = None) -> Any:
        return self.request("GET", path, query=query)

    def post(self, path: str, payload: dict[str, Any]) -> Any:
        return self.request("POST", path, payload=payload)

    def delete(self, path: str) -> Any:
        return self.request("DELETE", path)

    def request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
    ) -> Any:
        url = self._url(path, query)
        body = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = Request(url, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                content = response.read()
        except HTTPError as error:
            detail = self._error_detail(error)
            raise APIError(f"API returned HTTP {error.code}: {detail}") from error
        except URLError as error:
            raise APIError(f"Could not reach {url}: {error.reason}") from error

        if not content:
            return None
        try:
            return json.loads(content)
        except json.JSONDecodeError as error:
            raise APIError(f"API returned invalid JSON from {url}") from error

    def download(self, path: str, destination: str | Path) -> tuple[Path, int]:
        url = self._url(path)
        target = Path(destination).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.part")
        request = Request(url, headers={"Accept": "*/*"}, method="GET")

        try:
            with urlopen(request, timeout=self.timeout) as response:
                with temporary.open("wb") as output:
                    total = 0
                    while chunk := response.read(1024 * 1024):
                        output.write(chunk)
                        total += len(chunk)
            os.replace(temporary, target)
        except HTTPError as error:
            temporary.unlink(missing_ok=True)
            detail = self._error_detail(error)
            raise APIError(f"API returned HTTP {error.code}: {detail}") from error
        except (URLError, OSError) as error:
            temporary.unlink(missing_ok=True)
            reason = getattr(error, "reason", error)
            raise APIError(f"Download from {url} failed: {reason}") from error

        return target, total

    def _url(
        self,
        path: str,
        query: dict[str, Any] | None = None,
    ) -> str:
        parsed = urlparse(path)
        if parsed.scheme in {"http", "https"}:
            url = path
        elif path.startswith("/"):
            url = urljoin(self.base_url + "/", path)
        else:
            url = f"{self.base_url}/{path.lstrip('/')}"

        filtered_query = {
            key: value
            for key, value in (query or {}).items()
            if value is not None
        }
        if filtered_query:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{urlencode(filtered_query, doseq=True)}"
        return url

    @staticmethod
    def _error_detail(error: HTTPError) -> str:
        try:
            payload = json.loads(error.read())
        except (json.JSONDecodeError, UnicodeDecodeError):
            return error.reason
        if isinstance(payload, dict) and "detail" in payload:
            return str(payload["detail"])
        return json.dumps(payload, ensure_ascii=False)
