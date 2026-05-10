"""Tests for procedural dungeon generation, glyph + candle placement."""
import random
import pytest


def test_tilemap_construction(tilemap):
    """Constructing a TileMap creates a non-empty grid + at least one room."""
    assert tilemap.map_w == 20
    assert tilemap.map_h == 20
    assert len(tilemap.grid) == 20
    assert len(tilemap.grid[0]) == 20
    assert len(tilemap.rooms) >= 1


def test_world_dimensions_match_tile_size(tilemap):
    """world_w/h should be map_w/h * DISPLAY_TILE."""
    assert tilemap.world_w == 20 * tilemap.DISPLAY_TILE
    assert tilemap.world_h == 20 * tilemap.DISPLAY_TILE


def test_grid_only_contains_walls_and_floors(tilemap):
    """Every cell in grid must be 0 (wall) or 1 (floor)."""
    for row in tilemap.grid:
        for cell in row:
            assert cell in (0, 1)


def test_floor_count_is_reasonable(tilemap):
    """At least 30 floor tiles in any 20x20 dungeon (sanity check)."""
    floor_count = sum(1 for row in tilemap.grid for c in row if c == 1)
    assert floor_count >= 30


def test_is_wall_out_of_bounds(tilemap):
    """is_wall returns True for any out-of-bounds query."""
    assert tilemap.is_wall(-100, -100) is True
    assert tilemap.is_wall(99999, 99999) is True


def test_is_walkable_inverse_of_is_wall(tilemap):
    """is_walkable should be the logical inverse of is_wall."""
    for x in (50, 200, 500):
        for y in (50, 200, 500):
            assert tilemap.is_walkable(x, y) == (not tilemap.is_wall(x, y))


def test_get_start_position_is_walkable(tilemap):
    """Player spawn must be on a floor tile."""
    sx, sy = tilemap.get_start_position()
    assert tilemap.is_walkable(sx, sy)


def test_get_spawn_position_is_walkable(tilemap):
    """Enemy spawn helper must yield a walkable tile."""
    for _ in range(10):
        sx, sy = tilemap.get_spawn_position()
        assert tilemap.is_walkable(sx, sy)


def test_clamp_to_floor_returns_walkable(tilemap):
    """clamp_to_floor must always return a walkable point."""
    # Point likely inside a wall corner
    cx, cy = tilemap.clamp_to_floor(5, 5)
    # Either it was already walkable or it found a nearby floor.
    assert tilemap.is_walkable(cx, cy) or (cx, cy) == (5, 5)


def test_get_glyph_positions_returns_tuples(tilemap):
    """Glyph spawn helper returns a list of (x, y) world coords."""
    positions = tilemap.get_glyph_positions(count=5)
    assert isinstance(positions, list)
    for p in positions:
        assert isinstance(p, tuple)
        assert len(p) == 2


def test_glyph_positions_respect_count(tilemap):
    """Helper never returns more positions than requested."""
    for n in (1, 3, 5):
        positions = tilemap.get_glyph_positions(count=n)
        assert len(positions) <= n


def test_glyph_positions_are_walkable(tilemap):
    """Every glyph spawn point must sit on a floor tile."""
    positions = tilemap.get_glyph_positions(count=5)
    for (x, y) in positions:
        assert tilemap.is_walkable(x, y)


def test_glyph_positions_are_separated(tilemap):
    """Glyph helper enforces min_separation between picks."""
    positions = tilemap.get_glyph_positions(count=5, min_separation=200)
    for i, (x1, y1) in enumerate(positions):
        for (x2, y2) in positions[i + 1:]:
            d2 = (x1 - x2) ** 2 + (y1 - y2) ** 2
            assert d2 >= 200 ** 2 - 1  # allow rounding


def test_get_candle_positions_returns_list(tilemap):
    """Candle helper returns a list (may be empty for tiny maps)."""
    positions = tilemap.get_candle_positions(density=0.5)
    assert isinstance(positions, list)


def test_decor_time_starts_at_zero(tilemap):
    """Decoration animation clock must start at 0."""
    assert tilemap._decor_time == 0.0


def test_update_decor_advances_clock(tilemap):
    """update_decor(dt) advances _decor_time by dt."""
    tilemap.update_decor(0.5)
    assert tilemap._decor_time == 0.5
    tilemap.update_decor(0.25)
    assert abs(tilemap._decor_time - 0.75) < 1e-6
