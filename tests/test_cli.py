from pathlib import Path

from typer.testing import CliRunner

from sheetflow.cli import app
from sheetflow.config import load_workflow


def test_suggest_command_saves_workflow(tmp_path: Path) -> None:
    source = tmp_path / "订单.csv"
    source.write_text("订单号,城市\n1,武汉\n1,武汉\n", encoding="utf-8")
    workflow = tmp_path / "workflow.yaml"
    result = CliRunner().invoke(
        app,
        ["suggest", str(source), "按订单号去重", "--save", str(workflow)],
    )
    assert result.exit_code == 0, result.output
    config = load_workflow(workflow)
    assert config.operations[0].type == "drop_duplicates"
    assert config.operations[0].params()["columns"] == ["订单号"]
