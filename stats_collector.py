"""
stats_collector.py - StatsCollector class for Deadline Dungeon
Collects, stores, and exports gameplay statistics for analysis and visualization.
All 8 features produce meaningful data regardless of session length or outcome.
"""
import csv
import os
import time


class StatsCollector:
    """Collects and persists gameplay statistics across sessions."""

    DATA_DIR = "stats_data"

    def __init__(self):
        self.records = {
            "damage_dealt":          [],
            "damage_received":       [],
            "kills_per_level":       [],
            "hp_over_time":          [],
            "skill_usage":           [],
            "session_outcomes":      [],
            "exp_over_time":         [],
            "death_cause":           [],
        }

        self.session_id = int(time.time())
        self._kills_at_level = {}
        self._hp_sample_timer = 0.0
        self._hp_sample_interval = 2.0
        self._exp_sample_timer = 0.0
        self._exp_sample_interval = 3.0

        os.makedirs(self.DATA_DIR, exist_ok=True)

    def record_event(self, event_type, data):
        if event_type not in self.records:
            self.records[event_type] = []
        data["session_id"] = self.session_id
        data["timestamp"] = time.time()
        self.records[event_type].append(data)

    # Feature 1
    def record_damage_dealt(self, damage, skill_name, player_class, enemy_type, player_level):
        self.record_event("damage_dealt", {
            "damage": damage, "skill_name": skill_name,
            "player_class": player_class, "enemy_type": enemy_type,
            "player_level": player_level,
        })

    # Feature 2
    def record_damage_received(self, raw_damage, actual_damage, enemy_type,
                                player_level, player_hp, player_max_hp, game_time):
        self.record_event("damage_received", {
            "raw_damage": raw_damage, "actual_damage": actual_damage,
            "enemy_type": enemy_type, "player_level": player_level,
            "player_hp_after": player_hp, "player_max_hp": player_max_hp,
            "game_time": round(game_time, 2),
        })

    # Feature 3
    def record_kill(self, enemy_type, player_level, game_time):
        key = player_level
        self._kills_at_level[key] = self._kills_at_level.get(key, 0) + 1
        self.record_event("kills_per_level", {
            "player_level": player_level, "enemy_type": enemy_type,
            "total_at_level": self._kills_at_level[key],
            "game_time": round(game_time, 2),
        })

    # Feature 4
    def record_hp_sample(self, current_hp, max_hp, game_time, player_level):
        self.record_event("hp_over_time", {
            "current_hp": current_hp, "max_hp": max_hp,
            "hp_ratio": round(current_hp / max_hp, 3) if max_hp > 0 else 0,
            "game_time": round(game_time, 2), "player_level": player_level,
        })

    # Feature 5
    def record_skill_use(self, skill_name, player_class, hit, damage, game_time):
        self.record_event("skill_usage", {
            "skill_name": skill_name, "player_class": player_class,
            "hit": hit, "damage": damage, "game_time": round(game_time, 2),
        })

    # Feature 6
    def record_session_outcome(self, won, final_level, time_survived,
                                player_class, boss_defeated, timed_out):
        self.record_event("session_outcomes", {
            "won": won, "final_level": final_level,
            "time_survived": round(time_survived, 2),
            "player_class": player_class, "boss_defeated": boss_defeated,
            "timed_out": timed_out,
        })

    # Feature 7
    def record_exp_snapshot(self, total_exp, current_level, game_time):
        self.record_event("exp_over_time", {
            "total_exp": total_exp, "current_level": current_level,
            "game_time": round(game_time, 2),
        })

    def record_exp_gain(self, exp_gained, source_enemy, total_exp, current_level, game_time):
        self.record_event("exp_over_time", {
            "exp_gained": exp_gained, "source_enemy": source_enemy,
            "total_exp": total_exp, "current_level": current_level,
            "game_time": round(game_time, 2),
        })

    # Feature 8
    def record_death(self, killer_type, killer_attack, player_level,
                      player_hp_before, game_time, time_remaining):
        self.record_event("death_cause", {
            "killer_type": killer_type, "killer_attack": killer_attack,
            "player_level": player_level, "player_hp_before": player_hp_before,
            "game_time": round(game_time, 2),
            "time_remaining": round(time_remaining, 2),
        })

    # Called every frame from main.py
    def update(self, dt, player, game_time):
        """Periodic HP and EXP sampling."""
        self._hp_sample_timer += dt
        if self._hp_sample_timer >= self._hp_sample_interval:
            self._hp_sample_timer = 0.0
            self.record_hp_sample(player.hp, player.max_hp, game_time, player.level)

        self._exp_sample_timer += dt
        if self._exp_sample_timer >= self._exp_sample_interval:
            self._exp_sample_timer = 0.0
            self.record_exp_snapshot(player.total_exp, player.level, game_time)

    def export_csv(self):
        for feature_name, records in self.records.items():
            if not records:
                continue
            filepath = os.path.join(self.DATA_DIR, f"{feature_name}.csv")
            all_keys = set()
            for record in records:
                all_keys.update(record.keys())
            all_keys = sorted(all_keys)

            file_exists = os.path.exists(filepath)
            with open(filepath, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=all_keys)
                if not file_exists:
                    writer.writeheader()
                writer.writerows(records)

        total = sum(len(r) for r in self.records.values())
        print(f"[StatsCollector] Exported {total} records to {self.DATA_DIR}/")

    def generate_summary(self):
        lines = [f"=== Session {self.session_id} Summary ==="]
        for name, records in self.records.items():
            lines.append(f"  {name}: {len(records)} records")
        total = sum(len(r) for r in self.records.values())
        lines.append(f"  TOTAL: {total} records")
        return "\n".join(lines)

    def get_record_count(self):
        return {k: len(v) for k, v in self.records.items()}