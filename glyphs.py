"""glyphs.py - Sloth Glyphs: cursed gothic runes that punish lingering.

A glyph sits dormant on the dungeon floor as a faint dark sigil. The
moment the player steps inside its radius and stays for 1.5 seconds —
even while moving — the glyph awakens, drains HP, and accelerates the
in-game timer until the player walks back out of the circle.

Visuals are drawn with primitives only: inverted pentagram inside
concentric runed rings, crimson glow, and embers drifting upward.
"""
import math
import random
import pygame


class SlothGlyph:
    """A single cursed glyph on the dungeon floor."""

    # Tunables ---------------------------------------------------------
    RADIUS              = 120     # effect zone in pixels (was 90)
    WAKE_TIME           = 1.20    # seconds inside before activation
    DRAIN_HP_PER_SEC    = 1.5     # HP/s drained while awake
    TIME_MULT_AWAKE     = 2.8     # in-game timer runs this much faster
    SLEEP_TIME          = 1.0     # seconds to fully cool off after exit

    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)
        # 0.0 = fully dormant, 1.0 = fully awake.
        self.awake_phase = 0.0
        # Continuous time-inside counter — resets the moment the player exits.
        self.time_inside = 0.0
        # 0..2pi rolling angle for animation.
        self.anim_time = random.uniform(0.0, math.pi * 2)
        self.player_inside = False

    # Update -----------------------------------------------------------
    def update(self, dt, player_x, player_y):
        """Tick awake phase: 1.5 sec inside (any movement counts) wakes
        the glyph and it stays awake until the player exits the radius."""
        self.anim_time += dt

        dx = player_x - self.x
        dy = player_y - self.y
        dist_sq = dx * dx + dy * dy
        self.player_inside = (dist_sq <= self.RADIUS * self.RADIUS)

        if self.player_inside:
            self.time_inside += dt
            if self.time_inside >= self.WAKE_TIME:
                # Rapid ramp once threshold crossed (~0.3s to full power).
                self.awake_phase = min(1.0, self.awake_phase + dt / 0.3)
        else:
            # Walked out → reset counter and cool down smoothly.
            self.time_inside = 0.0
            self.awake_phase = max(0.0, self.awake_phase - dt / self.SLEEP_TIME)

    # Effect strength --------------------------------------------------
    @property
    def is_active(self):
        return self.awake_phase > 0.05 and self.player_inside

    def hp_drain(self, dt):
        if not self.is_active:
            return 0.0
        return self.DRAIN_HP_PER_SEC * self.awake_phase * dt

    def time_multiplier(self):
        if not self.is_active:
            return 1.0
        return 1.0 + (self.TIME_MULT_AWAKE - 1.0) * self.awake_phase

    # Draw -------------------------------------------------------------
    def draw(self, surface, camera_x, camera_y):
        sx = int(self.x - camera_x)
        sy = int(self.y - camera_y)
        if sx < -self.RADIUS or sx > surface.get_width() + self.RADIUS:
            return
        if sy < -self.RADIUS or sy > surface.get_height() + self.RADIUS:
            return

        phase = self.awake_phase
        beat = 0.5 + 0.5 * math.sin(self.anim_time * (2.0 + 4.0 * phase))

        # 1. Outer crimson halo (additive) — fills most of the radius.
        halo_r = 80 + int(28 * phase)
        halo = pygame.Surface((halo_r * 2 + 4, halo_r * 2 + 4), pygame.SRCALPHA)
        layers = 9
        for i in range(layers, 0, -1):
            rr = int(halo_r * (i / layers))
            base_a = 14 + int(60 * phase) + int(22 * phase * beat)
            a = int(base_a * (i / layers) * 0.55)
            r_col = int(85 + 145 * phase)
            pygame.draw.circle(halo, (r_col, 18, 28, a),
                               (halo_r + 2, halo_r + 2), rr)
        surface.blit(halo, (sx - halo_r - 2, sy - halo_r - 2),
                     special_flags=pygame.BLEND_RGBA_ADD)

        # 2. Outer ring (now matches the larger zone).
        outer_r = 56
        ring_color = self._lerp_color((50, 35, 40), (210, 45, 55), phase)
        pygame.draw.circle(surface, ring_color, (sx, sy), outer_r, 3)

        # 3. 8 rotating rune ticks reach further out.
        rotation = self.anim_time * 0.4 * (0.2 + 0.8 * phase)
        for i in range(8):
            ang = (math.pi * 2 / 8) * i + rotation
            x1 = sx + int(math.cos(ang) * outer_r)
            y1 = sy + int(math.sin(ang) * outer_r)
            x2 = sx + int(math.cos(ang) * (outer_r + 9))
            y2 = sy + int(math.sin(ang) * (outer_r + 9))
            pygame.draw.line(surface, ring_color, (x1, y1), (x2, y2), 2)

        # 4. Middle ring.
        mid_r = 42
        mid_color = self._lerp_color((70, 45, 50), (245, 75, 85), phase)
        pygame.draw.circle(surface, mid_color, (sx, sy), mid_r, 2)

        # 5. Inverted pentagram (point DOWN), bigger.
        star_color = self._lerp_color((100, 60, 65), (255, 105, 115), phase)
        star_r = mid_r - 6
        wobble = math.sin(self.anim_time * 1.7) * 0.05 * phase
        star_pts = []
        for i in range(5):
            ang = math.pi / 2 + (math.pi * 2 / 5) * i + wobble
            px = sx + math.cos(ang) * star_r
            py = sy + math.sin(ang) * star_r
            star_pts.append((px, py))
        order = [0, 2, 4, 1, 3, 0]
        for i in range(len(order) - 1):
            a = star_pts[order[i]]
            b = star_pts[order[i + 1]]
            thick = 2 + (1 if phase > 0.5 else 0)
            pygame.draw.line(surface, star_color,
                             (int(a[0]), int(a[1])),
                             (int(b[0]), int(b[1])), thick)

        # 6. Center bloodspot when waking (bigger, more pulsing).
        if phase > 0.10:
            core_r = max(3, int(5 + 4 * phase * beat))
            core_col = (
                int(140 + 100 * phase),
                int(20 + 30 * phase),
                int(30 + 30 * phase),
            )
            pygame.draw.circle(surface, core_col, (sx, sy), core_r)

        # 7. Ember particles drifting upward.
        if phase > 0.20:
            n = int(3 + 8 * phase)
            for _ in range(n):
                ang = random.uniform(0, math.pi * 2)
                r = random.uniform(10, outer_r + 6)
                px = sx + math.cos(ang) * r
                drift = random.uniform(-14, -2)
                py = sy + math.sin(ang) * r + drift
                size = random.choice([1, 1, 2, 2])
                ember_col = (
                    255,
                    int(110 + 110 * phase),
                    int(60 + 40 * random.random()),
                )
                pygame.draw.circle(surface, ember_col,
                                   (int(px), int(py)), size)

    @staticmethod
    def _lerp_color(c1, c2, t):
        t = max(0.0, min(1.0, t))
        return (
            int(c1[0] + (c2[0] - c1[0]) * t),
            int(c1[1] + (c2[1] - c1[1]) * t),
            int(c1[2] + (c2[2] - c1[2]) * t),
        )


# Helper: build a list of glyphs from a tilemap ----------------------
def spawn_glyphs(tilemap, count=5):
    """Sample `count` floor positions from the tilemap and create glyphs."""
    positions = tilemap.get_glyph_positions(count=count)
    return [SlothGlyph(x, y) for (x, y) in positions]
