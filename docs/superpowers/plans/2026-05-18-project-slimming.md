# Project Slimming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 停止仓库继续跟踪缓存、日志和本地派生文件，并提供一个只读的本地清理 `dry-run` 脚本输出候选项与预计释放空间。

**Architecture:** 通过一个独立的 `scripts/dry_run_cleanup.py` 脚本承载本地空间盘点逻辑，并用 `tests/test_dry_run_cleanup.py` 做最小可回归覆盖。仓库侧只做两类变更：补齐 `.gitignore` 规则，以及通过 `git rm --cached` 从索引移除已入库的派生文件，避免触碰本地真实文件。

**Tech Stack:** Python 3.11, unittest, PowerShell, Git

---

### Task 1: 为清理脚本写失败测试

**Files:**
- Create: `tests/test_dry_run_cleanup.py`
- Test: `tests/test_dry_run_cleanup.py`

- [ ] **Step 1: 写入失败测试文件**

```python
from __future__ import annotations

import importlib.util
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "dry_run_cleanup.py"


def load_module():
    spec = importlib.util.spec_from_file_location("dry_run_cleanup", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Unable to load module from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DryRunCleanupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def write_bytes(self, relative_path: str, size: int) -> Path:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * size)
        return path

    def test_collect_cleanup_candidates_reports_existing_targets(self) -> None:
        module = load_module()
        self.write_bytes(".venv/Lib/site-packages/demo.dll", 12)
        self.write_bytes("logs/app.log", 7)
        self.write_bytes("pkg/__pycache__/module.cpython-311.pyc", 5)
        self.write_bytes("tmp-dashboard.png", 3)

        candidates = module.collect_cleanup_candidates(self.root)
        by_path = {item.path.relative_to(self.root).as_posix(): item for item in candidates}

        self.assertIn(".venv", by_path)
        self.assertIn("logs", by_path)
        self.assertIn("pkg/__pycache__", by_path)
        self.assertIn("tmp-dashboard.png", by_path)
        self.assertEqual(by_path[".venv"].size_bytes, 12)
        self.assertEqual(by_path["logs"].size_bytes, 7)
        self.assertEqual(by_path["pkg/__pycache__"].size_bytes, 5)
        self.assertEqual(by_path["tmp-dashboard.png"].size_bytes, 3)

    def test_collect_cleanup_candidates_skips_missing_targets(self) -> None:
        module = load_module()

        candidates = module.collect_cleanup_candidates(self.root)

        self.assertEqual(candidates, [])

    def test_main_is_read_only_and_keeps_files(self) -> None:
        module = load_module()
        log_path = self.write_bytes("logs/app.log", 11)
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            exit_code = module.main(["--root", str(self.root)])

        self.assertEqual(exit_code, 0)
        self.assertTrue(log_path.exists())
        output = stdout.getvalue()
        self.assertIn("No files were deleted.", output)
        self.assertIn("logs", output)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试并确认当前失败**

Run: `python -m unittest tests.test_dry_run_cleanup -v`

Expected: `ERROR`，报错指向 `scripts/dry_run_cleanup.py` 不存在，说明测试先行且尚未实现脚本。

- [ ] **Step 3: 提交失败测试**

```bash
git add tests/test_dry_run_cleanup.py
git commit -m "test: cover cleanup dry run script"
```

### Task 2: 实现只读清理盘点脚本

**Files:**
- Create: `scripts/dry_run_cleanup.py`
- Modify: `tests/test_dry_run_cleanup.py`
- Test: `tests/test_dry_run_cleanup.py`

- [ ] **Step 1: 写入最小实现让测试通过**

```python
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class CandidateSpec:
    label: str
    kind: str
    recommendation: str
    note: str


@dataclass(frozen=True)
class CleanupCandidate:
    path: Path
    kind: str
    size_bytes: int
    recommendation: str
    note: str


