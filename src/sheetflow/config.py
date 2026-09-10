from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from sheetflow.exceptions import ConfigurationError


class InputConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    paths: list[str] = Field(min_length=1)
    sheet: str | int | None = None
    header: int = 0
    encoding: str | None = None
    delimiter: str | None = None
    on_error: Literal["stop", "continue"] = "stop"


class OperationConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: str

    @field_validator("type")
    @classmethod
    def non_empty_type(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("操作类型不能为空")
        return value.strip()

    def params(self) -> dict[str, Any]:
        data = self.model_dump()
        data.pop("type", None)
        return data


class OutputConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    format: Literal["xlsx", "csv"] | None = None
    overwrite: bool = False
    encoding: str = "utf-8-sig"
    delimiter: str = ","


class WorkflowConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1]
    input: InputConfig
    operations: list[OperationConfig] = Field(default_factory=list)
    output: OutputConfig
    mapping: dict[str, str] = Field(default_factory=dict)


def load_workflow(path: str | Path) -> WorkflowConfig:
    config_path = Path(path)
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        config = WorkflowConfig.model_validate(raw)
    except OSError as exc:
        raise ConfigurationError(f"无法读取配置文件：{config_path}") from exc
    except (yaml.YAMLError, ValidationError, TypeError) as exc:
        raise ConfigurationError(f"配置文件格式错误：{exc}") from exc

    base = config_path.resolve().parent
    config.input.paths = [
        str((base / p).resolve()) if not Path(p).is_absolute() else p for p in config.input.paths
    ]
    if not Path(config.output.path).is_absolute():
        config.output.path = str((base / config.output.path).resolve())
    return config


def save_workflow(config: WorkflowConfig, path: str | Path) -> None:
    target = Path(path)
    target.write_text(
        yaml.safe_dump(config.model_dump(exclude_none=True), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
