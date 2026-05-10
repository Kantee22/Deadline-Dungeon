"""glyphs.py - Sloth Glyphs: cursed gothic runes that punish standing still.

A glyph sits dormant on the dungeon floor as a faint dark sigil. When the
player stands within its radius and idles for a few seconds, it "wakes"
and starts draining HP while accelerating in-game time, embodying the
deadline theme: stay too long in one place and the deadline catches up.

Visuals are drawn with primitives only (no extra art assets) so the
gothic look comes from layered circles + an inverted-cross sigil + a
flickering crimson glow.
"""
import math
import random
import pygame


class SlothGlyph:
    """A single cursed glyph on the dungeon floor."""

    # Tunables (kept here so they're easy to balance from one place).
    RADIUS              = 90      # effect zone in pixels
    WAKE_TIME           = 2.0     # seconds of player idle inside before active
    DRAIN_HP_PER_SEC    = 1.5     # HP/s drained while awake
    TIME_MULT_AWAKE     = 1.5     # in-game timer runs this much faster
    SLEEP_TIME          = 1.2     # seconds to fully cool off after player leaves

    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)
        # 0.0 = fully dormant, 1.0 = fully awake.
        self.awake_phase = 0.0
        # 0..2π rolling angle for animation.
        self.anim_time = random.uniform(0.0, math.pi * 2)
        self.player_inside = False
        self.player_idle_inside = False

    # ───── Update ──────────────────────────────────────────────────
    def update(self, dt, player_x, player_y, player_idle_time):
        """Update the glyph's awake phase based on whether the player is
        idle inside its radius.
        `player_idle_time` is how many seconds the player has been still
        (in seconds). The glyph treats >0 as "idling"."""
        self.anim_time += dt

        dx = player_x - self.x
        dy = player_y - self.y
        dist_sq = dx * dx + dy * dy
        self.player_inside = (dist_sq <= self.RADIUS * self.RADIUS)
        self.player_idle_inside = (self.player_inside and player_idle_time >= self.WAKE_TIME)

        if self.player_idle_inside:
            # Wake up: phase climbs to 1.0 over WAKE_TIME extra seconds.
            self.awake_phase = min(1.0, self.awake_phase + dt / max(0.5, self.WAKE_TIME * 0.5))
        else:
            # Cool off whenever the player isn't standing still in zone.
            self.awake_phase = max(0.0, self.awake_phase - dt / self.SLEEP_TIME)

    # ───── Effect strength ──────────────────────────────────────────
    @property
    def is_active(self):
        """Glyph is currently siphoning the player."""
        return self.awake_phase > 0.05 and self.player_inside

    def hp_drain(self, dt):
        """How much HP to drain THIS frame (0 if not active)."""
        if not self.is_active:
            return 0.0
        return self.DRAIN_HP_PER_SEC * self.awake_phase * dt

    def time_multiplier(self):
        """Multiplier to apply to the dungeon timer this frame."""
        if not self.is_active:
            return 1.0
        # Lerp 1.0 → TIME_MULT_AWAKE based on awake_phase.
        return 1.0 + (self.TIME_MULT_AWAKE - 1.0) * self.awake_phase

    # ───── Draw ────────────────────────────────────────────────────
    def draw(self, surface, camera_x, camera_y):
        """Render the glyph on the floor. Drawn before entities."""
        sx = int(self.x - camera_x)
        sy = int(self.y - camera_y)

        # Skip off-screen draws cheaply.
        if sx < -self.RADIUS or sx > surface.get_width() + self.RADIUS:
            return
        if sy < -self.RADIUS or sy > surface.get_height() + self.RADIUS:
            return

        phase = self.awake_phase
        pulse = 0.5 + 0.5 * math.sin(self.anim_time * 3.0)

        # ── Outer halo: faint when dormant, strong red when awake.
        halo_alpha = int(20 + 80 * phase + 30 * phase * pulse)
        halo_color_r = int(80 + 140 * phase)
        halo = pygame.Surface((self.RADIUS * 2, self.RADIUS * 2), pygame.SRCALPHA)
        for i in range(6, 0, -1):
            r = int(self.RADIUS * (i / 6.0))
            a = int(halo_alpha * (i / 6.0) * 0.3)
            pygame.draw.circle(halo, (halo_color_r, 20, 30, a),
                               (self.RADIUS, self.RADIUS), r)
        surface.blit(halo, (sx - self.RADIUS, sy - self.RADIUS),
                     special_flags=pygame.BLEND_RGBA_ADD)

        # ── Sigil ring: outer dark circle.
        ring_color = self._lerp_color((40, 30, 35), (170, 30, 40), phase)
        pygame.draw.circle(surface, ring_color, (sx, sy), 38, 3)

        # Inner ring: thinner, brightens with phase.
        inner_color = self._lerp_color((60, 40, 45), (220, 60, 60), phase)
        pygame.draw.circle(surface, inner_color, (sx, sy), 28, 2)

        # ── Inverted-cross sigil in the center (gothic).
        cross_color = self._lerp_color((90, 60, 65), (255, 90, 90), phase)
        # Vertical line (long downward stroke for inverted cross feel).
        pygame.draw.line(surface, cross_color,
                         (sx, sy - 10), (sx, sy + 22), 3)
        # Horizontal line near the top (so the long arm is downward).
        pygame.draw.line(surface, cross_color,
                         (sx - 8, sy - 4), (sx + 8, sy - 4), 3)

        # ── Tick marks around the ring at 4 cardinal points (rune detail).
        for i in range(4):
            ang = math.pi * 0.5 * i + self.anim_time * 0.3 * phase
            x1 = sx + int(math.cos(ang) * 38)
            y1 = sy + int(math.sin(ang) * 38)
            x2 = sx + int(math.cos(ang) * 44)
            y2 = sy + int(math.sin(ang) * 44)
            pygame.draw.line(surface, ring_color, (x1, y1), (x2, y2), 2)

        # ── When awake, add crackling spark particles around the rim.
        if phase > 0.4:
            n_sparks = int(3 + 5 * phase)
            for _ in range(n_sparks):
                ang = random.uniform(0, math.pi * 2)
                r = random.uniform(20, 42)
                px = sx + math.cos(ang) * r
                py = sy + math.sin(ang) * r
                spark_col = (255, int(120 + 100 * phase), 80)
                pygame.draw.circle(surface, spark_col,
                                   (int(px), int(py)),
                                   random.randint(1, 2))

    @staticmethod
    def _lerp_color(c1, c2, t):
        t = max(0.0, min(1.0, t))
        return (
            int(c1[0] + (c2[0] - c1[0]) * t),
            int(c1[1] + (c2[1] - c1[1]) * t),
            int(c1[2] + (c2[2] - c1[2]) * t),
        )


# ───── Helper: build a list of glyphs from a tilemap ──────────────────
def spawn_glyphs(tilemap, count=5):
    """Sample `count` floor positions from the tilemap and create glyphs."""
    positions = tilemap.get_glyph_positions(count=count)
    return [SlothGlyph(x, y) for (x, y) in positions]
