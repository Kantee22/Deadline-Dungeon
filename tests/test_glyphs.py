"""Tests for the Sloth Glyph mechanic."""
import math
import pytest


def test_glyph_starts_dormant():
    """A freshly spawned glyph must be inactive."""
    from glyphs import SlothGlyph
    g = SlothGlyph(100, 100)
    assert g.awake_phase == 0.0
    assert g.time_inside == 0.0
    assert g.is_active is False


def test_glyph_detects_player_inside():
    """player_inside flips True when player is within RADIUS."""
    from glyphs import SlothGlyph
    g = SlothGlyph(0, 0)
    g.update(0.01, 50, 0)  # well inside
    assert g.player_inside is True


def test_glyph_detects_player_outside():
    """player_inside is False when distance > RADIUS."""
    from glyphs import SlothGlyph
    g = SlothGlyph(0, 0)
    g.update(0.01, 999, 999)
    assert g.player_inside is False


def test_glyph_wake_after_threshold():
    """Standing inside for ≥ WAKE_TIME should activate the glyph."""
    from glyphs import SlothGlyph
    g = SlothGlyph(0, 0)
    # Tick 1.5x WAKE_TIME of small steps to fully ramp up.
    for _ in range(int(g.WAKE_TIME * 60) + 30):
        g.update(1 / 60.0, 0, 0)
    assert g.is_active is True
    assert g.awake_phase > 0.05


def test_glyph_does_not_wake_if_player_outside():
    """If the player never enters the radius, glyph stays dormant forever."""
    from glyphs import SlothGlyph
    g = SlothGlyph(0, 0)
    for _ in range(120):
        g.update(1 / 60.0, 9999, 9999)
    assert g.is_active is False
    assert g.awake_phase == 0.0


def test_glyph_resets_time_inside_on_exit():
    """Walking out of the radius zeros the time-inside counter."""
    from glyphs import SlothGlyph
    g = SlothGlyph(0, 0)
    g.update(0.5, 0, 0)
    assert g.time_inside > 0
    g.update(0.1, 9999, 9999)  # exit
    assert g.time_inside == 0.0


def test_glyph_time_multiplier_default():
    """Dormant glyph returns multiplier 1.0 (no effect)."""
    from glyphs import SlothGlyph
    g = SlothGlyph(0, 0)
    assert g.time_multiplier() == 1.0


def test_glyph_time_multiplier_when_awake():
    """Fully awake glyph returns TIME_MULT_AWAKE."""
    from glyphs import SlothGlyph
    g = SlothGlyph(0, 0)
    # Force a fully active state.
    g.player_inside = True
    g.awake_phase = 1.0
    assert math.isclose(g.time_multiplier(), g.TIME_MULT_AWAKE,
                        rel_tol=1e-3)


def test_glyph_hp_drain_when_dormant_is_zero():
    """Drain returns 0 when not active."""
    from glyphs import SlothGlyph
    g = SlothGlyph(0, 0)
    assert g.hp_drain(0.016) == 0.0


def test_glyph_hp_drain_when_awake():
    """Drain returns DRAIN_HP_PER_SEC * awake_phase * dt."""
    from glyphs import SlothGlyph
    g = SlothGlyph(0, 0)
    g.player_inside = True
    g.awake_phase = 1.0
    drain = g.hp_drain(0.5)
    expected = g.DRAIN_HP_PER_SEC * 1.0 * 0.5
    assert math.isclose(drain, expected, rel_tol=1e-3)


def test_glyph_radius_is_120():
    """Radius bumped to 120 so the zone is more visible."""
    from glyphs import SlothGlyph
    assert SlothGlyph.RADIUS == 120


def test_glyph_wake_time_is_1_2_seconds():
    """WAKE_TIME tuned to 1.20 seconds."""
    from glyphs import SlothGlyph
    assert SlothGlyph.WAKE_TIME == 1.20


def test_spawn_glyphs_returns_list_of_glyphs(tilemap):
    """spawn_glyphs returns a list of SlothGlyph instances."""
    from glyphs import spawn_glyphs, SlothGlyph
    glyphs = spawn_glyphs(tilemap, count=3)
    assert isinstance(glyphs, list)
    for g in glyphs:
        assert isinstance(g, SlothGlyph)
