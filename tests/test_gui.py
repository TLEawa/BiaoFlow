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
    assert window.windowTitle() == "SheetFlow 0.2.0"
    window.instruction.setPlainText("按编号去重")
    window.generate_operations()
    assert window.operations.count() == 1
    assert '"type": "drop_duplicates"' in window.operations.item(0).text()
    window.close()
    application.processEvents()
