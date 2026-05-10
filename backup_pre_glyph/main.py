"""
main.py - Entry point for Deadline Dungeon
Top-Down 2D Real-Time Action RPG with dungeon tilemap and time pressure.
Controls: WASD move, Mouse aim, Left click attack, Right click skill
"""
import pygame
import sys
import math
import os
import random
import subprocess
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
        # Use SCALED + DOUBLEBUF for consistent rendering on Mac/Retina displays.
        # SCALED tells pygame to scale the logical 780x720 surface to whatever
        # the display actually renders at, preventing stale-buffer artifacts
        # and incorrect window sizing on high-DPI screens.
        flags = pygame.SCALED | pygame.DOUBLEBUF
        try:
            self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), flags, vsync=1)
        except pygame.error:
            # Fallback if the display doesn't support vsync=1
            self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), flags)
        self.clock = pygame.time.Clock()
        self.ui = UI(SCREEN_W, SCREEN_H)
        self.game_state = "start"

        # Player name input state
        self.player_name = ""
        self.name_max_len = 14
        self._cursor_blink_timer = 0.0
        self._cursor_visible = True

        # Pause menu state
        self._pause_selected = 0
        # State to return to when resuming (could be "playing" or "dying")
        self._pre_pause_state = None

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

        # Screen shake state — trauma decays over time and the per-frame
        # offset is computed as trauma² so big hits feel disproportionately
        # bigger than light ones.
        self._shake_trauma = 0.0
        self._shake_offset_x = 0.0
        self._shake_offset_y = 0.0
        self._last_player_hp = self.player.hp

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
                # Blink cursor (toggle every 0.5s)
                self._cursor_blink_timer += dt
                if self._cursor_blink_timer >= 0.5:
                    self._cursor_blink_timer = 0.0
                    self._cursor_visible = not self._cursor_visible
                self.ui.draw_start_screen(self.screen, self.player_name,
                                          input_active=True,
                                          cursor_visible=self._cursor_visible)
            elif self.game_state in ("playing", "dying"):
                # "dying" keeps the world rendering so the death animation
                # plays out before the defeat screen appears.
                self._update(dt)
                self._draw()
            elif self.game_state == "paused":
                # Freeze the world, redraw the last frame under the overlay.
                self._draw()
                hover = self._pause_hover_action()
                self.ui.draw_pause_menu(self.screen,
                                        selected_index=self._pause_selected,
                                        hover_action=hover)
            elif self.game_state == "game_over":
                self._draw()
                self.ui.draw_game_over(self.screen, self.won,
                                       self.player, self.world.timer)

            pygame.display.flip()

        self.stats.export_csv()
        print(self.stats.generate_summary())
        pygame.quit()
        sys.exit()

    def _pause_hover_action(self):
        """Return the pause-menu action whose rect is under the mouse, or
        None if the cursor isn't over any button."""
        if self.game_state != "paused":
            return None
        mx, my = pygame.mouse.get_pos()
        for rect, action in self.ui.get_pause_button_rects():
            if rect.collidepoint(mx, my):
                return action
        return None

    def _pause_do_action(self, action):
        """Execute a pause-menu action."""
        if action == "resume":
            self.game_state = self._pre_pause_state or "playing"
            self._pre_pause_state = None
        elif action == "restart":
            self._init_game()
            self.stats.player_name = self.player_name.strip() or "Player"
            self.ui.reset_game_over_state()
            self._pre_pause_state = None
            self.game_state = "playing"
        elif action == "quit":
            try:
                self.stats.export_csv()
            except Exception:
                pass
            pygame.quit()
            sys.exit()

    def _launch_visualizer(self):
        """Open the matplotlib stats dashboard in a separate process.
        Flushes the current session's CSVs first so the dashboard sees the
        most recent data. The game keeps running in the background."""
        try:
            self.stats.export_csv()
        except Exception:
            pass
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            script_path = os.path.join(script_dir, "visualize.py")
            # Use the same Python interpreter that's running the game so we
            # don't accidentally pick up a different env without matplotlib.
            subprocess.Popen(
                [sys.executable, script_path],
                cwd=script_dir,
                # On Windows, detach so closing the dashboard doesn't kill
                # the game and vice versa.
                creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP
                               if os.name == "nt" else 0),
            )
        except Exception as e:
            print(f"[Visualizer] Failed to launch dashboard: {e}")

    # ───── Screen shake ─────────────────────────────────────────────
    # Trauma model: bigger hits add more trauma, trauma decays smoothly,
    # and on-screen offset uses trauma² so a 3× damage hit feels ~9× shakier.
    SHAKE_MAX_PIXELS = 18      # peak offset at trauma == 1.0
    SHAKE_DECAY = 1.6          # trauma units lost per second
    SHAKE_TRAUMA_CAP = 1.0

    def _add_shake_from_damage(self, damage):
        """Translate raw damage taken into a trauma bump.
        Light hits (slime nibble): ~0.15 trauma
        Mid hits (orc/skeleton):   ~0.30–0.45
        Heavy hits (boss melee):   ~0.60–0.80
        Devastating (boss specials, timeout enrage): up to 0.95
        """
        if damage <= 0:
            return
        bump = 0.12 + 0.025 * damage
        bump = min(0.95, bump)
        self._shake_trauma = min(self.SHAKE_TRAUMA_CAP,
                                 self._shake_trauma + bump)

    def _update_shake(self, dt):
        """Decay trauma and compute the current frame's shake offset."""
        if self._shake_trauma > 0.0:
            self._shake_trauma = max(0.0, self._shake_trauma - self.SHAKE_DECAY * dt)
        if self._shake_trauma > 0.0:
            intensity = (self._shake_trauma ** 2) * self.SHAKE_MAX_PIXELS
            self._shake_offset_x = random.uniform(-intensity, intensity)
            self._shake_offset_y = random.uniform(-intensity, intensity)
        else:
            self._shake_offset_x = 0.0
            self._shake_offset_y = 0.0

    def _toggle_pause(self):
        """Enter pause from gameplay, or leave pause if currently paused."""
        if self.game_state in ("playing", "dying"):
            self._pre_pause_state = self.game_state
            self._pause_selected = 0
            self.game_state = "paused"
        elif self.game_state == "paused":
            self.game_state = self._pre_pause_state or "playing"
            self._pre_pause_state = None

    def _handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if self.game_state == "start":
                # Ctrl+V on the start screen opens the stats dashboard
                # without consuming the keystroke as a name character.
                if event.key == pygame.K_v and (event.mod & pygame.KMOD_CTRL):
                    self._launch_visualizer()
                    return
                # Name input
                if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                    # Only start if name is non-empty
                    if self.player_name.strip():
                        self.stats.player_name = self.player_name.strip()
                        self.game_state = "playing"
                elif event.key == pygame.K_BACKSPACE:
                    self.player_name = self.player_name[:-1]
                else:
                    # Accept printable characters
                    ch = event.unicode
                    if ch and ch.isprintable() and len(self.player_name) < self.name_max_len:
                        # Allow letters, digits, space, basic punctuation
                        if ch.isalnum() or ch in (" ", "_", "-", "."):
                            self.player_name += ch

            elif self.game_state == "game_over":
                if event.key == pygame.K_r:
                    self._init_game()
                    self.stats.player_name = self.player_name.strip() or "Player"
                    # Reset UI state so next game-over re-seeds particles /
                    # replays entrance animation.
                    self.ui.reset_game_over_state()
                    self.game_state = "playing"
                elif event.key == pygame.K_v:
                    # Open the stats dashboard in a side window
                    self._launch_visualizer()
                elif event.key == pygame.K_q:
                    self.stats.export_csv()
                    pygame.quit()
                    sys.exit()

            elif self.game_state == "paused":
                # Pause menu keyboard navigation
                entries = self.ui.PAUSE_ENTRIES
                if event.key == pygame.K_ESCAPE:
                    self._toggle_pause()
                elif event.key in (pygame.K_UP, pygame.K_w):
                    self._pause_selected = (self._pause_selected - 1) % len(entries)
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    self._pause_selected = (self._pause_selected + 1) % len(entries)
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER,
                                   pygame.K_SPACE):
                    action = entries[self._pause_selected][1]
                    self._pause_do_action(action)

            elif self.game_state in ("playing", "dying"):
                # ESC toggles pause from any gameplay sub-state
                if event.key == pygame.K_ESCAPE:
                    self._toggle_pause()
                    return
                # Class selection (only meaningful in playing)
                if self.game_state == "playing" and self.world.state == "class_select":
                    if event.key == pygame.K_1:
                        self._select_class("Knight")
                    elif event.key == pygame.K_2:
                        self._select_class("Wizard")
                    elif event.key == pygame.K_3:
                        self._select_class("Archer")
                elif self.game_state == "playing":
                    # Keyboard alternatives for attack/skill (Mac users etc.)
                    # Q = attack (like left click), E = skill (like right click)
                    if event.key == pygame.K_q:
                        result = self.player.left_click()
                        if result:
                            self.stats.record_skill_use(
                                "attack", self.player.class_type,
                                False, result.get("damage", 0),
                                self.world.timer)
                    elif event.key == pygame.K_e:
                        result = self.player.right_click()
                        if result:
                            self.stats.record_skill_use(
                                "skill", self.player.class_type,
                                False, result.get("damage", 0),
                                self.world.timer)

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

        # Mouse click on pause menu buttons
        if event.type == pygame.MOUSEBUTTONDOWN and self.game_state == "paused":
            if event.button == 1:
                mx, my = event.pos
                for rect, action in self.ui.get_pause_button_rects():
                    if rect.collidepoint(mx, my):
                        self._pause_do_action(action)
                        break

    def _select_class(self, class_name):
        self.player.change_class(class_name)
        self.world.state = "playing"
        # Log class selection as a skill_usage row so it appears in stats
        self.stats.record_skill_use(
            "class_change_to_" + class_name,
            class_name,
            True, 0, self.world.timer)

    def _update(self, dt):
        # "dying" — player is dead and we're waiting for the death animation
        # to finish. Tick animations / camera only; no input / no new damage.
        if self.game_state == "dying":
            self.player.update(dt, self.world.tilemap)
            self.world.update(dt, self.player)

            target_cx = self.player.x - SCREEN_W // 2
            target_cy = self.player.y - SCREEN_H // 2
            lerp = 5.0 * dt
            self.camera_x += (target_cx - self.camera_x) * lerp
            self.camera_y += (target_cy - self.camera_y) * lerp
            self.camera_x = max(0, min(self.world.world_w - SCREEN_W, self.camera_x))
            self.camera_y = max(0, min(self.world.world_h - SCREEN_H, self.camera_y))

            # Keep the shake easing out smoothly during the death animation.
            self._update_shake(dt)

            if getattr(self.player, "death_complete", False):
                self.game_state = "game_over"
            return

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

        # Hitbox is at the FEET (lower portion of sprite), not center
        # Sprite is drawn with character's body upper half near y-center
        # and feet ~14-16px below center. Hitbox represents physical footprint.
        old_x = self.player.x
        old_y = self.player.y
        self.player.move(dx, dy, dt, self.world.world_w, self.world.world_h)

        def has_wall_at(x, y):
            """Check footprint box at the character's feet."""
            tm = self.world.tilemap
            fw = 10         # half-width of physical body (narrow)
            foot_top = 4    # hitbox top = 4px below center
            foot_bot = 22   # hitbox bottom = 22px below center (at feet)
            return (tm.is_wall(x - fw, y + foot_top) or
                    tm.is_wall(x + fw, y + foot_top) or
                    tm.is_wall(x - fw, y + foot_bot) or
                    tm.is_wall(x + fw, y + foot_bot))

        if has_wall_at(self.player.x, self.player.y):
            new_x = self.player.x
            new_y = self.player.y
            if not has_wall_at(new_x, old_y):
                self.player.y = old_y
            elif not has_wall_at(old_x, new_y):
                self.player.x = old_x
            else:
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

        # Find the last defeated boss name from this tick's events (if any)
        # so the victory log records which variant the player actually beat.
        last_boss_name = None
        from boss import Boss as _Boss
        for event in events:
            if isinstance(event, tuple) and len(event) == 2 and event[0] == "boss_defeated":
                tpl = _Boss.BOSS_TEMPLATES.get(event[1])
                if tpl:
                    last_boss_name = tpl.get("name", event[1])

        for event in events:
            if event == "victory":
                self.won = True
                self.game_state = "game_over"
                self.stats.record_session_outcome(
                    True, self.player.level, self.world.timer,
                    self.player.class_type,
                    last_boss_name or "Final Boss",
                    self.world.timeout_triggered)
                # Export immediately so data is saved even if user force-closes
                self.stats.export_csv(verbose=False)

        # Collision: Player projectiles/melee → Enemies
        self._check_player_attacks()

        # Collision: Enemies → Player
        for enemy in self.world.enemies:
            # Start attack if in range (this queues damage, returns 0)
            enemy.attack_player(self.player)
            # Release queued damage if animation timer hit
            damage = enemy._release_pending_attack_if_due(dt, self.player)
            if damage > 0:
                self.stats.record_damage_received(
                    enemy.attack, damage, enemy.enemy_type,
                    self.player.level, self.player.hp,
                    self.player.max_hp, self.world.timer)

        for boss in self.world.bosses:
            boss.attack_player(self.player)
            damage = boss._release_pending_attack_if_due(dt, self.player)
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

        # Detect HP loss this frame and convert it into screen-shake trauma.
        # We diff against a stored last_hp instead of summing damage at every
        # call site so heals/regen don't accidentally trigger shake either.
        hp_lost = max(0, self._last_player_hp - self.player.hp)
        if hp_lost > 0:
            self._add_shake_from_damage(hp_lost)
        self._last_player_hp = self.player.hp

        # Tick the shake state every frame so trauma decays smoothly.
        self._update_shake(dt)

        # Player death — transition to the "dying" animation state rather
        # than immediately showing the defeat screen. The "dying" branch at
        # the top of _update() will flip the state to "game_over" once the
        # death animation finishes (see Player.death_complete).
        if not self.player.is_alive() and self.game_state != "dying":
            self.game_state = "dying"
            self.won = False
            # Record death cause now so stats are preserved even if the
            # user closes the window during the death animation.
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
            # Export immediately so data is saved even if user force-closes
            self.stats.export_csv(verbose=False)

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

        # World gets the shake offset so the dungeon, enemies and player all
        # appear to jolt together. HUD/minimap/boss-bar are intentionally
        # drawn at the un-shaken camera so on-screen text stays readable.
        cx = self.camera_x + self._shake_offset_x
        cy = self.camera_y + self._shake_offset_y

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

        # Minimap (top-right)
        self.ui.draw_minimap(self.screen, self.player,
                             self.world.enemies, self.world.bosses,
                             self.world.tilemap)

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