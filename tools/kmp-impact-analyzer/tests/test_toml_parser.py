"""Tests for TOML version catalog parser."""

import tempfile
from pathlib import Path

from kmp_impact_analyzer.phase1_shadow.toml_parser import VersionCatalog

SAMPLE_TOML = """\
[versions]
agp = "8.10.1"
ktor = "2.3.8"
sqldelight = "2.0.1"
kotlin = "1.9.22"

[libraries]
ktor-core = { module = "io.ktor:ktor-client-core", version.ref = "ktor" }
ktor-cio = { module = "io.ktor:ktor-client-cio", version.ref = "ktor" }
sqldelight-driver = { group = "app.cash.sqldelight", name = "android-driver", version.ref = "sqldelight" }

[plugins]
android-application = { id = "com.android.application", version.ref = "agp" }
"""


def _write_toml(content: str) -> Path:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False)
    f.write(content)
    f.close()
    return Path(f.name)


def test_parse_versions():
    path = _write_toml(SAMPLE_TOML)
    catalog = VersionCatalog(path)
    assert catalog.versions["ktor"] == "2.3.8"
    assert catalog.versions["sqldelight"] == "2.0.1"


def test_find_version_key():
    path = _write_toml(SAMPLE_TOML)
    catalog = VersionCatalog(path)
    assert catalog.find_version_key("io.ktor") == "ktor"
    assert catalog.find_version_key("app.cash.sqldelight") == "sqldelight"
    assert catalog.find_version_key("com.android.application") == "agp"
    assert catalog.find_version_key("nonexistent") is None


def test_set_version():
    path = _write_toml(SAMPLE_TOML)
    catalog = VersionCatalog(path)
    catalog.set_version("ktor", "2.3.11")
    assert catalog.versions["ktor"] == "2.3.11"

    # Verify written back to file
    content = path.read_text()
    assert '"2.3.11"' in content
    assert '"2.3.8"' not in content
