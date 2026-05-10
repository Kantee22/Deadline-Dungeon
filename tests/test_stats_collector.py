"""Tests for StatsCollector recording + aggregation."""
import pytest


def test_stats_initialized_empty(stats):
    """Brand new collector starts with zero aggregates."""
    assert stats.total_kills == 0
    assert stats.total_damage_dealt == 0
    assert stats.total_damage_received == 0
    assert stats.peak_level == 1


def test_record_damage_dealt_aggregates(stats):
    stats.record_damage_dealt(15, "attack", "Soldier", "slime", 3)
    assert stats.total_damage_dealt >= 15


def test_record_damage_received_aggregates(stats):
    stats.record_damage_received(10, 8, "skeleton", 5, 80, 100, 30.5)
    assert stats.total_damage_received >= 8


def test_record_kill_increments_total(stats):
    stats.record_kill("orc", 7, 60.0)
    assert stats.total_kills == 1
    stats.record_kill("orc", 8, 70.0)
    assert stats.total_kills == 2


def test_record_kill_tracks_per_type(stats):
    stats.record_kill("slime", 1, 5.0)
    stats.record_kill("slime", 2, 12.0)
    stats.record_kill("orc", 3, 15.0)
    assert stats.kills_by_type.get("slime") == 2
    assert stats.kills_by_type.get("orc") == 1


def test_record_skill_use_appends_record(stats):
    before = len(stats.records["skill_usage"])
    stats.record_skill_use("attack", "Wizard", True, 25, 33.0)
    assert len(stats.records["skill_usage"]) == before + 1


def test_record_session_outcome(stats):
    stats.record_session_outcome(won=True, final_level=22,
                                 time_survived=540.0,
                                 player_class="Knight",
                                 boss_defeated="final_boss",
                                 timed_out=False)
    assert len(stats.records["session_outcomes"]) == 1


def test_get_record_count_returns_dict(stats):
    """get_record_count returns a dict mapping feature name -> count."""
    stats.record_kill("slime", 1, 1.0)
    counts = stats.get_record_count()
    assert isinstance(counts, dict)
    # records["kills_per_level"] is what record_kill writes to.
    assert counts.get("kills_per_level", 0) >= 1


def test_peak_level_updates(stats):
    """peak_level tracks highest level seen via record_kill."""
    stats.record_kill("slime", 5, 10.0)
    stats.record_kill("orc", 12, 30.0)
    assert stats.peak_level >= 12


def test_record_hp_sample_appends(stats):
    """record_hp_sample writes to records['hp_over_time']."""
    before = len(stats.records["hp_over_time"])
    stats.record_hp_sample(80, 100, 12.5, 5)
    assert len(stats.records["hp_over_time"]) == before + 1


def test_record_exp_gain_appends(stats):
    """record_exp_gain writes a row in exp_over_time."""
    before = len(stats.records["exp_over_time"])
    stats.record_exp_gain(20, "slime", 100, 3, 30.0)
    assert len(stats.records["exp_over_time"]) == before + 1


def test_record_death_appends(stats):
    """record_death writes a row in death_cause."""
    before = len(stats.records["death_cause"])
    stats.record_death("orc", 12, 5, 0, 90.0, 510.0)
    assert len(stats.records["death_cause"]) == before + 1


def test_session_id_is_set(stats):
    """Each StatsCollector gets a numeric session_id at init."""
    assert isinstance(stats.session_id, int)
    assert stats.session_id > 0