ROOT_TARGETS: dict[str, CandidateSpec] = {
    ".worktrees": CandidateSpec(
        label=".worktrees",
        kind="dir",
        recommendation="high-value",
        note="Contains extra worktrees; verify active branches before deleting.",
    ),
    ".venv": CandidateSpec(
        label=".venv",
        kind="dir",
        recommendation="high-value",
        note="Rebuild cost is moderate; recreate with pip install if cleaned.",
    ),
    "logs": CandidateSpec(
        label="logs",
        kind="dir",
        recommendation="low-risk",
        note="Runtime logs are reproducible; safe to archive or rotate.",
    ),
    ".mypy_cache": CandidateSpec(
        label=".mypy_cache",
        kind="dir",
        recommendation="low-risk",
        note="Static-analysis cache; safe to regenerate.",
    ),
    ".pytest_cache": CandidateSpec(
        label=".pytest_cache",
        kind="dir",
        recommendation="low-risk",
        note="pytest cache; safe to regenerate.",
    ),
    ".ruff_cache": CandidateSpec(
        label=".ruff_cache",
        kind="dir",
        recommendation="low-risk",
        note="ruff cache; safe to regenerate.",
    ),
    "checkpoints": CandidateSpec(
        label="checkpoints",
        kind="dir",
        recommendation="medium-value",
        note="Review whether pending runs still depend on these checkpoints.",
    ),
}

RECURSIVE_PATTERNS: tuple[tuple[str, CandidateSpec], ...] = (
    (
        "**/__pycache__",
        CandidateSpec(
            label="__pycache__",
            kind="dir",
            recommendation="low-risk",
            note="Python bytecode cache; safe to regenerate.",
        ),
    ),
    (
        "tmp-*.png",
        CandidateSpec(
            label="tmp-*.png",
            kind="file",
            recommendation="low-risk",
            note="Temporary screenshots can be recreated if still needed.",
        ),
    ),
)


