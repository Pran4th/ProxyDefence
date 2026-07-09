from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from backend.shared.logging_config import get_logger
from config import DVC_REMOTE

logger = get_logger(__name__)


class DvcManager:
    def __init__(self, remote: str = DVC_REMOTE):
        self._remote = remote
        self._dvc_available = shutil.which("dvc") is not None

    def track(self, path: str) -> dict:
        p = Path(path)
        if self._dvc_available:
            try:
                subprocess.run(["dvc", "add", str(p)], check=True, capture_output=True, timeout=60)
                logger.info("dvc tracked", path=path)
                return {"tracked": True, "method": "dvc", "path": path}
            except Exception as e:
                logger.warning("dvc add failed, falling back to metadata tracking", path=path, error=str(e))

        remote_dir = Path(self._remote)
        remote_dir.mkdir(parents=True, exist_ok=True)
        meta_path = remote_dir / f"{p.name}.meta.json"
        meta_path.write_text(json.dumps({
            "path": str(p),
            "tracked_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        }))
        return {"tracked": True, "method": "metadata", "path": path, "meta_path": str(meta_path)}
