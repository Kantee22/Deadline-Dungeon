"""
player.py - Player class for Deadline Dungeon
Manages player state: movement, combat (left click = attack, right click = skill),
leveling, HP recovery, class selection, and sprite animation.
"""
import pygame
import math
import os
from animation import SpriteAnimator


class Player:
    """The player character with sprite animation and mouse-based combat."""

    EXP_TABLE = [0] + [int(15 + i * 8 + (i ** 1.4)) for i in range(1, 35)]

    CLASS_STATS = {
        "Soldier": (120, 12, 5, 180),
        "Knight":  (180, 22, 8, 160),
        "Wizard":  (110, 30, 3, 170),
        "Archer":  (130, 18, 5, 200),
    }

    CLASS_SPRITES = {
        "Soldier": "soldier",
        "Knight":  "knight",
        "Wizard":  "wizard",
        "Archer":  "archer",
    }

    CLASS_COMBAT = {
        "Soldier": {
            "attack_type": "melee",
            "attack_damage": 1.0,
            "attack_range": 55,
            "attack_release": 0.18,         # damage fires N seconds after click
            "attack_duration": 0.4,          # total animation lock time
            "skill_type": "projectile",
            "skill_damage": 0.8,
            "skill_range": 300,
            "skill_speed": 400,
            "skill_cooldown": 0.8,
            "skill_release": 0.25,           # draw bow takes longer
            "skill_duration": 0.5,
            "projectile_color": (220, 200, 130),
            "projectile_sprite": "fire_arrow",
        },
        "Knight": {
            "attack_type": "melee",
            "attack_damage": 1.3,
            "attack_range": 60,
            "attack_release": 0.2,
            "attack_duration": 0.45,
            "skill_type": "melee_big",
            "skill_damage": 2.0,
            "skill_range": 80,
            "skill_cooldown": 2.5,
            "skill_release": 0.35,           # wind-up then swing
            "skill_duration": 0.6,
        },
        "Wizard": {
            "attack_type": "projectile",
            "attack_damage": 1.2,
            "attack_range": 350,
            "attack_speed": 350,
            "attack_release": 0.22,
            "attack_duration": 0.45,
            "projectile_color": (255, 100, 30),
            "projectile_sprite": "fire_arrow",
            "skill_type": "aoe",
            "skill_damage": 2.5,
            "skill_range": 100,
            "skill_cooldown": 3.0,
            "skill_release": 0.3,             # cast + release
            "skill_duration": 0.55,
            "skill_color": (100, 180, 255),
        },
        "Archer": {
            "attack_type": "projectile",
            "attack_damage": 1.0,
            "attack_range": 400,
            "attack_speed": 500,
            "attack_release": 0.2,
            "attack_duration": 0.45,
            "projectile_color": (180, 255, 100),
            "projectile_sprite": "fire_arrow",
            "skill_type": "projectile_pierce",
            "skill_damage": 1.5,
            "skill_range": 500,
            "skill_speed": 600,
            "skill_cooldown": 2.0,
            "skill_release": 0.3,             # strong pull
            "skill_duration": 0.55,
            "projectile_color_skill": (255, 255, 80),
        },
    }

    # Pixel scale: each source pixel becomes N display pixels
    # Soldier body ~17x21 → ~51x63 display
    SPRITE_SCALE = 3.0
    PROJECTILE_SCALE = 2.0

    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.width = 32
        self.height = 32

        self.class_type = "Soldier"
        base = self.CLASS_STATS["Soldier"]
        self.max_hp = base[0]
        self.hp = self.max_hp
        self.attack = base[1]
        self.defense = base[2]
        self.speed = base[3]

        self.level = 1
        self.exp = 0
        self.total_exp = 0

        self.direction = "right"
        self.facing = 0.0

        self.anim_state = "idle"
        self._attack_timer = 0.0
        self._skill_cooldown_timer = 0.0
        self._hurt_timer = 0.0
        self._is_dead = False

        self.projectiles = []
        self.active_effects = []
        self.pending_attacks = []   # queued attacks with release_timer

        self.invincible_timer = 0.0
        self.hit_flash_timer = 0.0

        self._load_sprites()

    def _load_sprites(self):
        folder = self.CLASS_SPRITES.get(self.class_type, "soldier")
        sprite_path = os.path.join("images", folder)
        self.animator = SpriteAnimator(sprite_path, pixel_scale=self.SPRITE_SCALE)
        self.has_sprites = self.animator.loaded

        self.projectile_animator = None
        combat = self.CLASS_COMBAT.get(self.class_type, {})
        proj_sprite = combat.get("projectile_sprite")
        if proj_sprite:
            proj_path = os.path.join("images", folder, proj_sprite)
            if os.path.isdir(proj_path):
                self.projectile_animator = SpriteAnimator(
                    proj_path, pixel_scale=self.PROJECTILE_SCALE)

    @property
    def rect(self):
        return pygame.Rect(self.x - self.width // 2, self.y - self.height // 2,
                           self.width, self.height)

    @property
    def exp_to_next(self):
        if self.level >= 30:
            return 999999
        return self.EXP_TABLE[self.level]

    @property
    def exp_fraction(self):
        needed = self.exp_to_next
        if needed <= 0:
            return 1.0
        return min(1.0, self.exp / needed)

    @property
    def skill_cooldown_fraction(self):
        combat = self.CLASS_COMBAT.get(self.class_type, {})
        cd = combat.get("skill_cooldown", 1.0)
        if cd <= 0:
            return 1.0
        return 1.0 - min(1.0, self._skill_cooldown_timer / cd)

    def move(self, dx, dy, dt, world_w, world_h):
        length = math.hypot(dx, dy)
        if length > 0:
            dx, dy = dx / length, dy / length

        self.x += dx * self.speed * dt
        self.y += dy * self.speed * dt

        half_w, half_h = self.width // 2, self.height // 2
        self.x = max(half_w, min(world_w - half_w, self.x))
        self.y = max(half_h, min(world_h - half_h, self.y))

        if abs(dx) > 0.1:
            new_dir = "right" if dx > 0 else "left"
            if new_dir != self.direction:
                self.direction = new_dir
                if self.has_sprites:
                    self.animator.set_direction(self.direction)

    def update_facing(self, mouse_x, mouse_y, screen_w, screen_h):
        aim_x = mouse_x - screen_w // 2
        aim_y = mouse_y - screen_h // 2
        if aim_x != 0 or aim_y != 0:
            self.facing = math.atan2(aim_y, aim_x)
            if aim_x < 0 and self.direction != "left":
                self.direction = "left"
                if self.has_sprites:
                    self.animator.set_direction("left")
            elif aim_x >= 0 and self.direction != "right":
                self.direction = "right"
                if self.has_sprites:
                    self.animator.set_direction("right")

    def _compute_release_time(self, action, is_projectile=False):
        """Return when damage/projectile should fire during animation.
        - Melee: fires 6 frames before end (1 frame later than previous tune)
        - Projectile (arrow/fireball): fires at the LAST frame (release moment)
        """
        if self.has_sprites:
            key = f"{action}_{self.direction}"
            anim = self.animator.animations.get(key)
            if anim and anim.frames:
                total = len(anim.frames) * anim.frame_duration
                min_release = anim.frame_duration * 2.0

                if is_projectile:
                    # Projectile: fire on final frame (release)
                    desired = total - anim.frame_duration * 0.5
                else:
                    # Melee: fire 6 frames before end (1 later than before)
                    desired = total - anim.frame_duration * 6.2

                return max(min_release, desired)
        return 0.15

    def left_click(self):
        """Start attack animation. Damage fires near end of animation."""
        if self._is_dead or self.anim_state in ("hurt", "death"):
            return None
        if self._attack_timer > 0:
            return None

        combat = self.CLASS_COMBAT.get(self.class_type, {})
        dmg = int(self.attack * combat.get("attack_damage", 1.0))
        atk_type = combat.get("attack_type", "melee")

        self.anim_state = "attack"
        if self.has_sprites:
            self.animator.set_action("attack", force=True)

        # Projectile attacks fire at the LAST frame; melee fires 6 frames before end
        is_proj = atk_type in ("projectile", "projectile_pierce")
        release = self._compute_release_time("attack", is_projectile=is_proj)
        if self.has_sprites:
            key = f"attack_{self.direction}"
            anim = self.animator.animations.get(key)
            duration = (len(anim.frames) * anim.frame_duration
                         if anim and anim.frames else 0.4)
        else:
            duration = 0.4
        self._attack_timer = duration

        pending = {
            "is_skill": False,
            "release_in": release,
            "atk_type": atk_type,
            "damage": dmg,
            "facing": self.facing,
            "combat": combat,
        }
        self.pending_attacks.append(pending)
        return pending

    def right_click(self):
        """Start skill animation. Damage fires near end of animation."""
        if self._is_dead or self.anim_state in ("hurt", "death"):
            return None
        if self._skill_cooldown_timer > 0:
            return None

        combat = self.CLASS_COMBAT.get(self.class_type, {})
        dmg = int(self.attack * combat.get("skill_damage", 1.5))
        cd = combat.get("skill_cooldown", 2.0)
        skill_type = combat.get("skill_type", "melee")

        self.anim_state = "skill"
        if self.has_sprites:
            self.animator.set_action("skill", force=True)
        self._skill_cooldown_timer = cd

        is_proj = skill_type in ("projectile", "projectile_pierce")
        release = self._compute_release_time("skill", is_projectile=is_proj)
        if self.has_sprites:
            key = f"skill_{self.direction}"
            anim = self.animator.animations.get(key)
            duration = (len(anim.frames) * anim.frame_duration
                         if anim and anim.frames else 0.5)
        else:
            duration = 0.5
        self._attack_timer = duration

        pending = {
            "is_skill": True,
            "release_in": release,
            "atk_type": skill_type,
            "damage": dmg,
            "facing": self.facing,
            "combat": combat,
        }
        self.pending_attacks.append(pending)
        return pending

    def _spawn_attack(self, pending):
        """Actually spawn the effect/projectile after the release delay."""
        atk_type = pending["atk_type"]
        dmg = pending["damage"]
        combat = pending["combat"]
        source = "skill" if pending["is_skill"] else "attack"

        # Use CURRENT player position and facing for spawn (not the click time)
        # This feels more natural — arrow fires from where you are now
        facing = pending["facing"]
        dx = math.cos(facing)
        dy = math.sin(facing)

        if atk_type == "melee":
            rng = combat.get("attack_range" if not pending["is_skill"] else "skill_range", 50)
            self.active_effects.append({
                "type": "melee",
                "x": self.x + dx * 40,
                "y": self.y + dy * 40,
                "damage": dmg,
                "range": rng, "radius": rng,
                "timer": 0.15, "source": source,
            })
        elif atk_type == "melee_big":
            rng = combat.get("skill_range", 80)
            self.active_effects.append({
                "type": "melee",
                "x": self.x + dx * 50,
                "y": self.y + dy * 50,
                "damage": dmg,
                "range": rng, "radius": rng,
                "timer": 0.2, "source": source,
            })
        elif atk_type == "projectile":
            speed = combat.get("skill_speed" if pending["is_skill"] else "attack_speed", 400)
            max_range = combat.get("skill_range" if pending["is_skill"] else "attack_range", 300)
            color = combat.get("projectile_color_skill",
                                combat.get("projectile_color", (255, 255, 100))) \
                    if pending["is_skill"] else combat.get("projectile_color", (255, 200, 100))
            self.projectiles.append({
                "type": "projectile",
                "x": self.x, "y": self.y,
                "dx": dx * speed, "dy": dy * speed,
                "damage": dmg,
                "max_range": max_range,
                "start_x": self.x, "start_y": self.y,
                "color": color, "radius": 8,
                "angle": facing, "source": source,
            })
        elif atk_type == "projectile_pierce":
            speed = combat.get("skill_speed", 600)
            self.projectiles.append({
                "type": "projectile",
                "x": self.x, "y": self.y,
                "dx": dx * speed, "dy": dy * speed,
                "damage": dmg,
                "max_range": combat.get("skill_range", 500),
                "start_x": self.x, "start_y": self.y,
                "color": combat.get("projectile_color_skill", (255, 255, 80)),
                "radius": 12,
                "angle": facing, "source": source,
                "pierce": True, "hit_targets": [],
            })
        elif atk_type == "aoe":
            self.active_effects.append({
                "type": "aoe",
                "x": self.x + dx * 50,
                "y": self.y + dy * 50,
                "damage": dmg,
                "radius": combat.get("skill_range", 100),
                "color": combat.get("skill_color", (100, 180, 255)),
                "timer": 0.3, "source": source,
            })

    def gain_exp(self, amount):
        levels_gained = []
        self.exp += amount
        self.total_exp += amount
        while self.exp >= self.exp_to_next and self.level < 30:
            self.exp -= self.exp_to_next
            self.level += 1
            levels_gained.append(self.level)
            self._on_level_up()
        return levels_gained

    def _on_level_up(self):
        growth = {
            "Soldier": (6, 1.5, 0.5),
            "Knight":  (10, 2, 1),
            "Wizard":  (4, 3, 0.3),
            "Archer":  (6, 2, 0.5),
        }
        hp_g, atk_g, def_g = growth.get(self.class_type, (5, 1, 0.5))
        self.max_hp += int(hp_g)
        self.attack += int(atk_g)
        self.defense += int(def_g)
        self.hp = self.max_hp  # Full HP restore!

    def change_class(self, new_class):
        if new_class not in self.CLASS_STATS:
            return
        self.class_type = new_class
        base = self.CLASS_STATS[new_class]
        level_bonus = self.level - 1
        self.max_hp = base[0] + level_bonus * 8
        self.hp = self.max_hp
        self.attack = base[1] + level_bonus * 2
        self.defense = base[2] + level_bonus
        self.speed = base[3]
        self._load_sprites()

    def take_damage(self, raw_damage):
        if self.invincible_timer > 0:
            return 0
        actual = max(1, raw_damage - self.defense)
        self.hp = max(0, self.hp - actual)
        self.invincible_timer = 0.5
        self.hit_flash_timer = 0.2

        if self.hp <= 0:
            self._is_dead = True
            self.anim_state = "death"
            if self.has_sprites:
                self.animator.set_action("death", force=True)
        else:
            self._hurt_timer = 0.2
            self.anim_state = "hurt"
            if self.has_sprites:
                self.animator.set_action("hurt", force=True)
        return actual

    def is_alive(self):
        return self.hp > 0

    def update(self, dt, tilemap=None):
        if self.invincible_timer > 0:
            self.invincible_timer -= dt
        if self.hit_flash_timer > 0:
            self.hit_flash_timer -= dt
        if self._attack_timer > 0:
            self._attack_timer -= dt
        if self._skill_cooldown_timer > 0:
            self._skill_cooldown_timer -= dt

        if self._hurt_timer > 0:
            self._hurt_timer -= dt
            if self._hurt_timer <= 0 and self.anim_state == "hurt":
                self.anim_state = "idle"
                if self.has_sprites:
                    self.animator.set_action("idle")

        if self.anim_state in ("attack", "skill"):
            if self.has_sprites:
                if self.animator.is_action_finished():
                    self.anim_state = "idle"
                    self.animator.set_action("idle")
            elif self._attack_timer <= 0:
                self.anim_state = "idle"

        # Release pending attacks when their timer expires
        for pending in self.pending_attacks[:]:
            pending["release_in"] -= dt
            if pending["release_in"] <= 0:
                self._spawn_attack(pending)
                self.pending_attacks.remove(pending)

        # Update projectiles + wall collision
        for proj in self.projectiles[:]:
            proj["x"] += proj["dx"] * dt
            proj["y"] += proj["dy"] * dt

            # Remove if hit wall
            if tilemap and tilemap.is_wall(proj["x"], proj["y"]):
                self.projectiles.remove(proj)
                continue

            # Remove if exceeded max range
            dist = math.hypot(proj["x"] - proj["start_x"],
                              proj["y"] - proj["start_y"])
            if dist > proj["max_range"]:
                self.projectiles.remove(proj)

        # Update AoE effects
        for effect in self.active_effects[:]:
            effect["timer"] -= dt
            if effect["timer"] <= 0:
                self.active_effects.remove(effect)

        if self.has_sprites:
            self.animator.update(dt)

        if self.projectile_animator:
            self.projectile_animator.update(dt)

    def set_walk_or_idle(self, is_moving):
        if self.anim_state in ("attack", "skill", "hurt", "death"):
            return
        if is_moving and self.anim_state != "walk":
            self.anim_state = "walk"
            if self.has_sprites:
                self.animator.set_action("walk")
        elif not is_moving and self.anim_state != "idle":
            self.anim_state = "idle"
            if self.has_sprites:
                self.animator.set_action("idle")

    def draw(self, surface, camera_x, camera_y):
        sx = self.x - camera_x
        sy = self.y - camera_y

        if self.has_sprites:
            if self.invincible_timer > 0 and int(self.invincible_timer * 10) % 2 == 0:
                pass  # skip frame for blink
            else:
                self.animator.draw(surface, self.x, self.y, camera_x, camera_y)
        else:
            colors = {
                "Soldier": (120, 180, 120),
                "Knight":  (220, 80, 80),
                "Wizard":  (100, 100, 240),
                "Archer":  (80, 200, 80),
            }
            color = colors.get(self.class_type, (120, 180, 120))
            if self.hit_flash_timer > 0:
                color = (255, 255, 255)
            pygame.draw.circle(surface, color, (int(sx), int(sy)), self.width // 2)
            pygame.draw.circle(surface, (40, 40, 40), (int(sx), int(sy)),
                               self.width // 2, 2)
            fx = sx + math.cos(self.facing) * 18
            fy = sy + math.sin(self.facing) * 18
            pygame.draw.circle(surface, (255, 255, 220), (int(fx), int(fy)), 4)

    def draw_attacks(self, surface, camera_x, camera_y):
        """Draw projectiles (using sprite if available) and AoE effects."""
        # Projectiles
        for proj in self.projectiles:
            px = proj["x"] - camera_x
            py = proj["y"] - camera_y

            drew_sprite = False
            if self.projectile_animator and self.projectile_animator.loaded:
                frame = self.projectile_animator.get_frame()
                if frame:
                    # Rotate sprite to match projectile direction
                    # Pygame rotates counter-clockwise; negate angle for screen coords
                    angle_deg = -math.degrees(proj.get("angle", 0))
                    rotated = pygame.transform.rotate(frame, angle_deg)
                    rect = rotated.get_rect(center=(int(px), int(py)))
                    surface.blit(rotated, rect)
                    drew_sprite = True

            if not drew_sprite:
                # Fallback: colored circle with glow
                pygame.draw.circle(surface, proj["color"],
                                   (int(px), int(py)), proj["radius"])
                glow_surf = pygame.Surface((24, 24), pygame.SRCALPHA)
                pygame.draw.circle(glow_surf, (*proj["color"], 70), (12, 12), 12)
                surface.blit(glow_surf, (int(px) - 12, int(py) - 12))

        # AoE effects (ice explosion, shockwaves)
        for effect in self.active_effects:
            if effect["type"] != "aoe":
                continue
            ex = effect["x"] - camera_x
            ey = effect["y"] - camera_y
            radius = effect["radius"]
            alpha = int(180 * (effect["timer"] / 0.3))
            aoe_surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(aoe_surf,
                               (*effect["color"], alpha),
                               (radius, radius), radius)
            surface.blit(aoe_surf, (int(ex) - radius, int(ey) - radius))

        # Melee swings visual
        for effect in self.active_effects:
            if effect["type"] != "melee":
                continue
            ex = effect["x"] - camera_x
            ey = effect["y"] - camera_y
            alpha = int(180 * (effect["timer"] / 0.2))
            r = effect.get("radius", 50)
            arc_surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(arc_surf, (255, 255, 255, alpha), (r, r), r, 4)
            surface.blit(arc_surf, (int(ex) - r, int(ey) - r))