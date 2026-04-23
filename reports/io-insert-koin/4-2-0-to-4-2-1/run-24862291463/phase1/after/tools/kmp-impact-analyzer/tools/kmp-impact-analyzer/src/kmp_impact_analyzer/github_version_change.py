"""Utilities for detecting dependency version changes in Gradle version catalogs."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from .phase1_shadow.toml_parser import VersionCatalog


class DetectedVersionChange(BaseModel):
    dependency_group: str
    version_key: str
    before_version: str
    after_version: str


class VersionChangeSet(BaseModel):
    changes: list[DetectedVersionChange] = Field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.changes)


def detect_version_changes(before_toml: str | Path, after_toml: str | Path) -> VersionChangeSet:
    """Compare two version catalogs and return changed dependency groups.

    The comparison is keyed by ``version.ref`` so one version bump can fan out to
    multiple dependency groups that share the same alias.
    """
    before = VersionCatalog(Path(before_toml))
    after = VersionCatalog(Path(after_toml))

    groups_by_version_key: dict[str, set[str]] = {}
    for catalog in (before, after):
        for library in catalog.libraries.values():
            groups_by_version_key.setdefault(library["version_ref"], set()).add(library["group"])
        for plugin in catalog.plugins.values():
            groups_by_version_key.setdefault(plugin["version_ref"], set()).add(plugin["id"])

    changes: list[DetectedVersionChange] = []
    for version_key in sorted(groups_by_version_key):
        before_version = before.get_version(version_key)
        after_version = after.get_version(version_key)
        if before_version is None or after_version is None or before_version == after_version:
            continue

        for dependency_group in sorted(groups_by_version_key[version_key]):
            changes.append(
                DetectedVersionChange(
                    dependency_group=dependency_group,
                    version_key=version_key,
                    before_version=before_version,
                    after_version=after_version,
                )
            )

    return VersionChangeSet(changes=changes)
