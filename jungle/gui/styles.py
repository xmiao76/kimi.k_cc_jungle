"""Application stylesheet."""

APP_QSS = """
QMainWindow, QDialog {
    background: #2b2b30;
}
QWidget {
    color: #ececf1;
    font-family: "Segoe UI";
    font-size: 10pt;
}
QMenuBar {
    background: #1f1f23;
    border-bottom: 1px solid #3a3a41;
}
QMenuBar::item {
    padding: 4px 12px;
    background: transparent;
}
QMenuBar::item:selected, QMenu::item:selected {
    background: #3d6fa8;
}
QMenu {
    background: #232328;
    border: 1px solid #3a3a41;
}
QMenu::item {
    padding: 5px 24px;
}
QStatusBar {
    background: #1f1f23;
    border-top: 1px solid #3a3a41;
    font-size: 10pt;
}
QLabel {
    padding: 2px;
}
QPushButton {
    background: #3d6fa8;
    border: 1px solid #2c527d;
    border-radius: 4px;
    padding: 6px 18px;
    min-width: 72px;
}
QPushButton:hover {
    background: #4a80bd;
}
QPushButton:pressed {
    background: #2c527d;
}
QComboBox {
    background: #38383f;
    border: 1px solid #4a4a52;
    border-radius: 3px;
    padding: 4px 8px;
    min-width: 140px;
}
QComboBox QAbstractItemView {
    background: #232328;
    border: 1px solid #4a4a52;
    selection-background-color: #3d6fa8;
}
"""
