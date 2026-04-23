"""Tests for GitHub-oriented version change detection."""

from pathlib import Path

from click.testing import CliRunner

from kmp_impact_analyzer.cli import main
from kmp_impact_analyzer.github_version_change import detect_version_changes

BASE_TOML = """\
[versions]
agp = "8.10.1"
ktor = "2.3.8"
sqldelight = "2.0.1"
compose = "1.6.0"

[libraries]
ktor-core = { module = "io.ktor:ktor-client-core", version.ref = "ktor" }
ktor-cio = { module = "io.ktor:ktor-client-cio", version.ref = "ktor" }
sqldelight-driver = { group = "app.cash.sqldelight", name = "android-driver", version.ref = "sqldelight" }
compose-ui = { group = "androidx.compose.ui", name = "ui", version.ref = "compose" }

[plugins]
android-application = { id = "com.android.application", version.ref = "agp" }
"""

HEAD_TOML = """\
[versions]
agp = "9.1.0"
ktor = "2.3.11"
sqldelight = "2.0.1"
compose = "1.6.1"

[libraries]
ktor-core = { module = "io.ktor:ktor-client-core", version.ref = "ktor" }
ktor-cio = { module = "io.ktor:ktor-client-cio", version.ref = "ktor" }
sqldelight-driver = { group = "app.cash.sqldelight", name = "android-driver", version.ref = "sqldelight" }
compose-ui = { group = "androidx.compose.ui", name = "ui", version.ref = "compose" }

[plugins]
android-application = { id = "com.android.application", version.ref = "agp" }
"""


def _write_catalog(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_detect_version_changes_returns_changed_groups(tmp_path):
    before = _write_catalog(tmp_path / "before.toml", BASE_TOML)
    after = _write_catalog(tmp_path / "after.toml", HEAD_TOML)

    changes = detect_version_changes(before, after)

    assert changes.has_changes is True
    groups = {(c.dependency_group, c.before_version, c.after_version) for c in changes.changes}
    assert ("com.android.application", "8.10.1", "9.1.0") in groups
    assert ("io.ktor", "2.3.8", "2.3.11") in groups
    assert ("androidx.compose.ui", "1.6.0", "1.6.1") in groups
    assert all(c.dependency_group != "app.cash.sqldelight" for c in changes.changes)


def test_detect_version_changes_cli_github_format(tmp_path):
    before = _write_catalog(tmp_path / "before.toml", BASE_TOML)
    after = _write_catalog(tmp_path / "after.toml", HEAD_TOML)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "detect-version-changes",
            "--before",
            str(before),
            "--after",
            str(after),
            "--format",
            "github",
        ],
    )

    assert result.exit_code == 0
    assert "has_changes=true" in result.output
    assert (
        "dependency_group=com.android.application" in result.output
        or "dependency_group=androidx.compose.ui" in result.output
        or "dependency_group=io.ktor" in result.output
    )
    assert "before_version=" in result.output
    assert "after_version=" in result.output
