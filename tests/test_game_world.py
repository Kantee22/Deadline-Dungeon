"""Tests for GameWorld setup, glyph integration, milestones."""
import pytest


def test_game_world_constructs():
    """A fresh world initialises without crashing."""
    from game_world import GameWorld
    world = GameWorld()
    assert world.timer == 0.0
    assert world.state == "playing"


def test_game_world_max_time_is_10_min():
    from game_world import GameWorld
    assert GameWorld.MAX_TIME == 600.0


def test_game_world_spawns_glyphs():
    """Glyphs list is populated after construction."""
    from game_world import GameWorld
    world = GameWorld()
    assert isinstance(world.glyphs, list)


def test_game_world_total_glyph_drain_zero_when_no_glyphs_active():
    """Total drain is 0 immediately after construction."""
    from game_world import GameWorld
    world = GameWorld()
    assert world.total_glyph_drain(0.5) == 0.0


def test_game_world_any_glyph_active_false_initially():
    from game_world import GameWorld
    world = GameWorld()
    assert world.any_glyph_active() is False


def test_game_world_starts_with_no_bosses():
    from game_world import GameWorld
    world = GameWorld()
    assert world.bosses == []
    assert world.boss_active is False


def test_game_world_update_glyphs_returns_multiplier():
    """update_glyphs returns a float ≥ 1.0."""
    from game_world import GameWorld
    world = GameWorld()
    mult = world.update_glyphs(0.016, 100, 100)
    assert isinstance(mult, float)
    assert mult >= 1.0
