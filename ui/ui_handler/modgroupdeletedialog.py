from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PySide6.QtGui import QFont

class ModGroupDeleteDialog(QDialog):
    def __init__(self, group_name: str, mod_count: int, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Delete Mod Group")
        self.setFixedWidth(380)
        self.setStyleSheet("""
            QDialog {
                background-color: #141518;
                color: #FFFFFF;
            }
            QLabel {
                color: #DDDDDD;
                font-size: 11px;
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
            QPushButton#deleteGroupBtn {
                background-color: #FF5050;
                border: none;
            }
            QPushButton#deleteGroupBtn:hover {
                background-color: #FF6666;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel(f"Delete group '{group_name}'?")
        title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        title.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(title)

        desc = QLabel(
            f"Deleting group '{group_name}' will remove this group and move all its mods ({mod_count} mod{'s' if mod_count != 1 else ''}) back to Root in the loader.\n\n"
            "Mod files on disk will remain intact."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        delete_btn = QPushButton("Delete Group")
        delete_btn.setObjectName("deleteGroupBtn")
        delete_btn.clicked.connect(self.accept)
        btn_layout.addWidget(delete_btn)

        layout.addLayout(btn_layout)

