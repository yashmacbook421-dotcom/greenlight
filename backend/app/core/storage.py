"""Content-addressed blob storage for uploaded documents.

Files are stored under their SHA-256, so identical uploads share one blob and
a stored file can be re-verified against the hash recorded in `documents`.
Local disk for now; an S3 implementation only needs `put` and `open`.
"""

import os
import tempfile
from pathlib import Path


class LocalStorage:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def _path(self, sha256: str) -> Path:
        return self.root / sha256[:2] / f"{sha256}.pdf"

    def put(self, sha256: str, data: bytes) -> str:
        path = self._path(sha256)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            # Write-then-rename so a crash never leaves a truncated file under a valid hash.
            fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".part")
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            os.replace(tmp, path)
        return path.as_uri()

    def open(self, sha256: str) -> bytes:
        return self._path(sha256).read_bytes()
