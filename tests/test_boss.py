"""Tests for Boss subclass: tier pools, phases, variants."""
import pytest


def test_boss_default_construction():
    from boss import Boss
    b = Boss(0, 0, "mini_boss_1")
    assert b.boss_type == "mini_boss_1"
    assert b.alive is True


def test_boss_template_has_all_tiers():
    """Templates cover tier 1, 2, 3."""
    from boss import Boss
    tiers = {v["tier"] for v in Boss.BOSS_TEMPLATES.values()}
    assert tiers == {1, 2, 3}


def test_boss_get_tier_pool_returns_keys():
    from boss import Boss
    pool1 = Boss.get_tier_pool(1)
    pool2 = Boss.get_tier_pool(2)
    pool3 = Boss.get_tier_pool(3)
    assert len(pool1) >= 1
    assert len(pool2) >= 1
    assert len(pool3) >= 1
    for k in pool1 + pool2 + pool3:
        assert k in Boss.BOSS_TEMPLATES


def test_boss_enraged_has_higher_stats():
    """enraged=True should give stronger stats than the default."""
    from boss import Boss
    normal = Boss(0, 0, "final_boss", enraged=False)
    enraged = Boss(0, 0, "final_boss", enraged=True)
    assert enraged.max_hp > normal.max_hp
    assert enraged.attack > normal.attack


def test_boss_starts_in_phase_1():
    """All bosses start in phase 1."""
    from boss import Boss
    b = Boss(0, 0, "mini_boss_2")
    assert b.phase == 1


def test_boss_phase_thresholds_count_matches_phases():
    """phase_thresholds list size = max_phases - 1."""
    from boss import Boss
    b = Boss(0, 0, "final_boss")
    assert len(b.phase_thresholds) == b.max_phases - 1


def test_boss_take_damage_reduces_hp():
    from boss import Boss
    b = Boss(0, 0, "mini_boss_1")
    initial = b.hp
    b.take_damage(50)
    assert b.hp < initial


def test_boss_special_effects_list_exists():
    """Boss exposes a _special_effects list for shockwaves / melee AoEs."""
    from boss import Boss
    b = Boss(0, 0, "mini_boss_2")
    assert hasattr(b, "_special_effects")
    assert isinstance(b._special_effects, list)


def test_boss_starts_not_using_special():
    """A freshly spawned boss is not in the middle of a special attack."""
    from boss import Boss
    b = Boss(0, 0, "final_boss")
    assert b._using_special is False
    assert b._pending_special is None
