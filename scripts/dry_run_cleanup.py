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


def _directory_size(path: Path) -> int:
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            total += child.stat().st_size
    return total


def _path_size(path: Path) -> int:
    if path.is_dir():
        return _directory_size(path)
    if path.is_file():
        return path.stat().st_size
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

    def add(path: Path, level: str, reason: str) -> None:
        resolved = path.resolve()
        if not path.exists() or resolved in seen:
            return
        seen.add(resolved)
        candidates.append(_make_candidate(path, level, reason))

    fixed_targets = [
        (".worktrees", "high", "Workspace cache or nested worktrees that are often safe to review before cleanup."),
        (".venv", "medium", "Local virtual environment can be recreated from dependency files."),
        ("logs", "high", "Runtime logs can grow quickly and are usually disposable after troubleshooting."),
        (".mypy_cache", "high", "Static analysis cache is regenerated automatically."),
        (".pytest_cache", "high", "Pytest cache is regenerated automatically."),
        (".ruff_cache", "high", "Ruff cache is regenerated automatically."),
        ("checkpoints", "medium", "Checkpoint artifacts may be restorable from source or reruns."),
    ]

    for relative_path, level, reason in fixed_targets:
        add(root / relative_path, level, reason)

    for path in root.rglob("__pycache__"):
        add(path, "high", "Python bytecode cache is regenerated automatically.")

    for path in root.glob("tmp-*.png"):
        add(path, "medium", "Temporary image artifact that may be removable after review.")

    return sorted(candidates, key=lambda candidate: str(candidate.path))


def _format_size(size: int) -> str:
    return f"{size} B"


def _render_report(candidates: Iterable[CleanupCandidate], root: Path) -> str:
    lines = [f"Dry-run cleanup report for: {root.resolve()}"]
    candidate_list = list(candidates)

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
    candidates = collect_cleanup_candidates(root)
    print(_render_report(candidates, root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
