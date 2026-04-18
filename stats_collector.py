"""
stats_collector.py - StatsCollector class for Deadline Dungeon
Collects, stores, and exports gameplay statistics to CSV files.

Exports 9 CSV files to the `stats_data/` folder:
1. damage_dealt.csv         - every hit player lands
2. damage_received.csv      - every hit player takes
3. kills_per_level.csv      - every enemy killed
4. hp_over_time.csv         - HP sampled every 2s
5. skill_usage.csv          - every click (attack / skill)
6. session_outcomes.csv     - win/loss summary per session
7. exp_over_time.csv        - EXP gain events + periodic snapshots
8. death_cause.csv          - what killed the player
9. leaderboard.csv          - aggregated per-session stats for ranking

All rows include `session_id`, `player_name`, and `timestamp` for joining.
"""
import csv
import os
import time
from datetime import datetime


class StatsCollector:
    """Collects and persists gameplay statistics to CSV files."""

    DATA_DIR = "stats_data"

    # Ordered column definitions for each CSV file
    # First 3 columns are always: session_id, player_name, timestamp
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

        # Session info
        self.session_id = int(time.time())
        self.session_start = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.player_name = "Player"

        # Aggregated stats (for leaderboard)
        self.total_damage_dealt = 0
        self.total_damage_received = 0
        self.total_kills = 0
        self.peak_level = 1
        self.kills_by_type = {}

        # Sampling timers
        self._kills_at_level = {}
        self._hp_sample_timer = 0.0
        self._hp_sample_interval = 2.0
        self._exp_sample_timer = 0.0
        self._exp_sample_interval = 3.0

        # Auto-save timer (flush to disk every 30s to prevent data loss)
        self._autosave_timer = 0.0
        self._autosave_interval = 30.0

        os.makedirs(self.DATA_DIR, exist_ok=True)

    def _record_event(self, event_type, data):
        """Append a record with common fields."""
        data["session_id"] = self.session_id
        data["player_name"] = self.player_name
        data["timestamp"] = round(time.time(), 2)
        self.records[event_type].append(data)

    # -------- Feature 1: Damage Dealt --------
    def record_damage_dealt(self, damage, skill_name, player_class, enemy_type, player_level):
        self._record_event("damage_dealt", {
            "damage": damage,
            "skill_name": skill_name,
            "player_class": player_class,
            "enemy_type": enemy_type,
            "player_level": player_level,
        })
        self.total_damage_dealt += damage

    # -------- Feature 2: Damage Received --------
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

    # -------- Feature 3: Kills Per Level --------
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

    # -------- Feature 4: HP Over Time --------
    def record_hp_sample(self, current_hp, max_hp, game_time, player_level):
        self._record_event("hp_over_time", {
            "current_hp": current_hp,
            "max_hp": max_hp,
            "hp_ratio": round(current_hp / max_hp, 3) if max_hp > 0 else 0.0,
            "player_level": player_level,
            "game_time": round(game_time, 2),
        })

    # -------- Feature 5: Skill Usage --------
    def record_skill_use(self, skill_name, player_class, hit, damage, game_time):
        self._record_event("skill_usage", {
            "skill_name": skill_name,
            "player_class": player_class,
            "hit": bool(hit),
            "damage": damage,
            "game_time": round(game_time, 2),
        })

    # -------- Feature 6: Session Outcomes --------
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

    # -------- Feature 7: EXP Over Time --------
    def record_exp_snapshot(self, total_exp, current_level, game_time):
        """Periodic EXP sample (event_type='snapshot')."""
        self._record_event("exp_over_time", {
            "event_type": "snapshot",
            "total_exp": total_exp,
            "current_level": current_level,
            "exp_gained": 0,
            "source_enemy": "",
            "game_time": round(game_time, 2),
        })

    def record_exp_gain(self, exp_gained, source_enemy, total_exp, current_level, game_time):
        """EXP gain event (event_type='gain')."""
        self._record_event("exp_over_time", {
            "event_type": "gain",
            "total_exp": total_exp,
            "current_level": current_level,
            "exp_gained": exp_gained,
            "source_enemy": source_enemy,
            "game_time": round(game_time, 2),
        })

    # -------- Feature 8: Death Cause --------
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

    # -------- Per-frame update --------
    def update(self, dt, player, game_time):
        """Sample HP periodically, EXP periodically, and auto-save to CSV."""
        self._hp_sample_timer += dt
        if self._hp_sample_timer >= self._hp_sample_interval:
            self._hp_sample_timer = 0.0
            self.record_hp_sample(player.hp, player.max_hp, game_time, player.level)

        self._exp_sample_timer += dt
        if self._exp_sample_timer >= self._exp_sample_interval:
            self._exp_sample_timer = 0.0
            self.record_exp_snapshot(player.total_exp, player.level, game_time)

        # Auto-flush to disk every 30s so crashes don't lose data
        self._autosave_timer += dt
        if self._autosave_timer >= self._autosave_interval:
            self._autosave_timer = 0.0
            self.export_csv(verbose=False)

    # -------- CSV Export --------
    def export_csv(self, verbose=True):
        """Append all pending records to CSV files.
        After export, clears in-memory records so next auto-save doesn't duplicate.
        """
        total_exported = 0
        for feature_name, records in self.records.items():
            if not records:
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
                    writer.writerows(records)
                total_exported += len(records)
            except (IOError, OSError) as e:
                if verbose:
                    print(f"[StatsCollector] Failed to write {feature_name}.csv: {e}")
                continue

            # Clear in-memory records after successful export
            self.records[feature_name] = []

        # Also write/update leaderboard summary
        self._export_leaderboard()

        if verbose:
            print(f"[StatsCollector] Exported {total_exported} records to {self.DATA_DIR}/")

    def _export_leaderboard(self):
        """Append or update this session's row in leaderboard.csv."""
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

        # Read existing leaderboard, remove any old row for this session_id
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

        # Rewrite full leaderboard (so we can update the current session's row)
        try:
            with open(leaderboard_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(existing_rows)
        except (IOError, OSError) as e:
            print(f"[StatsCollector] Failed to write leaderboard: {e}")

    # -------- Summary helpers --------
    def generate_summary(self):
        """Text summary of the session."""
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
        """Static helper: read leaderboard and return top N sorted by peak_level then kills."""
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