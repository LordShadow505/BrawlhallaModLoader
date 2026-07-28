import os
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QWidget, QFileDialog
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QFont, QIcon

from ..utils.config import LoaderConfig


class SettingsFrame(QFrame):
    def __init__(self, saveCallback=None, openCacheMethod=None, clearCacheMethod=None,
                 bhPath="", modsPath="", cacheSize=""):
        super().__init__()
        self.config = LoaderConfig()
        self.saveCallback = saveCallback
        self.openCacheMethod = openCacheMethod
        self.clearCacheMethod = clearCacheMethod
        
        # Initial resolved paths
        self.bhPath = bhPath
        self.modsPath = modsPath
        self.cacheSize = cacheSize
        self.hasUnsavedChanges = False
        
        self.setObjectName("SettingsFrame")
        self.setStyleSheet("#SettingsFrame { background-color: #151518; }")

        self.scrollLayout = QVBoxLayout(self)
        self.scrollLayout.setContentsMargins(0, 0, 0, 0)
        
        self.scrollArea = QScrollArea()
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setStyleSheet("""
            QScrollArea { 
                border: none; 
                background-color: transparent; 
            }
            QScrollBar:vertical {         
                border: none;
                background: #2B2C32;
                width: 7px;
                margin: 0 0 0 0;
                border-radius: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #616161;
                min-height: 30px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #A1A1A1;
            }
            QScrollBar::handle:vertical:pressed {
                background-color: #717171;
            }
            QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
            QScrollBar::add-line:vertical {
                border: none;
                background: none;
            }
            QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {
                background: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        
        self.scrollContent = QWidget()
        self.scrollContent.setStyleSheet("background-color: transparent;")
        self.mainLayout = QVBoxLayout(self.scrollContent)
        self.mainLayout.setContentsMargins(40, 20, 40, 40)
        self.mainLayout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.mainLayout.setSpacing(24)
        
        self.scrollArea.setWidget(self.scrollContent)
        self.scrollLayout.addWidget(self.scrollArea)

        # ── Card 1: Paths ─────────────────────────────────────────
        self.card1 = self._createCard("Game Path Settings", "#42A5F5")
        self.brawlhallaPathEdit = self._addPathRow(self.card1, "Brawlhalla Path:", self.bhPath)
        self.modsPathEdit       = self._addPathRow(self.card1, "Mods Path:",       self.modsPath)
        
        pathWarning = QLabel("Warning: Only change paths if you know what you're doing!")
        pathWarning.setStyleSheet("color: #EF5350; font-size: 8pt; font-style: italic; margin-top: 4px;")
        self.card1.layout().addWidget(pathWarning)
        
        self.mainLayout.addWidget(self.card1)

        # ── Card 2: Cache ─────────────────────────────────────────
        self.card2 = self._createCard("Application Cache", "#EF5350")
        
        cacheInfoLayout = QHBoxLayout()
        self.cacheSizeLabel = QLabel(f"Total Cache Size: {self.cacheSize}")
        self.cacheSizeLabel.setStyleSheet("color: #bbbbbb; font-size: 9pt; margin-bottom: 8px;")
        cacheInfoLayout.addWidget(self.cacheSizeLabel)
        self.card2.layout().addLayout(cacheInfoLayout)
        
        cacheButtonsLayout = QHBoxLayout()
        cacheButtonsLayout.setSpacing(12)
        
        self.openCacheBtn = QPushButton("Open Cache Folder")
        self.openCacheBtn.setFixedSize(QSize(180, 36))
        self.openCacheBtn.setCursor(Qt.PointingHandCursor)
        self.openCacheBtn.setStyleSheet(self._getButtonStyle("#42A5F5"))
        self.openCacheBtn.clicked.connect(self.openCacheMethod)
        
        self.clearCacheBtn = QPushButton(" Clear Cache")
        self.clearCacheBtn.setFixedSize(QSize(180, 36))
        self.clearCacheBtn.setCursor(Qt.PointingHandCursor)
        self.clearCacheBtn.setIcon(QIcon(":/icons/resources/icons/UninstallAllMods.png"))
        self.clearCacheBtn.setIconSize(QSize(16, 16))
        self.clearCacheBtn.setStyleSheet(self._getButtonStyle("#EF5350"))
        self.clearCacheBtn.clicked.connect(self.clearCacheMethod)
        
        cacheButtonsLayout.addWidget(self.openCacheBtn)
        cacheButtonsLayout.addWidget(self.clearCacheBtn)
        cacheButtonsLayout.addStretch()
        
        self.card2.layout().addLayout(cacheButtonsLayout)
        self.mainLayout.addWidget(self.card2)

        # ── Card 3: GameBanana ───────────────────────────────────
        self.card3 = self._createCard("GameBanana Integration", "#F59E0B")
        
        # NSFW Filter Switch
        nsfw_row = QHBoxLayout()
        nsfw_row.setSpacing(12)
        nsfw_lbl = QLabel("NSFW Content Filter:")
        nsfw_lbl.setFixedWidth(160)
        nsfw_lbl.setStyleSheet("color: #aaaaaa; font-size: 9pt;")
        nsfw_row.addWidget(nsfw_lbl)
        
        icons_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ui_sources", "resources", "icons")).replace("\\", "/")
        cb_unchecked = f"{icons_dir}/CheckBox.svg"
        cb_checked = f"{icons_dir}/CheckBox_Mark.svg"

        from PySide6.QtWidgets import QCheckBox
        self.nsfwCheckBox = QCheckBox("Enable NSFW Filter (Blur Sensitive Media)")
        self.nsfwCheckBox.setChecked(self.config.nsfwFilter)
        self.nsfwCheckBox.setStyleSheet(f"""
            QCheckBox {{ color: #eeeeee; font-size: 9pt; font-weight: bold; spacing: 6px; }}
            QCheckBox::indicator {{ width: 18px; height: 18px; background: transparent; border: none; }}
            QCheckBox::indicator:unchecked {{ image: url("{cb_unchecked}"); }}
            QCheckBox::indicator:checked {{ image: url("{cb_checked}"); }}
        """)
        self.nsfwCheckBox.stateChanged.connect(lambda: setattr(self, 'hasUnsavedChanges', True))

        nsfw_row.addWidget(self.nsfwCheckBox)
        nsfw_row.addStretch()
        self.card3.layout().addLayout(nsfw_row)
        
        # Clear GameBanana Cache Button
        gb_cache_row = QHBoxLayout()
        gb_cache_row.setSpacing(12)
        gb_lbl = QLabel("GameBanana Image Cache:")
        gb_lbl.setFixedWidth(160)
        gb_lbl.setStyleSheet("color: #aaaaaa; font-size: 9pt;")
        gb_cache_row.addWidget(gb_lbl)
        
        self.clearGbCacheBtn = QPushButton("Clear GameBanana Cache")
        self.clearGbCacheBtn.setFixedSize(QSize(200, 34))
        self.clearGbCacheBtn.setCursor(Qt.PointingHandCursor)
        self.clearGbCacheBtn.setStyleSheet(self._getButtonStyle("#F59E0B"))
        self.clearGbCacheBtn.clicked.connect(self._clear_gb_cache)
        gb_cache_row.addWidget(self.clearGbCacheBtn)
        
        self.gbCacheStatusLbl = QLabel("")
        self.gbCacheStatusLbl.setStyleSheet("color: #2ecc71; font-size: 9pt; font-weight: bold;")
        gb_cache_row.addWidget(self.gbCacheStatusLbl)
        gb_cache_row.addStretch()
        
        self.card3.layout().addLayout(gb_cache_row)
        self.mainLayout.addWidget(self.card3)

        # ── Save button ───────────────────────────────────────────
        self.saveButton = QPushButton("Save Settings")
        self.saveButton.setFixedSize(QSize(180, 40))
        self.saveButton.setCursor(Qt.PointingHandCursor)
        self._setSaveButtonStyle(saved=False)
        self.saveButton.clicked.connect(self.saveSettings)
        self.mainLayout.addWidget(self.saveButton, alignment=Qt.AlignCenter)

    def _clear_gb_cache(self):
        try:
            cache_dir = os.path.join(os.environ.get("APPDATA", ""), "BModLoader", "gb_cache")
            count = 0
            if os.path.exists(cache_dir):
                import shutil
                count = len(os.listdir(cache_dir))
                shutil.rmtree(cache_dir, ignore_errors=True)
                os.makedirs(cache_dir, exist_ok=True)
            self.gbCacheStatusLbl.setText("Cache Cleared!")
            print(f"[Settings] Cleared {count} items from GameBanana cache.")
            QTimer.singleShot(2500, lambda: self.gbCacheStatusLbl.setText(""))
        except Exception as e:
            print(f"[Settings ERROR] Failed to clear GB cache: {e}")

    def _createCard(self, title: str, color: str) -> QFrame:
        card = QFrame()
        card.setFixedWidth(520)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #303136;
                border-left: 4px solid {color};
                border-radius: 0px;
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(16)

        titleLabel = QLabel(title)
        titleFont = QFont()
        titleFont.setPointSize(12)
        titleFont.setBold(True)
        titleLabel.setFont(titleFont)
        titleLabel.setStyleSheet(f"color: {color}; margin-bottom: 4px;")
        layout.addWidget(titleLabel)
        
        return card

    def _addPathRow(self, card: QFrame, labelText: str, initialValue: str) -> QLineEdit:
        row = QHBoxLayout()
        row.setSpacing(12)

        label = QLabel(labelText)
        label.setFixedWidth(160)
        label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        label.setStyleSheet("color: #aaaaaa; font-size: 9pt;")
        row.addWidget(label)

        edit = QLineEdit()
        edit.setText(initialValue)
        edit.setCursorPosition(0)
        edit.setReadOnly(True)
        edit.setMinimumHeight(32)
        edit.setStyleSheet("""
            QLineEdit {
                background-color: #1D1E20;
                color: #bbbbbb;
                border: 1px solid #404146;
                border-radius: 4px;
                padding-left: 10px;
                font-size: 9pt;
            }
        """)
        row.addWidget(edit)

        browseBtn = QPushButton()
        browseBtn.setFixedSize(QSize(32, 32))
        browseBtn.setCursor(Qt.PointingHandCursor)
        browseBtn.setIcon(QIcon(":/icons/resources/icons/OpenModsFolder.png"))
        browseBtn.setIconSize(QSize(18, 18))
        browseBtn.setStyleSheet("""
            QPushButton {
                background-color: #404146;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #505156; }
        """)
        
        def browse():
            dir_path = QFileDialog.getExistingDirectory(self, "Select Folder", edit.text() if os.path.exists(edit.text()) else "")
            if dir_path:
                edit.setText(dir_path)
                edit.setCursorPosition(0)
                self.hasUnsavedChanges = True
        
        browseBtn.clicked.connect(browse)
        row.addWidget(browseBtn)

        card.layout().addLayout(row)
        return edit

    def _addRow(self, card: QFrame, labelText: str, initialValue: str) -> QLineEdit:
        row = QHBoxLayout()
        row.setSpacing(12)

        label = QLabel(labelText)
        label.setFixedWidth(160)
        label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        label.setStyleSheet("color: #aaaaaa; font-size: 9pt;")
        row.addWidget(label)

        edit = QLineEdit()
        edit.setText(initialValue)
        edit.setMinimumHeight(32)
        edit.setStyleSheet("""
            QLineEdit {
                background-color: #151518;
                color: #eeeeee;
                border: 1px solid #404146;
                border-radius: 4px;
                padding-left: 10px;
                font-size: 9pt;
            }
            QLineEdit:focus {
                border: 1px solid #42A5F5;
            }
        """)
        edit.textChanged.connect(lambda: setattr(self, 'hasUnsavedChanges', True))
        row.addWidget(edit)

        card.layout().addLayout(row)
        return edit

    def _getButtonStyle(self, color: str):
        return f"""
            QPushButton {{
                background-color: {color};
                color: #eeeeee;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 9pt;
            }}
            QPushButton:hover {{ opacity: 0.8; }}
        """

    def _setSaveButtonStyle(self, saved: bool):
        if saved:
            bg, hover, pressed = "#2ecc71", "#27ae60", "#1e8449"
        else:
            bg, hover, pressed = "#42A5F5", "#64B5F6", "#1E88E5"
        self.saveButton.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: #eeeeee;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 10pt;
            }}
            QPushButton:hover {{ background-color: {hover}; }}
            QPushButton:pressed {{ background-color: {pressed}; }}
        """)

    def saveSettings(self):
        bh_path = self.brawlhallaPathEdit.text().strip()
        if bh_path in ["Default (Steam)", ""]:
            self.config.brawlhallaPath = ""
        else:
            self.config.brawlhallaPath = bh_path

        m_path = self.modsPathEdit.text().strip()
        if m_path in ["Default", ""]:
            self.config.modsPath = ""
        else:
            self.config.modsPath = m_path

        self.config.nsfwFilter = self.nsfwCheckBox.isChecked()

        if self.saveCallback:
            self.saveCallback()

        self.hasUnsavedChanges = False
        self.saveButton.setText("Settings Saved!")
        self._setSaveButtonStyle(saved=True)
        QTimer.singleShot(2000, self._resetSaveButton)

    def _resetSaveButton(self):
        self.saveButton.setText("Save Settings")
        self._setSaveButtonStyle(saved=False)
