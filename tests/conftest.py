"""Shared pytest fixtures + headless pygame setup.

The CI runner is headless (no display attached), so we tell SDL to use
the dummy video driver before pygame initialises any display surface.
"""
import os
import sys

# Force headless before pygame is imported anywhere.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

# Make the project root importable.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pygame  # noqa: E402

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _pygame_headless():
    """Initialise pygame once per test session (headless)."""
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield
    pygame.quit()


@pytest.fixture
def tilemap():
    """Small deterministic dungeon for tests that need a TileMap."""
    import random
    random.seed(42)
    from tilemap import TileMap
    return TileMap(20, 20, "Dungeon_Tileset.png")


@pytest.fixture
def player():
    """A fresh Soldier at world origin."""
    from player import Player
    return Player(100, 100)


@pytest.fixture
def stats():
    """A fresh StatsCollector with stable session id."""
    from stats_collector import StatsCollector
    sc = StatsCollector()
    sc.player_name = "TestPlayer"
    return sc
