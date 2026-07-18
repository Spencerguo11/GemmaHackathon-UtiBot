"""Safe local folder navigation for the coordinator agent."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from config import DATA_DIR, PROJECT_ROOT, get_settings

settings = get_settings()


def _is_under_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return path == root


def _default_roots() -> list[Path]:
    home = Path.home()
    roots = [
        home,
        home / "Downloads",
        home / "Documents",
        home / "Desktop",
        PROJECT_ROOT,
        DATA_DIR,
    ]
    extra = os.getenv("ALLOWED_BROWSE_ROOTS", "")
    for item in extra.split(","):
        item = item.strip()
        if item:
            roots.append(Path(item).expanduser().resolve())
    unique: list[Path] = []
    for root in roots:
        try:
            resolved = root.expanduser().resolve()
        except OSError:
            continue
        if resolved.exists() and resolved not in unique:
            unique.append(resolved)
    return unique


def resolve_user_path(path_str: str) -> Path:
    """Resolve and validate a user/agent supplied path."""
    if not path_str or not str(path_str).strip():
        raise ValueError("Path is required")

    raw = str(path_str).strip().replace("\\", "/")
    if raw.startswith("~"):
        candidate = Path(raw).expanduser()
    elif raw.startswith("/"):
        candidate = Path(raw)
    else:
        candidate = Path.home() / raw

    resolved = candidate.resolve()
    allowed_roots = _default_roots()
    if not any(_is_under_root(resolved, root) for root in allowed_roots):
        allowed = ", ".join(str(r) for r in allowed_roots[:5])
        raise ValueError(f"Path not allowed: {resolved}. Allowed areas include: {allowed}")

    if not resolved.exists():
        raise ValueError(f"Path does not exist: {resolved}")
    return resolved


def list_directory(path_str: str) -> dict:
    """List files and folders at a path."""
    path = resolve_user_path(path_str)
    if not path.is_dir():
        raise ValueError(f"Not a directory: {path}")

    entries = []
    for entry in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))[:100]:
        if entry.name.startswith("."):
            continue
        entries.append(
            {
                "name": entry.name,
                "type": "directory" if entry.is_dir() else "file",
                "path": str(entry),
            }
        )
    return {"path": str(path), "entries": entries}


def find_zip_files(path_str: str, *, max_depth: int = 4) -> dict:
    """Find ZIP archives under a directory."""
    root = resolve_user_path(path_str)
    if root.is_file() and root.suffix.lower() == ".zip":
        return {"path": str(root.parent), "zip_files": [str(root)]}

    if not root.is_dir():
        raise ValueError(f"Not a directory: {root}")

    matches: list[str] = []

    def walk(current: Path, depth: int) -> None:
        if depth > max_depth:
            return
        for entry in current.iterdir():
            if entry.name.startswith("."):
                continue
            if entry.is_file() and entry.suffix.lower() == ".zip":
                matches.append(str(entry))
            elif entry.is_dir():
                walk(entry, depth + 1)

    walk(root, 0)
    matches.sort(key=lambda p: Path(p).stat().st_mtime, reverse=True)
    return {"path": str(root), "zip_files": matches[:settings.max_zip_files]}
