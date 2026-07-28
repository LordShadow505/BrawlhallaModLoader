from typing import List
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit, QWidget, QGridLayout, QFrame
from PySide6.QtGui import QFont, QColor, QPainter, QPainterPath
from PySide6.QtCore import Qt, Signal, QRectF

from ..utils.tags_helper import CATEGORY_PALETTE

class ColorBadgeWidget(QWidget):
    clicked = Signal(str)

    def __init__(self, color_hex: str, selected: bool = False, parent=None):
        super().__init__(parent)
        self.color_hex = color_hex
        self.selected = selected
        self.setFixedSize(24, 24)
        self.setCursor(Qt.PointingHandCursor)

    def setSelected(self, val: bool):
        self.selected = val
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        path = QPainterPath()
        path.addRoundedRect(QRectF(1, 1, 22, 22), 5, 5)
        p.fillPath(path, QColor(self.color_hex))

        if self.selected:
            p.setPen(QColor("#FFFFFF"))
            p.drawRoundedRect(QRectF(1, 1, 22, 22), 5, 5)
            p.drawRoundedRect(QRectF(2, 2, 20, 20), 4, 4)
        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.color_hex)
        super().mousePressEvent(event)


class ModGroupSettingsDialog(QDialog):
    def __init__(self, group_name: str, group_color: str, mod_count: int, icon: str = "Folder.png", is_create: bool = False, parent=None):
        super().__init__(parent)
        import os
        from PySide6.QtGui import QIcon, QPixmap
        from PySide6.QtCore import QSize

        self.new_name = group_name
        self.new_color = group_color
        self.selected_icon = icon or "Folder.png"
        self.new_icon = self.selected_icon
        self.mod_count = mod_count
        self.is_create = is_create
        self.delete_requested = False
        self.delete_action = None

        self.setWindowTitle("Create New Mod Group" if is_create else "Group Settings")
        self.setFixedWidth(360)
        self.setStyleSheet("""
            QDialog {
                background-color: #141518;
                color: #FFFFFF;
            }
            QLabel {
                color: #FFFFFF;
                font-size: 11px;
            }
            QLineEdit {
                background-color: #191A1E;
                color: #FFFFFF;
                border: 1px solid #2B2C30;
                border-radius: 4px;
                padding: 6px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #24638C;
            }
            QPushButton {
                background-color: #23242A;
                color: #FFFFFF;
                border: 1px solid #3A3C4A;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2D2E38;
            }
            QPushButton#saveBtn {
                background-color: #43C15F;
                border: none;
            }
            QPushButton#saveBtn:hover {
                background-color: #4BD469;
            }
            QPushButton#deleteBtn {
                background-color: #FF5050;
                border: none;
            }
            QPushButton#deleteBtn:hover {
                background-color: #FF6666;
            }

        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        title = QLabel("Create New Mod Group" if is_create else "Edit Group Settings")
        title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        layout.addWidget(title)

        layout.addWidget(QLabel("Group Name:"))
        self.name_edit = QLineEdit(group_name)
        self.name_edit.setPlaceholderText("Enter group name...")
        layout.addWidget(self.name_edit)

        layout.addWidget(QLabel("Group Color:"))
        
        # Color palette grid
        grid_frame = QFrame()
        grid_layout = QGridLayout(grid_frame)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(6)

        self.color_widgets = []
        palette = CATEGORY_PALETTE[:20]  # First 20 curated dark colors
        if group_color and group_color not in palette:
            palette.insert(0, group_color)

        for idx, col in enumerate(palette):
            r = idx // 10
            c = idx % 10
            w = ColorBadgeWidget(col, selected=(col.lower() == group_color.lower()))
            w.clicked.connect(self.select_color)
            grid_layout.addWidget(w, r, c)
            self.color_widgets.append(w)

        layout.addWidget(grid_frame)

        # Sección de iconos
        layout.addWidget(QLabel("Group Icon:"))

        # Cuadrícula de iconos
        icon_grid = QFrame()
        icon_layout = QGridLayout(icon_grid)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setSpacing(6)

        icons_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ui_sources", "resources", "group_icons"))
        icon_files = [f for f in os.listdir(icons_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.svg', '.bmp'))] if os.path.exists(icons_dir) else []
        self.icon_buttons = []

        for idx, fname in enumerate(icon_files):
            btn = QPushButton()
            btn.setFixedSize(40, 40)
            btn.setCursor(Qt.PointingHandCursor)
            icon_path = os.path.join(icons_dir, fname)
            pix = QPixmap(icon_path).scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            btn.setIcon(QIcon(pix))
            btn.setIconSize(QSize(32, 32))
            btn.setToolTip(fname)
            if fname == self.selected_icon:
                btn.setStyleSheet("border: 2px solid #24638C; background: #1A1B1F; border-radius: 4px;")
            else:
                btn.setStyleSheet("border: 1px solid transparent; background: transparent; border-radius: 4px;")
            btn.clicked.connect(lambda checked=False, f=fname: self.select_icon(f))
            row = idx // 6
            col = idx % 6
            icon_layout.addWidget(btn, row, col)
            self.icon_buttons.append(btn)

        layout.addWidget(icon_grid)

        # Delete Group Button (Only when editing existing group)
        if not is_create:
            delete_btn = QPushButton("Delete Group...")
            delete_btn.setObjectName("deleteBtn")
            delete_btn.clicked.connect(self.on_delete_click)
            layout.addWidget(delete_btn)

        layout.addSpacing(6)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Create" if is_create else "Save")
        save_btn.setObjectName("saveBtn")
        save_btn.clicked.connect(self.on_save)
        btn_layout.addWidget(save_btn)


        layout.addLayout(btn_layout)

    def select_color(self, color_hex: str):
        self.new_color = color_hex
        for w in self.color_widgets:
            w.setSelected(w.color_hex.lower() == color_hex.lower())

    def select_icon(self, fname: str):
        self.selected_icon = fname
        for btn in self.icon_buttons:
            if btn.toolTip() == fname:
                btn.setStyleSheet("border: 2px solid #24638C; background: #1A1B1F; border-radius: 4px;")
            else:
                btn.setStyleSheet("border: 1px solid transparent; background: transparent; border-radius: 4px;")

    def on_save(self):
        name = self.name_edit.text().strip()
        if name:
            self.new_name = name
        self.new_icon = self.selected_icon
        self.accept()

    def on_delete_click(self):
        from .modgroupdeletedialog import ModGroupDeleteDialog
        dlg = ModGroupDeleteDialog(self.new_name, self.mod_count, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self.delete_requested = True
            self.accept()


