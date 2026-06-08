from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from pygiffer.config import load_config, save_config
from pygiffer.paths import taskbar_icon_path
from pygiffer.ui.cli_runner import CliProcessRunner
from pygiffer.ui.flow_layout import FlowLayout
from pygiffer.ui.theme import (
    FOLDER_LIST_MAX_HEIGHT,
    THUMB_SIZE,
    default_window_size,
)
from pygiffer.utils import format_timestamp, scan_gifs


class GifThumb(QFrame):
    clicked = pyqtSignal(str)

    def __init__(self, gif_path: Path):
        super().__init__()
        self.gif_path = gif_path
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(str(gif_path))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.image_label = QLabel()
        self.image_label.setFixedSize(THUMB_SIZE, THUMB_SIZE)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background:#1e1e24;border-radius:4px;")
        layout.addWidget(self.image_label)

        name_label = QLabel(gif_path.name)
        name_label.setWordWrap(True)
        name_label.setMaximumWidth(THUMB_SIZE + 16)
        name_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(name_label)

        self._load_thumb()

    def _load_thumb(self):
        pix = QPixmap(str(self.gif_path))
        if pix.isNull():
            self.image_label.setText("GIF")
            return
        scaled = pix.scaled(
            THUMB_SIZE,
            THUMB_SIZE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(str(self.gif_path))
        super().mousePressEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyGiffer")
        self.resize(default_window_size())
        self._apply_window_icon()

        self.config = load_config()
        self.material_folders = list(self.config.get("material_folders", []))
        self.merge_output_path: Path | None = None
        self._merge_output_customized = False
        self.gif_index = {}
        self.worker: CliProcessRunner | None = None

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setSpacing(12)

        layout.addWidget(self._build_convert_group())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_material_panel())
        splitter.addWidget(self._build_merge_panel())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, stretch=1)

        self.status_label = QLabel("就绪")
        self.status_label.setObjectName("StatusLabel")
        layout.addWidget(self.status_label)

        self._refresh_folder_list()
        self._rescan_all_gifs()
        self._refresh_merge_output_path()

    def _apply_window_icon(self):
        icon_file = taskbar_icon_path()
        if icon_file.exists():
            self.setWindowIcon(QIcon(str(icon_file)))

    def _build_convert_group(self):
        group = QGroupBox("格式转换")
        row = QHBoxLayout(group)

        self.convert_path_label = QLabel("未选择文件")
        self.convert_path_label.setObjectName("MutedLabel")
        row.addWidget(self.convert_path_label, stretch=1)

        pick_btn = QPushButton("选择文件")
        pick_btn.clicked.connect(self._pick_convert_file)
        row.addWidget(pick_btn)

        self.convert_btn = QPushButton("转换为 GIF")
        self.convert_btn.setEnabled(False)
        self.convert_btn.clicked.connect(self._run_convert)
        row.addWidget(self.convert_btn)

        return group

    def _build_material_panel(self):
        group = QGroupBox("素材文件夹")
        layout = QVBoxLayout(group)

        toolbar = QHBoxLayout()
        add_btn = QPushButton("添加素材文件夹")
        add_btn.clicked.connect(self._add_material_folder)
        toolbar.addWidget(add_btn)

        remove_btn = QPushButton("移除选中文件夹")
        remove_btn.clicked.connect(self._remove_material_folder)
        toolbar.addWidget(remove_btn)

        rescan_btn = QPushButton("重新扫描")
        rescan_btn.clicked.connect(self._rescan_all_gifs)
        toolbar.addWidget(rescan_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.folder_list = QListWidget()
        self.folder_list.setMaximumHeight(FOLDER_LIST_MAX_HEIGHT)
        layout.addWidget(self.folder_list)

        self.preview_scroll = QScrollArea()
        self.preview_scroll.setWidgetResizable(True)
        self.preview_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.preview_host = QWidget()
        self.preview_layout = FlowLayout(self.preview_host, margin=8, spacing=12)
        self.preview_host.setLayout(self.preview_layout)
        self.preview_scroll.setWidget(self.preview_host)
        layout.addWidget(self.preview_scroll, stretch=1)

        return group

    def _build_merge_panel(self):
        group = QGroupBox("合并队列")
        layout = QVBoxLayout(group)

        hint = QLabel("点击左侧 GIF 预览加入队列；可重复添加同一文件；拖拽调整顺序")
        hint.setObjectName("HintLabel")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.merge_list = QListWidget()
        self.merge_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.merge_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.merge_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.merge_list.model().rowsMoved.connect(self._on_merge_queue_changed)
        layout.addWidget(self.merge_list, stretch=1)

        row = QHBoxLayout()
        remove_btn = QPushButton("移除选中")
        remove_btn.clicked.connect(self._remove_selected_merge_items)
        row.addWidget(remove_btn)

        clear_btn = QPushButton("清空")
        clear_btn.clicked.connect(self._clear_merge_queue)
        row.addWidget(clear_btn)
        row.addStretch()
        layout.addLayout(row)

        self.remove_transparent_cb = QCheckBox("去除透明背景（填充白色）")
        layout.addWidget(self.remove_transparent_cb)

        out_row = QHBoxLayout()
        self.output_path_label = QLabel("（加入 GIF 后自动生成保存路径）")
        self.output_path_label.setObjectName("MutedLabel")
        self.output_path_label.setWordWrap(True)
        out_row.addWidget(self.output_path_label, stretch=1)
        out_btn = QPushButton("保存路径")
        out_btn.clicked.connect(self._pick_merge_output_path)
        out_row.addWidget(out_btn)
        layout.addLayout(out_row)

        self.merge_btn = QPushButton("横向合并")
        self.merge_btn.clicked.connect(self._run_merge)
        layout.addWidget(self.merge_btn)

        return group

    def _set_busy(self, busy, message=""):
        self.convert_btn.setEnabled(not busy and bool(self.convert_path_label.toolTip()))
        self.merge_btn.setEnabled(not busy)
        if message:
            self.status_label.setText(message)

    def _pick_convert_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择文件",
            "",
            "Media (*.webp *.gif *.png *.jpg *.jpeg *.bmp *.mp4 *.webm *.mov *.avi *.mkv);;All (*.*)",
        )
        if not path:
            return
        self.convert_path_label.setText(Path(path).name)
        self.convert_path_label.setToolTip(path)
        self.convert_btn.setEnabled(True)

    def _run_convert(self):
        src = Path(self.convert_path_label.toolTip())
        if not src.exists():
            QMessageBox.warning(self, "PyGiffer", "源文件不存在")
            return

        output = src.parent / f"{src.stem}-{format_timestamp()}.gif"

        self._set_busy(True, f"正在转换 {src.name}...")
        self.worker = CliProcessRunner(self)
        self.worker.finished_ok.connect(self._on_convert_ok)
        self.worker.finished_err.connect(self._on_task_err)
        self.worker.start(["convert", "-o", str(output), str(src)], str(output))

    def _on_convert_ok(self, output):
        self._set_busy(False, f"转换完成: {output}")
        QMessageBox.information(self, "PyGiffer", f"已保存:\n{output}")

    def _on_task_err(self, message):
        self._set_busy(False, "操作失败")
        QMessageBox.critical(self, "PyGiffer", message)

    def _add_material_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择素材文件夹")
        if not folder:
            return
        folder = str(Path(folder).resolve())
        if folder not in self.material_folders:
            self.material_folders.append(folder)
            self._persist_config()
        self._refresh_folder_list()
        self._rescan_all_gifs()

    def _remove_material_folder(self):
        row = self.folder_list.currentRow()
        if row < 0:
            return
        self.material_folders.pop(row)
        self._persist_config()
        self._refresh_folder_list()
        self._rescan_all_gifs()

    def _refresh_folder_list(self):
        self.folder_list.clear()
        for folder in self.material_folders:
            self.folder_list.addItem(folder)

    def _persist_config(self):
        self.config["material_folders"] = self.material_folders
        save_config(self.config)

    def _default_merge_output_path(self) -> Path | None:
        paths = self._collect_merge_paths()
        if not paths:
            return None
        return paths[0].parent / f"{format_timestamp()}.gif"

    def _refresh_merge_output_path(self):
        if self._merge_output_customized and self.merge_output_path is not None:
            self.output_path_label.setText(str(self.merge_output_path))
            return

        default = self._default_merge_output_path()
        self.merge_output_path = default
        if default is None:
            self.output_path_label.setText("（加入 GIF 后自动生成保存路径）")
        else:
            self.output_path_label.setText(str(default))

    def _on_merge_queue_changed(self):
        if not self._merge_output_customized:
            self._refresh_merge_output_path()

    def _pick_merge_output_path(self):
        default = self.merge_output_path or self._default_merge_output_path()
        start_dir = str(default.parent) if default else str(Path.home())
        start_name = default.name if default else f"{format_timestamp()}.gif"

        path, _ = QFileDialog.getSaveFileName(
            self,
            "选择保存路径",
            str(Path(start_dir) / start_name),
            "GIF (*.gif);;All (*.*)",
        )
        if not path:
            return

        save_path = Path(path)
        if save_path.suffix.lower() != ".gif":
            save_path = save_path.with_suffix(".gif")

        self.merge_output_path = save_path
        self._merge_output_customized = True
        self.output_path_label.setText(str(save_path))

    def _clear_preview(self):
        while self.preview_layout.count():
            item = self.preview_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _rescan_all_gifs(self):
        self._clear_preview()
        self.gif_index.clear()
        seen = set()

        for folder in self.material_folders:
            for gif_path in scan_gifs(Path(folder)):
                key = str(gif_path)
                if key in seen:
                    continue
                seen.add(key)
                self.gif_index[key] = gif_path
                thumb = GifThumb(gif_path)
                thumb.clicked.connect(self._add_to_merge_queue)
                self.preview_layout.addWidget(thumb)

        self.preview_host.adjustSize()
        self.status_label.setText(f"已扫描 {len(self.gif_index)} 个 GIF")

    def _add_to_merge_queue(self, gif_path):
        path = Path(gif_path)
        item = QListWidgetItem(path.name)
        item.setToolTip(gif_path)
        item.setData(Qt.ItemDataRole.UserRole, gif_path)
        self.merge_list.addItem(item)
        self._on_merge_queue_changed()

    def _remove_selected_merge_items(self):
        for item in self.merge_list.selectedItems():
            row = self.merge_list.row(item)
            self.merge_list.takeItem(row)
        self._on_merge_queue_changed()

    def _clear_merge_queue(self):
        self.merge_list.clear()
        self._merge_output_customized = False
        self._refresh_merge_output_path()

    def _collect_merge_paths(self):
        paths = []
        for i in range(self.merge_list.count()):
            item = self.merge_list.item(i)
            paths.append(Path(item.data(Qt.ItemDataRole.UserRole)))
        return paths

    def _run_merge(self):
        paths = self._collect_merge_paths()
        if len(paths) < 2:
            QMessageBox.warning(self, "PyGiffer", "请至少加入 2 个 GIF")
            return

        if self._merge_output_customized:
            output = self.merge_output_path
        else:
            output = self._default_merge_output_path()
        if output is None:
            QMessageBox.warning(self, "PyGiffer", "无法确定保存路径")
            return

        output.parent.mkdir(parents=True, exist_ok=True)
        remove_bg = self.remove_transparent_cb.isChecked()
        cli_args = ["merge", "-o", str(output)]
        if remove_bg:
            cli_args.append("--flat")
        cli_args.extend(str(path) for path in paths)

        self._set_busy(True, "正在合并 GIF...")
        self.worker = CliProcessRunner(self)
        self.worker.finished_ok.connect(self._on_merge_ok)
        self.worker.finished_err.connect(self._on_task_err)
        self.worker.start(cli_args, str(output))

    def _on_merge_ok(self, output):
        self._set_busy(False, f"合并完成: {output}")
        QMessageBox.information(self, "PyGiffer", f"已保存:\n{output}")

    def closeEvent(self, event):
        self._persist_config()
        super().closeEvent(event)
