from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from sheetflow.exceptions import InputFileError

SUPPORTED_SUFFIXES = {".csv", ".xlsx"}


def _detect_csv(path: Path, encoding: str | None, delimiter: str | None) -> tuple[str, str]:
    encodings = [encoding] if encoding else ["utf-8-sig", "utf-8", "gb18030", "gbk"]
    for candidate in encodings:
        if candidate is None:
            continue
        try:
            sample = path.read_text(encoding=candidate)[:8192]
            if delimiter:
                return candidate, delimiter
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
                return candidate, dialect.delimiter
            except csv.Error:
                return candidate, ","
        except UnicodeDecodeError:
            continue
    raise InputFileError(f"无法识别 CSV 编码：{path}")


def read_table(
    path: str | Path,
    *,
    sheet: str | int | None = None,
    header: int = 0,
    encoding: str | None = None,
    delimiter: str | None = None,
) -> pd.DataFrame:
    source = Path(path)
    if not source.is_file():
        raise InputFileError(f"文件不存在：{source}")
    if source.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise InputFileError(f"不支持的文件格式：{source.suffix}")
    try:
        if source.suffix.lower() == ".csv":
            real_encoding, real_delimiter = _detect_csv(source, encoding, delimiter)
            return pd.read_csv(source, encoding=real_encoding, sep=real_delimiter, header=header)
        return pd.read_excel(source, sheet_name=sheet if sheet is not None else 0, header=header)
    except InputFileError:
        raise
    except Exception as exc:
        raise InputFileError(f"读取失败：{source}（{exc}）") from exc


def inspect_table(
    path: str | Path,
    *,
    sheet: str | int | None = None,
    header: int = 0,
    encoding: str | None = None,
    delimiter: str | None = None,
) -> dict[str, object]:
    frame = read_table(
        path,
        sheet=sheet,
        header=header,
        encoding=encoding,
        delimiter=delimiter,
    )
    return {
        "path": str(Path(path).resolve()),
        "rows": int(len(frame)),
        "columns": [str(column) for column in frame.columns],
        "column_count": int(len(frame.columns)),
        "preview": frame.head(5).where(pd.notna(frame.head(5)), None).to_dict("records"),
    }
