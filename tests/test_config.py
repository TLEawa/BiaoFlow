from pathlib import Path

import pytest
from pydantic import ValidationError

from sheetflow.config import WorkflowConfig, load_workflow
from sheetflow.exceptions import ConfigurationError


def test_load_relative_paths(tmp_path: Path) -> None:
    path = tmp_path / "flow.yaml"
    path.write_text(
        "version: 1\ninput:\n  paths: [input.csv]\noperations: []\noutput:\n  path: result.xlsx\n",
        encoding="utf-8",
    )
    config = load_workflow(path)
    assert Path(config.input.paths[0]) == tmp_path / "input.csv"
    assert Path(config.output.path) == tmp_path / "result.xlsx"


def test_reject_unknown_top_level() -> None:
    with pytest.raises(ValidationError):
        WorkflowConfig.model_validate(
            {
                "version": 1,
                "input": {"paths": ["a.csv"]},
                "operations": [],
                "output": {"path": "x.csv"},
                "extra": True,
            }
        )


def test_bad_yaml_is_user_error(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("version: [", encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_workflow(path)
