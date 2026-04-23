"""Git helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .log import get_logger

log = get_logger(__name__)


def clone_repo(url: str, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", "--depth=1", url, str(dest)],
        check=True,
        capture_output=True,
        text=True,
    )
    log.info(f"Cloned {url} → {dest}")
    return dest


def is_git_repo(path: Path) -> bool:
    return (path / ".git").is_dir()
