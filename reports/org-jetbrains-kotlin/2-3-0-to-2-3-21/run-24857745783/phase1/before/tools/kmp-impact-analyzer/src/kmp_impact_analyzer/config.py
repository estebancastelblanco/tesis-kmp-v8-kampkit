"""Configuration loading from YAML files and CLI arguments."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class AnalysisConfig:
    repo_path: str = ""
    dependency_group: str = ""
    before_version: str = ""
    after_version: str = ""
    output_dir: str = "output"
    skip_dynamic: bool = False
    init_script_path: str = ""
    droidbot_timeout: int = 120
    droidbot_policy: str = "dfs_greedy"
    before_apk: str = ""
    after_apk: str = ""
    droidbot_before_output: str = ""
    droidbot_after_output: str = ""
    extra_seed_packages: list[str] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: str | Path) -> AnalysisConfig:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Config file not found: {p}")
        with open(p) as f:
            data = yaml.safe_load(f) or {}
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @classmethod
    def from_cli(cls, **kwargs: object) -> AnalysisConfig:
        filtered = {k: v for k, v in kwargs.items() if v is not None and k in cls.__dataclass_fields__}
        return cls(**filtered)

    def resolve_init_script(self) -> Path:
        if self.init_script_path:
            return Path(self.init_script_path)
        return Path(__file__).parent.parent.parent / "gradle-init" / "impact-analyzer-init.gradle.kts"
