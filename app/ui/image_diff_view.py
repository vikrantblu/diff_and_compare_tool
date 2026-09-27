"""
Visual Media & Image Diffing Studio
Features:
- Swipe curtain / split slider with mouse drag tracking.
- Onion-skin transparency overlay with dynamic alpha slider.
- Tolerance-based pixel difference heatmap.
- Flicker / blink comparison mode.
- Side-by-side synchronized view.
"""

import os
from typing import Optional, Dict, Any
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QComboBox, QSlider, QScrollArea, QFrame,
    QSplitter, QStackedWidget, QPlainTextEdit, QTableWidget,
    QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt, QTimer, Signal, QPoint
from PySide6.QtGui import QPixmap, QImage, QPainter, QColor, QPen, QBrush, QFont
from PIL import Image

from app.core.image_diff import ImageDiffEngine, ImageDiffResult
from app.ui.styles.icons import get_line_icon


def pil_to_qpixmap(pil_img: Image.Image) -> QPixmap:
    """Converts a PIL Image to a PySide6 QPixmap."""
    if pil_img.mode != "RGBA":
        pil_img = pil_img.convert("RGBA")
    data = pil_img.tobytes("raw", "RGBA")
    qimg = QImage(data, pil_img.width, pil_img.height, QImage.Format_RGBA8888)
    return QPixmap.fromImage(qimg)


