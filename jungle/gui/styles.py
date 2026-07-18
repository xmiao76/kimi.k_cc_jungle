"""Application-wide styles and theme constants."""

from __future__ import annotations

from PyQt6.QtGui import QColor

WINDOW_BACKGROUND = QColor("#2c3e50")
STATUS_BACKGROUND = QColor("#34495e")
STATUS_FOREGROUND = QColor("#ecf0f1")
BUTTON_BACKGROUND = QColor("#3498db")
BUTTON_FOREGROUND = QColor("#ffffff")

MAIN_WINDOW_QSS = """
QMainWindow {
    background-color: #2c3e50;
}
QMenuBar {
    background-color: #34495e;
    color: #ecf0f1;
}
QMenuBar::item:selected {
    background-color: #3498db;
}
QMenu {
    background-color: #34495e;
    color: #ecf0f1;
}
QMenu::item:selected {
    background-color: #3498db;
}
QStatusBar {
    background-color: #34495e;
    color: #ecf0f1;
}
QPushButton {
    background-color: #3498db;
    color: #ffffff;
    border: none;
    padding: 8px 16px;
    border-radius: 4px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #2980b9;
}
QPushButton:pressed {
    background-color: #1c6ea4;
}
QDialog {
    background-color: #2c3e50;
}
QLabel {
    color: #ecf0f1;
}
QRadioButton {
    color: #ecf0f1;
}
"""
