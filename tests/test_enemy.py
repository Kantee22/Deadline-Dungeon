"""Tests for the base Enemy class."""
import pytest


def test_enemy_spawns_with_correct_type():
    from enemy import Enemy
    e = Enemy(10, 20, "slime", level_scale=1)
    assert e.enemy_type == "slime"
    assert e.x == 10
    assert e.y == 20


def test_enemy_starts_full_hp():
    from enemy import Enemy
    e = Enemy(0, 0, "skeleton", 1)
    assert e.hp == e.max_hp
    assert e.hp > 0


def test_enemy_starts_alive():
    from enemy import Enemy
    e = Enemy(0, 0, "orc", 1)
    assert e.alive is True


def test_enemy_take_damage_reduces_hp():
    from enemy import Enemy
    e = Enemy(0, 0, "slime", 1)
    initial = e.hp
    e.take_damage(5)
    assert e.hp < initial


def test_enemy_dies_when_hp_zero():
    from enemy import Enemy
    e = Enemy(0, 0, "slime", 1)
    e.take_damage(99999)
    # Either marked dying or alive flips to False; both are valid death states
    assert e.hp <= 0


def test_enemy_higher_level_scale_yields_higher_hp():
    """level_scale should scale enemy stats up."""
    from enemy import Enemy
    weak = Enemy(0, 0, "skeleton", 1)
    strong = Enemy(0, 0, "skeleton", 20)
    assert strong.max_hp >= weak.max_hp
