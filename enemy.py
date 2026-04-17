"""
enemy.py - Enemy class for Deadline Dungeon
Base class for all enemy types with AI behavior, combat stats, and sprite animation.
Normal enemies have: idle, walk, attack, hurt, death (NO special)
"""
import pygame
import math
import random
import os
from animation import SpriteAnimator


class Enemy:
    """Base enemy with chase AI, attack behavior, and sprite animation."""

    SPRITE_FOLDERS = {
        "slime":    "slime",
        "skeleton": "skeleton",
        "orc":      "orc",
    }

    def __init__(self, x, y, enemy_type="slime", level_scale=1):
        self.x = x
        self.y = y
        self.enemy_type = enemy_type
        self.level_scale = level_scale

        templates = {
            "slime":   {"hp": 25,  "attack": 6,  "speed": 55,  "exp": 12,
                        "size": 18, "color": (80, 200, 80),  "atk_cd": 1.2,
                        "pixel_scale": 3.0},
            "skeleton":{"hp": 50,  "attack": 14, "speed": 70,  "exp": 25,
                        "size": 20, "color": (220, 220, 200),"atk_cd": 1.3,
                        "pixel_scale": 3.0},
            "orc":     {"hp": 85,  "attack": 20, "speed": 75,  "exp": 40,
                        "size": 24, "color": (100, 160, 60), "atk_cd": 1.0,
                        "pixel_scale": 3.0},
        }

        t = templates.get(enemy_type, templates["slime"])
        scale = 1 + (level_scale - 1) * 0.15

        self.max_hp = int(t["hp"] * scale)
        self.hp = self.max_hp
        self.attack = int(t["attack"] * scale)
        self.speed = t["speed"]
        self.exp_reward = int(t["exp"] * scale)
        self.size = t["size"]
        self.color = t["color"]
        self.attack_cooldown = t["atk_cd"]

        self._attack_timer = 0.0
        self._wander_angle = random.uniform(0, math.pi * 2)
        self._wander_timer = random.uniform(1, 3)
        self.hit_flash = 0.0
        self.alive = True

        # Direction and animation state
        self.direction = "right"
        self.anim_state = "idle"  # idle, walk, attack, hurt, death
        self._hurt_timer = 0.0
        self._death_timer = 0.0
        self._is_dying = False

        # Detection / aggro range
        self.detect_range = 200
        self.attack_range = 30

        # Load sprites
        sprite_folder = self.SPRITE_FOLDERS.get(enemy_type, enemy_type)
        sprite_path = os.path.join("images", "enemies", sprite_folder)
        self.animator = SpriteAnimator(sprite_path, pixel_scale=t.get("pixel_scale", 3.0))
        self.has_sprites = self.animator.loaded

    @property
    def rect(self):
        return pygame.Rect(self.x - self.size, self.y - self.size,
                           self.size * 2, self.size * 2)

    def _update_animation(self, new_state):
        """Change animation state and update animator."""
        if new_state != self.anim_state or self.anim_state in ("attack", "hurt"):
            self.anim_state = new_state
            if self.has_sprites:
                self.animator.set_action(new_state, force=True)

    def update(self, dt, player_x, player_y, world_w, world_h, tilemap=None):
        """Update AI: chase player if close, wander otherwise.
        If tilemap provided, avoid walking through walls (slide along them)."""
        # Death animation
        if self._is_dying:
            self._death_timer -= dt
            if self.has_sprites:
                self.animator.update(dt)
            if self._death_timer <= 0:
                self.alive = False
            return

        if not self.alive:
            return

        self._attack_timer = max(0, self._attack_timer - dt)
        self.hit_flash = max(0, self.hit_flash - dt)

        # Hurt stun
        if self._hurt_timer > 0:
            self._hurt_timer -= dt
            if self.has_sprites:
                self.animator.update(dt)
            if self._hurt_timer <= 0 and self.anim_state == "hurt":
                self._update_animation("idle")
            return

        # If attack animation is still playing, wait
        if self.anim_state == "attack":
            if self.has_sprites:
                self.animator.update(dt)
                if self.animator.is_action_finished():
                    self._update_animation("idle")
                else:
                    return
            else:
                self._update_animation("idle")

        prev_x = self.x
        prev_y = self.y
        dist = math.hypot(player_x - self.x, player_y - self.y)

        # Compute desired movement
        move_dx = 0.0
        move_dy = 0.0
        if dist < self.detect_range:
            if dist > 0:
                move_dx = (player_x - self.x) / dist * self.speed * dt
                move_dy = (player_y - self.y) / dist * self.speed * dt
        else:
            self._wander_timer -= dt
            if self._wander_timer <= 0:
                self._wander_angle = random.uniform(0, math.pi * 2)
                self._wander_timer = random.uniform(1.5, 3.5)
            move_dx = math.cos(self._wander_angle) * self.speed * 0.3 * dt
            move_dy = math.sin(self._wander_angle) * self.speed * 0.3 * dt

        # Apply movement with wall collision
        if tilemap:
            new_x = self.x + move_dx
            new_y = self.y + move_dy

            if not tilemap.is_wall(new_x, new_y):
                self.x = new_x
                self.y = new_y
            elif not tilemap.is_wall(new_x, self.y):
                # Slide horizontally
                self.x = new_x
            elif not tilemap.is_wall(self.x, new_y):
                # Slide vertically
                self.y = new_y
            elif dist < self.detect_range and dist > 0:
                # Chasing and blocked — try perpendicular direction to go around
                # Try the two perpendicular directions, pick whichever is walkable
                perp_dx = -move_dy
                perp_dy = move_dx
                test_x = self.x + perp_dx
                test_y = self.y + perp_dy
                if not tilemap.is_wall(test_x, test_y):
                    self.x = test_x
                    self.y = test_y
                else:
                    # Try opposite perpendicular
                    test_x = self.x - perp_dx
                    test_y = self.y - perp_dy
                    if not tilemap.is_wall(test_x, test_y):
                        self.x = test_x
                        self.y = test_y
                    # else: stay in place
        else:
            self.x += move_dx
            self.y += move_dy

        # Clamp to world
        self.x = max(self.size, min(world_w - self.size, self.x))
        self.y = max(self.size, min(world_h - self.size, self.y))

        # Update direction based on actual movement
        move_dx_actual = self.x - prev_x
        if abs(move_dx_actual) > 0.1:
            new_dir = "right" if move_dx_actual > 0 else "left"
            if new_dir != self.direction:
                self.direction = new_dir
                if self.has_sprites:
                    self.animator.set_direction(self.direction)

        # Update animation state
        is_moving = abs(move_dx_actual) > 0.5 or abs(self.y - prev_y) > 0.5 or dist < self.detect_range
        if is_moving and self.anim_state != "walk":
            self._update_animation("walk")
        elif not is_moving and self.anim_state != "idle":
            self._update_animation("idle")

        if self.has_sprites:
            self.animator.update(dt)

    def attack_player(self, player):
        """Try to attack the player if in range and cooldown ready."""
        if not self.alive or self._attack_timer > 0 or self._is_dying:
            return 0

        dist = math.hypot(player.x - self.x, player.y - self.y)
        if dist < self.attack_range + player.width // 2 + self.size:
            self._attack_timer = self.attack_cooldown

            # Face the player
            self.direction = "right" if player.x > self.x else "left"
            if self.has_sprites:
                self.animator.set_direction(self.direction)
            self._update_animation("attack")

            damage = player.take_damage(self.attack)
            return damage
        return 0

    def take_damage(self, amount):
        """Receive damage."""
        if not self.alive or self._is_dying:
            return 0

        actual = max(1, amount)
        self.hp -= actual
        self.hit_flash = 0.15

        if self.hp <= 0:
            self.hp = 0
            self._start_death()
        else:
            self._hurt_timer = 0.3
            self._update_animation("hurt")

        return actual

    def _start_death(self):
        """Begin death animation."""
        self._is_dying = True
        self._death_timer = 0.6
        self._update_animation("death")

    def on_death(self):
        self.alive = False
        return self.exp_reward

    def draw(self, surface, camera_x, camera_y):
        """Draw enemy using sprites or circle fallback."""
        if not self.alive and not self._is_dying:
            return

        sx = int(self.x - camera_x)
        sy = int(self.y - camera_y)

        if self.has_sprites:
            self.animator.draw(surface, self.x, self.y, camera_x, camera_y)
        else:
            # Fallback circle
            color = (255, 255, 255) if self.hit_flash > 0 else self.color
            if self._is_dying:
                alpha = int(255 * (self._death_timer / 0.6))
                color = tuple(min(255, c + (255 - c) * (1 - alpha / 255)) for c in self.color)

            pygame.draw.circle(surface, color, (sx, sy), self.size)
            pygame.draw.circle(surface, (30, 30, 30), (sx, sy), self.size, 2)
            eye_offset = self.size // 3
            pygame.draw.circle(surface, (20, 20, 20), (sx - eye_offset, sy - 3), 3)
            pygame.draw.circle(surface, (20, 20, 20), (sx + eye_offset, sy - 3), 3)

        # HP bar
        if self.hp < self.max_hp and not self._is_dying:
            bar_w = self.size * 2
            bar_h = 4
            bx = sx - bar_w // 2
            by = sy - self.size - 10
            ratio = self.hp / self.max_hp
            pygame.draw.rect(surface, (60, 0, 0), (bx, by, bar_w, bar_h))
            pygame.draw.rect(surface, (220, 40, 40),
                             (bx, by, int(bar_w * ratio), bar_h))