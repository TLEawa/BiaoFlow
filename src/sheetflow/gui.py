from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from sheetflow.assistant import (
    TEMPLATES,
    WorkflowSuggestion,
    suggest_operations,
    template_operations,
)
from sheetflow.config import (
    InputConfig,
    OperationConfig,
    OutputConfig,
    WorkflowConfig,
    load_workflow,
    save_workflow,
)
from sheetflow.exceptions import SheetFlowError
from sheetflow.readers import read_table
from sheetflow.service import TaskReport, preview_workflow, run_workflow

PRESETS: dict[str, dict[str, object]] = {
    "合并文件": {"type": "merge", "add_source_column": True},
    "删除空行和空列": {"type": "drop_empty", "axis": "both"},
    "清理文本空格": {"type": "trim_text"},
    "删除重复行": {"type": "drop_duplicates"},
    "重命名列": {"type": "rename_columns", "mapping": {"旧列名": "新列名"}},
    "删除列": {"type": "drop_columns", "columns": ["列名"]},
    "调整列顺序": {"type": "reorder_columns", "columns": ["列名"]},
    "筛选行": {"type": "filter", "column": "列名", "operator": "eq", "value": "值"},
    "排序": {"type": "sort", "columns": ["列名"], "ascending": True},
    "类型转换": {"type": "convert_type", "column": "列名", "target": "number"},
    "填充空值": {"type": "fill_null", "columns": ["列名"], "value": ""},
    "分组汇总": {
        "type": "group_summary",
        "group_by": ["分组列"],
        "aggregations": {"数值列": "sum"},
    },
    "按列拆分文件": {"type": "split_by", "column": "列名"},
}


