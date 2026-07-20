"""Shared pytest configuration.

GUI tests must run offscreen: long-lived in-process Qt sessions on Windows
are prone to intermittent RPC_E_CALL_REJECTED (0x8001010d) crashes, so the
offscreen platform is forced before any Qt import happens.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from jungle.model.board import GameState


@pytest.fixture()
def initial_state() -> GameState:
    """A fresh game at the standard starting position, RED to move."""
    return GameState.starting()
