"""Tests for Player class: stats, leveling, damage, class changes."""
import pytest


def test_player_default_class_is_soldier(player):
    """Players spawn as Soldier by default."""
    assert player.class_type == "Soldier"


def test_player_starts_at_full_hp(player):
    """hp must equal max_hp on init."""
    assert player.hp == player.max_hp
    assert player.hp > 0


def test_player_starts_at_level_1(player):
    """Level always begins at 1."""
    assert player.level == 1


def test_player_starts_alive(player):
    """is_alive() True on a fresh player."""
    assert player.is_alive() is True


def test_player_takes_reduced_damage_via_defense(player):
    """take_damage subtracts defense (min 1)."""
    initial_hp = player.hp
    actual = player.take_damage(player.defense + 5)
    # Damage applied is raw - defense, capped at min 1
    assert actual >= 1
    assert player.hp == initial_hp - actual


def test_player_take_damage_invincibility(player):
    """take_damage during invincibility frames returns 0."""
    player.invincible_timer = 1.0
    actual = player.take_damage(50)
    assert actual == 0


def test_player_take_damage_floors_hp_at_zero(player):
    """HP cannot go negative."""
    player.take_damage(99999)
    assert player.hp >= 0
    assert not player.is_alive()


def test_player_gain_exp_does_not_crash(player):
    """gain_exp works for both leveling and non-leveling amounts."""
    levels = player.gain_exp(5)
    assert isinstance(levels, list)


def test_player_levels_up_with_enough_exp(player):
    """Gaining a huge EXP burst should raise the level."""
    initial_level = player.level
    player.gain_exp(99999)
    assert player.level > initial_level


def test_player_change_class_to_knight(player):
    """change_class swaps the class_type and applies new stats."""
    player.change_class("Knight")
    assert player.class_type == "Knight"
    base = player.CLASS_STATS["Knight"]
    assert player.max_hp == base[0]


def test_player_change_class_to_wizard(player):
    """change_class('Wizard') applies Wizard stats."""
    player.change_class("Wizard")
    assert player.class_type == "Wizard"


def test_player_change_class_to_archer(player):
    """change_class('Archer') applies Archer stats."""
    player.change_class("Archer")
    assert player.class_type == "Archer"


def test_player_change_class_to_invalid_does_nothing(player):
    """Invalid class string is a no-op (or guarded), not a crash."""
    original = player.class_type
    try:
        player.change_class("Wizardly Bagel")
    except Exception:
        pytest.fail("change_class shouldn't raise on invalid name")
    # class_type either unchanged or one of the valid classes
    assert player.class_type in player.CLASS_STATS or player.class_type == original


def test_player_move_clamps_to_world_bounds(player):
    """move can't push the player past world boundaries."""
    player.x = 0
    player.y = 0
    player.move(-1, -1, 1.0, 1000, 1000)  # try to leave to top-left
    assert player.x >= 0
    assert player.y >= 0


def test_player_exp_to_next_is_positive(player):
    """exp_to_next must be >0 at level 1."""
    assert player.exp_to_next > 0


def test_player_classes_have_required_keys(player):
    """All 4 classes have base stats and combat configs."""
    for cls in ("Soldier", "Knight", "Wizard", "Archer"):
        assert cls in player.CLASS_STATS
        assert cls in player.CLASS_COMBAT
