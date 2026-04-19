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
            "size": 38, "color": (60, 120, 40), "atk_cd": 0.7,
            "phases": 3, "sprite_folder": "EliteOrc",
            "pixel_scale": 4.0,
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
        self._pending_special = None      # animation-synced special payload

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

    def attack_player(self, player):
        """Elite Orc has a radial spin attack - hits all around at once.
        Other bosses use the normal enemy attack (inherits pending_attack pattern).
        """
        if self.boss_type != "final_boss":
            return super().attack_player(player)

        # Final boss radial attack: bigger range, no facing requirement
        if (not self.alive or self._attack_timer > 0 or self._pending_attack
                or self._is_dying or self._using_special):
            return 0

        dist = math.hypot(player.x - self.x, player.y - self.y)
        spin_radius = self.size + 75
        if dist < spin_radius:
            self._attack_timer = self.attack_cooldown
            self.direction = "right" if player.x > self.x else "left"
            if self.has_sprites:
                self.animator.set_direction(self.direction)
            self._update_animation("attack")

            # Queue damage to fire mid/late animation instead of instant
            self._pending_attack = {
                "release_in": self._compute_attack_release(),
                "damage": self.attack,
                "range": spin_radius + 25,  # a bit forgiving for player movement
            }
        return 0

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

    def _get_animation_duration(self, action):
        """Get the total duration of an animation for this boss."""
        if self.has_sprites:
            key = f"{action}_{self.direction}"
            anim = self.animator.animations.get(key)
            if anim and anim.frames:
                return len(anim.frames) * anim.frame_duration
        return 0.6

    def can_use_special(self):
        """Phase gating for special:
        - Mini bosses (1, 2): phase 1 = no special, phase 2+ = special enabled
        - Final boss (Elite Orc): special available from phase 1
        """
        if self.boss_type == "final_boss":
            return True
        return self.phase >= 2

    def special_attack(self, player_x, player_y):
        """Execute boss-type-specific special.
        Special is only available in phase 2+ for mini bosses.
        Elite Orc (final) has special from the start.
        """
        if self.special_timer > 0 or self._using_special:
            return None
        # Phase-gate: mini bosses don't use special in phase 1
        if self.boss_type in ("mini_boss_1", "mini_boss_2") and not self.can_use_special():
            return None

        self.special_timer = self.special_cooldown
        self._using_special = True

        # Face player
        self.direction = "right" if player_x > self.x else "left"
        self.anim_state = "special"
        if self.has_sprites and self.has_special_anim:
            self.animator.set_direction(self.direction)
            self.animator.set_action("special", force=True)

        anim_dur = self._get_animation_duration("special")

        # Dispatch by boss type
        if self.boss_type == "mini_boss_1":
            return self._skill_ground_slam(player_x, player_y, anim_dur)
        elif self.boss_type == "mini_boss_2":
            return self._skill_charge_bite(player_x, player_y, anim_dur)
        elif self.boss_type == "final_boss":
            return self._skill_jump_slam(player_x, player_y, anim_dur)
        return None

    def _skill_ground_slam(self, player_x, player_y, anim_dur):
        """Boss 1 phase 2: slam with gray shockwave at end of animation."""
        self._pending_special = {
            "type": "ground_slam",
            "release_in": max(0.1, anim_dur - 0.12),  # trigger at second-to-last frame
            "damage": self.attack * 1.2,
        }
        return {"type": "ground_slam"}

    def _skill_charge_bite(self, player_x, player_y, anim_dur):
        """Boss 2 phase 2: lunge forward, stop, damage when anim ends."""
        dx = player_x - self.x
        dy = player_y - self.y
        dist = math.hypot(dx, dy)
        if dist < 1:
            return None
        travel = min(dist - 20, 220 + self.phase * 20)
        travel = max(50, travel)
        vx = dx / dist
        vy = dy / dist

        # Dash takes first 60% of animation, then hold still for hit
        dash_time = anim_dur * 0.6
        self._pending_special = {
            "type": "charge_dash",
            "vx": vx, "vy": vy,
            "dash_remaining": dash_time,
            "dash_speed": travel / dash_time if dash_time > 0 else 0,
            "release_in": anim_dur - 0.1,   # damage near end
            "damage": self.attack * 1.5,
            "trail": [],
        }
        return {"type": "charge"}

    def _skill_jump_slam(self, player_x, player_y, anim_dur):
        """Boss 3 phase 2+: jump to player, slam shockwave when anim ends."""
        # Move partway toward player during jump animation
        dx = player_x - self.x
        dy = player_y - self.y
        dist = math.hypot(dx, dy)

        jump_time = anim_dur * 0.7
        if dist > 0:
            jump_dist = min(dist, 280)
            vx = (dx / dist) * (jump_dist / jump_time) if jump_time > 0 else 0
            vy = (dy / dist) * (jump_dist / jump_time) if jump_time > 0 else 0
        else:
            vx = vy = 0

        self._pending_special = {
            "type": "jump_slam",
            "vx": vx, "vy": vy,
            "jump_remaining": jump_time,
            "release_in": anim_dur - 0.1,
            "damage": self.attack * 1.4,
        }
        return {"type": "jump_slam"}

    def _release_special(self, pending):
        """Actually spawn the special effect when timer runs out."""
        kind = pending["type"]

        if kind == "ground_slam":
            self._special_effects.append({
                "type": "shockwave",
                "x": self.x, "y": self.y,
                "radius": 0,
                "max_radius": 170 + self.phase * 25,
                "damage": pending["damage"],
                "timer": 0.5, "life": 0.5,
                "hit": False,
                "color": (210, 210, 210),
                "thickness": 6,
                "impact_delay": 0.0,
            })

        elif kind == "charge_dash":
            # Damage at where boss stopped (bigger radius so lunge bite feels wider)
            self._special_effects.append({
                "type": "boss_melee",
                "x": self.x, "y": self.y,
                "radius": 140,
                "damage": pending["damage"],
                "timer": 0.3, "life": 0.3,
                "hit": False,
                "color": (200, 50, 50),
            })

        elif kind == "jump_slam":
            # Damage at landing + shockwave
            self._special_effects.append({
                "type": "boss_melee",
                "x": self.x, "y": self.y,
                "radius": 90,
                "damage": pending["damage"] * 0.5,
                "timer": 0.2, "life": 0.2,
                "hit": False,
                "color": (255, 100, 40),
            })
            self._special_effects.append({
                "type": "shockwave",
                "x": self.x, "y": self.y,
                "radius": 0,
                "max_radius": 240 + self.phase * 30,
                "damage": pending["damage"],
                "timer": 0.7, "life": 0.7,
                "hit": False,
                "color": (255, 140, 50),
                "thickness": 8,
                "impact_delay": 0.0,
                "inner_ring": True,
            })

    def update(self, dt, player_x, player_y, world_w, world_h, tilemap=None):
        """Update boss AI and special attack logic."""
        if not self.alive and not self._is_dying:
            return

        self.special_timer = max(0, self.special_timer - dt)
        self._pulse_timer += dt

        # Special animation playing
        if self._using_special:
            # Handle movement during special (dash / jump)
            if self._pending_special:
                ps = self._pending_special

                # Boss 2: dash forward during dash_remaining time
                if ps["type"] == "charge_dash" and ps["dash_remaining"] > 0:
                    move = min(ps["dash_remaining"], dt)
                    step_x = ps["vx"] * ps["dash_speed"] * move
                    step_y = ps["vy"] * ps["dash_speed"] * move
                    # Axis-separated wall collision for the dash
                    if tilemap:
                        if not tilemap.is_wall(self.x + step_x, self.y + step_y):
                            self.x += step_x
                            self.y += step_y
                        elif not tilemap.is_wall(self.x + step_x, self.y):
                            self.x += step_x
                        elif not tilemap.is_wall(self.x, self.y + step_y):
                            self.y += step_y
                    else:
                        self.x += step_x
                        self.y += step_y
                    ps["dash_remaining"] -= move

                    # Trail for visual
                    trail = ps.get("trail", [])
                    trail.append((self.x, self.y, 0.3))
                    ps["trail"] = [
                        (tx, ty, tl - dt) for (tx, ty, tl) in trail if tl - dt > 0
                    ]

                # Boss 3: jump motion during jump_remaining
                elif ps["type"] == "jump_slam" and ps["jump_remaining"] > 0:
                    move = min(ps["jump_remaining"], dt)
                    step_x = ps["vx"] * move
                    step_y = ps["vy"] * move
                    if tilemap:
                        if not tilemap.is_wall(self.x + step_x, self.y + step_y):
                            self.x += step_x
                            self.y += step_y
                        elif not tilemap.is_wall(self.x + step_x, self.y):
                            self.x += step_x
                        elif not tilemap.is_wall(self.x, self.y + step_y):
                            self.y += step_y
                    else:
                        self.x += step_x
                        self.y += step_y
                    ps["jump_remaining"] -= move

                # Release damage when timer fires
                ps["release_in"] -= dt
                if ps["release_in"] <= 0 and not ps.get("released"):
                    self._release_special(ps)
                    ps["released"] = True

            # Wait for animation to finish
            if self.has_sprites:
                self.animator.update(dt)
                if self.animator.is_action_finished():
                    self._using_special = False
                    self._pending_special = None
                    self.anim_state = "idle"
                    self.animator.set_action("idle")
            else:
                # No sprite - use fallback timer
                if self._pending_special and self._pending_special.get("released"):
                    self._using_special = False
                    self._pending_special = None

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
                if effect.get("impact_delay", 0) > 0:
                    effect["impact_delay"] -= dt
                    continue
                effect["timer"] -= dt
                life = effect.get("life", 0.5)
                effect["radius"] += (effect["max_radius"] / life) * dt
                if effect["timer"] <= 0:
                    self._special_effects.remove(effect)

            elif effect["type"] == "boss_melee":
                effect["timer"] -= dt
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

        # Draw dash trail if boss is currently charging
        if self._using_special and self._pending_special:
            ps = self._pending_special
            if ps.get("type") == "charge_dash":
                for (tx, ty, life) in ps.get("trail", []):
                    alpha = int(140 * (life / 0.3))
                    trail_surf = pygame.Surface((50, 50), pygame.SRCALPHA)
                    pygame.draw.circle(trail_surf, (180, 100, 100, alpha),
                                       (25, 25), 20)
                    surface.blit(trail_surf,
                                 (int(tx - camera_x) - 25,
                                  int(ty - camera_y) - 25))

        # Draw special effects
        for effect in self._special_effects:
            if effect["type"] == "shockwave":
                # Don't draw before impact starts (but show charge-up indicator)
                if effect.get("impact_delay", 0) > 0:
                    # Tiny warning marker
                    ex = int(effect["x"] - camera_x)
                    ey = int(effect["y"] - camera_y)
                    warn_surf = pygame.Surface((40, 40), pygame.SRCALPHA)
                    pygame.draw.circle(warn_surf, (255, 220, 100, 120), (20, 20), 20, 2)
                    surface.blit(warn_surf, (ex - 20, ey - 20))
                    continue

                r = int(effect["radius"])
                life = effect.get("life", 0.5)
                alpha = int(180 * (effect["timer"] / life))
                color = effect.get("color", (255, 100, 50))
                thickness = effect.get("thickness", 4)

                wave_surf = pygame.Surface((r * 2 + 8, r * 2 + 8), pygame.SRCALPHA)
                pygame.draw.circle(wave_surf, (*color, alpha),
                                   (r + 4, r + 4), r, thickness)
                # Inner ring for intense shockwaves (boss 3)
                if effect.get("inner_ring") and r > 30:
                    pygame.draw.circle(wave_surf, (*color, alpha // 2),
                                       (r + 4, r + 4), max(1, r - 25), 3)
                ex = int(effect["x"] - camera_x)
                ey = int(effect["y"] - camera_y)
                surface.blit(wave_surf, (ex - r - 4, ey - r - 4))

            elif effect["type"] == "boss_melee":
                r = effect["radius"]
                life = effect.get("life", 0.25)
                alpha = int(200 * (effect["timer"] / life))
                color = effect.get("color", (255, 80, 80))
                hit_surf = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
                pygame.draw.circle(hit_surf, (*color, alpha),
                                   (r + 2, r + 2), r)
                pygame.draw.circle(hit_surf, (*color, min(255, alpha + 60)),
                                   (r + 2, r + 2), r, 3)
                ex = int(effect["x"] - camera_x)
                ey = int(effect["y"] - camera_y)
                surface.blit(hit_surf, (ex - r - 2, ey - r - 2))

            elif effect["type"] == "boss_projectile":
                px = int(effect["x"] - camera_x)
                py = int(effect["y"] - camera_y)
                pygame.draw.circle(surface, (255, 80, 30), (px, py), effect["radius"])