class ImageCanvas(QWidget):
    """Interactive canvas that renders images, tracks curtain drag, and zoom."""
    curtainMoved = Signal(float)

    def __init__(self):
        super().__init__()
        self.pixmap: Optional[QPixmap] = None
        self.is_dragging_curtain = False
        self.zoom_factor = 1.0
        self.setMouseTracking(True)
        self.setMinimumSize(400, 300)

    def set_pixmap(self, pm: QPixmap):
        self.pixmap = pm
        if pm:
            self.setMinimumSize(int(pm.width() * self.zoom_factor), int(pm.height() * self.zoom_factor))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#f6f8fa"))

        if not self.pixmap or self.pixmap.isNull():
            painter.setPen(QColor("#8c959f"))
            painter.drawText(self.rect(), Qt.AlignCenter, "Select two visual files or documents to compare")
            return

        # Center image
        target_w = int(self.pixmap.width() * self.zoom_factor)
        target_h = int(self.pixmap.height() * self.zoom_factor)
        x = max(0, (self.width() - target_w) // 2)
        y = max(0, (self.height() - target_h) // 2)

        painter.drawPixmap(x, y, target_w, target_h, self.pixmap)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_dragging_curtain = True
            self._update_curtain_from_pos(event.pos())

    def mouseMoveEvent(self, event):
        if self.is_dragging_curtain:
            self._update_curtain_from_pos(event.pos())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_dragging_curtain = False

    def _update_curtain_from_pos(self, pos: QPoint):
        if not self.pixmap or self.pixmap.isNull():
            return
        target_w = self.pixmap.width() * self.zoom_factor
        x_offset = max(0, (self.width() - target_w) // 2)
        rel_x = pos.x() - x_offset
        ratio = max(0.0, min(1.0, rel_x / target_w))
        self.curtainMoved.emit(ratio)


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
                border-bottom: 1.5px solid #cbd5e1;
                padding: 4px;
            }
            #ImageFileBar QLabel {
                border: none;
                background: transparent;
            }
        """)
        fb_layout = QHBoxLayout(file_bar)
        fb_layout.setContentsMargins(10, 6, 10, 6)
        fb_layout.setSpacing(10)

        self.btn_left = QPushButton(" Browse Left Media...")
        self.btn_left.setIcon(get_line_icon("folder", "#0969da"))
        self.btn_left.setFixedHeight(30)
        self.btn_left.clicked.connect(self._browse_left)
        self.lbl_left = QLabel("Left: (None)")
        self.lbl_left.setStyleSheet("color: #475569; font-weight: 600; border: none; background: transparent;")

        self.btn_right = QPushButton(" Browse Right Media...")
        self.btn_right.setIcon(get_line_icon("folder", "#0969da"))
        self.btn_right.setFixedHeight(30)
        self.btn_right.clicked.connect(self._browse_right)
        self.lbl_right = QLabel("Right: (None)")
        self.lbl_right.setStyleSheet("color: #475569; font-weight: 600; border: none; background: transparent;")

        fb_layout.addWidget(self.btn_left)
        fb_layout.addWidget(self.lbl_left, 1)
        fb_layout.addWidget(self.btn_right)
        fb_layout.addWidget(self.lbl_right, 1)

        layout.addWidget(file_bar)

        # 2. Command Bar (Mode Selection, Sliders, PDF Navigation & Inspection Toggles)
        cmd_bar = QFrame()
        cmd_bar.setObjectName("ImageCmdBar")
        cmd_bar.setFixedHeight(46)
        cmd_bar.setStyleSheet("""
            #ImageCmdBar {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #f8fafc);
                border-bottom: 1.5px solid #cbd5e1;
                padding: 4px;
            }
            #ImageCmdBar QLabel {
                border: none;
                background: transparent;
                color: #334155;
                font-weight: 500;
            }
        """)
        cb_layout = QHBoxLayout(cmd_bar)
        cb_layout.setContentsMargins(10, 6, 10, 6)
        cb_layout.setSpacing(8)

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

        self.lbl_slider = QLabel(" Curtain Split:")
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(50)
        self.slider.setFixedWidth(120)
        self.slider.valueChanged.connect(self._on_slider_changed)
        cb_layout.addWidget(self.lbl_slider)
        cb_layout.addWidget(self.slider)

        cb_layout.addWidget(QLabel(" Tol:"))
        self.slider_tol = QSlider(Qt.Horizontal)
        self.slider_tol.setRange(0, 50)
        self.slider_tol.setValue(8)
        self.slider_tol.setFixedWidth(70)
        self.slider_tol.valueChanged.connect(self._recompute_diff)
        cb_layout.addWidget(self.slider_tol)

        # Multi-page PDF Controls (hidden by default unless multi-page document loaded)
        self.page_container = QWidget()
        self.page_container.setStyleSheet("background: transparent; border: none;")
        pc_layout = QHBoxLayout(self.page_container)
        pc_layout.setContentsMargins(0, 0, 0, 0)
        pc_layout.setSpacing(4)

        self.btn_prev_page = QPushButton()
        self.btn_prev_page.setIcon(get_line_icon("arrow-left", "#1e293b", size=14))
        self.btn_prev_page.setFixedSize(28, 28)
        self.btn_prev_page.setStyleSheet("padding: 2px;")
        self.btn_prev_page.setToolTip("Previous Page")
        self.btn_prev_page.clicked.connect(self._prev_page)
        pc_layout.addWidget(self.btn_prev_page)

        self.lbl_page = QLabel("Page 1/1")
        self.lbl_page.setStyleSheet("font-weight: 600; color: #334155; padding: 0 4px;")
        pc_layout.addWidget(self.lbl_page)

        self.btn_next_page = QPushButton()
        self.btn_next_page.setIcon(get_line_icon("arrow-right", "#1e293b", size=14))
        self.btn_next_page.setFixedSize(28, 28)
        self.btn_next_page.setStyleSheet("padding: 2px;")
        self.btn_next_page.setToolTip("Next Page")
        self.btn_next_page.clicked.connect(self._next_page)
        pc_layout.addWidget(self.btn_next_page)

        self.page_container.setVisible(False)
        cb_layout.addWidget(self.page_container)

        # Inspection View Toggles (using clean vector icons instead of emojis)
        self.btn_toggle_text = QPushButton(" Text Diff")
        self.btn_toggle_text.setIcon(get_line_icon("file-text", "#0969da"))
        self.btn_toggle_text.setCheckable(True)
        self.btn_toggle_text.setFixedHeight(30)
        self.btn_toggle_text.setToolTip("Toggle extracted document text view")
        self.btn_toggle_text.clicked.connect(self._toggle_text_view)
        cb_layout.addWidget(self.btn_toggle_text)

        self.btn_toggle_exif = QPushButton(" EXIF / Metadata")
        self.btn_toggle_exif.setIcon(get_line_icon("sliders", "#475569"))
        self.btn_toggle_exif.setCheckable(True)
        self.btn_toggle_exif.setFixedHeight(30)
        self.btn_toggle_exif.setToolTip("Toggle EXIF photographic and document metadata inspection panel")
        self.btn_toggle_exif.clicked.connect(self._toggle_exif_view)
        cb_layout.addWidget(self.btn_toggle_exif)

        self.lbl_metrics = QLabel("  ● Ready")
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

        # 3. Main Splitter (Top Viewport Stack + Bottom EXIF Inspection Table)
        self.main_splitter = QSplitter(Qt.Vertical)

        # Viewport Stack: Index 0 = Image Canvas, Index 1 = Extracted Text Diff
        self.viewport_stack = QStackedWidget()

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.canvas = ImageCanvas()
        self.canvas.curtainMoved.connect(self._on_curtain_dragged)
        self.scroll_area.setWidget(self.canvas)
        self.viewport_stack.addWidget(self.scroll_area)

        # Text diff view
        self.text_panel = QWidget()
        tp_layout = QHBoxLayout(self.text_panel)
        tp_layout.setContentsMargins(4, 4, 4, 4)
        tp_layout.setSpacing(6)

        left_text_box = QVBoxLayout()
        left_text_box.addWidget(QLabel("Left Document Extracted Text:"))
        self.txt_left = QPlainTextEdit()
        self.txt_left.setReadOnly(True)
        self.txt_left.setStyleSheet("font-family: Consolas, monospace; font-size: 12px; background: #ffffff;")
        left_text_box.addWidget(self.txt_left)
        tp_layout.addLayout(left_text_box, 1)

        right_text_box = QVBoxLayout()
        right_text_box.addWidget(QLabel("Right Document Extracted Text:"))
        self.txt_right = QPlainTextEdit()
        self.txt_right.setReadOnly(True)
        self.txt_right.setStyleSheet("font-family: Consolas, monospace; font-size: 12px; background: #ffffff;")
        right_text_box.addWidget(self.txt_right)
        tp_layout.addLayout(right_text_box, 1)

        self.viewport_stack.addWidget(self.text_panel)

        self.main_splitter.addWidget(self.viewport_stack)

        # Bottom EXIF / Metadata Inspection Panel
        self.exif_panel = QFrame()
        self.exif_panel.setStyleSheet("background: #ffffff; border-top: 1px solid #cbd5e1;")
        ep_layout = QVBoxLayout(self.exif_panel)
        ep_layout.setContentsMargins(6, 6, 6, 6)
        ep_layout.setSpacing(4)

        ep_header = QHBoxLayout()
        lbl_exif_title = QLabel("📷 Photographic EXIF & Document Metadata Inspection")
        lbl_exif_title.setStyleSheet("font-weight: 700; color: #1e293b; font-size: 12px;")
        ep_header.addWidget(lbl_exif_title)
        ep_header.addStretch()

        btn_close_exif = QPushButton("✕")
        btn_close_exif.setFixedSize(22, 22)
        btn_close_exif.clicked.connect(lambda: self.btn_toggle_exif.setChecked(False) or self.exif_panel.setVisible(False))
        ep_header.addWidget(btn_close_exif)
        ep_layout.addLayout(ep_header)

        self.table_exif = QTableWidget(0, 3)
        self.table_exif.setHorizontalHeaderLabels(["Property / EXIF Tag", "Left Document", "Right Document"])
        self.table_exif.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_exif.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_exif.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table_exif.setAlternatingRowColors(True)
        self.table_exif.setStyleSheet("""
            QTableWidget {
                border: 1px solid #e2e8f0;
                gridline-color: #f1f5f9;
                font-family: 'Segoe UI', sans-serif;
                font-size: 11px;
            }
            QHeaderView::section {
                background: #f8fafc;
                font-weight: 600;
                color: #334155;
                padding: 4px;
                border: 1px solid #cbd5e1;
            }
        """)
        ep_layout.addWidget(self.table_exif)

        self.main_splitter.addWidget(self.exif_panel)
        self.exif_panel.setVisible(False)
        self.main_splitter.setSizes([500, 200])

        layout.addWidget(self.main_splitter, 1)

    def _browse_left(self):
        file, _ = QFileDialog.getOpenFileName(
            self, "Open Left Media or Document", "",
            "Visual & Document Files (*.png *.jpg *.jpeg *.bmp *.webp *.ico *.pdf *.svg);;Images (*.png *.jpg *.jpeg *.bmp *.webp *.ico);;PDF Documents (*.pdf);;SVG Files (*.svg);;All Files (*.*)"
        )
        if file:
            self.left_path = file
            self.lbl_left.setText(f"Left: {os.path.basename(file)}")
            self.current_page = 0
            self._recompute_diff()

    def _browse_right(self):
        file, _ = QFileDialog.getOpenFileName(
            self, "Open Right Media or Document", "",
            "Visual & Document Files (*.png *.jpg *.jpeg *.bmp *.webp *.ico *.pdf *.svg);;Images (*.png *.jpg *.jpeg *.bmp *.webp *.ico);;PDF Documents (*.pdf);;SVG Files (*.svg);;All Files (*.*)"
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
        self.txt_left.setPlainText(self.diff_result.text1 or "(No extracted text for this page/file)")
        self.txt_right.setPlainText(self.diff_result.text2 or "(No extracted text for this page/file)")

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

            if is_diff:
                item_tag.setBackground(c_diff)
                item_v1.setBackground(c_diff)
                item_v2.setBackground(c_diff)

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
            self.lbl_metrics.setText("⚠️ Failed to compare documents/images")
            return

        self.max_pages = max(self.diff_result.total_pages_1, self.diff_result.total_pages_2, 1)
        self._update_page_controls()

        pct = self.diff_result.diff_percentage
        pixels = self.diff_result.diff_pixel_count
        dim = f"{self.diff_result.img1.width}x{self.diff_result.img1.height}"
        page_str = f"Page {self.current_page + 1}/{self.max_pages} | " if self.max_pages > 1 else ""
        self.lbl_metrics.setText(f"{page_str}Diff: {pct:.2f}% ({pixels:,} px) | {dim}")

        self._render_current_view()
        if self.btn_toggle_text.isChecked():
            self._populate_text_views()
        if self.btn_toggle_exif.isChecked():
            self._populate_exif_table()

    def _on_mode_changed(self, idx: int):
        if idx == 3:  # Blink
            self.blink_timer.start()
            self.lbl_slider.setVisible(False)
            self.slider.setVisible(False)
        else:
            self.blink_timer.stop()
            self.lbl_slider.setVisible(True)
            self.slider.setVisible(True)
            if idx == 0:
                self.lbl_slider.setText(" Curtain Split:")
            elif idx == 1:
                self.lbl_slider.setText(" Onion-Skin Alpha:")
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

        mode = self.combo_mode.currentIndex()

        if mode == 0:  # Swipe Curtain
            composite = ImageDiffEngine.render_swipe_curtain(
                self.diff_result.img1, self.diff_result.img2, split_ratio=self.curtain_ratio
            )
            self.canvas.set_pixmap(pil_to_qpixmap(composite))

        elif mode == 1:  # Onion-Skin
            composite = ImageDiffEngine.render_onion_skin(
                self.diff_result.img1, self.diff_result.img2, alpha=self.onion_alpha
            )
            self.canvas.set_pixmap(pil_to_qpixmap(composite))

        elif mode == 2:  # Heatmap
            self.canvas.set_pixmap(pil_to_qpixmap(self.diff_result.heatmap_img))

        elif mode == 3:  # Blink
            active_img = self.diff_result.img1 if self.blink_state else self.diff_result.img2
            self.canvas.set_pixmap(pil_to_qpixmap(active_img))

        elif mode == 4:  # Side-by-Side
            w, h = self.diff_result.img1.size
            sbs = Image.new("RGBA", (w * 2 + 4, h), (200, 200, 200, 255))
            sbs.paste(self.diff_result.img1, (0, 0))
            sbs.paste(self.diff_result.img2, (w + 4, 0))
            self.canvas.set_pixmap(pil_to_qpixmap(sbs))
