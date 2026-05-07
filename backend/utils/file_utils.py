import json
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_") or "item"


async def save_upload_file(upload_file, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as handle:
        while True:
            chunk = await upload_file.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)


def safe_extract_zip(zip_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with zipfile.ZipFile(zip_path, "r") as archive:
        for member in archive.infolist():
            target = (destination / member.filename).resolve()
            if root not in target.parents and target != root:
                raise ValueError(f"Unsafe ZIP path rejected: {member.filename}")
        archive.extractall(destination)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def latest_child_dir(parent: Path) -> Optional[Path]:
    if not parent.exists():
        return None
    dirs = [path for path in parent.iterdir() if path.is_dir()]
    if not dirs:
        return None
    return max(dirs, key=lambda path: path.stat().st_mtime)


def iter_supported_files(root: Path, extensions: Iterable[str]):
    suffixes = {ext.lower() for ext in extensions}
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in suffixes:
            yield path

