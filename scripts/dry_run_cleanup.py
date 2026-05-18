from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class CleanupCandidate:
    path: Path
    size: int
    kind: str
    level: str
    reason: str


def _is_relative_to(path: Path, other: Path) -> bool:
    try:
        path.relative_to(other)
        return True
    except ValueError:
        return False


def _safe_is_file(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


def _safe_file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _directory_size(path: Path) -> int:
    total = 0
    for child in path.rglob("*"):
        if _safe_is_file(child):
            total += _safe_file_size(child)
    return total


def _path_size(path: Path) -> int:
    if path.is_dir():
        return _directory_size(path)
    if _safe_is_file(path):
        return _safe_file_size(path)
    return 0


def _make_candidate(path: Path, level: str, reason: str) -> CleanupCandidate:
    return CleanupCandidate(
        path=path.resolve(),
        size=_path_size(path),
        kind="directory" if path.is_dir() else "file",
        level=level,
        reason=reason,
    )


def collect_cleanup_candidates(project_root: Path | str) -> list[CleanupCandidate]:
    root = Path(project_root)
    candidates: list[CleanupCandidate] = []
    seen: set[Path] = set()
    aggregated_roots: set[Path] = set()

    def add(path: Path, level: str, reason: str) -> None:
        resolved = path.resolve()
        if not path.exists() or resolved in seen:
            return
        seen.add(resolved)
        candidates.append(_make_candidate(path, level, reason))

    def is_under_aggregated_root(path: Path) -> bool:
        return any(_is_relative_to(path, aggregated_root) for aggregated_root in aggregated_roots)

    def add_match(path: Path, level: str, reason: str, expected_kind: str) -> None:
        resolved = path.resolve()
        if not path.exists() or resolved in seen or is_under_aggregated_root(resolved):
            return
        if expected_kind == "directory" and not path.is_dir():
            return
        if expected_kind == "file" and not path.is_file():
            return
        seen.add(resolved)
        candidates.append(_make_candidate(path, level, reason))
        if path.is_dir():
            aggregated_roots.add(resolved)

    def scan(pattern: str, level: str, reason: str, expected_kind: str) -> None:
        for path in root.rglob(pattern):
            add_match(path, level, reason, expected_kind)

    fixed_targets = [
        (
            ".worktrees",
            "high",
            "directory",
            "High-risk Git worktree storage. Prefer `git worktree list`, `git worktree remove`, and `git worktree prune`; do not delete active worktree directories directly.",
        ),
        (".idea", "medium", "directory", "IDE project metadata is local to this workspace and can usually be recreated."),
        (".claude", "medium", "directory", "Local agent or collaboration metadata is workspace-specific and can usually be recreated."),
        (".install_salt", "medium", "file", "Local machine marker or setup artifact that is usually safe to review before cleanup."),
        (".venv", "medium", "directory", "Local virtual environment can be recreated from dependency files."),
        ("log", "high", "directory", "Runtime logs can grow quickly and are usually disposable after troubleshooting."),
        ("logs", "high", "directory", "Runtime logs can grow quickly and are usually disposable after troubleshooting."),
        (".mypy_cache", "high", "directory", "Static analysis cache is regenerated automatically."),
        (".pytest_cache", "high", "directory", "Pytest cache is regenerated automatically."),
        (".ruff_cache", "high", "directory", "Ruff cache is regenerated automatically."),
        ("config.local.ini", "medium", "file", "Local configuration should be reviewed before cleanup."),
        ("config.ini.backup", "medium", "file", "Backup configuration should be reviewed before cleanup."),
        ("checkpoints", "medium", "directory", "Checkpoint artifacts may be restorable from source or reruns."),
    ]

    for relative_path, level, expected_kind, reason in fixed_targets:
        scan(relative_path, level, reason, expected_kind)

    for path in root.rglob("__pycache__"):
        add_match(path, "high", "Python bytecode cache is regenerated automatically.", "directory")

    for path in root.rglob(".DS_Store"):
        add_match(path, "high", "macOS Finder metadata is regenerated automatically.", "file")

    for path in root.rglob("tmp-*.png"):
        add_match(path, "medium", "Temporary image artifact that may be removable after review.", "file")

    return sorted(candidates, key=lambda candidate: str(candidate.path))


def _format_size(size: int) -> str:
    return f"{size} B"


def _render_report(candidates: Iterable[CleanupCandidate], root: Path) -> str:
    lines = [f"Dry-run cleanup report for: {root.resolve()}"]
    candidate_list = list(candidates)
    total_size = sum(candidate.size for candidate in candidate_list)
    lines.append(
        f"Summary: {len(candidate_list)} candidate(s), total size: {_format_size(total_size)}"
    )

    if not candidate_list:
        lines.append("No cleanup candidates found.")
        lines.append("No files were deleted.")
        return "\n".join(lines)

    for candidate in candidate_list:
        lines.extend(
            [
                f"Path: {candidate.path}",
                f"type: {candidate.kind}",
                f"size: {_format_size(candidate.size)}",
                f"recommendation: {candidate.level}",
                f"reason: {candidate.reason}",
                "",
            ]
        )

    lines.append("No files were deleted.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show cleanup candidates without deleting files.")
    parser.add_argument("--root", default=".", help="Project root to inspect.")
    args = parser.parse_args(argv)

    root = Path(args.root)
    if not root.exists() or not root.is_dir():
        parser.error(f"Root path does not exist or is not a directory: {root}")

    candidates = collect_cleanup_candidates(root)
    print(_render_report(candidates, root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
