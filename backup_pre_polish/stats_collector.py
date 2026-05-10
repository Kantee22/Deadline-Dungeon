"""stats_collector.py - Record gameplay events and export them to CSVs in stats_data/."""
import csv
import os
import time
from datetime import datetime


# Anchor DATA_DIR to this file so CSVs save next to the code, not cwd.
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


class StatsCollector:
    """In-memory stats buffer + CSV exporter."""

    DATA_DIR = os.path.join(_SCRIPT_DIR, "stats_data")

    # Column order per CSV file (first 3 cols always session_id/name/timestamp).
    FIELD_ORDER = {
        "damage_dealt": [
            "session_id", "player_name", "timestamp",
            "damage", "skill_name", "player_class",
            "enemy_type", "player_level",
        ],
        "damage_received": [
            "session_id", "player_name", "timestamp",
            "raw_damage", "actual_damage", "enemy_type",
            "player_level", "player_hp_after", "player_max_hp", "game_time",
        ],
        "kills_per_level": [
            "session_id", "player_name", "timestamp",
            "player_level", "enemy_type", "total_at_level", "game_time",
        ],
        "hp_over_time": [
            "session_id", "player_name", "timestamp",
            "current_hp", "max_hp", "hp_ratio", "player_level", "game_time",
        ],
        "skill_usage": [
            "session_id", "player_name", "timestamp",
            "skill_name", "player_class", "hit", "damage", "game_time",
        ],
        "session_outcomes": [
            "session_id", "player_name", "timestamp",
            "won", "final_level", "time_survived",
            "player_class", "boss_defeated", "timed_out",
        ],
        "exp_over_time": [
            "session_id", "player_name", "timestamp",
            "event_type", "total_exp", "current_level",
            "exp_gained", "source_enemy", "game_time",
        ],
        "death_cause": [
            "session_id", "player_name", "timestamp",
            "killer_type", "killer_attack", "player_level",
            "player_hp_before", "game_time", "time_remaining",
        ],
    }

    def __init__(self):
        self.records = {name: [] for name in self.FIELD_ORDER.keys()}

        # Cursor per feature: export_csv() writes records[cursor:] then advances.
        self._export_cursor = {name: 0 for name in self.FIELD_ORDER.keys()}

        # Session identity.
        self.session_id = int(time.time())
        self.session_start = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.player_name = "Player"

        # Aggregates for leaderboard row.
        self.total_damage_dealt = 0
        self.total_damage_received = 0
        self.total_kills = 0
        self.peak_level = 1
        self.kills_by_type = {}

        # Periodic sampling timers.
        self._kills_at_level = {}
        self._hp_sample_timer = 0.0
        self._hp_sample_interval = 2.0
        self._exp_sample_timer = 0.0
        self._exp_sample_interval = 3.0

        # Auto-flush so a crash doesn't lose data.
        self._autosave_timer = 0.0
        self._autosave_interval = 15.0

        os.makedirs(self.DATA_DIR, exist_ok=True)

    def _record_event(self, event_type, data):
        """Append a row with common session fields filled in."""
        data["session_id"] = self.session_id
        data["player_name"] = self.player_name
        data["timestamp"] = round(time.time(), 2)
        self.records[event_type].append(data)

    # -- Damage dealt --
    def record_damage_dealt(self, damage, skill_name, player_class, enemy_type, player_level):
        self._record_event("damage_dealt", {
            "damage": damage,
            "skill_name": skill_name,
            "player_class": player_class,
            "enemy_type": enemy_type,
            "player_level": player_level,
        })
        self.total_damage_dealt += damage

    # -- Damage received --
    def record_damage_received(self, raw_damage, actual_damage, enemy_type,
                                player_level, player_hp, player_max_hp, game_time):
        self._record_event("damage_received", {
            "raw_damage": raw_damage,
            "actual_damage": actual_damage,
            "enemy_type": enemy_type,
            "player_level": player_level,
            "player_hp_after": player_hp,
            "player_max_hp": player_max_hp,
            "game_time": round(game_time, 2),
        })
        self.total_damage_received += actual_damage

    # -- Kills per level --
    def record_kill(self, enemy_type, player_level, game_time):
        self._kills_at_level[player_level] = self._kills_at_level.get(player_level, 0) + 1
        self._record_event("kills_per_level", {
            "player_level": player_level,
            "enemy_type": enemy_type,
            "total_at_level": self._kills_at_level[player_level],
            "game_time": round(game_time, 2),
        })
        self.total_kills += 1
        self.kills_by_type[enemy_type] = self.kills_by_type.get(enemy_type, 0) + 1
        self.peak_level = max(self.peak_level, player_level)

    # -- HP over time --
    def record_hp_sample(self, current_hp, max_hp, game_time, player_level):
        self._record_event("hp_over_time", {
            "current_hp": current_hp,
            "max_hp": max_hp,
            "hp_ratio": round(current_hp / max_hp, 3) if max_hp > 0 else 0.0,
            "player_level": player_level,
            "game_time": round(game_time, 2),
        })

    # -- Skill usage --
    def record_skill_use(self, skill_name, player_class, hit, damage, game_time):
        self._record_event("skill_usage", {
            "skill_name": skill_name,
            "player_class": player_class,
            "hit": bool(hit),
            "damage": damage,
            "game_time": round(game_time, 2),
        })

    # -- Session outcomes --
    def record_session_outcome(self, won, final_level, time_survived,
                                player_class, boss_defeated, timed_out):
        self._record_event("session_outcomes", {
            "won": bool(won),
            "final_level": final_level,
            "time_survived": round(time_survived, 2),
            "player_class": player_class,
            "boss_defeated": boss_defeated,
            "timed_out": bool(timed_out),
        })
        self.peak_level = max(self.peak_level, final_level)

    # -- EXP over time --
    def record_exp_snapshot(self, total_exp, current_level, game_time):
        """Periodic EXP snapshot."""
        self._record_event("exp_over_time", {
            "event_type": "snapshot",
            "total_exp": total_exp,
            "current_level": current_level,
            "exp_gained": 0,
            "source_enemy": "",
            "game_time": round(game_time, 2),
        })

    def record_exp_gain(self, exp_gained, source_enemy, total_exp, current_level, game_time):
        """One-off EXP gain event."""
        self._record_event("exp_over_time", {
            "event_type": "gain",
            "total_exp": total_exp,
            "current_level": current_level,
            "exp_gained": exp_gained,
            "source_enemy": source_enemy,
            "game_time": round(game_time, 2),
        })

    # -- Death cause --
    def record_death(self, killer_type, killer_attack, player_level,
                      player_hp_before, game_time, time_remaining):
        self._record_event("death_cause", {
            "killer_type": killer_type,
            "killer_attack": killer_attack,
            "player_level": player_level,
            "player_hp_before": player_hp_before,
            "game_time": round(game_time, 2),
            "time_remaining": round(time_remaining, 2),
        })

    # -- Per-frame --
    def update(self, dt, player, game_time):
        """Sample HP/EXP on interval and auto-flush CSVs."""
        self._hp_sample_timer += dt
        if self._hp_sample_timer >= self._hp_sample_interval:
            self._hp_sample_timer = 0.0
            self.record_hp_sample(player.hp, player.max_hp, game_time, player.level)

        self._exp_sample_timer += dt
        if self._exp_sample_timer >= self._exp_sample_interval:
            self._exp_sample_timer = 0.0
            self.record_exp_snapshot(player.total_exp, player.level, game_time)

        self._autosave_timer += dt
        if self._autosave_timer >= self._autosave_interval:
            self._autosave_timer = 0.0
            self.export_csv(verbose=False)

    # -- CSV export --
    def export_csv(self, verbose=True):
        """Append new records to each CSV (cursor-based, no duplicate rows)."""
        total_exported = 0
        for feature_name, records in self.records.items():
            cursor = self._export_cursor.get(feature_name, 0)
            new_records = records[cursor:]
            if not new_records:
                continue

            filepath = os.path.join(self.DATA_DIR, f"{feature_name}.csv")
            fields = self.FIELD_ORDER[feature_name]

            file_exists = os.path.exists(filepath) and os.path.getsize(filepath) > 0
            try:
                with open(filepath, "a", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(
                        f, fieldnames=fields, extrasaction="ignore")
                    if not file_exists:
                        writer.writeheader()
                    writer.writerows(new_records)
                total_exported += len(new_records)
                self._export_cursor[feature_name] = len(records)
            except (IOError, OSError) as e:
                if verbose:
                    print(f"[StatsCollector] Failed to write {feature_name}.csv: {e}")
                continue

        # Leaderboard is derived from aggregates, so update it every flush.
        self._export_leaderboard()

        if verbose:
            total_in_memory = sum(len(r) for r in self.records.values())
            print(f"[StatsCollector] Exported {total_exported} new rows "
                  f"({total_in_memory} total tracked) → {self.DATA_DIR}/")

    def _export_leaderboard(self):
        """Write/overwrite this session's row in leaderboard.csv."""
        leaderboard_path = os.path.join(self.DATA_DIR, "leaderboard.csv")
        fields = [
            "session_id", "player_name", "session_start",
            "peak_level", "total_kills", "total_damage_dealt",
            "total_damage_received", "slime_kills", "skeleton_kills",
            "orc_kills", "boss_kills",
        ]

        row = {
            "session_id": self.session_id,
            "player_name": self.player_name,
            "session_start": self.session_start,
            "peak_level": self.peak_level,
            "total_kills": self.total_kills,
            "total_damage_dealt": self.total_damage_dealt,
            "total_damage_received": self.total_damage_received,
            "slime_kills": self.kills_by_type.get("slime", 0),
            "skeleton_kills": self.kills_by_type.get("skeleton", 0),
            "orc_kills": self.kills_by_type.get("orc", 0),
            "boss_kills": (self.kills_by_type.get("mini_boss_1", 0)
                           + self.kills_by_type.get("mini_boss_2", 0)
                           + self.kills_by_type.get("final_boss", 0)),
        }

        # Drop any stale row for this session, then append current one.
        existing_rows = []
        if os.path.exists(leaderboard_path):
            try:
                with open(leaderboard_path, "r", newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        if r.get("session_id") != str(self.session_id):
                            existing_rows.append(r)
            except (IOError, OSError):
                pass

        existing_rows.append(row)

        try:
            with open(leaderboard_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(existing_rows)
        except (IOError, OSError) as e:
            print(f"[StatsCollector] Failed to write leaderboard: {e}")

    # -- Summary helpers --
    def generate_summary(self):
        """Return a text summary of the current session."""
        pending = sum(len(r) for r in self.records.values())
        lines = [
            f"=== Session {self.session_id} ({self.player_name}) ===",
            f"  Peak Level:       {self.peak_level}",
            f"  Total Kills:      {self.total_kills}",
            f"  Damage Dealt:     {self.total_damage_dealt}",
            f"  Damage Received:  {self.total_damage_received}",
            f"  Kills by type:    {self.kills_by_type}",
            f"  Pending in memory: {pending} records (flushed on export)",
        ]
        return "\n".join(lines)

    def get_record_count(self):
        return {k: len(v) for k, v in self.records.items()}

    @classmethod
    def read_leaderboard(cls, top_n=10):
        """Load leaderboard.csv and return the top N rows."""
        path = os.path.join(cls.DATA_DIR, "leaderboard.csv")
        if not os.path.exists(path):
            return []
        rows = []
        try:
            with open(path, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    try:
                        r["peak_level"] = int(r.get("peak_level", 0))
                        r["total_kills"] = int(r.get("total_kills", 0))
                        r["total_damage_dealt"] = int(r.get("total_damage_dealt", 0))
                    except (ValueError, TypeError):
                        continue
                    rows.append(r)
        except (IOError, OSError):
            return []
        rows.sort(key=lambda r: (-r["peak_level"],
                                  -r["total_kills"],
                                  -r["total_damage_dealt"]))
        return rows[:top_n]