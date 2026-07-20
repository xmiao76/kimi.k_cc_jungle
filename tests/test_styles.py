"""Stylesheet sanity."""

from jungle.gui.styles import APP_QSS


def test_stylesheet_is_present_and_references_key_widgets():
    assert isinstance(APP_QSS, str) and len(APP_QSS) > 200
    for selector in ("QMainWindow", "QMenuBar", "QStatusBar", "QPushButton", "QComboBox"):
        assert selector in APP_QSS
