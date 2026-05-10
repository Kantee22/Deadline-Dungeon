"""boss.py - Boss enemy with phases, special attacks, and enrage."""
import pygame
import math
import random
import os
from enemy import Enemy
from animation import SpriteAnimator


class Boss(Enemy):
    """Multi-phase boss (extends Enemy with special attacks)."""

    # Boss variants grouped by tier (1 = Lv.10, 2 = Lv.20, 3 = final/timeout).
    # Multiple variants per tier make each run feel different. `tint` is an
    # optional RGB multiplier applied to shared sprite folders.
    BOSS_TEMPLATES = {
        # -- Tier 1 (mini boss #1) --
        "mini_boss_1": {
            "tier": 1, "name": "Greatsword Skeleton",
            "hp": 440, "attack": 22, "speed": 75, "exp": 120,
            "size": 34, "color": (220, 210, 180), "atk_cd": 0.95,
            "phases": 2, "sprite_folder": "Greatsword Skeleton",
            "pixel_scale": 4.0,
        },
        "mini_boss_1_cursed": {
            "tier": 1, "name": "Cursed Revenant",
            "hp": 380, "attack": 26, "speed": 95, "exp": 140,
            "size": 34, "color": (160, 140, 220), "atk_cd": 0.8,
            "phases": 2, "sprite_folder": "Greatsword Skeleton",
            "pixel_scale": 4.0,
            "tint": (150, 120, 220),
        },
        "mini_boss_1_colossus": {
            "tier": 1, "name": "Bone Colossus",
            "hp": 640, "attack": 20, "speed": 60, "exp": 160,
            "size": 38, "color": (250, 245, 220), "atk_cd": 1.1,
            "phases": 2, "sprite_folder": "Greatsword Skeleton",
            "pixel_scale": 4.5,
            "tint": (255, 240, 200),
        },

        # -- Tier 2 (mini boss #2) --
        "mini_boss_2": {
            "tier": 2, "name": "Werewolf",
            "hp": 700, "attack": 28, "speed": 95, "exp": 200,
            "size": 38, "color": (120, 80, 50), "atk_cd": 0.7,
            "phases": 2, "sprite_folder": "werewolf",
            "pixel_scale": 4.5,
        },
        "mini_boss_2_alpha": {
            "tier": 2, "name": "Alpha Werewolf",
            "hp": 950, "attack": 30, "speed": 110, "exp": 240,
            "size": 40, "color": (90, 55, 35), "atk_cd": 0.65,
            "phases": 3, "sprite_folder": "werewolf",
            "pixel_scale": 4.7,
            "tint": (210, 170, 120),
        },
        "mini_boss_2_shadow": {
            "tier": 2, "name": "Shadow Stalker",
            "hp": 580, "attack": 34, "speed": 120, "exp": 230,
            "size": 36, "color": (60, 60, 80), "atk_cd": 0.6,
            "phases": 2, "sprite_folder": "werewolf",
            "pixel_scale": 4.4,
            "tint": (110, 110, 160),
        },

        # -- Tier 3 (final boss) --
        "final_boss": {
            "tier": 3, "name": "Elite Orc",
            "hp": 1200, "attack": 35, "speed": 80, "exp": 500,
            "size": 38, "color": (60, 120, 40), "atk_cd": 0.7,
            "phases": 3, "sprite_folder": "EliteOrc",
            "pixel_scale": 4.0,
        },
        "final_boss_warchief": {
            "tier": 3, "name": "Warchief Zarkoth",
            "hp": 1600, "attack": 33, "speed": 70, "exp": 600,
            "size": 42, "color": (90, 90, 40), "atk_cd": 0.75,
            "phases": 3, "sprite_folder": "EliteOrc",
            "pixel_scale": 4.4,
            "tint": (200, 170, 90),
        },
        "final_boss_berserker": {
            "tier": 3, "name": "Berserker Grom",
            "hp": 1000, "attack": 42, "speed": 105, "exp": 580,
            "size": 38, "color": (180, 60, 40), "atk_cd": 0.55,
            "phases": 3, "sprite_folder": "EliteOrc",
            "pixel_scale": 4.0,
            "tint": (255, 120, 120),
        },
    }

    @classmethod
    def get_tier_pool(cls, tier):
        """Return keys of all boss templates in a given tier."""
        return [k for k, v in cls.BOSS_TEMPLATES.items() if v.get("tier") == tier]

    def __init__(self, x, y, boss_type="mini_boss_1", enraged=False):
        # Build from base Enemy first, then override with boss stats.
        super().__init__(x, y, "slime", 1)

        self.boss_type = boss_type
        t = self.BOSS_TEMPLATES.get(boss_type, self.BOSS_TEMPLATES["mini_boss_1"])

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

        # Tier decides AI + special skill (all variants in tier share them).
        self.tier = t.get("tier", 1)
        self.tint = t.get("tint")

        self.enemy_type = boss_type
        self.detect_range = 500

        # Enrage buff (applied when deadline expires).
        self.enraged = enraged
        if enraged:
            self.max_hp = int(self.max_hp * 1.5)
            self.hp = self.max_hp
            self.attack = int(self.attack * 1.3)
            self.speed = int(self.speed * 1.2)

        # Phase state.
        self.phase = 1
        self.phase_thresholds = self._calculate_thresholds()

        # Flipped by GameWorld when spawned via the timeout jump-in.
        self.spawned_jump_in = False

        # Special attack state.
        self.special_timer = 0.0
        self.special_cooldown = 4.0
        self._special_effects = []
        self._using_special = False
        self._pending_special = None

        self._pulse_timer = 0.0
        self.attack_range = 40

        # Load boss sprites (replaces the base enemy sprites).
        sprite_folder = t.get("sprite_folder", boss_type)
        sprite_path = os.path.join("images", "enemies", sprite_folder)
        px_scale = t.get("pixel_scale", 4.0)
        self.animator = SpriteAnimator(sprite_path, pixel_scale=px_scale)
        self.has_sprites = self.animator.loaded
        self.has_special_anim = self.animator.has_action("special")

    def _calculate_thresholds(self):
        """HP values at which boss transitions to the next phase."""
        thresholds = []
        for i in range(1, self.max_phases):
            thresholds.append(self.max_hp * (1 - i / self.max_phases))
        return thresholds

    def attack_player(self, player):
        """Tier-3 uses a 360° spin attack; other tiers use Enemy's attack."""
        if self.tier != 3:
            return super().attack_player(player)

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

            # Hit radius slightly larger than spin_radius for forgiveness.
            self._pending_attack = {
                "release_in": self._compute_attack_release(),
                "damage": self.attack,
                "range": spin_radius + 25,
            }
        return 0

    def phase_transition(self):
        """Advance to next phase when HP crosses a threshold."""
        for i, threshold in enumerate(self.phase_thresholds):
            if self.hp <= threshold and self.phase <= i + 1:
                self.phase = i + 2
                self._on_phase_change()
                return True
        return False

    def _on_phase_change(self):
        """Buff stats and shorten special cooldown on phase up."""
        self.attack = int(self.attack * 1.15)
        self.speed = int(self.speed * 1.1)
        self.special_cooldown = max(1.5, self.special_cooldown * 0.8)

    def _get_animation_duration(self, action):
        """Return total time for an action animation, or 0.6 fallback."""
        if self.has_sprites:
            key = f"{action}_{self.direction}"
            anim = self.animator.animations.get(key)
            if anim and anim.frames:
                return len(anim.frames) * anim.frame_duration
        return 0.6

    def can_use_special(self):
        """Tier 3 can always special; other tiers need phase 2+."""
        if self.tier == 3:
            return True
        return self.phase >= 2

    def special_attack(self, player_x, player_y):
        """Trigger this boss's tier-specific special attack."""
        if self.special_timer > 0 or self._using_special:
            return None
        if self.tier != 3 and not self.can_use_special():
            return None

        self.special_timer = self.special_cooldown
        self._using_special = True

        self.direction = "right" if player_x > self.x else "left"
        self.anim_state = "special"
        if self.has_sprites and self.has_special_anim:
            self.animator.set_direction(self.direction)
            self.animator.set_action("special", force=True)

        anim_dur = self._get_animation_duration("special")

        # Per-tier skill dispatch.
        if self.tier == 1:
            return self._skill_ground_slam(player_x, player_y, anim_dur)
        elif self.tier == 2:
            return self._skill_charge_bite(player_x, player_y, anim_dur)
        elif self.tier == 3:
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
            # Damage at where boss stopped (bigger radius so the lunge-bite
            # combo reads as a real area-of-effect and is easier to dodge).
            self._special_effects.append({
                "type": "boss_melee",
                "x": self.x, "y": self.y,
                "radius": 175,
                "damage": pending["damage"],
                "timer": 0.4, "life": 0.4,
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

    # ───── Movement collision helpers (used by dash / jump_slam) ─────
    def _box_blocked(self, cx, cy, tilemap):
        """Return True if the boss's bounding box at (cx, cy) overlaps any
        wall tile. Checks all 4 corners + center, not just the centerpoint,
        so the boss's wide body can't slip its center past a wall while the
        rest of it gets stuck inside."""
        if tilemap is None:
            return False
        # Use a slightly conservative half-size so the boss doesn't graze.
        half = max(8, int(self.size * 0.45))
        pts = (
            (cx,        cy),
            (cx - half, cy - half),
            (cx + half, cy - half),
            (cx - half, cy + half),
            (cx + half, cy + half),
        )
        for (px, py) in pts:
            if tilemap.is_wall(px, py):
                return True
        return False

    def _dash_step_with_collision(self, step_x, step_y, tilemap):
        """Try to move (step_x, step_y) using axis-separated, fat collision.
        Returns (actual_dx, actual_dy)."""
        if tilemap is None:
            self.x += step_x
            self.y += step_y
            return step_x, step_y
        moved_x = 0.0
        moved_y = 0.0
        # Try both axes together first (handles diagonal dashes cleanly).
        if not self._box_blocked(self.x + step_x, self.y + step_y, tilemap):
            self.x += step_x
            self.y += step_y
            return step_x, step_y
        # Otherwise slide along whichever axis is still clear.
        if step_x and not self._box_blocked(self.x + step_x, self.y, tilemap):
            self.x += step_x
            moved_x = step_x
        if step_y and not self._box_blocked(self.x, self.y + step_y, tilemap):
            self.y += step_y
            moved_y = step_y
        return moved_x, moved_y

    def _unstick_from_wall(self, tilemap):
        """If the boss ended up overlapping a wall (e.g. spawn next to one,
        or a dash ended in geometry), nudge it out toward the nearest
        walkable direction. Tried each frame of update() as a safety net."""
        if tilemap is None or not self._box_blocked(self.x, self.y, tilemap):
            return
        # Try increasing radii until we find a free spot.
        for radius in (12, 24, 36, 48, 64, 80, 100):
            for ang_deg in range(0, 360, 30):
                ang = math.radians(ang_deg)
                tx = self.x + math.cos(ang) * radius
                ty = self.y + math.sin(ang) * radius
                if not self._box_blocked(tx, ty, tilemap):
                    self.x = tx
                    self.y = ty
                    return

    def update(self, dt, player_x, player_y, world_w, world_h, tilemap=None):
        """Update boss AI and special attack logic."""
        if not self.alive and not self._is_dying:
            return

        self.special_timer = max(0, self.special_timer - dt)
        self._pulse_timer += dt

        # On the very first tick after a timeout jump-in, fire a dramatic
        # landing shockwave so the player gets the "oh shit, it's here" feel.
        if self.spawned_jump_in:
            self.spawned_jump_in = False
            self._special_effects.append({
                "type": "shockwave",
                "x": self.x, "y": self.y,
                "radius": 0,
                "max_radius": 260,
                "damage": self.attack * 0.8,
                "timer": 0.7, "life": 0.7,
                "hit": False,
                "color": (255, 80, 50),
                "thickness": 8,
                "impact_delay": 0.0,
                "inner_ring": True,
            })
            # Small delay before the boss acts so the player registers it
            self.special_timer = 0.8
            self._attack_timer = 0.5

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
                    moved_x, moved_y = self._dash_step_with_collision(
                        step_x, step_y, tilemap)
                    # If we couldn't move on EITHER axis, the boss has slammed
                    # into a wall — cancel the rest of the dash so it can't
                    # accumulate speed against geometry and end up clipped.
                    if moved_x == 0 and moved_y == 0:
                        ps["dash_remaining"] = 0
                    else:
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
                    moved_x, moved_y = self._dash_step_with_collision(
                        step_x, step_y, tilemap)
                    if moved_x == 0 and moved_y == 0:
                        # Landed on a wall — bail out of the jump early so
                        # the slam fires here instead of clipping further in.
                        ps["jump_remaining"] = 0
                    else:
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

            # Safety net: if a dash/jump or any prior step parked us inside
            # geometry, nudge us back into walkable space before next frame.
            self._unstick_from_wall(tilemap)

            self._update_special_effects(dt)
            return

        # Normal update (inherited from Enemy) - pass tilemap for wall collision
        super().update(dt, player_x, player_y, world_w, world_h, tilemap)

        # Even outside specials, periodically unstick (covers spawn-on-wall
        # and any edge case where the inherited movement clipped us in).
        self._unstick_from_wall(tilemap)

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

    def _draw_tinted_sprite(self, surface, camera_x, camera_y):
        """Draw the current sprite frame with a multiplicative color tint.
        Falls back to normal draw if tinting fails for any reason."""
        frame = self.animator.get_frame()
        if frame is None:
            return False
        try:
            tinted = frame.copy()
            tint_surf = pygame.Surface(tinted.get_size(), pygame.SRCALPHA)
            tint_surf.fill((*self.tint, 255))
            tinted.blit(tint_surf, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
            sx = self.x - camera_x - tinted.get_width() // 2
            sy = self.y - camera_y - tinted.get_height() // 2
            surface.blit(tinted, (int(sx), int(sy)))
            return True
        except Exception:
            return False

    def draw(self, surface, camera_x, camera_y):
        """Draw boss with sprites or fallback visuals."""
        if not self.alive and not self._is_dying:
            return

        sx = int(self.x - camera_x)
        sy = int(self.y - camera_y)

        if self.has_sprites:
            drew = False
            if self.tint is not None:
                drew = self._draw_tinted_sprite(surface, camera_x, camera_y)
            if not drew:
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
