"""
boss.py - Boss class for Deadline Dungeon
Extends Enemy with multi-phase combat, special attacks, and enrage.
Bosses have: idle, walk, attack, hurt, death, AND special (extra animation)
"""
import pygame
import math
import random
import os
from enemy import Enemy
from animation import SpriteAnimator


class Boss(Enemy):
    """Boss enemy with phases, special attacks, and enrage mechanics."""

    BOSS_TEMPLATES = {
        "mini_boss_1": {
            "name": "Greatsword Skeleton",
            "hp": 350, "attack": 18, "speed": 70, "exp": 100,
            "size": 34, "color": (220, 210, 180), "atk_cd": 1.0,
            "phases": 2, "sprite_folder": "Greatsword Skeleton",
            "pixel_scale": 4.0,
        },
        "mini_boss_2": {
            "name": "Werewolf",
            "hp": 700, "attack": 28, "speed": 95, "exp": 200,
            "size": 38, "color": (120, 80, 50), "atk_cd": 0.7,
            "phases": 2, "sprite_folder": "werewolf",
            "pixel_scale": 4.5,
        },
        "final_boss": {
            "name": "Elite Orc",
            "hp": 1200, "attack": 35, "speed": 80, "exp": 500,
            "size": 46, "color": (60, 120, 40), "atk_cd": 0.7,
            "phases": 3, "sprite_folder": "EliteOrc",
            "pixel_scale": 5.0,
        },
    }

    def __init__(self, x, y, boss_type="mini_boss_1", enraged=False):
        # Init base Enemy with slime defaults first
        super().__init__(x, y, "slime", 1)

        self.boss_type = boss_type
        t = self.BOSS_TEMPLATES.get(boss_type, self.BOSS_TEMPLATES["mini_boss_1"])

        # Override stats
        self.boss_name = t["name"]
        self.max_hp = t["hp"]
        self.hp = self.max_hp
        self.attack = t["attack"]
        self.speed = t["speed"]
        self.exp_reward = t["exp"]
        self.size = t["size"]
        self.color = t["color"]
        self.attack_cooldown = t["atk_cd"]
        self.max_phases = t["phases"]

        self.enemy_type = boss_type
        self.detect_range = 500

        # Enrage (when timer runs out)
        self.enraged = enraged
        if enraged:
            self.max_hp = int(self.max_hp * 1.5)
            self.hp = self.max_hp
            self.attack = int(self.attack * 1.3)
            self.speed = int(self.speed * 1.2)

        # Phase system
        self.phase = 1
        self.phase_thresholds = self._calculate_thresholds()

        # Special attack
        self.special_timer = 0.0
        self.special_cooldown = 4.0
        self._special_effects = []
        self._using_special = False

        # Visual
        self._pulse_timer = 0.0
        self.attack_range = 40

        # Load boss sprites (override enemy sprites)
        sprite_folder = t.get("sprite_folder", boss_type)
        sprite_path = os.path.join("images", "enemies", sprite_folder)
        px_scale = t.get("pixel_scale", 4.0)
        self.animator = SpriteAnimator(sprite_path, pixel_scale=px_scale)
        self.has_sprites = self.animator.loaded
        self.has_special_anim = self.animator.has_action("special")

    def _calculate_thresholds(self):
        thresholds = []
        for i in range(1, self.max_phases):
            thresholds.append(self.max_hp * (1 - i / self.max_phases))
        return thresholds

    def phase_transition(self):
        for i, threshold in enumerate(self.phase_thresholds):
            if self.hp <= threshold and self.phase <= i + 1:
                self.phase = i + 2
                self._on_phase_change()
                return True
        return False

    def _on_phase_change(self):
        self.attack = int(self.attack * 1.15)
        self.speed = int(self.speed * 1.1)
        self.special_cooldown = max(1.5, self.special_cooldown * 0.8)

    def special_attack(self, player_x, player_y):
        """Execute a special attack with special animation."""
        if self.special_timer > 0 or self._using_special:
            return None

        self.special_timer = self.special_cooldown
        self._using_special = True

        # Play special animation
        self.direction = "right" if player_x > self.x else "left"
        self.anim_state = "special"
        if self.has_sprites and self.has_special_anim:
            self.animator.set_direction(self.direction)
            self.animator.set_action("special", force=True)

        attack_type = random.choice(["charge", "shockwave", "volley"])

        if attack_type == "charge":
            dx = player_x - self.x
            dy = player_y - self.y
            dist = math.hypot(dx, dy)
            if dist > 0:
                self.x += (dx / dist) * 120
                self.y += (dy / dist) * 120
            return {"type": "charge", "damage": self.attack * 1.5}

        elif attack_type == "shockwave":
            effect = {
                "type": "shockwave",
                "x": self.x, "y": self.y,
                "radius": 0, "max_radius": 120 + self.phase * 20,
                "damage": self.attack,
                "timer": 0.5,
                "hit": False,
            }
            self._special_effects.append(effect)
            return effect

        else:  # volley
            for angle in range(0, 360, 45 // self.phase):
                rad = math.radians(angle)
                proj = {
                    "type": "boss_projectile",
                    "x": self.x, "y": self.y,
                    "dx": math.cos(rad) * 200,
                    "dy": math.sin(rad) * 200,
                    "damage": self.attack * 0.6,
                    "timer": 2.0,
                    "radius": 8,
                }
                self._special_effects.append(proj)
            return {"type": "volley", "damage": self.attack * 0.6}

    def update(self, dt, player_x, player_y, world_w, world_h, tilemap=None):
        """Update boss AI and special attack logic."""
        if not self.alive and not self._is_dying:
            return

        self.special_timer = max(0, self.special_timer - dt)
        self._pulse_timer += dt

        # Handle special animation finishing
        if self._using_special:
            if self.has_sprites:
                self.animator.update(dt)
                if self.animator.is_action_finished():
                    self._using_special = False
                    self.anim_state = "idle"
                    self.animator.set_action("idle")
            else:
                self._using_special = False

            self._update_special_effects(dt)
            return

        # Normal update (inherited from Enemy) - pass tilemap for wall collision
        super().update(dt, player_x, player_y, world_w, world_h, tilemap)

        if not self.alive or self._is_dying:
            return

        # Phase transition check
        self.phase_transition()

        # Try special attack
        if self.special_timer <= 0:
            dist = math.hypot(player_x - self.x, player_y - self.y)
            if dist < 300:
                self.special_attack(player_x, player_y)

        # Update special effects
        self._update_special_effects(dt)

    def _update_special_effects(self, dt):
        for effect in self._special_effects[:]:
            if effect["type"] == "shockwave":
                effect["timer"] -= dt
                effect["radius"] += (effect["max_radius"] / 0.5) * dt
                if effect["timer"] <= 0:
                    self._special_effects.remove(effect)
            elif effect["type"] == "boss_projectile":
                effect["x"] += effect["dx"] * dt
                effect["y"] += effect["dy"] * dt
                effect["timer"] -= dt
                if effect["timer"] <= 0:
                    self._special_effects.remove(effect)

    def get_special_effects(self):
        return self._special_effects

    def remove_special_effect(self, effect):
        if effect in self._special_effects:
            self._special_effects.remove(effect)

    def draw(self, surface, camera_x, camera_y):
        """Draw boss with sprites or fallback visuals."""
        if not self.alive and not self._is_dying:
            return

        sx = int(self.x - camera_x)
        sy = int(self.y - camera_y)

        if self.has_sprites:
            self.animator.draw(surface, self.x, self.y, camera_x, camera_y)
        else:
            # Fallback: pulsing circle
            pulse = abs(math.sin(self._pulse_timer * 2))
            glow_r = self.size + int(8 * pulse)

            glow_surf = pygame.Surface((glow_r * 2 + 20, glow_r * 2 + 20), pygame.SRCALPHA)
            glow_color = tuple(min(255, c + int(40 * pulse)) for c in self.color)
            pygame.draw.circle(glow_surf, (*glow_color, 40),
                               (glow_r + 10, glow_r + 10), glow_r + 8)
            surface.blit(glow_surf, (sx - glow_r - 10, sy - glow_r - 10))

            color = (255, 255, 255) if self.hit_flash > 0 else self.color
            if self.enraged:
                color = (min(255, color[0] + 60), max(0, color[1] - 30),
                         max(0, color[2] - 30))

            pygame.draw.circle(surface, color, (sx, sy), self.size)
            pygame.draw.circle(surface, (255, 200, 50), (sx, sy), self.size, 3)

        # Phase dots
        for i in range(self.max_phases):
            dot_x = sx - (self.max_phases - 1) * 6 + i * 12
            dot_y = sy - self.size - 18
            dot_color = (255, 200, 50) if i < self.phase else (80, 80, 80)
            pygame.draw.circle(surface, dot_color, (dot_x, dot_y), 4)

        # Boss HP bar
        if not self._is_dying:
            bar_w = self.size * 3
            bar_h = 6
            bx = sx - bar_w // 2
            by = sy - self.size - 10
            ratio = self.hp / self.max_hp
            pygame.draw.rect(surface, (40, 0, 0), (bx, by, bar_w, bar_h))
            bar_color = (220, 40, 40) if self.phase < self.max_phases else (255, 100, 30)
            pygame.draw.rect(surface, bar_color, (bx, by, int(bar_w * ratio), bar_h))

        # Draw special effects
        for effect in self._special_effects:
            if effect["type"] == "shockwave":
                r = int(effect["radius"])
                alpha = int(150 * (effect["timer"] / 0.5))
                wave_surf = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
                pygame.draw.circle(wave_surf, (255, 100, 50, alpha),
                                   (r + 2, r + 2), r, 4)
                ex = int(effect["x"] - camera_x)
                ey = int(effect["y"] - camera_y)
                surface.blit(wave_surf, (ex - r - 2, ey - r - 2))
            elif effect["type"] == "boss_projectile":
                px = int(effect["x"] - camera_x)
                py = int(effect["y"] - camera_y)
                pygame.draw.circle(surface, (255, 80, 30), (px, py), effect["radius"])