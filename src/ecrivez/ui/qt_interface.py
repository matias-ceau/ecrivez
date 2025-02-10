import sys

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QPlainTextEdit,
    QSplitter,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

# from qtermwidget import QTermWidget


class BrowserView(QWebEngineView):
    def keyPressEvent(self, event: QKeyEvent) -> None:
        parent = self.parent()
        if isinstance(parent, BrowserTerminalApp):
            parent.handleBrowserKeys(event)
        else:
            super().keyPressEvent(event)
        return None


class BrowserTerminalApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Browser + Terminal")

        # Create tab widget
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Tab 1: Browser + Terminal
        self.tab1 = QWidget()
        self.tab1_layout = QHBoxLayout()

        # Create splitter for tab1
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # Terminal widget
        self.terminal = QPlainTextEdit()
        self.terminal.setStyleSheet("background-color: #002b36; color: #839496;")

        # Browser widget
        self.browser = BrowserView()
        self.browser.setParent(self)
        if sys.argv[1:]:
            path = QUrl(sys.argv[1])
        else:
            path = QUrl(
                "file:///home/matias/git/matias-ceau/pyfiber/docs/_build/html/index.html"
            )
        self.browser.load(path)

        # Add widgets to splitter
        self.splitter.addWidget(self.terminal)
        self.splitter.addWidget(self.browser)
        self.splitter.setStretchFactor(1, 2)  # Make browser take more space

        self.tab1_layout.addWidget(self.splitter)
        self.tab1.setLayout(self.tab1_layout)

        # Tab 2: Nvim + Command Prompt
        self.tab2 = QWidget()
        self.tab2_layout = QVBoxLayout()

        # Create toolbar for tab2
        self.toolbar = QToolBar()
        self.tab2_layout.addWidget(self.toolbar)

        # Create horizontal splitter for nvim and command prompt
        self.nvim_splitter = QSplitter(Qt.Orientation.Vertical)

        # Terminal for nvim
        self.nvim_terminal = QPlainTextEdit()
        self.nvim_terminal.setStyleSheet("background-color: #002b36; color: #839496;")
        # Since QPlainTextEdit doesn't have sendText, we'll skip the nvim command for now
        # self.nvim_terminal.sendText("nvim\n")

        # Command prompt terminal
        self.cmd_terminal = QPlainTextEdit()
        self.cmd_terminal.setStyleSheet("background-color: #002b36; color: #839496;")

        self.nvim_splitter.addWidget(self.nvim_terminal)
        self.nvim_splitter.addWidget(self.cmd_terminal)
        self.nvim_splitter.setStretchFactor(0, 3)  # Make nvim take more space

        self.tab2_layout.addWidget(self.nvim_splitter)
        self.tab2.setLayout(self.tab2_layout)

        # Add tabs to widget
        self.tabs.addTab(self.tab1, "Browser + Terminal")
        self.tabs.addTab(self.tab2, "Nvim + Command")

        # Window setup
        self.setGeometry(100, 100, 1200, 800)

    def setupVimBindings(self):
        pass  # Remove this as we're now handling keys in BrowserView

    def handleBrowserKeys(self, event: QKeyEvent):
        # Basic vim-style navigation
        key = event.key()
        page = self.browser.page()
        if not page:
            return

        if key == Qt.Key.Key_J:
            page.runJavaScript("window.scrollBy(0, 50)", lambda _: None)
        elif key == Qt.Key.Key_K:
            page.runJavaScript("window.scrollBy(0, -50)", lambda _: None)
        elif key == Qt.Key.Key_H:
            self.browser.back()
        elif key == Qt.Key.Key_L:
            self.browser.forward()
        elif key == Qt.Key.Key_G:
            page.runJavaScript("window.scrollTo(0, 0)", lambda _: None)
        elif key == Qt.Key.Key_Shift and event.text() == "G":
            page.runJavaScript(
                "window.scrollTo(0, document.body.scrollHeight)", lambda _: None
            )
        else:
            # Pass other keys to the default handler
            QWebEngineView.keyPressEvent(self.browser, event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BrowserTerminalApp()
    window.show()
    sys.exit(app.exec())

# python qtconsole -> jupyter
# connectivity
# positionning
# sensors
# speech
# webchannel/socket
# serial svg
# datavisualization
# networkauth
# networkauth
