"""Tests for SpriteAnimator (animation loader)."""
import os
import pytest


def test_sprite_animator_no_loop_actions():
    """Verify the canonical NO_LOOP set."""
    from animation import SpriteAnimator
    assert "attack" in SpriteAnimator.NO_LOOP
    assert "death" in SpriteAnimator.NO_LOOP
    assert "idle" not in SpriteAnimator.NO_LOOP


def test_sprite_animator_default_durations_are_floats():
    """All default durations are positive floats."""
    from animation import SpriteAnimator
    for key, val in SpriteAnimator.DEFAULT_DURATIONS.items():
        assert isinstance(val, (int, float))
        assert val > 0


def test_sprite_animator_handles_missing_folder():
    """Loading a non-existent folder fails gracefully (loaded=False)."""
    from animation import SpriteAnimator
    sa = SpriteAnimator("/nonexistent/path/that/does/not/exist",
                        pixel_scale=2.0)
    assert sa.loaded is False


def test_sprite_animator_set_action_no_crash_on_unloaded():
    """Setting an action on an unloaded animator should not raise."""
    from animation import SpriteAnimator
    sa = SpriteAnimator("/nope", pixel_scale=2.0)
    try:
        sa.set_action("idle")
    except Exception as e:
        pytest.fail(f"set_action raised on unloaded animator: {e}")
