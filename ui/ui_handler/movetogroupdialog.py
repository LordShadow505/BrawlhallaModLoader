import os
from typing import List, Dict, Tuple
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QListWidget, QListWidgetItem, QFrame
from PySide6.QtGui import QColor, QPixmap, QPainter, QPainterPath, QFont
from PySide6.QtCore import Qt, QSize, QRectF

class MoveToGroupDialog(QDialog):
    def __init__(self, groups: List[Tuple[str, str, str]], current_group_id: str = "", parent=None):
        """
        groups: List of tuples (group_id, group_name, group_color)
        """
        super().__init__(parent)
        self.selected_group_id = None
        self.selected_group_name = ""
        self.setWindowTitle("Move Mods to Group")
        self.setMinimumWidth(320)

        self.setStyleSheet("""
            QDialog {
                background-color: #141518;
                color: #FFFFFF;
            }
            QLabel {
                color: #FFFFFF;
                font-size: 12px;
            }
            QListWidget {
                background-color: #191A1E;
                color: #FFFFFF;
                border: 1px solid #2B2C30;
                border-radius: 6px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 6px;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: #24262C;
            }
            QListWidget::item:selected {
                background-color: #24638C;
            }
            QPushButton {
                background-color: #1F2024;
                color: #FFFFFF;
                border: 1px solid #33343A;
                border-radius: 4px;
                padding: 6px 16px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2A2C32;
            }
            QPushButton#moveBtn {
                background-color: #24638C;
                border: none;
            }
            QPushButton#moveBtn:hover {
                background-color: #347BA9;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header_label = QLabel("Select destination group:")
        header_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        layout.addWidget(header_label)

        self.list_widget = QListWidget()
        
        # Root option
        root_item = QListWidgetItem("Root (No Group)")
        root_item.setData(Qt.UserRole, "")
        self.list_widget.addItem(root_item)

        for gid, gname, gcolor in groups:
            item = QListWidgetItem(gname)
            item.setData(Qt.UserRole, gid)
            
            # Icon color badge
            pixmap = QPixmap(14, 14)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            path = QPainterPath()
            path.addRoundedRect(QRectF(0, 0, 14, 14), 3, 3)
            painter.fillPath(path, QColor(gcolor or "#24638C"))
            painter.end()
            item.setIcon(pixmap)

            self.list_widget.addItem(item)
            if gid == current_group_id:
                self.list_widget.setCurrentItem(item)

        if not self.list_widget.currentItem():
            self.list_widget.setCurrentRow(0)

        layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        move_btn = QPushButton("Move")
        move_btn.setObjectName("moveBtn")
        move_btn.clicked.connect(self.on_move)
        btn_layout.addWidget(move_btn)

        layout.addLayout(btn_layout)

    def on_move(self):
        item = self.list_widget.currentItem()
        if item:
            self.selected_group_id = item.data(Qt.UserRole)
            self.selected_group_name = item.text()
            self.accept()
        else:
            self.reject()
