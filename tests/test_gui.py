import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from sheetflow.gui import MainWindow


def test_main_window_builds_workflow(tmp_path) -> None:
    application = QApplication.instance() or QApplication([])
    window = MainWindow()
    source = tmp_path / "输入.csv"
    source.write_text("编号,值\n1,A\n", encoding="utf-8")
    window.files.addItem(str(source))
    window.output_path = str(tmp_path / "输出.xlsx")
    window.add_operation("清理文本空格")
    config = window.build_config()
    assert config.operations[0].type == "trim_text"
    assert window.windowTitle() == "SheetFlow 0.1.0"
    window.close()
    application.processEvents()
