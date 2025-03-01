import re
import uuid
from pathlib import Path

_UNSAFE = re.compile(r"[^\w.\-]+", re.UNICODE)


class FileStorage:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def save(self, site_id: uuid.UUID, filename: str, data: bytes) -> str:
        safe_name = _UNSAFE.sub("_", Path(filename).name)[-120:] or "file"
        relative = Path(str(site_id)) / f"{uuid.uuid4().hex[:12]}_{safe_name}"
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return relative.as_posix()

    def read(self, relative: str) -> bytes:
        return self._resolve(relative).read_bytes()

    def delete(self, relative: str) -> None:
        self._resolve(relative).unlink(missing_ok=True)

    def _resolve(self, relative: str) -> Path:
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError("Path escapes storage root")
        return path
