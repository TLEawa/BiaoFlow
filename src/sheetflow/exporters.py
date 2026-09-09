from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font

from sheetflow.config import OutputConfig
from sheetflow.exceptions import ExportError


def export_table(frame: pd.DataFrame, config: OutputConfig, path: str | Path | None = None) -> Path:
    target = Path(path or config.path)
    output_format = config.format or target.suffix.lower().lstrip(".")
    if output_format not in {"csv", "xlsx"}:
        raise ExportError(f"不支持的输出格式：{output_format}")
    if target.exists() and not config.overwrite:
        raise ExportError(f"输出文件已存在：{target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{target.stem}-", suffix=f".{output_format}", dir=target.parent
    )
    os.close(fd)
    temp = Path(temp_name)
    try:
        if output_format == "csv":
            frame.to_csv(temp, index=False, encoding=config.encoding, sep=config.delimiter)
        else:
            frame.to_excel(temp, index=False, engine="openpyxl")
            _format_excel(temp)
        os.replace(temp, target)
        return target
    except Exception as exc:
        temp.unlink(missing_ok=True)
        if isinstance(exc, ExportError):
            raise
        raise ExportError(f"导出失败：{target}（{exc}）") from exc


def _format_excel(path: Path) -> None:
    book = load_workbook(path)
    sheet = book.active
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for column in sheet.columns:
        values = [len(str(cell.value)) if cell.value is not None else 0 for cell in column[:200]]
        width = min(max(values + [8]) + 2, 50)
        sheet.column_dimensions[column[0].column_letter].width = width
    book.save(path)
