"""
Visual Media & Image Diffing Studio (White / Light Theme)
Features:
- Hardware-accelerated QPainter Swipe Curtain, Onion-Skin, Heatmap, Flicker, and Side-by-Side modes
  (zero PIL re-encoding during curtain drag).
- Interactive Zoom (Fit, 100%, +/-, Ctrl+Wheel), Swap, and Drag & Drop.
- Multi-page PDF diffing with aligned text diff view (DiffEngine + ModernCodeEditor).
- EXIF / Document metadata comparison table.
"""

import os
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QComboBox, QSlider, QScrollArea, QFrame,
    QSplitter, QStackedWidget, QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt, QTimer, Signal, QPoint, QRect
from PySide6.QtGui import QPixmap, QImage, QPainter, QColor, QPen, QBrush, QDragEnterEvent, QDropEvent
from PIL import Image

from app.core.image_diff import ImageDiffEngine, ImageDiffResult
from app.core.diff_engine import DiffEngine
from app.ui.widgets.modern_editor import ModernCodeEditor
from app.ui.styles.icons import get_line_icon


def pil_to_qpixmap(pil_img: Image.Image) -> QPixmap:
    """Converts a PIL Image to a PySide6 QPixmap."""
    if pil_img.mode != "RGBA":
        pil_img = pil_img.convert("RGBA")
    data = pil_img.tobytes("raw", "RGBA")
    qimg = QImage(data, pil_img.width, pil_img.height, QImage.Format_RGBA8888)
    return QPixmap.fromImage(qimg.copy())


