"""
game_world.py - GameWorld class for Deadline Dungeon
Manages the game map, enemy spawning, session timer, and milestone events.
"""
import pygame
import math
import random
from enemy import Enemy
from boss import Boss


class GameWorld:
    """Manages the world, spawning, timer, and game progression."""

    MAX_TIME = 600.0  # 10 minutes

    SPAWN_TABLE = {
        1:  ["slime"],
        3:  ["slime", "skeleton"],
        8:  ["skeleton", "slime"],
        14: ["skeleton", "orc"],
        22: ["orc", "skeleton"],
    }

    def __init__(self, world_w=2000, world_h=2000):
        # Create dungeon tilemap
        from tilemap import TileMap
        self.tilemap = TileMap(42, 42, "Dungeon_Tileset.png")
        self.world_w = self.tilemap.world_w
        self.world_h = self.tilemap.world_h

        self.timer = 0.0
        self.enemies = []
        self.bosses = []

        self.spawn_timer = 0.0
        self.spawn_interval = 2.5
        self.max_enemies = 12

        self.state = "playing"
        self.boss_active = False

        self.mini_boss_1_spawned = False
        self.mini_boss_1_defeated = False
        self.mini_boss_2_spawned = False
        self.mini_boss_2_defeated = False
        self.final_boss_spawned = False
        self.final_boss_defeated = False
        self.timeout_triggered = False

        self.level_up_timer = 0.0

    def get_start_position(self):
        """Get player start position from tilemap."""
        return self.tilemap.get_start_position()

    def _get_available_enemies(self, player_level):
        result = ["slime"]
        for threshold, types in sorted(self.SPAWN_TABLE.items()):
            if player_level >= threshold:
                result = types
        return result

    def spawn_enemy(self, player):
        if len(self.enemies) >= self.max_enemies:
            return

        # Try to spawn on a walkable tile away from player
        for _ in range(30):
            x, y = self.tilemap.get_spawn_position()
            dist = math.hypot(x - player.x, y - player.y)
            if 200 < dist < 800 and self.tilemap.is_walkable(x, y):
                break

        types = self._get_available_enemies(player.level)
        enemy_type = random.choice(types)
        enemy = Enemy(x, y, enemy_type, level_scale=player.level)
        self.enemies.append(enemy)

    def _spawn_boss(self, boss_type, player, enraged=False):
        # Spawn boss in a room far from player
        bx, by = self.tilemap.get_boss_spawn(player.x, player.y)

        boss = Boss(bx, by, boss_type, enraged=enraged)
        self.bosses.append(boss)
        self.boss_active = True

        for enemy in self.enemies[:]:
            d = math.hypot(enemy.x - bx, enemy.y - by)
            if d < 200:
                self.enemies.remove(enemy)

    def check_milestones(self, player):
        events = []

        if player.level >= 10 and not self.mini_boss_1_spawned:
            self.mini_boss_1_spawned = True
            self._spawn_boss("mini_boss_1", player)
            events.append("mini_boss_1_spawn")

        if (player.level >= 20 and not self.mini_boss_2_spawned
                and self.mini_boss_1_defeated):
            self.mini_boss_2_spawned = True
            self._spawn_boss("mini_boss_2", player)
            events.append("mini_boss_2_spawn")

        if (player.level >= 30 and not self.final_boss_spawned
                and self.mini_boss_2_defeated):
            self.final_boss_spawned = True
            self._spawn_boss("final_boss", player)
            events.append("final_boss_spawn")

        if (self.timer >= self.MAX_TIME and not self.final_boss_spawned
                and not self.timeout_triggered):
            self.timeout_triggered = True
            self.final_boss_spawned = True
            self._spawn_boss("final_boss", player, enraged=True)
            events.append("timeout_boss_spawn")

        return events

    def update(self, dt, player):
        if self.state == "class_select" or self.state == "game_over":
            return []

        self.timer += dt
        events = []

        if self.level_up_timer > 0:
            self.level_up_timer -= dt

        milestone_events = self.check_milestones(player)
        events.extend(milestone_events)

        self.spawn_timer -= dt
        spawn_rate = self.spawn_interval * (2.0 if self.boss_active else 1.0)
        if self.spawn_timer <= 0 and not self.boss_active:
            self.spawn_timer = spawn_rate
            self.spawn_enemy(player)

        for enemy in self.enemies[:]:
            enemy.update(dt, player.x, player.y, self.world_w, self.world_h,
                         self.tilemap)
            if not enemy.alive:
                self.enemies.remove(enemy)

        for boss in self.bosses[:]:
            boss.update(dt, player.x, player.y, self.world_w, self.world_h,
                        self.tilemap)
            if not boss.alive:
                self.bosses.remove(boss)
                self.boss_active = len(self.bosses) > 0
                events.append(("boss_defeated", boss.boss_type))

                if boss.boss_type == "mini_boss_1":
                    self.mini_boss_1_defeated = True
                    self.state = "class_select"
                    events.append("class_select")
                elif boss.boss_type == "mini_boss_2":
                    self.mini_boss_2_defeated = True
                elif boss.boss_type == "final_boss":
                    self.final_boss_defeated = True
                    self.state = "game_over"
                    events.append("victory")

        time_factor = self.timer / self.MAX_TIME
        self.max_enemies = int(12 + time_factor * 8)
        self.spawn_interval = max(1.0, 2.5 - time_factor * 1.0)

        return events

    def draw_ground(self, surface, camera_x, camera_y, screen_w, screen_h):
        self.tilemap.draw(surface, camera_x, camera_y, screen_w, screen_h)

    def draw_entities(self, surface, camera_x, camera_y):
        for enemy in self.enemies:
            enemy.draw(surface, camera_x, camera_y)
        for boss in self.bosses:
            boss.draw(surface, camera_x, camera_y)