"""
main.py - Entry point for Deadline Dungeon
Top-Down 2D Real-Time Action RPG with dungeon tilemap and time pressure.
Controls: WASD move, Mouse aim, Left click attack, Right click skill
"""
import pygame
import sys
import math
from player import Player
from game_world import GameWorld
from stats_collector import StatsCollector
from ui import UI

SCREEN_W = 800
SCREEN_H = 600
FPS = 60
TITLE = "Deadline Dungeon"


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption(TITLE)
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        self.clock = pygame.time.Clock()
        self.ui = UI(SCREEN_W, SCREEN_H)
        self.game_state = "start"
        self._init_game()

    def _init_game(self):
        self.world = GameWorld()
        start_x, start_y = self.world.get_start_position()
        self.player = Player(start_x, start_y)
        self.stats = StatsCollector()
        self.camera_x = 0.0
        self.camera_y = 0.0
        self.level_up_flash = 0.0
        self.won = False

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            dt = min(dt, 0.05)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                self._handle_event(event)

            if self.game_state == "start":
                self.ui.draw_start_screen(self.screen)
            elif self.game_state == "playing":
                self._update(dt)
                self._draw()
            elif self.game_state == "game_over":
                self._draw()
                self.ui.draw_game_over(self.screen, self.won,
                                       self.player, self.world.timer)

            pygame.display.flip()

        self.stats.export_csv()
        print(self.stats.generate_summary())
        pygame.quit()
        sys.exit()

    def _handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if self.game_state == "start":
                if event.key == pygame.K_SPACE:
                    self.game_state = "playing"

            elif self.game_state == "game_over":
                if event.key == pygame.K_r:
                    self._init_game()
                    self.game_state = "playing"
                elif event.key == pygame.K_q:
                    self.stats.export_csv()
                    pygame.quit()
                    sys.exit()

            elif self.game_state == "playing":
                if self.world.state == "class_select":
                    if event.key == pygame.K_1:
                        self._select_class("Knight")
                    elif event.key == pygame.K_2:
                        self._select_class("Wizard")
                    elif event.key == pygame.K_3:
                        self._select_class("Archer")

        # Mouse click for combat
        if event.type == pygame.MOUSEBUTTONDOWN and self.game_state == "playing":
            if self.world.state != "class_select":
                if event.button == 1:  # Left click = attack
                    result = self.player.left_click()
                    if result:
                        self.stats.record_skill_use(
                            "attack", self.player.class_type,
                            False, result.get("damage", 0),
                            self.world.timer)
                elif event.button == 3:  # Right click = skill
                    result = self.player.right_click()
                    if result:
                        self.stats.record_skill_use(
                            "skill", self.player.class_type,
                            False, result.get("damage", 0),
                            self.world.timer)

    def _select_class(self, class_name):
        self.player.change_class(class_name)
        self.world.state = "playing"
        self.stats.record_event("class_selection", {
            "chosen_class": class_name,
            "level": self.player.level,
            "game_time": self.world.timer,
        })

    def _update(self, dt):
        if self.world.state == "class_select":
            return
        if self.world.state == "game_over":
            self.game_state = "game_over"
            return

        # Player input
        keys = pygame.key.get_pressed()
        dx, dy = 0, 0
        if keys[pygame.K_w] or keys[pygame.K_UP]:    dy -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:   dy += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:   dx -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:  dx += 1

        is_moving = dx != 0 or dy != 0

        # Remember old position for axis-separated collision
        old_x = self.player.x
        old_y = self.player.y
        self.player.move(dx, dy, dt, self.world.world_w, self.world.world_h)

        # Axis-separated wall collision: lets player slide along walls
        if self.world.tilemap.is_wall(self.player.x, self.player.y):
            new_x = self.player.x
            new_y = self.player.y
            # Try horizontal movement only (revert Y)
            if not self.world.tilemap.is_wall(new_x, old_y):
                self.player.y = old_y
            # Try vertical movement only (revert X)
            elif not self.world.tilemap.is_wall(old_x, new_y):
                self.player.x = old_x
            else:
                # Fully blocked in this direction — revert both
                self.player.x = old_x
                self.player.y = old_y

        # Mouse aiming
        mx, my = pygame.mouse.get_pos()
        self.player.update_facing(mx, my, SCREEN_W, SCREEN_H)

        # Walk/idle animation
        self.player.set_walk_or_idle(is_moving)

        # Update player
        self.player.update(dt, self.world.tilemap)

        # Update world
        events = self.world.update(dt, self.player)

        for event in events:
            if event == "victory":
                self.won = True
                self.game_state = "game_over"
                self.stats.record_session_outcome(
                    True, self.player.level, self.world.timer,
                    self.player.class_type, "Elite Orc",
                    self.world.timeout_triggered)

        # Collision: Player projectiles/melee → Enemies
        self._check_player_attacks()

        # Collision: Enemies → Player
        for enemy in self.world.enemies:
            damage = enemy.attack_player(self.player)
            if damage > 0:
                self.stats.record_damage_received(
                    enemy.attack, damage, enemy.enemy_type,
                    self.player.level, self.player.hp,
                    self.player.max_hp, self.world.timer)

        for boss in self.world.bosses:
            damage = boss.attack_player(self.player)
            if damage > 0:
                self.stats.record_damage_received(
                    boss.attack, damage, boss.boss_type,
                    self.player.level, self.player.hp,
                    self.player.max_hp, self.world.timer)

            # Boss special effect collision
            for effect in boss.get_special_effects()[:]:
                if effect["type"] == "shockwave" and not effect.get("hit"):
                    # Skip while charging up
                    if effect.get("impact_delay", 0) > 0:
                        continue
                    dist = math.hypot(effect["x"] - self.player.x,
                                      effect["y"] - self.player.y)
                    if abs(dist - effect["radius"]) < 30:
                        self.player.take_damage(int(effect["damage"]))
                        effect["hit"] = True
                elif effect["type"] == "boss_melee" and not effect.get("hit"):
                    dist = math.hypot(effect["x"] - self.player.x,
                                      effect["y"] - self.player.y)
                    if dist < effect["radius"] + self.player.width // 2:
                        self.player.take_damage(int(effect["damage"]))
                        effect["hit"] = True
                elif effect["type"] == "boss_projectile":
                    dist = math.hypot(effect["x"] - self.player.x,
                                      effect["y"] - self.player.y)
                    if dist < effect["radius"] + self.player.width // 2:
                        self.player.take_damage(int(effect["damage"]))
                        boss.remove_special_effect(effect)

        # Player death
        if not self.player.is_alive():
            self.game_state = "game_over"
            self.won = False
            # Record death cause
            last_killer = "unknown"
            for enemy in self.world.enemies + self.world.bosses:
                dist = math.hypot(enemy.x - self.player.x,
                                  enemy.y - self.player.y)
                if dist < 100:
                    last_killer = enemy.enemy_type
                    break
            self.stats.record_death(
                last_killer, 0, self.player.level,
                0, self.world.timer,
                max(0, GameWorld.MAX_TIME - self.world.timer))
            self.stats.record_session_outcome(
                False, self.player.level, self.world.timer,
                self.player.class_type, "none",
                self.world.timeout_triggered)

        # Stats: periodic sampling
        self.stats.update(dt, self.player, self.world.timer)

        # Level up flash
        if self.level_up_flash > 0:
            self.level_up_flash -= dt

        # Camera (smooth follow)
        target_cx = self.player.x - SCREEN_W // 2
        target_cy = self.player.y - SCREEN_H // 2
        lerp = 5.0 * dt
        self.camera_x += (target_cx - self.camera_x) * lerp
        self.camera_y += (target_cy - self.camera_y) * lerp
        self.camera_x = max(0, min(self.world.world_w - SCREEN_W, self.camera_x))
        self.camera_y = max(0, min(self.world.world_h - SCREEN_H, self.camera_y))

    def _check_player_attacks(self):
        all_targets = self.world.enemies + self.world.bosses

        # Projectile hits
        for proj in self.player.projectiles[:]:
            for target in all_targets:
                if not target.alive or target._is_dying:
                    continue
                if proj.get("pierce") and id(target) in proj.get("hit_targets", []):
                    continue

                dist = math.hypot(proj["x"] - target.x, proj["y"] - target.y)
                if dist < proj["radius"] + target.size:
                    total_dmg = proj["damage"]
                    prev_hp = target.hp
                    target.take_damage(total_dmg)

                    self.stats.record_damage_dealt(
                        total_dmg, proj.get("source", "attack"),
                        self.player.class_type, target.enemy_type,
                        self.player.level)

                    # Killed this hit?
                    if prev_hp > 0 and target.hp <= 0:
                        self._on_enemy_killed(target)

                    if proj.get("pierce"):
                        proj.setdefault("hit_targets", []).append(id(target))
                    else:
                        if proj in self.player.projectiles:
                            self.player.projectiles.remove(proj)
                        break

        # Melee + AoE hits (both stored in active_effects)
        for effect in self.player.active_effects[:]:
            if effect["type"] not in ("melee", "aoe"):
                continue
            # Each effect should only hit each enemy once
            hit_ids = effect.setdefault("hit_ids", [])
            for target in all_targets:
                if not target.alive or target._is_dying:
                    continue
                if id(target) in hit_ids:
                    continue
                dist = math.hypot(effect["x"] - target.x,
                                  effect["y"] - target.y)
                if dist < effect.get("radius", 50) + target.size:
                    total_dmg = effect["damage"]
                    prev_hp = target.hp
                    target.take_damage(total_dmg)
                    hit_ids.append(id(target))

                    self.stats.record_damage_dealt(
                        total_dmg, effect.get("source", "attack"),
                        self.player.class_type, target.enemy_type,
                        self.player.level)

                    if prev_hp > 0 and target.hp <= 0:
                        self._on_enemy_killed(target)

    def _on_enemy_killed(self, enemy):
        """Called once when enemy's HP reaches zero. Grants EXP."""
        exp = enemy.exp_reward

        levels = self.player.gain_exp(exp)

        self.stats.record_kill(enemy.enemy_type, self.player.level,
                               self.world.timer)
        self.stats.record_exp_gain(
            exp, enemy.enemy_type, self.player.total_exp,
            self.player.level, self.world.timer)

        for lv in levels:
            self.level_up_flash = 1.0
            self.world.level_up_timer = 1.0

    def _draw(self):
        self.screen.fill((10, 8, 12))

        cx, cy = self.camera_x, self.camera_y

        # Dungeon tilemap
        self.world.draw_ground(self.screen, cx, cy, SCREEN_W, SCREEN_H)

        # Enemies & Bosses
        self.world.draw_entities(self.screen, cx, cy)

        # Player attacks
        self.player.draw_attacks(self.screen, cx, cy)

        # Player
        self.player.draw(self.screen, cx, cy)

        # HUD
        self.ui.draw_hud(self.screen, self.player,
                          self.world.timer, GameWorld.MAX_TIME)

        # Boss HP bar
        for boss in self.world.bosses:
            if boss.alive:
                self.ui.draw_boss_hp_bar(self.screen, boss)

        # Level up flash
        if self.level_up_flash > 0:
            self.ui.draw_level_up_effect(self.screen, self.level_up_flash)

        # Class selection overlay
        if self.world.state == "class_select":
            self.ui.draw_class_selection(self.screen)


if __name__ == "__main__":
    game = Game()
    game.run()