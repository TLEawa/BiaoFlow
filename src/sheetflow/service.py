from __future__ import annotations

import glob
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from sheetflow.config import WorkflowConfig
from sheetflow.exceptions import InputFileError, OperationError, TaskCancelled
from sheetflow.exporters import export_table
from sheetflow.operations import apply_operation
from sheetflow.readers import SUPPORTED_SUFFIXES, read_table

Progress = Callable[[int, str], None]
Cancelled = Callable[[], bool]


@dataclass
class TaskReport:
    output_paths: list[Path] = field(default_factory=list)
    input_count: int = 0
    success_count: int = 0
    skipped_count: int = 0
    rows: int = 0
    elapsed_seconds: float = 0.0
    failures: list[dict[str, str]] = field(default_factory=list)

    @property
    def partial_failure(self) -> bool:
        return bool(self.failures)


def resolve_inputs(patterns: list[str]) -> list[Path]:
    found: list[Path] = []
    for raw in patterns:
        path = Path(raw)
        candidates: list[Path]
        if any(char in raw for char in "*?["):
            candidates = [Path(value) for value in glob.glob(raw)]
        elif path.is_dir():
            candidates = [
                item for item in path.iterdir() if item.suffix.lower() in SUPPORTED_SUFFIXES
            ]
        else:
            candidates = [path]
        for candidate in candidates:
            if candidate not in found:
                found.append(candidate)
    return sorted(found, key=lambda value: str(value).lower())


def run_workflow(
    config: WorkflowConfig,
    *,
    progress: Progress | None = None,
    cancelled: Cancelled | None = None,
) -> TaskReport:
    started = time.monotonic()
    report = TaskReport()
    paths = resolve_inputs(config.input.paths)
    report.input_count = len(paths)
    if not paths:
        raise InputFileError("没有找到可处理的 CSV/XLSX 文件")

    frames: list[pd.DataFrame] = []
    merge_operation = next((op for op in config.operations if op.type == "merge"), None)
    for index, path in enumerate(paths, 1):
        _check_cancelled(cancelled)
        if progress:
            progress(int(index / (len(paths) + 2) * 55), f"正在读取：{path.name}")
        try:
            frame = read_table(
                path,
                sheet=config.input.sheet,
                header=config.input.header,
                encoding=config.input.encoding,
                delimiter=config.input.delimiter,
            )
            if merge_operation and merge_operation.params().get("add_source_column", False):
                frame[merge_operation.params().get("source_column", "来源文件")] = path.name
            frames.append(frame)
            report.success_count += 1
        except InputFileError as exc:
            report.failures.append({"path": str(path), "error": str(exc)})
            report.skipped_count += 1
            if config.input.on_error == "stop":
                raise

    if not frames:
        raise InputFileError("所有输入文件均读取失败")
    _check_cancelled(cancelled)
    frame = pd.concat(frames, ignore_index=True, sort=False)

    operations = [op for op in config.operations if op.type not in {"merge", "split_by"}]
    for index, operation in enumerate(operations, 1):
        _check_cancelled(cancelled)
        if progress:
            progress(55 + int(index / max(len(operations), 1) * 30), f"正在执行：{operation.type}")
        frame = apply_operation(frame, operation.type, operation.params())

    _check_cancelled(cancelled)
    split = next((op for op in config.operations if op.type == "split_by"), None)
    if split:
        column = split.params().get("column")
        if column not in frame.columns:
            raise OperationError(f"拆分列不存在：{column}")
        base = Path(config.output.path)
        for value, part in frame.groupby(column, dropna=False):
            safe = re.sub(r'[<>:"/\\|?*]+', "_", str(value))[:80] or "空值"
            output = base.with_name(f"{base.stem}_{safe}{base.suffix}")
            report.output_paths.append(
                export_table(part.reset_index(drop=True), config.output, output)
            )
    else:
        report.output_paths.append(export_table(frame, config.output))

    report.rows = len(frame)
    report.elapsed_seconds = time.monotonic() - started
    if progress:
        progress(100, "处理完成")
    return report


def _check_cancelled(cancelled: Cancelled | None) -> None:
    if cancelled and cancelled():
        raise TaskCancelled("任务已取消")