def size_bytes(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            total += child.stat().st_size
    return total


def is_covered(path: Path, covered_roots: Iterable[Path]) -> bool:
    for root in covered_roots:
        if path == root or root in path.parents:
            return True
    return False


def collect_cleanup_candidates(project_root: Path) -> list[CleanupCandidate]:
    candidates: list[CleanupCandidate] = []
    covered_roots: list[Path] = []

    for relative_name, spec in ROOT_TARGETS.items():
        candidate_path = project_root / relative_name
        if not candidate_path.exists():
            continue
        candidates.append(
            CleanupCandidate(
                path=candidate_path,
                kind=spec.kind,
                size_bytes=size_bytes(candidate_path),
                recommendation=spec.recommendation,
                note=spec.note,
            )
        )
        if candidate_path.is_dir():
            covered_roots.append(candidate_path)

    for pattern, spec in RECURSIVE_PATTERNS:
        for candidate_path in sorted(project_root.glob(pattern)):
            if is_covered(candidate_path, covered_roots):
                continue
            candidates.append(
                CleanupCandidate(
                    path=candidate_path,
                    kind=spec.kind,
                    size_bytes=size_bytes(candidate_path),
                    recommendation=spec.recommendation,
                    note=spec.note,
                )
            )

    return sorted(candidates, key=lambda item: item.size_bytes, reverse=True)


def format_size(size: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{value:.2f} TB"


def render_report(project_root: Path, candidates: list[CleanupCandidate]) -> str:
    lines = [f"Cleanup dry-run for {project_root}", "No files were deleted.", ""]
    if not candidates:
        lines.append("No cleanup candidates found.")
        return "\n".join(lines)

    for item in candidates:
        relative_path = item.path.relative_to(project_root).as_posix()
        lines.append(
            f"{item.kind:>4}  {format_size(item.size_bytes):>10}  "
            f"{relative_path:<40}  {item.recommendation:<11}  {item.note}"
        )

    total_size = sum(item.size_bytes for item in candidates)
    lines.extend(["", f"Total candidate size: {format_size(total_size)}"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preview local cleanup candidates without deleting files.")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Project root to inspect.")
    args = parser.parse_args(argv)

    project_root = args.root.resolve()
    candidates = collect_cleanup_candidates(project_root)
    print(render_report(project_root, candidates))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: 如果测试因 `dataclass` 模块名解析失败，补充模块注册**

```python
def load_module():
    spec = importlib.util.spec_from_file_location("dry_run_cleanup", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Unable to load module from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
```

- [ ] **Step 3: 运行测试并确认通过**

Run: `python -m unittest tests.test_dry_run_cleanup -v`

Expected: `OK`

- [ ] **Step 4: 手工执行脚本 dry-run**

Run: `python scripts/dry_run_cleanup.py --root .`

Expected: 输出 `Cleanup dry-run for ...`、`No files were deleted.`，并列出 `.worktrees`、`.venv`、`logs` 等候选项及大小。

- [ ] **Step 5: 提交脚本与测试**

```bash
git add scripts/dry_run_cleanup.py tests/test_dry_run_cleanup.py
git commit -m "feat: add cleanup dry run report"
```

### Task 3: 补齐忽略规则与使用说明

**Files:**
- Modify: `.gitignore`
- Modify: `README.md`
- Test: `python scripts/dry_run_cleanup.py --root .`

- [ ] **Step 1: 扩展 `.gitignore`，覆盖当前遗漏的本地派生文件**

```gitignore
# 虚拟环境
.venv/

# 缓存文件
__pycache__/
**/__pycache__/
.mypy_cache/
**/.mypy_cache/
.pytest_cache/
**/.pytest_cache/
.ruff_cache/
**/.ruff_cache/
*.pyc

# 构建和打包目录
build/
dist/

# PyInstaller spec 文件
*.spec

# 日志文件
logs/
**/logs/
log/
debug_startup.txt
debug_reporting.txt
startup_log.txt
startup_log_v2.txt
temp_log.txt

# 运行时断点目录
checkpoints/
**/checkpoints/

# 本地协作 / 机器相关文件
.claude/
.idea/
.install_salt
config.local.ini
config.ini.backup
.worktrees
.worktrees/
.DS_Store
**/.DS_Store
tmp-*.png
```

- [ ] **Step 2: 在 `README.md` 增加瘦身说明**

````markdown
## 项目瘦身

- `.worktrees`、`.venv`、`logs`、各类缓存目录都属于本地派生内容，不应提交到仓库。
- 如需盘点本机可清理空间，执行：

```bash
python scripts/dry_run_cleanup.py --root .
```

- 该脚本只输出候选项和预计空间，不会删除任何文件。
- `.worktrees` 和 `.venv` 可能仍被当前开发环境使用，是否清理应由人工确认。
````

- [ ] **Step 3: 运行脚本确认 README 中的命令真实可用**

Run: `python scripts/dry_run_cleanup.py --root .`

Expected: 进程退出码为 `0`，输出中包含 `No files were deleted.`

- [ ] **Step 4: 提交文档与忽略规则**

```bash
git add .gitignore README.md
git commit -m "chore: ignore local derived files"
```

### Task 4: 从索引移除已跟踪派生文件并完成验证

**Files:**
- Modify: Git index only for `.idea/`, `.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/`, `.venv/`, `.worktrees/`, `logs/`, `checkpoints/`, `config.local.ini`, `config.ini.backup`, `tmp-*.png`, `.DS_Store`, all `__pycache__/`, all `*.pyc`
- Test: `tests/test_dry_run_cleanup.py`

- [ ] **Step 1: 先查看将被移出索引的跟踪文件**

```powershell
$tracked = git ls-files
$tracked | Select-String -Pattern '(^|/)(__pycache__/|\.pytest_cache/|\.ruff_cache/|\.mypy_cache/|\.venv/|\.worktrees/|logs/|checkpoints/|\.idea/|tmp-.*\.png$|\.DS_Store$|config\.local\.ini$|config\.ini\.backup$|.*\.pyc$)' | ForEach-Object { $_.Line }
```

Expected: 输出大量派生文件路径，例如 `.mypy_cache/...`、`logs/app.log`、`src/core/__pycache__/...`。

- [ ] **Step 2: 只从索引移除这些派生文件，保留本地文件**

```powershell
$tracked = git ls-files
$matches = $tracked | Where-Object {
    $_ -match '(^|/)(__pycache__/|\.pytest_cache/|\.ruff_cache/|\.mypy_cache/|\.venv/|\.worktrees/|logs/|checkpoints/|\.idea/)' -or
    $_ -match '(^|/)\.DS_Store$' -or
    $_ -match '^tmp-.*\.png$' -or
    $_ -match '^config\.local\.ini$' -or
    $_ -match '^config\.ini\.backup$' -or
    $_ -match '\.pyc$'
}

if ($matches.Count -gt 0) {
    for ($i = 0; $i -lt $matches.Count; $i += 200) {
        $upper = [Math]::Min($i + 199, $matches.Count - 1)
        $chunk = $matches[$i..$upper]
        git rm --cached -r --ignore-unmatch -- $chunk
    }
}
```

Expected: Git 输出 `rm '...'`，但磁盘上的文件仍然存在。

- [ ] **Step 3: 重新运行单元测试和 dry-run**

Run: `python -m unittest tests.test_dry_run_cleanup -v`

Expected: `OK`

Run: `python scripts/dry_run_cleanup.py --root .`

Expected: 输出仍能看到 `.worktrees`、`.venv`、`logs` 等候选项，证明脚本只读且本地文件仍保留。

- [ ] **Step 4: 检查 Git 状态是否只剩预期的索引删除与文档改动**

```bash
git status --short
```

Expected: 能看到大量 `D` 状态对应派生文件，以及 `.gitignore`、`README.md`、`scripts/dry_run_cleanup.py`、`tests/test_dry_run_cleanup.py` 的变更；后续重新生成缓存后不应再次出现在未跟踪列表中。

- [ ] **Step 5: 提交索引清理结果**

```bash
git add .gitignore README.md scripts/dry_run_cleanup.py tests/test_dry_run_cleanup.py
git commit -m "chore: slim tracked derived files"
```

### Task 5: 最终回归与结果留痕

**Files:**
- Verify: `.gitignore`
- Verify: `README.md`
- Verify: `scripts/dry_run_cleanup.py`
- Verify: `tests/test_dry_run_cleanup.py`

- [ ] **Step 1: 运行与本次变更直接相关的单元测试**

Run: `python -m unittest tests.test_dry_run_cleanup -v`

Expected: `OK`

- [ ] **Step 2: 执行脚本 dry-run，保存预期日志口径**

Run: `python scripts/dry_run_cleanup.py --root .`

Expected: 输出 `No files were deleted.`，并列出候选项和总大小。

- [ ] **Step 3: 用一个新生成缓存路径验证忽略规则生效**

```powershell
New-Item -ItemType Directory -Force -Path 'temp_verify/__pycache__' | Out-Null
Set-Content -Path 'temp_verify/__pycache__/demo.pyc' -Value 'x'
git status --short -- 'temp_verify'
Remove-Item -Recurse -Force 'temp_verify'
```

Expected: `git status` 对 `temp_verify` 没有输出，说明 `__pycache__` 和 `*.pyc` 已被忽略。

- [ ] **Step 4: 记录预期仓库与日志变化**

```text
- 预期 `git status` 不再持续被 logs、缓存目录和临时图片刷屏。
- 预期后续运行同步程序时，`logs/` 仍会继续产生业务日志，但这些日志不会重新进入 Git 跟踪。
- 预期 SQL Server 写入链路日志本身不变；变化只在版本控制层面，新增/滚动的日志文件不再出现在待提交列表。
```

- [ ] **Step 5: 检查最终工作区**

```bash
git status --short
```

Expected: 仅剩本次计划内的代码、文档和索引清理变更；没有额外的派生文件重新进入状态列表。