class ImageCanvas(QWidget):
    """Interactive canvas that renders cached QPixmaps directly in QPainter for 60fps curtain/zoom."""
    curtainMoved = Signal(float)
    zoomChanged = Signal(float)
    filesDropped = Signal(list)

    def __init__(self):
        super().__init__()
        self.pm_left: Optional[QPixmap] = None
        self.pm_right: Optional[QPixmap] = None
        self.pm_heatmap: Optional[QPixmap] = None
        self.mode = 0              # 0=curtain, 1=onion, 2=heatmap, 3=blink, 4=side-by-side
        self.curtain_ratio = 0.5
        self.onion_alpha = 0.5
        self.blink_state = False

        self.is_dragging_curtain = False
        self.zoom_factor = 1.0
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.setMinimumSize(400, 300)

    def set_layers(self, pm_left: Optional[QPixmap], pm_right: Optional[QPixmap], pm_heatmap: Optional[QPixmap]):
        self.pm_left = pm_left
        self.pm_right = pm_right
        self.pm_heatmap = pm_heatmap
        self._update_canvas_size()
        self.update()

    def set_render_params(self, mode: int, curtain_ratio: float, onion_alpha: float, blink_state: bool):
        mode_changed = (self.mode != mode)
        self.mode = mode
        self.curtain_ratio = curtain_ratio
        self.onion_alpha = onion_alpha
        self.blink_state = blink_state
        if mode_changed:
            self._update_canvas_size()
        self.update()

    def set_zoom(self, zoom: float):
        self.zoom_factor = max(0.1, min(8.0, zoom))
        self._update_canvas_size()
        self.update()
        self.zoomChanged.emit(self.zoom_factor)

    def _base_size(self):
        if not self.pm_left or self.pm_left.isNull():
            return 0, 0
        w = self.pm_left.width()
        h = self.pm_left.height()
        if self.mode == 4:  # Side-by-side
            return w * 2 + 6, h
        return w, h

    def _update_canvas_size(self):
        bw, bh = self._base_size()
        if bw > 0 and bh > 0:
            self.setMinimumSize(int(bw * self.zoom_factor), int(bh * self.zoom_factor))
        else:
            self.setMinimumSize(400, 300)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#f6f8fa"))

        if not self.pm_left or self.pm_left.isNull():
            painter.setPen(QColor("#8c959f"))
            painter.drawText(self.rect(), Qt.AlignCenter, "Drop two images or PDFs here, or click Browse Left / Right Media")
            return

        painter.setRenderHint(QPainter.SmoothPixmapTransform, self.zoom_factor < 2.0)

        bw, bh = self._base_size()
        target_w = int(bw * self.zoom_factor)
        target_h = int(bh * self.zoom_factor)
        x = max(0, (self.width() - target_w) // 2)
        y = max(0, (self.height() - target_h) // 2)

        if self.mode == 0 and self.pm_right:  # Swipe Curtain
            split_x = int(target_w * self.curtain_ratio)
            full_rect = QRect(x, y, target_w, target_h)

            painter.save()
            painter.setClipRect(QRect(x, y, split_x, target_h))
            painter.drawPixmap(full_rect, self.pm_left)
            painter.restore()

            painter.save()
            painter.setClipRect(QRect(x + split_x, y, target_w - split_x, target_h))
            painter.drawPixmap(full_rect, self.pm_right)
            painter.restore()

            painter.setPen(QPen(QColor("#0969da"), 2))
            painter.drawLine(x + split_x, y, x + split_x, y + target_h)

        elif self.mode == 1 and self.pm_right:  # Onion-Skin
            full_rect = QRect(x, y, target_w, target_h)
            painter.drawPixmap(full_rect, self.pm_left)
            painter.setOpacity(max(0.0, min(1.0, self.onion_alpha)))
            painter.drawPixmap(full_rect, self.pm_right)
            painter.setOpacity(1.0)

        elif self.mode == 2 and self.pm_heatmap:  # Difference Heatmap
            painter.drawPixmap(QRect(x, y, target_w, target_h), self.pm_heatmap)

        elif self.mode == 3 and self.pm_right:  # Blink
            pm = self.pm_left if self.blink_state else self.pm_right
            painter.drawPixmap(QRect(x, y, target_w, target_h), pm)

        elif self.mode == 4 and self.pm_right:  # Side-by-Side
            single_w = int(self.pm_left.width() * self.zoom_factor)
            gap = max(2, int(6 * self.zoom_factor))
            painter.drawPixmap(QRect(x, y, single_w, target_h), self.pm_left)
            painter.drawPixmap(QRect(x + single_w + gap, y, single_w, target_h), self.pm_right)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            factor = 1.15 if delta > 0 else (1.0 / 1.15)
            self.set_zoom(self.zoom_factor * factor)
            event.accept()
            return
        super().wheelEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.mode == 0:
            self.is_dragging_curtain = True
            self._update_curtain_from_pos(event.pos())

    def mouseMoveEvent(self, event):
        if self.is_dragging_curtain and self.mode == 0:
            self._update_curtain_from_pos(event.pos())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_dragging_curtain = False

    def _update_curtain_from_pos(self, pos: QPoint):
        if not self.pm_left or self.pm_left.isNull():
            return
        target_w = max(1.0, self.pm_left.width() * self.zoom_factor)
        x_offset = max(0.0, (self.width() - target_w) / 2.0)
        rel_x = pos.x() - x_offset
        ratio = max(0.0, min(1.0, rel_x / target_w))
        self.curtainMoved.emit(ratio)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile() and os.path.isfile(u.toLocalFile())]
        if paths:
            self.filesDropped.emit(paths)


class ImageDiffView(QWidget):
    """Studio for visual image comparisons and multi-page PDF document diffing."""

    def __init__(self):
        super().__init__()
        self.left_path: Optional[str] = None
        self.right_path: Optional[str] = None
        self.diff_result: Optional[ImageDiffResult] = None
        self.curtain_ratio = 0.5
        self.onion_alpha = 0.5
        self.blink_state = False
        self.current_page = 0
        self.max_pages = 1
        self._is_syncing_text_scroll = False

        self.blink_timer = QTimer(self)
        self.blink_timer.setInterval(400)
        self.blink_timer.timeout.connect(self._on_blink_toggle)

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 1. Top File Selection Bar
        file_bar = QFrame()
        file_bar.setObjectName("ImageFileBar")
        file_bar.setFixedHeight(46)
        file_bar.setStyleSheet("""
            #ImageFileBar {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #f8fafc);
                border-bottom: 1px solid #cbd5e1;
                padding: 4px;
            }
            #ImageFileBar QLabel { border: none; background: transparent; }
        """)
        fb_layout = QHBoxLayout(file_bar)
        fb_layout.setContentsMargins(10, 4, 10, 4)
        fb_layout.setSpacing(10)

        self.btn_left = QPushButton(" Browse Left Media...")
        self.btn_left.setIcon(get_line_icon("folder", "#0969da"))
        self.btn_left.setFixedHeight(30)
        self.btn_left.clicked.connect(self._browse_left)
        self.lbl_left = QLabel("Left: (None)")
        self.lbl_left.setStyleSheet("color: #475569; font-weight: 600; border: none; background: transparent;")

        self.btn_swap = QPushButton(" Swap")
        self.btn_swap.setIcon(get_line_icon("swap", "#1e293b"))
        self.btn_swap.setFixedHeight(30)
        self.btn_swap.clicked.connect(self._swap_media)

        self.btn_right = QPushButton(" Browse Right Media...")
        self.btn_right.setIcon(get_line_icon("folder", "#16a34a"))
        self.btn_right.setFixedHeight(30)
        self.btn_right.clicked.connect(self._browse_right)
        self.lbl_right = QLabel("Right: (None)")
        self.lbl_right.setStyleSheet("color: #475569; font-weight: 600; border: none; background: transparent;")

        fb_layout.addWidget(self.btn_left)
        fb_layout.addWidget(self.lbl_left, 1)
        fb_layout.addWidget(self.btn_swap)
        fb_layout.addWidget(self.btn_right)
        fb_layout.addWidget(self.lbl_right, 1)

        layout.addWidget(file_bar)

        # 2. Command Bar
        cmd_bar = QFrame()
        cmd_bar.setObjectName("ImageCmdBar")
        cmd_bar.setFixedHeight(46)
        cmd_bar.setStyleSheet("""
            #ImageCmdBar {
                background: #ffffff;
                border-bottom: 1.5px solid #cbd5e1;
                padding: 4px;
            }
            #ImageCmdBar QLabel { border: none; background: transparent; color: #334155; font-weight: 500; }
        """)
        cb_layout = QHBoxLayout(cmd_bar)
        cb_layout.setContentsMargins(10, 4, 10, 4)
        cb_layout.setSpacing(6)

        cb_layout.addWidget(QLabel("Mode:"))
        self.combo_mode = QComboBox()
        self.combo_mode.setFixedHeight(30)
        self.combo_mode.addItems([
            "Swipe Curtain (Slider)",
            "Onion-Skin (Alpha)",
            "Difference Heatmap",
            "Flicker / Blink",
            "Side-by-Side"
        ])
        self.combo_mode.currentIndexChanged.connect(self._on_mode_changed)
        cb_layout.addWidget(self.combo_mode)

        self.lbl_slider = QLabel(" Split:")
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(50)
        self.slider.setFixedWidth(100)
        self.slider.valueChanged.connect(self._on_slider_changed)
        cb_layout.addWidget(self.lbl_slider)
        cb_layout.addWidget(self.slider)

        cb_layout.addWidget(QLabel(" Tol:"))
        self.slider_tol = QSlider(Qt.Horizontal)
        self.slider_tol.setRange(0, 50)
        self.slider_tol.setValue(8)
        self.slider_tol.setFixedWidth(60)
        self.slider_tol.valueChanged.connect(self._recompute_diff)
        cb_layout.addWidget(self.slider_tol)

        # Zoom controls
        self.btn_zoom_out = QPushButton()
        self.btn_zoom_out.setIcon(get_line_icon("zoom-out", "#1e293b", size=14))
        self.btn_zoom_out.setFixedSize(28, 28)
        self.btn_zoom_out.setToolTip("Zoom Out (Ctrl+-)")
        self.btn_zoom_out.clicked.connect(lambda: self.canvas.set_zoom(self.canvas.zoom_factor / 1.25))
        cb_layout.addWidget(self.btn_zoom_out)

        self.btn_zoom_100 = QPushButton("100%")
        self.btn_zoom_100.setFixedHeight(28)
        self.btn_zoom_100.setToolTip("Actual Size (100%)")
        self.btn_zoom_100.clicked.connect(lambda: self.canvas.set_zoom(1.0))
        cb_layout.addWidget(self.btn_zoom_100)

        self.btn_zoom_fit = QPushButton("Fit")
        self.btn_zoom_fit.setFixedHeight(28)
        self.btn_zoom_fit.setToolTip("Fit image inside viewport")
        self.btn_zoom_fit.clicked.connect(self._zoom_to_fit)
        cb_layout.addWidget(self.btn_zoom_fit)

        self.btn_zoom_in = QPushButton()
        self.btn_zoom_in.setIcon(get_line_icon("zoom-in", "#1e293b", size=14))
        self.btn_zoom_in.setFixedSize(28, 28)
        self.btn_zoom_in.setToolTip("Zoom In (Ctrl++)")
        self.btn_zoom_in.clicked.connect(lambda: self.canvas.set_zoom(self.canvas.zoom_factor * 1.25))
        cb_layout.addWidget(self.btn_zoom_in)

        # Multi-page PDF Controls
        self.page_container = QWidget()
        self.page_container.setStyleSheet("background: transparent; border: none;")
        pc_layout = QHBoxLayout(self.page_container)
        pc_layout.setContentsMargins(0, 0, 0, 0)
        pc_layout.setSpacing(4)

        self.btn_prev_page = QPushButton()
        self.btn_prev_page.setIcon(get_line_icon("arrow-left", "#1e293b", size=14))
        self.btn_prev_page.setFixedSize(28, 28)
        self.btn_prev_page.clicked.connect(self._prev_page)
        pc_layout.addWidget(self.btn_prev_page)

        self.lbl_page = QLabel("Page 1/1")
        pc_layout.addWidget(self.lbl_page)

        self.btn_next_page = QPushButton()
        self.btn_next_page.setIcon(get_line_icon("arrow-right", "#1e293b", size=14))
        self.btn_next_page.setFixedSize(28, 28)
        self.btn_next_page.clicked.connect(self._next_page)
        pc_layout.addWidget(self.btn_next_page)

        self.page_container.setVisible(False)
        cb_layout.addWidget(self.page_container)

        self.btn_toggle_text = QPushButton(" Text Diff")
        self.btn_toggle_text.setIcon(get_line_icon("file-text", "#0969da"))
        self.btn_toggle_text.setCheckable(True)
        self.btn_toggle_text.setFixedHeight(30)
        self.btn_toggle_text.setToolTip("Toggle aligned extracted document text diff view")
        self.btn_toggle_text.clicked.connect(self._toggle_text_view)
        cb_layout.addWidget(self.btn_toggle_text)

        self.btn_toggle_exif = QPushButton(" EXIF")
        self.btn_toggle_exif.setIcon(get_line_icon("sliders", "#475569"))
        self.btn_toggle_exif.setCheckable(True)
        self.btn_toggle_exif.setFixedHeight(30)
        self.btn_toggle_exif.setToolTip("Toggle EXIF & document metadata inspection panel")
        self.btn_toggle_exif.clicked.connect(self._toggle_exif_view)
        cb_layout.addWidget(self.btn_toggle_exif)

        self.lbl_metrics = QLabel("● Ready")
        self.lbl_metrics.setFixedHeight(30)
        self.lbl_metrics.setStyleSheet("""
            color: #0969da;
            font-weight: 600;
            padding: 4px 10px;
            background: #eff6ff;
            border: 1px solid #bfdbfe;
            border-radius: 6px;
            font-size: 11px;
        """)
        cb_layout.addWidget(self.lbl_metrics)

        cb_layout.addStretch()

        self.btn_refresh = QPushButton(" Refresh")
        self.btn_refresh.setIcon(get_line_icon("refresh", "#1e293b"))
        self.btn_refresh.setFixedHeight(30)
        self.btn_refresh.clicked.connect(self._recompute_diff)
        cb_layout.addWidget(self.btn_refresh)

        layout.addWidget(cmd_bar)

        # 3. Main Splitter
        self.main_splitter = QSplitter(Qt.Vertical)
        self.viewport_stack = QStackedWidget()

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.canvas = ImageCanvas()
        self.canvas.curtainMoved.connect(self._on_curtain_dragged)
        self.canvas.zoomChanged.connect(lambda z: self.btn_zoom_100.setText(f"{int(round(z * 100))}%"))
        self.canvas.filesDropped.connect(self._on_canvas_files_dropped)
        self.scroll_area.setWidget(self.canvas)
        self.viewport_stack.addWidget(self.scroll_area)

        # Aligned Extracted Text Diff Panel (reuses ModernCodeEditor + DiffEngine)
        self.text_panel = QSplitter(Qt.Horizontal)
        self.txt_left = ModernCodeEditor()
        self.txt_left.setReadOnly(True)
        self.txt_right = ModernCodeEditor()
        self.txt_right.setReadOnly(True)
        self.txt_left.scrolled.connect(self._sync_text_left)
        self.txt_right.scrolled.connect(self._sync_text_right)
        self.text_panel.addWidget(self.txt_left)
        self.text_panel.addWidget(self.txt_right)
        self.viewport_stack.addWidget(self.text_panel)

        self.main_splitter.addWidget(self.viewport_stack)

        # Bottom EXIF / Metadata Inspection Panel
        self.exif_panel = QFrame()
        self.exif_panel.setStyleSheet("background: #ffffff; border-top: 1px solid #cbd5e1;")
        ep_layout = QVBoxLayout(self.exif_panel)
        ep_layout.setContentsMargins(6, 6, 6, 6)
        ep_layout.setSpacing(4)

        ep_header = QHBoxLayout()
        lbl_exif_title = QLabel("Photographic EXIF & Document Metadata Inspection")
        lbl_exif_title.setStyleSheet("font-weight: 700; color: #1e293b; font-size: 12px; border: none; background: transparent;")
        ep_header.addWidget(lbl_exif_title)
        ep_header.addStretch()

        btn_close_exif = QPushButton("✕")
        btn_close_exif.setFixedSize(22, 22)
        btn_close_exif.clicked.connect(lambda: (self.btn_toggle_exif.setChecked(False), self.exif_panel.setVisible(False)))
        ep_header.addWidget(btn_close_exif)
        ep_layout.addLayout(ep_header)

        self.table_exif = QTableWidget(0, 3)
        self.table_exif.setHorizontalHeaderLabels(["Property / EXIF Tag", "Left Document", "Right Document"])
        self.table_exif.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_exif.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_exif.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table_exif.setAlternatingRowColors(True)
        ep_layout.addWidget(self.table_exif)

        self.main_splitter.addWidget(self.exif_panel)
        self.exif_panel.setVisible(False)
        self.main_splitter.setSizes([500, 200])

        layout.addWidget(self.main_splitter, 1)

    def _sync_text_left(self, val: int):
        if not self._is_syncing_text_scroll:
            self._is_syncing_text_scroll = True
            self.txt_right.set_sync_scroll_value(val)
            self._is_syncing_text_scroll = False

    def _sync_text_right(self, val: int):
        if not self._is_syncing_text_scroll:
            self._is_syncing_text_scroll = True
            self.txt_left.set_sync_scroll_value(val)
            self._is_syncing_text_scroll = False

    def _on_canvas_files_dropped(self, paths: list):
        if len(paths) >= 2:
            self.set_images(paths[0], paths[1])
        elif len(paths) == 1:
            if not self.left_path:
                self.left_path = paths[0]
                self.lbl_left.setText(f"Left: {os.path.basename(paths[0])}")
            else:
                self.right_path = paths[0]
                self.lbl_right.setText(f"Right: {os.path.basename(paths[0])}")
            if self.left_path and self.right_path:
                self.current_page = 0
                self._recompute_diff()

    def _swap_media(self):
        if not self.left_path and not self.right_path:
            return
        self.left_path, self.right_path = self.right_path, self.left_path
        self.lbl_left.setText(f"Left: {os.path.basename(self.left_path)}" if self.left_path else "Left: (None)")
        self.lbl_right.setText(f"Right: {os.path.basename(self.right_path)}" if self.right_path else "Right: (None)")
        self._recompute_diff()

    def _zoom_to_fit(self):
        bw, bh = self.canvas._base_size()
        if bw <= 0 or bh <= 0:
            return
        vp = self.scroll_area.viewport().size()
        zx = max(0.1, (vp.width() - 16) / bw)
        zy = max(0.1, (vp.height() - 16) / bh)
        self.canvas.set_zoom(min(zx, zy, 2.0))

    def _browse_left(self):
        file, _ = QFileDialog.getOpenFileName(
            self, "Open Left Media or Document", "",
            "Visual & Document Files (*.png *.jpg *.jpeg *.bmp *.webp *.ico *.pdf *.svg);;All Files (*.*)"
        )
        if file:
            self.left_path = file
            self.lbl_left.setText(f"Left: {os.path.basename(file)}")
            self.current_page = 0
            self._recompute_diff()

    def _browse_right(self):
        file, _ = QFileDialog.getOpenFileName(
            self, "Open Right Media or Document", "",
            "Visual & Document Files (*.png *.jpg *.jpeg *.bmp *.webp *.ico *.pdf *.svg);;All Files (*.*)"
        )
        if file:
            self.right_path = file
            self.lbl_right.setText(f"Right: {os.path.basename(file)}")
            self.current_page = 0
            self._recompute_diff()

    def set_images(self, left_path: str, right_path: str):
        self.left_path = left_path
        self.right_path = right_path
        self.lbl_left.setText(f"Left: {os.path.basename(left_path)}")
        self.lbl_right.setText(f"Right: {os.path.basename(right_path)}")
        self.current_page = 0
        self._recompute_diff()

    def _prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self._recompute_diff()

    def _next_page(self):
        if self.current_page < self.max_pages - 1:
            self.current_page += 1
            self._recompute_diff()

    def _update_page_controls(self):
        has_pages = self.max_pages > 1
        self.page_container.setVisible(has_pages)
        if has_pages:
            self.lbl_page.setText(f"Page {self.current_page + 1}/{self.max_pages}")
            self.btn_prev_page.setEnabled(self.current_page > 0)
            self.btn_next_page.setEnabled(self.current_page < self.max_pages - 1)

    def _toggle_text_view(self):
        is_text = self.btn_toggle_text.isChecked()
        self.viewport_stack.setCurrentIndex(1 if is_text else 0)
        if is_text:
            self._populate_text_views()

    def _toggle_exif_view(self):
        is_exif = self.btn_toggle_exif.isChecked()
        self.exif_panel.setVisible(is_exif)
        if is_exif:
            self._populate_exif_table()

    def _populate_text_views(self):
        if not self.diff_result:
            return
        t1 = self.diff_result.text1 or "(No extracted text for this page/file)"
        t2 = self.diff_result.text2 or "(No extracted text for this page/file)"
        aligned = DiffEngine.build_aligned_diff(t1, t2)
        self.txt_left.set_aligned_lines(aligned.left_display_lines, aligned.left_spacers, aligned.left_line_numbers)
        self.txt_right.set_aligned_lines(aligned.right_display_lines, aligned.right_spacers, aligned.right_line_numbers)

        l_dec, r_dec = {}, {}
        for c in aligned.chunks:
            if c.tag == "delete":
                for i in range(c.left_start, c.left_end):
                    l_dec[i] = "#cf222e"
            elif c.tag == "insert":
                for j in range(c.right_start, c.right_end):
                    r_dec[j] = "#1a7f37"
            elif c.tag == "replace":
                for i in range(c.left_start, c.left_end):
                    if i not in aligned.left_spacers:
                        l_dec[i] = "#0969da"
                    if i not in aligned.right_spacers:
                        r_dec[i] = "#0969da"
        self.txt_left.apply_diff_decorations(l_dec)
        self.txt_right.apply_diff_decorations(r_dec)

    def _populate_exif_table(self):
        if not self.diff_result:
            return
        e1 = self.diff_result.exif1
        e2 = self.diff_result.exif2
        all_tags = sorted(list(set(list(e1.keys()) + list(e2.keys()))))

        self.table_exif.clearContents()
        self.table_exif.setRowCount(len(all_tags))
        c_diff = QBrush(QColor("#fff8c5"))

        for r_idx, tag in enumerate(all_tags):
            v1 = e1.get(tag, "—")
            v2 = e2.get(tag, "—")
            is_diff = (v1 != v2)

            item_tag = QTableWidgetItem(tag)
            item_v1 = QTableWidgetItem(str(v1))
            item_v2 = QTableWidgetItem(str(v2))
            for it in (item_tag, item_v1, item_v2):
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                if is_diff:
                    it.setBackground(c_diff)

            self.table_exif.setItem(r_idx, 0, item_tag)
            self.table_exif.setItem(r_idx, 1, item_v1)
            self.table_exif.setItem(r_idx, 2, item_v2)

    def _recompute_diff(self):
        if not self.left_path or not self.right_path:
            return

        tol = self.slider_tol.value()
        self.diff_result = ImageDiffEngine.compare_images(
            self.left_path, self.right_path, tolerance=tol, page_num=self.current_page
        )
        if not self.diff_result:
            self.lbl_metrics.setText("Failed to compare documents/images")
            return

        self.max_pages = max(self.diff_result.total_pages_1, self.diff_result.total_pages_2, 1)
        self._update_page_controls()

        pct = self.diff_result.diff_percentage
        pixels = self.diff_result.diff_pixel_count
        dim = f"{self.diff_result.img1.width}x{self.diff_result.img1.height}"
        page_str = f"Page {self.current_page + 1}/{self.max_pages} | " if self.max_pages > 1 else ""
        self.lbl_metrics.setText(f"{page_str}Diff: {pct:.2f}% ({pixels:,} px) | {dim}")

        self.canvas.set_layers(
            pil_to_qpixmap(self.diff_result.img1),
            pil_to_qpixmap(self.diff_result.img2),
            pil_to_qpixmap(self.diff_result.heatmap_img)
        )
        self._render_current_view()
        if self.btn_toggle_text.isChecked():
            self._populate_text_views()
        if self.btn_toggle_exif.isChecked():
            self._populate_exif_table()

    def _on_mode_changed(self, idx: int):
        if idx == 3:
            self.blink_timer.start()
            self.lbl_slider.setVisible(False)
            self.slider.setVisible(False)
        else:
            self.blink_timer.stop()
            if idx == 0:
                self.lbl_slider.setText(" Split:")
                self.lbl_slider.setVisible(True)
                self.slider.setVisible(True)
            elif idx == 1:
                self.lbl_slider.setText(" Alpha:")
                self.lbl_slider.setVisible(True)
                self.slider.setVisible(True)
            else:
                self.lbl_slider.setVisible(False)
                self.slider.setVisible(False)
        self._render_current_view()

    def _on_slider_changed(self, val: int):
        ratio = val / 100.0
        mode = self.combo_mode.currentIndex()
        if mode == 0:
            self.curtain_ratio = ratio
        elif mode == 1:
            self.onion_alpha = ratio
        self._render_current_view()

    def _on_curtain_dragged(self, ratio: float):
        if self.combo_mode.currentIndex() == 0:
            self.curtain_ratio = ratio
            self.slider.blockSignals(True)
            self.slider.setValue(int(ratio * 100))
            self.slider.blockSignals(False)
            self._render_current_view()

    def _on_blink_toggle(self):
        self.blink_state = not self.blink_state
        self._render_current_view()

    def _render_current_view(self):
        if not self.diff_result:
            return
        self.canvas.set_render_params(
            self.combo_mode.currentIndex(),
            self.curtain_ratio,
            self.onion_alpha,
            self.blink_state
        )
