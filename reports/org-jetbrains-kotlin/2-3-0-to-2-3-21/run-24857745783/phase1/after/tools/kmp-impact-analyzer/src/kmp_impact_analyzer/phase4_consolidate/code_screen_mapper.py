"""Map impacted code files to UI screens via navigation analysis."""

from __future__ import annotations

import re
from pathlib import Path

from ..contracts import FileImpact, ScreenMapping
from ..utils.log import get_logger

log = get_logger(__name__)

# Patterns for Compose Navigation routes
_NAV_ROUTE_RE = re.compile(r"""composable\s*\(\s*(?:route\s*=\s*)?["']([^"']+)["']""")
_NAV_CALL_RE = re.compile(r"""navigate\s*\(\s*["']([^"']+)["']""")
_SCREEN_SUFFIX_RE = re.compile(r"(Screen|View|Page|Fragment|Activity|Composable)$")
_COMPOSABLE_RE = re.compile(r"@Composable\s+fun\s+(\w+)")
_VIEWMODEL_CLASS_RE = re.compile(r"class\s+(\w+ViewModel)")
_ACTIVITY_RE = re.compile(r"""android:name\s*=\s*"\.?([^"]+)"?""")


class CodeScreenMapper:
    """Maps code files to UI screens using multiple heuristics."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self._route_to_composable: dict[str, str] = {}
        self._composable_to_files: dict[str, list[str]] = {}
        self._viewmodel_to_screen: dict[str, str] = {}
        self._activities: list[str] = []

    def build(self, impacted_files: list[FileImpact]) -> list[ScreenMapping]:
        """Build mappings from impacted files to screens."""
        self._scan_navigation()
        self._scan_manifest()

        mappings: list[ScreenMapping] = []
        seen_screens: set[str] = set()

        for fi in impacted_files:
            file_screens = self._map_file(fi)
            for screen, confidence, method in file_screens:
                if screen not in seen_screens:
                    seen_screens.add(screen)
                    mappings.append(
                        ScreenMapping(
                            screen_name=screen,
                            mapped_files=[fi.file_path],
                            confidence=confidence,
                            method=method,
                        )
                    )
                else:
                    # Append file to existing mapping
                    for m in mappings:
                        if m.screen_name == screen:
                            if fi.file_path not in m.mapped_files:
                                m.mapped_files.append(fi.file_path)
                            break

        log.info(f"Mapped {len(mappings)} screens from impacted files")
        return mappings

    def _scan_navigation(self) -> None:
        """Scan for Compose Navigation definitions."""
        for kt_file in self.project_root.rglob("*.kt"):
            parts = kt_file.parts
            if any(skip in parts for skip in ("build", ".gradle")):
                continue
            try:
                content = kt_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            # Find composable functions
            for m in _COMPOSABLE_RE.finditer(content):
                name = m.group(1)
                self._composable_to_files.setdefault(name, []).append(str(kt_file))

            # Find navigation routes linked to composables
            for m in _NAV_ROUTE_RE.finditer(content):
                route = m.group(1)
                # Find the composable in the same block
                composables = _COMPOSABLE_RE.findall(content)
                if composables:
                    self._route_to_composable[route] = composables[0]

            # Find ViewModel → Screen associations
            vm_match = _VIEWMODEL_CLASS_RE.search(content)
            if vm_match:
                vm_name = vm_match.group(1)
                screen_name = vm_name.replace("ViewModel", "")
                self._viewmodel_to_screen[vm_name] = screen_name

    def _scan_manifest(self) -> None:
        """Scan AndroidManifest.xml for activities."""
        manifest = self.project_root / "composeApp" / "src" / "androidMain" / "AndroidManifest.xml"
        if not manifest.exists():
            # Try alternative paths
            for candidate in self.project_root.rglob("AndroidManifest.xml"):
                if "build" not in str(candidate):
                    manifest = candidate
                    break

        if manifest.exists():
            content = manifest.read_text(encoding="utf-8", errors="replace")
            self._activities = [m.group(1) for m in _ACTIVITY_RE.finditer(content)]

    def _map_file(self, fi: FileImpact) -> list[tuple[str, float, str]]:
        """Map a single file to screens. Returns (screen_name, confidence, method)."""
        results: list[tuple[str, float, str]] = []
        filename = Path(fi.file_path).stem

        # Method 1: Direct composable match
        for decl in fi.declarations:
            short_name = decl.rsplit(".", 1)[-1] if "." in decl else decl
            if short_name in self._composable_to_files:
                results.append((short_name, 0.9, "composable_declaration"))

        # Method 2: ViewModel → Screen
        for decl in fi.declarations:
            short_name = decl.rsplit(".", 1)[-1] if "." in decl else decl
            if short_name in self._viewmodel_to_screen:
                screen = self._viewmodel_to_screen[short_name]
                results.append((screen, 0.8, "viewmodel_association"))

        # Method 3: Activity match
        for activity in self._activities:
            activity_short = activity.rsplit(".", 1)[-1]
            if activity_short in filename or filename in activity_short:
                screen_name = activity_short.replace("Activity", "")
                results.append((screen_name, 0.7, "activity_manifest"))

        # Method 4: Heuristic — file name ends with Screen/View suffix
        if not results and _SCREEN_SUFFIX_RE.search(filename):
            screen_name = _SCREEN_SUFFIX_RE.sub("", filename)
            results.append((screen_name, 0.5, "filename_heuristic"))

        return results
