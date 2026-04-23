"""DroidBot runner: verify prerequisites and execute automated UI exploration."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from ..config import AnalysisConfig
from ..contracts import DynamicStatus, UIRegressions
from ..utils.log import get_logger

log = get_logger(__name__)


def _check_command(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _check_adb_device() -> bool:
    try:
        result = subprocess.run(
            ["adb", "devices"], capture_output=True, text=True, timeout=10
        )
        lines = [l.strip() for l in result.stdout.strip().splitlines()[1:] if l.strip()]
        return any("device" in l for l in lines)
    except Exception:
        return False


def _run_droidbot(apk: Path, output_dir: Path, timeout: int, policy: str) -> bool:
    """Run DroidBot on an APK, return True if successful."""
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "droidbot",
        "-a", str(apk),
        "-o", str(output_dir),
        "-policy", policy,
        "-count", "200",
        "-timeout", str(timeout),
        "-grant_perm",
        "-keep_env",
        "-is_emulator",
    ]
    log.info(f"Running DroidBot: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True, timeout=timeout + 60)
        return True
    except subprocess.CalledProcessError as e:
        log.error(f"DroidBot failed: {e}")
        return False
    except subprocess.TimeoutExpired:
        log.warning("DroidBot timed out")
        return True  # Partial results may still be useful


def run_dynamic_analysis(config: AnalysisConfig) -> UIRegressions:
    """Execute Phase 3: run DroidBot on before/after APKs."""
    if config.skip_dynamic:
        log.info("Dynamic analysis skipped (--skip-dynamic)")
        return UIRegressions(status=DynamicStatus.SKIPPED)

    output = Path(config.output_dir) / "phase3"
    output.mkdir(parents=True, exist_ok=True)

    # Check for pre-generated DroidBot output
    pre_before = Path(config.droidbot_before_output) if config.droidbot_before_output else None
    pre_after = Path(config.droidbot_after_output) if config.droidbot_after_output else None

    if pre_before and pre_before.exists() and pre_after and pre_after.exists():
        log.info("Using pre-generated DroidBot output")
        before_dir = pre_before
        after_dir = pre_after
    else:
        # Check prerequisites for live DroidBot run
        missing: list[str] = []
        if not _check_command("droidbot"):
            missing.append("droidbot")
        if not _check_command("adb"):
            missing.append("adb")
        if not _check_adb_device():
            missing.append("Android emulator/device")
        if not config.before_apk or not Path(config.before_apk).exists():
            missing.append(f"before APK ({config.before_apk or 'not specified'})")
        if not config.after_apk or not Path(config.after_apk).exists():
            missing.append(f"after APK ({config.after_apk or 'not specified'})")

        if missing:
            reason = f"Missing prerequisites: {', '.join(missing)}"
            log.warning(f"Dynamic analysis blocked: {reason}")
            return UIRegressions(status=DynamicStatus.BLOCKED, blocked_reason=reason)

        # Run DroidBot on BEFORE APK
        before_dir = output / "before"
        log.info("Running DroidBot on BEFORE APK...")
        before_ok = _run_droidbot(
            Path(config.before_apk),
            before_dir,
            config.droidbot_timeout,
            config.droidbot_policy,
        )

        # Run DroidBot on AFTER APK
        after_dir = output / "after"
        log.info("Running DroidBot on AFTER APK...")
        after_ok = _run_droidbot(
            Path(config.after_apk),
            after_dir,
            config.droidbot_timeout,
            config.droidbot_policy,
        )

        if not before_ok and not after_ok:
            return UIRegressions(
                status=DynamicStatus.BLOCKED,
                blocked_reason="DroidBot failed on both APKs",
            )

    # Parse and compare UTGs
    from .utg_diff import compare_utgs
    from .utg_parser import parse_utg

    before_utg = parse_utg(before_dir)
    after_utg = parse_utg(after_dir)

    diffs = compare_utgs(before_utg, after_utg)

    result = UIRegressions(
        status=DynamicStatus.COMPLETED,
        before_screens=[n.screen_name for n in before_utg.nodes],
        after_screens=[n.screen_name for n in after_utg.nodes],
        diffs=diffs,
    )
    log.info(f"[bold green]Phase 3 complete[/bold green]: {len(diffs)} screen differences found")
    return result
