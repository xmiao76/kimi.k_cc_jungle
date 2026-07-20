"""CLI entry-point parsing."""

import pytest

from main import parse_args


def test_defaults():
    args = parse_args([])
    assert args.strength == "medium"
    assert not args.ai_first
    assert not args.ai_vs_ai
    assert args.depth is None
    assert args.time_limit is None
    assert not args.flip


def test_all_flags():
    args = parse_args([
        "--strength", "hard", "--ai-first", "--ai-vs-ai",
        "--depth", "7", "--time-limit", "1.5", "--flip",
    ])
    assert args.strength == "hard"
    assert args.ai_first
    assert args.ai_vs_ai
    assert args.depth == 7
    assert args.time_limit == 1.5
    assert args.flip


def test_invalid_strength_rejected():
    with pytest.raises(SystemExit):
        parse_args(["--strength", "impossible"])