class FileListWidget(QListWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.is_dir() or path.suffix.lower() in {".csv", ".xlsx"}:
                self.addItem(str(path))
        event.acceptProposedAction()


class Worker(QThread):
    progress = Signal(int, str)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, config: WorkflowConfig) -> None:
        super().__init__()
        self.config = config
        self.cancel_requested = False

    def run(self) -> None:
        try:
            report = run_workflow(
                self.config,
                progress=lambda value, text: self.progress.emit(value, text),
                cancelled=lambda: self.cancel_requested,
            )
            self.completed.emit(report)
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SheetFlow 0.2.0")
        self.resize(1040, 780)
        self.worker: Worker | None = None
        self.files = FileListWidget()
        self.operations = QListWidget()
        self.operation_editor = QPlainTextEdit()
        self.operation_editor.setPlaceholderText(
            '选中操作后可编辑 JSON 参数，例如 {"type":"trim_text"}'
        )
        self.operation_editor.setMaximumHeight(90)
        self.preview = QTableWidget()
        self.output_label = QLabel("尚未选择输出文件")
        self.output_path: str | None = None
        self.progress_bar = QProgressBar()
        self.status = QLabel("就绪")
        self.instruction = QPlainTextEdit()
        self.instruction.setPlaceholderText(
            "例如：合并文件并保留来源，删除空行空列，按手机号去重，再按城市拆分"
        )
        self.instruction.setMaximumHeight(64)
        self.template_combo = QComboBox()
        self.template_combo.addItems(list(TEMPLATES))
        self._build_ui()

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        file_buttons = QHBoxLayout()
        add_file = QPushButton("添加文件")
        add_dir = QPushButton("添加目录")
        clear = QPushButton("清空")
        add_file.clicked.connect(self.add_files)
        add_dir.clicked.connect(self.add_directory)
        clear.clicked.connect(self.files.clear)
        for button in (add_file, add_dir, clear):
            file_buttons.addWidget(button)
        layout.addWidget(QLabel("1. 输入文件（CSV/XLSX）"))
        layout.addLayout(file_buttons)
        layout.addWidget(self.files)

        assistant_row = QHBoxLayout()
        generate = QPushButton("从描述生成步骤")
        apply_template = QPushButton("应用模板")
        generate.clicked.connect(self.generate_operations)
        apply_template.clicked.connect(self.apply_template)
        assistant_row.addWidget(self.template_combo)
        assistant_row.addWidget(apply_template)
        assistant_row.addWidget(generate)
        layout.addWidget(QLabel("2. 智能创建流程（本地解析，不上传表格）"))
        layout.addWidget(self.instruction)
        layout.addLayout(assistant_row)

        operation_row = QHBoxLayout()
        preset = QComboBox()
        preset.addItems(list(PRESETS))
        add_operation = QPushButton("添加操作")
        remove_operation = QPushButton("删除操作")
        up = QPushButton("上移")
        down = QPushButton("下移")
        add_operation.clicked.connect(lambda: self.add_operation(preset.currentText()))
        remove_operation.clicked.connect(self.remove_operation)
        up.clicked.connect(lambda: self.move_operation(-1))
        down.clicked.connect(lambda: self.move_operation(1))
        self.operations.currentRowChanged.connect(self.show_operation)
        self.operation_editor.textChanged.connect(self.update_operation)
        for widget in (preset, add_operation, remove_operation, up, down):
            operation_row.addWidget(widget)
        layout.addWidget(QLabel("3. 处理步骤"))
        layout.addLayout(operation_row)
        layout.addWidget(self.operations)
        layout.addWidget(self.operation_editor)

        action_row = QHBoxLayout()
        preview = QPushButton("预览前 100 行")
        choose_output = QPushButton("选择输出文件")
        save = QPushButton("保存工作流")
        load = QPushButton("打开工作流")
        run = QPushButton("开始处理")
        cancel = QPushButton("取消")
        preview.clicked.connect(self.load_preview)
        choose_output.clicked.connect(self.choose_output)
        save.clicked.connect(self.save_config)
        load.clicked.connect(self.load_config)
        run.clicked.connect(self.start_task)
        cancel.clicked.connect(self.cancel_task)
        for button in (preview, choose_output, save, load, run, cancel):
            action_row.addWidget(button)
        layout.addWidget(QLabel("4. 预览、输出与执行"))
        layout.addLayout(action_row)
        layout.addWidget(self.output_label)
        layout.addWidget(self.preview)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status)
        self.setCentralWidget(root)

    def add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "选择文件", "", "表格 (*.csv *.xlsx)")
        for path in paths:
            self.files.addItem(path)

    def add_directory(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择目录")
        if path:
            self.files.addItem(path)

    def add_operation(self, label: str) -> None:
        self.operations.addItem(json.dumps(PRESETS[label], ensure_ascii=False))

    def _available_columns(self) -> list[str]:
        if self.files.count() == 0:
            return []
        source = Path(self.files.item(0).text())
        if source.is_dir():
            source = next(
                (p for p in source.iterdir() if p.suffix.lower() in {".csv", ".xlsx"}),
                source,
            )
        if not source.is_file():
            return []
        return [str(column) for column in read_table(source).columns]

    def _set_suggestion(self, suggestion: WorkflowSuggestion) -> None:
        operations = suggestion.operations
        warnings = suggestion.warnings
        if operations:
            self.operations.clear()
            for operation in operations:
                self.operations.addItem(json.dumps(operation.model_dump(), ensure_ascii=False))
        if warnings:
            self.status.setText("；".join(warnings))
        elif operations:
            self.status.setText(f"已生成 {len(operations)} 个处理步骤，请预览后再执行")

    def generate_operations(self) -> None:
        try:
            suggestion = suggest_operations(
                self.instruction.toPlainText(), self._available_columns()
            )
            self._set_suggestion(suggestion)
        except Exception as exc:
            QMessageBox.warning(self, "生成失败", str(exc))

    def apply_template(self) -> None:
        try:
            suggestion = template_operations(
                self.template_combo.currentText(), self._available_columns()
            )
            self._set_suggestion(suggestion)
            self.instruction.setPlainText(TEMPLATES[self.template_combo.currentText()].description)
        except Exception as exc:
            QMessageBox.warning(self, "无法应用模板", str(exc))

    def remove_operation(self) -> None:
        self.operations.takeItem(self.operations.currentRow())

    def move_operation(self, offset: int) -> None:
        row = self.operations.currentRow()
        target = row + offset
        if row >= 0 and 0 <= target < self.operations.count():
            item = self.operations.takeItem(row)
            self.operations.insertItem(target, item)
            self.operations.setCurrentRow(target)

    def show_operation(self, row: int) -> None:
        self.operation_editor.blockSignals(True)
        self.operation_editor.setPlainText(self.operations.item(row).text() if row >= 0 else "")
        self.operation_editor.blockSignals(False)

    def update_operation(self) -> None:
        row = self.operations.currentRow()
        if row >= 0:
            self.operations.item(row).setText(self.operation_editor.toPlainText())

    def choose_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "输出文件", "result.xlsx", "Excel (*.xlsx);;CSV (*.csv)"
        )
        if path:
            self.output_path = path
            self.output_label.setText(path)

    def build_config(self, *, require_output: bool = True) -> WorkflowConfig:
        if self.files.count() == 0:
            raise ValueError("请先添加输入文件")
        if require_output and not self.output_path:
            raise ValueError("请选择输出文件")
        operations = [
            OperationConfig.model_validate_json(self.operations.item(i).text())
            for i in range(self.operations.count())
        ]
        return WorkflowConfig(
            version=1,
            input=InputConfig(paths=[self.files.item(i).text() for i in range(self.files.count())]),
            operations=operations,
            output=OutputConfig(path=self.output_path or "preview.xlsx"),
        )

    def load_preview(self) -> None:
        try:
            report = preview_workflow(self.build_config(require_output=False))
            frame = report.frame
            self.preview.setRowCount(len(frame))
            self.preview.setColumnCount(len(frame.columns))
            self.preview.setHorizontalHeaderLabels([str(c) for c in frame.columns])
            for row in range(len(frame)):
                for column in range(len(frame.columns)):
                    self.preview.setItem(row, column, QTableWidgetItem(str(frame.iat[row, column])))
            removed = report.before_rows - report.after_rows
            changed_columns = len(report.after_columns) - len(report.before_columns)
            self.status.setText(
                f"预览完成：{report.before_rows} → {report.after_rows} 行"
                f"（减少 {removed}），列数变化 {changed_columns:+d}"
            )
        except Exception as exc:
            QMessageBox.warning(self, "预览失败", str(exc))

    def save_config(self) -> None:
        try:
            config = self.build_config()
            path, _ = QFileDialog.getSaveFileName(
                self, "保存工作流", "workflow.yaml", "YAML (*.yaml *.yml)"
            )
            if path:
                save_workflow(config, path)
                self.status.setText(f"工作流已保存：{path}")
        except Exception as exc:
            QMessageBox.warning(self, "无法保存", str(exc))

    def load_config(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "打开工作流", "", "YAML (*.yaml *.yml)")
        if not path:
            return
        try:
            config = load_workflow(path)
            self.files.clear()
            self.operations.clear()
            for value in config.input.paths:
                self.files.addItem(value)
            for operation in config.operations:
                self.operations.addItem(json.dumps(operation.model_dump(), ensure_ascii=False))
            self.output_path = config.output.path
            self.output_label.setText(config.output.path)
        except SheetFlowError as exc:
            QMessageBox.warning(self, "无法打开", str(exc))

    def start_task(self) -> None:
        try:
            config = self.build_config()
            if Path(config.output.path).exists():
                answer = QMessageBox.question(self, "确认覆盖", "输出文件已存在，是否覆盖？")
                if answer != QMessageBox.StandardButton.Yes:
                    return
                config.output.overwrite = True
            self.worker = Worker(config)
            self.worker.progress.connect(self.update_progress)
            self.worker.completed.connect(self.task_completed)
            self.worker.failed.connect(lambda text: QMessageBox.warning(self, "处理失败", text))
            self.worker.start()
        except Exception as exc:
            QMessageBox.warning(self, "无法开始", str(exc))

    def cancel_task(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.cancel_requested = True
            self.status.setText("正在安全取消……")

    def update_progress(self, value: int, text: str) -> None:
        self.progress_bar.setValue(value)
        self.status.setText(text)

    def task_completed(self, report: TaskReport) -> None:
        outputs = "\n".join(str(path) for path in report.output_paths)
        QMessageBox.information(self, "处理完成", f"已生成：\n{outputs}\n共 {report.rows} 行")


def main() -> None:
    application = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.show()
    application.exec()


if __name__ == "__main__":
    main()
