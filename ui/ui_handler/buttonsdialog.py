from typing import List, Tuple, Callable

from PySide6.QtGui import QFont, QCursor, Qt
from PySide6.QtWidgets import QWidget, QPushButton
from ..ui_sources.ui_buttons_dialog import Ui_ButtonsDialog


class ButtonsDialog(QWidget):
    font = QFont()
    font.setFamilies([u"Roboto Medium"])
    font.setPointSize(10)
    font.setBold(False)

    maxContentHeight = 420

    def __init__(self, window):
        super().__init__()

        self.ui = Ui_ButtonsDialog()
        self.ui.setupUi(self)
        self.ui.content.setWordWrap(True)
        self.ui.content.setTextFormat(Qt.RichText)
        self.ui.content.setOpenExternalLinks(True)

        self.mainWindow = window

        #self.buttons: List[Tuple[str, Callable]] = []
        self.buttons: List[QPushButton] = []

    def deleteButtons(self):
        for button in self.buttons:
            self.ui.buttons.layout().removeWidget(button)
            button.setParent(None)
            button.deleteLater()
            del button

        self.buttons.clear()

    def addButton(self, text: str, function: Callable):
        button = QPushButton()
        button.setFont(self.font)
        button.setCursor(QCursor(Qt.PointingHandCursor))
        button.setText(text)
        button.setParent(self.ui.buttons)
        button.clicked.connect(function)
        self.ui.buttons.layout().addWidget(button)
        self.buttons.append(button)

    def setButtons(self, buttons: List[Tuple[str, Callable]]):
        self.deleteButtons()
        for button in buttons:
            self.addButton(*button)

    def onResize(self):
        self.setGeometry(0, 0, self.mainWindow.width(), self.mainWindow.height())

    def isShown(self):
        return self.parent() is not None

    def show(self):
        if self.parent() is None:
            self.setParent(self.mainWindow)
            self.onResize()
            super().show()
            self.raise_()

            if hasattr(self.mainWindow, 'width') and hasattr(self.mainWindow, 'height'):
                target_width = min(740, max(520, self.mainWindow.width() - 50))
                self.ui.dialogBackground.setMinimumWidth(target_width)
                
                max_h = max(360, min(480, int(self.mainWindow.height() * 0.70)))
                self.maxContentHeight = max_h

            content_h = self.ui.content.height()
            if content_h <= self.maxContentHeight:
                self.ui.scrollLabel.setMinimumHeight(content_h)
                self.ui.scrollLabel.setMaximumHeight(content_h)
            else:
                self.ui.scrollLabel.setMinimumHeight(self.maxContentHeight)
                self.ui.scrollLabel.setMaximumHeight(self.maxContentHeight)

    def hide(self):
        if self.parent() is not None:
            super().hide()
            self.setParent(None)

    def setContent(self, content: str):
        self.ui.content.setText(content)

    def setTitle(self, title: str):
        self.ui.title.setText(title)
