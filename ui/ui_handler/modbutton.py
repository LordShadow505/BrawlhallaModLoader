import re

from PySide6.QtWidgets import QWidget, QScrollArea, QPushButton, QHBoxLayout
from PySide6.QtGui import QFontMetrics, Qt, QPixmap, QIcon, QCursor
from PySide6.QtCore import QEvent, QSize

from .modclass import ModClass

from ..ui_sources.ui_mod_button import Ui_ModButton


class ModButton(QWidget):
    buttons = []

    def __init__(self, modClass: ModClass, method, favoriteMethod):
        self.pressed = False
        self.modClass = modClass
        self.method = method
        self.favoriteMethod = favoriteMethod

        super().__init__()

        self.ui = Ui_ModButton()
        self.ui.setupUi(self)

        # Favorite button
        self.favoriteButton = QPushButton()
        self.favoriteButton.setFixedSize(QSize(24, 24))
        self.favoriteButton.setCursor(QCursor(Qt.PointingHandCursor))
        self.favoriteButton.setStyleSheet("background-color: transparent; border: none;")
        self.favoriteButton.clicked.connect(self.toggleFavorite)
        
        # Preview Container (Fixed width to avoid shifting status icons)
        from PySide6.QtWidgets import QFrame
        self.previewContainer = QFrame()
        self.previewContainer.setFixedWidth(74) # 64px + 10px margin
        self.previewContainer.setStyleSheet("background-color: transparent; border: none;")
        previewLayout = QHBoxLayout(self.previewContainer)
        previewLayout.setContentsMargins(0, 0, 10, 0) # 10px spacing after preview
        previewLayout.setSpacing(0)

        # List Preview Image
        from PySide6.QtWidgets import QLabel
        self.listPreviewLabel = QLabel()
        self.listPreviewLabel.setFixedSize(QSize(64, 36))
        self.listPreviewLabel.setAlignment(Qt.AlignCenter)
        self.listPreviewLabel.setStyleSheet("background-color: #000; border-radius: 4px; border: 1px solid #222;")
        previewLayout.addWidget(self.listPreviewLabel)
        
        # Insert into layout
        self.ui.horizontalLayout_2.insertWidget(0, self.favoriteButton)
        self.ui.horizontalLayout_2.insertSpacing(1, 6) # Margin between star and preview container
        self.ui.horizontalLayout_2.insertWidget(2, self.previewContainer)
        
        # Increase right margin to prevent status icon from being cut off
        self.ui.horizontalLayout_2.setContentsMargins(7, 0, 15, 0)

        self.updateData()
        self.updateListPreview()

        self.ui.background.installEventFilter(self)

        self.buttons.append(self)

    def updateData(self):
        self.ui.modName.setText(self.modClass.name)
        self.ui.gameVersion.setText(f"[{self.modClass.gameVersion}]")
        self.ui.modAuthor.setText("Author: " + self.modClass.author)
        if self.modClass.currentVersion:
            gameVersionColor = "#43C15F"
        else:
            gameVersionColor = "#3FAED1"
        self.ui.gameVersion.setStyleSheet(f"color: {gameVersionColor}")

        if self.modClass.installed and self.modClass.modFileExist:
            self.ui.modState.setPixmap(QPixmap(u":/icons/resources/icons/Installed.png"))
        elif self.modClass.installed:
            self.ui.modState.setPixmap(QPixmap(u":/icons/resources/icons/GhostInstalled.png"))
        else:
            self.ui.modState.setPixmap(QPixmap(u":/icons/resources/icons/NotInstalled.png"))

        # Update favorite icon
        if self.modClass.favorite:
            self.favoriteButton.setIcon(QIcon(":/icons/resources/icons/Star_Fill.png"))
        else:
            self.favoriteButton.setIcon(QIcon(":/icons/resources/icons/Star.png"))
        self.favoriteButton.setIconSize(QSize(18, 18))

    def toggleFavorite(self):
        self.modClass.favorite = not self.modClass.favorite
        self.updateData()
        if self.favoriteMethod:
            self.favoriteMethod(self.modClass.hash)

    # Global cache for thumbnails to prevent UI freezing
    _thumbCache = {}

    def updateListPreview(self):
        from ..utils.config import LoaderConfig
        if LoaderConfig().showListPreviews:
            self.previewContainer.show()
            
            path = ":/images/resources/images/DefaultPreview.png"
            if self.modClass.previewsPaths and len(self.modClass.previewsPaths) > 0:
                p = self.modClass.previewsPaths[0]
                if p and p != "None":
                    path = p
                    
            path = path.replace("\\", "/")
            if path not in self._thumbCache:
                original_pixmap = QPixmap(path)
                # Scale with KeepAspectRatio so it fits in 64x36, then QLabel centers it over black bg
                self._thumbCache[path] = original_pixmap.scaled(64, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            
            self.listPreviewLabel.setPixmap(self._thumbCache[path])
        else:
            self.previewContainer.hide()

    def onParentResize(self):
        parent = self
        while True:
            parent = parent.parent()
            if type(parent) == QScrollArea:
                break

            if parent is None:
                return False

        versionWidth = self.ui.gameVersion.fontMetrics().boundingRect(self.ui.gameVersion.text()).width()

        # Calculate current offset caused by margins, star, spacing, and status icon
        base_offset = 80 
        
        preview_offset = 0
        if hasattr(self, 'previewContainer') and not self.previewContainer.isHidden():
            preview_offset = self.previewContainer.width() + 6 # Container (74) + Spacing (6)

        total_offset = base_offset + versionWidth + preview_offset

        elided = self.ui.modName.fontMetrics().elidedText(self.modClass.name,
                                                           Qt.ElideRight, parent.width() - total_offset)
        self.ui.modName.setText(elided)
        self.ui.modName.setMaximumWidth(parent.width() - total_offset)

        author_offset = base_offset + preview_offset
        elided_author = self.ui.modAuthor.fontMetrics().elidedText(f"Author: {self.modClass.author}",
                                                            Qt.ElideRight, parent.width() - author_offset)
        self.ui.modAuthor.setText(elided_author)
        self.ui.modAuthor.setMaximumWidth(parent.width() - author_offset)

    def select(self):
        if self.pressed:
            pass
        else:
            for button in self.buttons:
                if button.pressed:
                    button.pressed = False
                    styleSheet = button.ui.background.styleSheet()
                    bgColor = re.findall(r"background-color: #FF(.+);", styleSheet)[0]
                    button.ui.background.setStyleSheet(
                        styleSheet.replace(f"#FF{bgColor}", f"#00{bgColor}").replace(f"#FE{bgColor}", f"#77{bgColor}"))

            self.pressed = True
            ss = self.ui.background.styleSheet()
            bgColor = re.findall(r"background-color: #00(.+);", ss)[0]
            self.ui.background.setStyleSheet(
                ss.replace(f"#00{bgColor}", f"#FF{bgColor}").replace(f"#77{bgColor}", f"#FE{bgColor}"))

            self.method(self.modClass)

    def remove(self):
        self.hide()
        self.setParent(None)

    def restore(self, frame):
        self.setParent(frame)
        frame.layout().addWidget(self)
        self.show()

    def eventFilter(self, qobject: QWidget, event):
        if event.type() == QEvent.MouseButtonPress:
            self.select()

        return False

    def eventFilter(self, qobject: QWidget, event):
        if event.type() == QEvent.MouseButtonPress:
            self.select()

        return False

    def cleanup(self):
        if self in self.buttons:
            self.buttons.remove(self)
        self.setParent(None)
        self.deleteLater()
