"""
ui.py - UI class for Deadline Dungeon
Handles HUD, menus, class selection, and game over screens.
"""
import pygame
import math
import random


class UI:
    def __init__(self, screen_w, screen_h):
        self.screen_w = screen_w
        self.screen_h = screen_h

        pygame.font.init()
        self.font_lg = pygame.font.SysFont("consolas", 28, bold=True)
        self.font_md = pygame.font.SysFont("consolas", 20)
        self.font_sm = pygame.font.SysFont("consolas", 15)
        self.font_title = pygame.font.SysFont("consolas", 48, bold=True)
        self.font_huge = pygame.font.SysFont("consolas", 72, bold=True)

        self.WHITE = (255, 255, 255)
        self.GRAY = (160, 160, 160)

        # ─── Animated game-over backdrop state ────────────────────────────
        # These are initialised on first draw of each game-over screen.
        self._go_time = 0.0          # seconds since screen was first shown
        self._go_last_state = None   # "victory" / "defeat" — detect reset
        self._go_particles = []      # list of floating particles
        self._go_bg_victory = None   # pre-rendered backdrop surface (win)
        self._go_bg_defeat = None    # pre-rendered backdrop surface (loss)

        # Load menu background from images/menu/menu_background.png
        self.menu_background = None
        import os
        bg_path = os.path.join("images", "menu", "menu_background.png")
        if os.path.exists(bg_path):
            try:
                raw = pygame.image.load(bg_path)
                # Menu background doesn't need alpha but we still use the
                # safe conversion pattern for consistency with sprites
                try:
                    raw = raw.convert()
                except pygame.error:
                    pass
                # Scale to screen size
                self.menu_background = pygame.transform.scale(
                    raw, (screen_w, screen_h))
            except pygame.error:
                pass

    def _draw_bar(self, surface, x, y, w, h, fraction, fill_color, bg_color):
        pygame.draw.rect(surface, bg_color, (x, y, w, h), border_radius=3)
        fill_w = int(w * max(0, min(1, fraction)))
        if fill_w > 0:
            pygame.draw.rect(surface, fill_color, (x, y, fill_w, h), border_radius=3)
        pygame.draw.rect(surface, (80, 80, 80), (x, y, w, h), 1, border_radius=3)

    def draw_hud(self, surface, player, game_time, max_time):
        # HP Bar
        hp_frac = player.hp / player.max_hp if player.max_hp > 0 else 0
        self._draw_bar(surface, 20, 20, 220, 22, hp_frac, (220, 50, 50), (60, 20, 20))
        hp_text = self.font_sm.render(f"HP {player.hp}/{player.max_hp}", True, self.WHITE)
        surface.blit(hp_text, (25, 22))

        # EXP Bar
        self._draw_bar(surface, 20, 48, 220, 14, player.exp_fraction, (60, 120, 220), (20, 30, 60))
        exp_text = self.font_sm.render(f"EXP {player.exp}/{player.exp_to_next}", True, self.WHITE)
        surface.blit(exp_text, (25, 48))

        # Level
        lv_text = self.font_lg.render(f"Lv.{player.level}", True, self.WHITE)
        surface.blit(lv_text, (20, 68))

        # Class
        class_colors = {
            "Soldier": self.GRAY,
            "Knight": (255, 100, 100),
            "Wizard": (120, 120, 255),
            "Archer": (100, 230, 100),
        }
        cls_color = class_colors.get(player.class_type, self.WHITE)
        cls_text = self.font_md.render(player.class_type, True, cls_color)
        surface.blit(cls_text, (110, 74))

        # Timer
        remaining = max(0, max_time - game_time)
        minutes = int(remaining) // 60
        seconds = int(remaining) % 60
        if remaining < 60:
            timer_color = (255, 40, 40)
        elif remaining < 180:
            timer_color = (255, 100, 50)
        else:
            timer_color = (220, 220, 220)

        timer_str = f"{minutes:02d}:{seconds:02d}"
        timer_text = self.font_lg.render(timer_str, True, timer_color)
        tr = timer_text.get_rect(midtop=(self.screen_w // 2, 15))
        surface.blit(timer_text, tr)

        # Skill cooldown indicator (bottom right)
        cd_frac = player.skill_cooldown_fraction
        cd_text = "Skill: READY" if cd_frac >= 1.0 else f"Skill: {cd_frac:.0%}"
        cd_color = (100, 255, 100) if cd_frac >= 1.0 else (255, 150, 50)
        cd_surf = self.font_sm.render(cd_text, True, cd_color)
        surface.blit(cd_surf, (self.screen_w - 140, self.screen_h - 30))

    def draw_minimap(self, surface, player, enemies, bosses, tilemap):
        """Draw a minimap in the top-right corner showing the dungeon layout,
        the player's current position (green dot) and all boss positions
        (pulsing red dot).  Shows regular enemies as faint yellow specks."""
        if tilemap is None:
            return

        # Minimap dimensions & position (top-right, sits below top HUD)
        map_w = 150
        map_h = 150
        margin = 12
        mx = self.screen_w - map_w - margin
        my = margin

        # Backdrop panel
        panel = pygame.Surface((map_w + 10, map_h + 26), pygame.SRCALPHA)
        panel.fill((10, 8, 14, 210))
        surface.blit(panel, (mx - 5, my - 21))
        pygame.draw.rect(surface, (120, 100, 60),
                         (mx - 5, my - 21, map_w + 10, map_h + 26),
                         1, border_radius=4)

        # Title
        title = self.font_sm.render("MAP", True, (255, 220, 120))
        surface.blit(title, (mx, my - 18))

        # Compute scale factors mapping world → minimap pixels
        sx = map_w / max(1, tilemap.world_w)
        sy = map_h / max(1, tilemap.world_h)

        # Build (or reuse cached) tile grid surface per tilemap instance
        cache_key = "_minimap_cache"
        cached = getattr(tilemap, cache_key, None)
        if cached is None or cached.get_size() != (map_w, map_h):
            grid_surf = pygame.Surface((map_w, map_h), pygame.SRCALPHA)
            grid_surf.fill((18, 14, 22, 255))
            tw = tilemap.map_w
            th = tilemap.map_h
            cell_w = map_w / max(1, tw)
            cell_h = map_h / max(1, th)
            for ty in range(th):
                for tx in range(tw):
                    if tilemap.grid[ty][tx] == 1:  # floor
                        px = int(tx * cell_w)
                        py = int(ty * cell_h)
                        ww = max(1, int(cell_w + 1))
                        hh = max(1, int(cell_h + 1))
                        pygame.draw.rect(grid_surf, (90, 78, 95, 255),
                                         (px, py, ww, hh))
            setattr(tilemap, cache_key, grid_surf)
            cached = grid_surf

        surface.blit(cached, (mx, my))
        # Inner border
        pygame.draw.rect(surface, (70, 55, 35),
                         (mx, my, map_w, map_h), 1)

        # Enemy specks (small, faint yellow)
        for e in enemies:
            if not e.alive or e._is_dying:
                continue
            ex = mx + int(e.x * sx)
            ey = my + int(e.y * sy)
            if mx <= ex < mx + map_w and my <= ey < my + map_h:
                pygame.draw.circle(surface, (220, 200, 80), (ex, ey), 1)

        # Boss markers — big pulsing red dot with ring
        # Use pygame ticks so it pulses independent of game-over timer
        t_pulse = pygame.time.get_ticks() / 1000.0
        pulse = 0.5 + 0.5 * math.sin(t_pulse * 4.0)
        for b in bosses:
            if not b.alive:
                continue
            bx = mx + int(b.x * sx)
            by = my + int(b.y * sy)
            if mx <= bx < mx + map_w and my <= by < my + map_h:
                # Outer pulsing ring
                r_ring = 6 + int(4 * pulse)
                ring_surf = pygame.Surface(
                    (r_ring * 2 + 2, r_ring * 2 + 2), pygame.SRCALPHA)
                pygame.draw.circle(ring_surf,
                                   (255, 60, 60, 160),
                                   (r_ring + 1, r_ring + 1), r_ring, 2)
                surface.blit(ring_surf, (bx - r_ring - 1, by - r_ring - 1))
                # Solid dot
                pygame.draw.circle(surface, (255, 40, 40), (bx, by), 3)
                pygame.draw.circle(surface, (120, 0, 0), (bx, by), 3, 1)
                # Tiny label "B" above
                label = self.font_sm.render("B", True, (255, 220, 120))
                surface.blit(label, (bx - 4, by - 16))

        # Player marker — green dot with facing arrow
        px = mx + int(player.x * sx)
        py = my + int(player.y * sy)
        if mx <= px < mx + map_w and my <= py < my + map_h:
            # Halo
            halo = pygame.Surface((18, 18), pygame.SRCALPHA)
            pygame.draw.circle(halo, (80, 255, 80, 90), (9, 9), 8)
            surface.blit(halo, (px - 9, py - 9))
            pygame.draw.circle(surface, (70, 240, 70), (px, py), 3)
            pygame.draw.circle(surface, (0, 40, 0), (px, py), 3, 1)
            # Facing arrow
            fx = px + math.cos(player.facing) * 8
            fy = py + math.sin(player.facing) * 8
            pygame.draw.line(surface, (180, 255, 180),
                             (px, py), (int(fx), int(fy)), 1)

    def draw_class_selection(self, surface):
        overlay = pygame.Surface((self.screen_w, self.screen_h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))

        title = self.font_title.render("Choose Your Class", True, (255, 220, 80))
        tr = title.get_rect(center=(self.screen_w // 2, 100))
        surface.blit(title, tr)

        classes = [
            {"name": "Knight", "key": "1", "color": (220, 80, 80),
             "desc": ["High HP & Defense", "Left: Sword slash", "Right: Fire sword"]},
            {"name": "Wizard", "key": "2", "color": (100, 100, 240),
             "desc": ["High Magic Damage", "Left: Fireball", "Right: Ice explosion"]},
            {"name": "Archer", "key": "3", "color": (80, 200, 80),
             "desc": ["Fast & Precise", "Left: Arrow shot", "Right: Pierce arrow"]},
        ]

        card_w = 200
        card_h = 200
        total = len(classes) * card_w + (len(classes) - 1) * 30
        start_x = (self.screen_w - total) // 2

        for i, cls in enumerate(classes):
            x = start_x + i * (card_w + 30)
            y = 180

            pygame.draw.rect(surface, (30, 30, 40), (x, y, card_w, card_h), border_radius=8)
            pygame.draw.rect(surface, cls["color"], (x, y, card_w, card_h), 2, border_radius=8)

            name_text = self.font_lg.render(cls["name"], True, cls["color"])
            nr = name_text.get_rect(center=(x + card_w // 2, y + 35))
            surface.blit(name_text, nr)

            for j, desc in enumerate(cls["desc"]):
                desc_text = self.font_sm.render(desc, True, self.GRAY)
                dr = desc_text.get_rect(center=(x + card_w // 2, y + 80 + j * 22))
                surface.blit(desc_text, dr)

            key_text = self.font_md.render(f"Press [{cls['key']}]", True, self.WHITE)
            kr = key_text.get_rect(center=(x + card_w // 2, y + card_h - 25))
            surface.blit(key_text, kr)

    def draw_boss_hp_bar(self, surface, boss):
        bar_w = 400
        bar_h = 20
        x = (self.screen_w - bar_w) // 2
        # Lowered from y=50 to y=88 so the boss bar + boss name no longer
        # collide with the centered session timer (which sits at y≈15-45).
        y = 88

        name_text = self.font_md.render(boss.boss_name, True, (255, 200, 50))
        nr = name_text.get_rect(center=(self.screen_w // 2, y - 14))
        surface.blit(name_text, nr)

        ratio = boss.hp / boss.max_hp
        pygame.draw.rect(surface, (40, 10, 10), (x, y, bar_w, bar_h), border_radius=4)
        if ratio > 0:
            pygame.draw.rect(surface, (200, 40, 40),
                             (x, y, int(bar_w * ratio), bar_h), border_radius=4)
        pygame.draw.rect(surface, (120, 80, 30), (x, y, bar_w, bar_h), 2, border_radius=4)

        phase_text = self.font_sm.render(
            f"Phase {boss.phase}/{boss.max_phases}", True, self.GRAY)
        pr = phase_text.get_rect(midleft=(x + bar_w + 10, y + bar_h // 2))
        surface.blit(phase_text, pr)

    def draw_level_up_effect(self, surface, timer):
        if timer <= 0:
            return

        # No full-screen flash — just a gentle fade-in text above player area
        # Fade the text in based on timer (short 0.5s burst)
        # timer goes from 1.0 down to 0; use 0.3-0.8 window
        if timer < 0.15:
            return
        fade = min(1.0, (1.0 - timer) * 2) if timer > 0.5 else timer * 1.5
        fade = max(0, min(1.0, fade))

        text = self.font_lg.render("LEVEL UP!", True, (255, 220, 50))
        text.set_alpha(int(255 * fade))
        tr = text.get_rect(center=(self.screen_w // 2, self.screen_h // 2 - 80))
        surface.blit(text, tr)

        # Subtle glow badge below text
        badge = pygame.Surface((140, 6), pygame.SRCALPHA)
        badge.fill((255, 220, 50, int(150 * fade)))
        br = badge.get_rect(center=(self.screen_w // 2, self.screen_h // 2 - 55))
        surface.blit(badge, br)

    # ──────────────────── Game-over backdrop helpers ────────────────────

    def reset_game_over_state(self):
        """Called when the game restarts so the next game-over screen
        re-seeds its particles and replays its entrance animation."""
        self._go_last_state = None
        self._go_time = 0.0
        self._go_particles.clear()

    def _build_victory_background(self):
        """Pre-render an elaborate gothic-cathedral victory backdrop:
        warm stone walls, a glowing stained-glass rose window, towering
        pointed-arch tracery, pillared nave, laurel-crown motif, scrollwork
        corners and ornate gold trim.  All drawn with primitives."""
        w, h = self.screen_w, self.screen_h
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        rng = random.Random(11)

        # ── 1) Warm stone gradient: amber top → deep umber floor
        for y in range(h):
            t = y / h
            col = (
                int(96 * (1 - t) + 26 * t),
                int(64 * (1 - t) + 14 * t),
                int(28 * (1 - t) + 6 * t),
            )
            pygame.draw.line(surf, (*col, 255), (0, y), (w, y))

        # ── 2) Stone noise / speckles
        for _ in range(700):
            sx = rng.randint(0, w - 1)
            sy = rng.randint(0, h - 1)
            shade = rng.randint(-16, 16)
            base = surf.get_at((sx, sy))
            r = max(0, min(255, base[0] + shade))
            g = max(0, min(255, base[1] + shade))
            b = max(0, min(255, base[2] + shade))
            surf.set_at((sx, sy), (r, g, b, 255))

        # Brick courses
        for y in range(0, h, 44):
            pygame.draw.line(surf, (40, 28, 14, 170), (0, y), (w, y), 1)
            offset = (y // 44 % 2) * 50
            for x in range(offset, w, 100):
                pygame.draw.line(surf, (32, 22, 10, 170),
                                 (x, y), (x, y + 44), 1)

        cx = w // 2

        # ── 3) Grand central pointed arch framing the rose window + nave
        arch_w = int(min(w * 0.62, 430))
        arch_top = 90
        arch_bot = h - 90
        arch_left = cx - arch_w // 2
        arch_right = cx + arch_w // 2
        arch_apex = arch_top - 50
        # Inside-arch pane (dim warm interior)
        pane_col = (44, 24, 10, 240)
        arch_points = [
            (arch_left, arch_bot),
            (arch_left, arch_top + 40),
            (cx, arch_apex),
            (arch_right, arch_top + 40),
            (arch_right, arch_bot),
        ]
        pygame.draw.polygon(surf, pane_col, arch_points)
        # Outer stone frame (double band)
        pygame.draw.polygon(surf, (180, 140, 70), arch_points, 5)
        inner_points = [
            (arch_left + 10, arch_bot),
            (arch_left + 10, arch_top + 50),
            (cx, arch_apex + 14),
            (arch_right - 10, arch_top + 50),
            (arch_right - 10, arch_bot),
        ]
        pygame.draw.polygon(surf, (120, 80, 30), inner_points, 2)

        # ── 4) Rose window (stained glass) in upper section of arch
        rose_cx = cx
        rose_cy = arch_top + 100
        rose_r = min(arch_w // 2 - 30, 110)

        # Radial beams of light behind the rose
        beams = pygame.Surface((w, h), pygame.SRCALPHA)
        for i in range(24):
            ang = i * math.tau / 24
            x1 = rose_cx + math.cos(ang) * (rose_r + 6)
            y1 = rose_cy + math.sin(ang) * (rose_r + 6)
            x2 = rose_cx + math.cos(ang) * (rose_r + 220)
            y2 = rose_cy + math.sin(ang) * (rose_r + 220)
            pygame.draw.line(beams, (255, 220, 110, 28),
                             (x1, y1), (x2, y2), 3)
        surf.blit(beams, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

        # Rose background disc (dim deep amber)
        pygame.draw.circle(surf, (60, 32, 14), (rose_cx, rose_cy), rose_r + 8)
        pygame.draw.circle(surf, (200, 160, 80), (rose_cx, rose_cy),
                           rose_r + 8, 3)
        pygame.draw.circle(surf, (120, 80, 30), (rose_cx, rose_cy),
                           rose_r + 2, 2)

        # Rose petals — 12 segments alternating warm colours
        petal_cols = [
            (235, 180, 70), (220, 110, 50),
            (240, 210, 120), (200, 80, 40),
        ]
        for i in range(12):
            a1 = i * math.tau / 12
            a2 = (i + 1) * math.tau / 12
            col = petal_cols[i % len(petal_cols)]
            # Build petal polygon from center outward
            pts = [(rose_cx, rose_cy)]
            steps = 6
            for s in range(steps + 1):
                ang = a1 + (a2 - a1) * s / steps
                pts.append((rose_cx + math.cos(ang) * rose_r,
                            rose_cy + math.sin(ang) * rose_r))
            pygame.draw.polygon(surf, col, pts)
            # Divider ribs between petals (dark stone)
            dx = math.cos(a1) * rose_r
            dy = math.sin(a1) * rose_r
            pygame.draw.line(surf, (40, 24, 10),
                             (rose_cx, rose_cy),
                             (rose_cx + dx, rose_cy + dy), 3)

        # Inner ring of the rose
        pygame.draw.circle(surf, (255, 240, 180),
                           (rose_cx, rose_cy), rose_r // 3)
        pygame.draw.circle(surf, (200, 140, 50),
                           (rose_cx, rose_cy), rose_r // 3, 2)
        # Center small cross
        pygame.draw.rect(surf, (90, 55, 20),
                         (rose_cx - 2, rose_cy - 10, 4, 20))
        pygame.draw.rect(surf, (90, 55, 20),
                         (rose_cx - 10, rose_cy - 2, 20, 4))

        # Rose halo (additive)
        halo = pygame.Surface((w, h), pygame.SRCALPHA)
        for r in range(rose_r + 140, 0, -10):
            a = int(3 + (rose_r + 140 - r) * 0.25)
            pygame.draw.circle(halo, (255, 210, 110, a),
                               (rose_cx, rose_cy), r)
        surf.blit(halo, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

        # ── 5) Lower tracery — vertical mullion and two sub-arches below rose
        lower_top = rose_cy + rose_r + 30
        pygame.draw.line(surf, (120, 80, 30),
                         (cx, lower_top), (cx, arch_bot), 3)
        for side in (-1, 1):
            mx = cx + side * (arch_w // 4)
            sub_top = lower_top + 30
            sub_points = [
                (mx - arch_w // 8, arch_bot),
                (mx - arch_w // 8, sub_top + 20),
                (mx, sub_top),
                (mx + arch_w // 8, sub_top + 20),
                (mx + arch_w // 8, arch_bot),
            ]
            pygame.draw.polygon(surf, (140, 100, 50), sub_points, 2)
            # Tiny quatrefoil in each sub-arch
            q_cx = mx
            q_cy = sub_top + 40
            for (qx, qy) in ((-7, 0), (7, 0), (0, -7), (0, 7)):
                pygame.draw.circle(surf, (220, 180, 90),
                                   (q_cx + qx, q_cy + qy), 5)
            pygame.draw.circle(surf, (120, 80, 30),
                               (q_cx, q_cy), 3)

        # ── 6) Side pillars with capitals & bases
        for px in (40, w - 70):
            pygame.draw.rect(surf, (64, 44, 22, 255), (px, 0, 30, h))
            pygame.draw.rect(surf, (140, 100, 50), (px, 0, 30, h), 2)
            for y in range(0, h, 28):
                pygame.draw.line(surf, (36, 24, 12, 200),
                                 (px, y), (px + 30, y), 1)
            # Capital (top)
            pygame.draw.rect(surf, (170, 130, 70), (px - 8, 58, 46, 18))
            pygame.draw.rect(surf, (90, 60, 25), (px - 8, 58, 46, 18), 2)
            pygame.draw.rect(surf, (200, 160, 80), (px - 10, 50, 50, 6))
            # Base
            pygame.draw.rect(surf, (170, 130, 70), (px - 8, h - 76, 46, 18))
            pygame.draw.rect(surf, (90, 60, 25), (px - 8, h - 76, 46, 18), 2)
            pygame.draw.rect(surf, (200, 160, 80), (px - 10, h - 56, 50, 6))
            # Fluting lines on shaft
            for fy in range(90, h - 90, 60):
                pygame.draw.line(surf, (200, 160, 80, 150),
                                 (px + 10, fy), (px + 10, fy + 40), 1)
                pygame.draw.line(surf, (200, 160, 80, 150),
                                 (px + 20, fy), (px + 20, fy + 40), 1)

        # ── 7) Laurel / crown motif above the arch apex
        crown_cx = cx
        crown_cy = arch_apex - 22
        # Base band
        pygame.draw.rect(surf, (220, 180, 80),
                         (crown_cx - 26, crown_cy + 6, 52, 10))
        pygame.draw.rect(surf, (120, 80, 25),
                         (crown_cx - 26, crown_cy + 6, 52, 10), 1)
        # Three crown peaks
        for (ox, oy, r) in ((-18, 0, 6), (0, -6, 8), (18, 0, 6)):
            pygame.draw.polygon(surf, (255, 220, 110),
                                [(crown_cx + ox - r, crown_cy + 6),
                                 (crown_cx + ox, crown_cy + 6 - r * 2),
                                 (crown_cx + ox + r, crown_cy + 6)])
            pygame.draw.circle(surf, (255, 240, 180),
                               (crown_cx + ox, crown_cy + 6 - r * 2 - 1), 2)
        # Laurel leaves flanking the crown
        for side in (-1, 1):
            for i in range(5):
                lx = crown_cx + side * (34 + i * 10)
                ly = crown_cy + 10 - i * 2
                pygame.draw.ellipse(surf, (120, 170, 80),
                                    (lx - 7, ly - 3, 12, 6))
                pygame.draw.ellipse(surf, (70, 110, 40),
                                    (lx - 7, ly - 3, 12, 6), 1)

        # ── 8) Banners with tassels hanging from top
        banner_cols = [(180, 40, 40), (60, 120, 200)]
        for i, bx in enumerate((arch_left - 60, arch_right + 30)):
            bcol = banner_cols[i % 2]
            top_y = 80
            # Flag body
            pts = [(bx, top_y), (bx + 40, top_y),
                   (bx + 40, top_y + 90),
                   (bx + 20, top_y + 104),
                   (bx, top_y + 90)]
            pygame.draw.polygon(surf, bcol, pts)
            pygame.draw.polygon(surf, (30, 20, 10), pts, 2)
            # Gold emblem (circle + star point)
            pygame.draw.circle(surf, (230, 190, 90),
                               (bx + 20, top_y + 45), 10)
            pygame.draw.circle(surf, (120, 80, 25),
                               (bx + 20, top_y + 45), 10, 1)
            pygame.draw.line(surf, (230, 190, 90),
                             (bx + 20, top_y + 30),
                             (bx + 20, top_y + 60), 2)
            pygame.draw.line(surf, (230, 190, 90),
                             (bx + 7, top_y + 45),
                             (bx + 33, top_y + 45), 2)
            # Pole / hanger
            pygame.draw.line(surf, (110, 80, 40),
                             (bx + 20, 60), (bx + 20, top_y), 2)
            # Tassel
            pygame.draw.circle(surf, (230, 190, 90),
                               (bx + 20, top_y + 110), 3)

        # ── 9) Floor — stepped altar dais silhouette at bottom center
        dais_w = arch_w + 120
        dais_top = arch_bot - 10
        for step in range(3):
            sw = dais_w - step * 60
            sx = cx - sw // 2
            sy = dais_top + step * 14
            pygame.draw.rect(surf, (80, 54, 22), (sx, sy, sw, 14))
            pygame.draw.rect(surf, (140, 100, 50), (sx, sy, sw, 14), 1)

        # Candelabra at the altar steps
        for side in (-1, 1):
            cx_c = cx + side * 120
            cy_c = dais_top - 30
            # Stand
            pygame.draw.rect(surf, (120, 90, 40),
                             (cx_c - 2, cy_c, 4, 30))
            pygame.draw.rect(surf, (200, 160, 80),
                             (cx_c - 10, cy_c + 28, 20, 4))
            # Flame halo
            halo = pygame.Surface((50, 50), pygame.SRCALPHA)
            for r in range(22, 0, -2):
                a = int(8 + (22 - r) * 3)
                pygame.draw.circle(halo, (255, 200, 100, a), (25, 25), r)
            surf.blit(halo, (cx_c - 25, cy_c - 25),
                      special_flags=pygame.BLEND_RGBA_ADD)

        # ── 10) Soft radial glow from the rose that suffuses the whole arch
        glow = pygame.Surface((w, h), pygame.SRCALPHA)
        big_r = int(min(w, h) * 0.7)
        for r in range(big_r, 0, -10):
            a = int(2 + (big_r - r) * 0.12)
            pygame.draw.circle(glow, (255, 210, 120, a),
                               (rose_cx, rose_cy), r)
        surf.blit(glow, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

        # ── 11) Vignette for cathedral depth
        vig = pygame.Surface((w, h), pygame.SRCALPHA)
        max_vr = int(math.hypot(cx, h // 2))
        for r in range(max_vr, 0, -8):
            t = 1 - r / max_vr
            a = int(110 * t * t)
            pygame.draw.circle(vig, (0, 0, 0, a), (cx, h // 2), r)
        surf.blit(vig, (0, 0))

        # ── 12) Top & bottom gold banners with ornate trim
        banner = pygame.Surface((w, 70), pygame.SRCALPHA)
        banner.fill((14, 8, 2, 210))
        surf.blit(banner, (0, 0))
        surf.blit(banner, (0, h - 70))
        pygame.draw.line(surf, (240, 200, 100), (0, 70), (w, 70), 3)
        pygame.draw.line(surf, (130, 90, 30), (0, 74), (w, 74), 1)
        pygame.draw.line(surf, (240, 200, 100), (0, h - 70), (w, h - 70), 3)
        pygame.draw.line(surf, (130, 90, 30), (0, h - 66), (w, h - 66), 1)
        # Ornamental dots along the trim
        for dx in range(40, w, 80):
            pygame.draw.circle(surf, (255, 230, 140), (dx, 72), 3)
            pygame.draw.circle(surf, (255, 230, 140), (dx, h - 68), 3)

        # ── 13) Corner scrollwork flourishes (filigree)
        def draw_scroll(ox, oy, mirror_x=1, mirror_y=1):
            # Main diamond
            pts = [(ox, oy - 10), (ox + 9 * mirror_x, oy),
                   (ox, oy + 10), (ox - 9 * mirror_x, oy)]
            pygame.draw.polygon(surf, (255, 220, 120), pts)
            pygame.draw.polygon(surf, (120, 80, 20), pts, 1)
            # Spiraling arc
            for i in range(6):
                ang = i * 0.4 * mirror_x
                rr = 14 + i * 3
                ax = ox + math.cos(ang) * rr * mirror_x
                ay = oy + math.sin(ang) * rr * mirror_y
                pygame.draw.circle(surf, (230, 190, 90),
                                   (int(ax), int(ay)), 2)
            # Lines fanning out
            for dang in (0.3, 0.6, 0.9):
                lx = ox + math.cos(dang) * 30 * mirror_x
                ly = oy + math.sin(dang) * 30 * mirror_y
                pygame.draw.line(surf, (200, 160, 80),
                                 (ox, oy), (int(lx), int(ly)), 1)

        draw_scroll(40, 40, 1, 1)
        draw_scroll(w - 40, 40, -1, 1)
        draw_scroll(40, h - 40, 1, -1)
        draw_scroll(w - 40, h - 40, -1, -1)

        return surf

    def _build_defeat_background(self):
        """Pre-render an elaborate Gothic defeat backdrop: shattered rose
        window bleeding red light, towering tracery arch, pillared crypt,
        gargoyle silhouettes, skull finials, chains, tombstones, candles,
        blood streaks, and deep vignette.  All drawn with primitives."""
        w, h = self.screen_w, self.screen_h
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        rng = random.Random(7)

        # ── 1) Cold stone gradient: bruise-violet top → near-black floor
        for y in range(h):
            t = y / h
            col = (
                int(34 * (1 - t) + 4 * t),
                int(22 * (1 - t) + 2 * t),
                int(42 * (1 - t) + 6 * t),
            )
            pygame.draw.line(surf, (*col, 255), (0, y), (w, y))

        # ── 2) Stone noise
        for _ in range(750):
            sx = rng.randint(0, w - 1)
            sy = rng.randint(0, h - 1)
            shade = rng.randint(-16, 16)
            base = surf.get_at((sx, sy))
            r = max(0, min(255, base[0] + shade))
            g = max(0, min(255, base[1] + shade))
            b = max(0, min(255, base[2] + shade))
            surf.set_at((sx, sy), (r, g, b, 255))

        # Brick courses
        for y in range(0, h, 42):
            pygame.draw.line(surf, (16, 10, 20, 200), (0, y), (w, y), 1)
            offset = (y // 42 % 2) * 48
            for x in range(offset, w, 96):
                pygame.draw.line(surf, (10, 6, 14, 200),
                                 (x, y), (x, y + 42), 1)

        cx = w // 2

        # ── 3) Central gothic pointed arch
        arch_w = int(min(w * 0.62, 430))
        arch_top = 90
        arch_bot = h - 90
        arch_left = cx - arch_w // 2
        arch_right = cx + arch_w // 2
        arch_apex = arch_top - 50
        # Inside-arch pane (very dark, with blood glow)
        pane_col = (10, 4, 10, 240)
        arch_points = [
            (arch_left, arch_bot),
            (arch_left, arch_top + 40),
            (cx, arch_apex),
            (arch_right, arch_top + 40),
            (arch_right, arch_bot),
        ]
        pygame.draw.polygon(surf, pane_col, arch_points)
        # Outer stone frame (double band)
        pygame.draw.polygon(surf, (72, 52, 58), arch_points, 5)
        inner_points = [
            (arch_left + 10, arch_bot),
            (arch_left + 10, arch_top + 50),
            (cx, arch_apex + 14),
            (arch_right - 10, arch_top + 50),
            (arch_right - 10, arch_bot),
        ]
        pygame.draw.polygon(surf, (50, 32, 40), inner_points, 2)

        # ── 4) Shattered rose window — red light bleeding through cracks
        rose_cx = cx
        rose_cy = arch_top + 100
        rose_r = min(arch_w // 2 - 30, 110)

        # Red light bleeding behind the rose (big additive glow)
        bleed = pygame.Surface((w, h), pygame.SRCALPHA)
        for r in range(rose_r + 260, 0, -10):
            a = int(2 + (rose_r + 260 - r) * 0.14)
            pygame.draw.circle(bleed, (180, 28, 30, a),
                               (rose_cx, rose_cy), r)
        surf.blit(bleed, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

        # Rose backing disc (deep shadow)
        pygame.draw.circle(surf, (28, 8, 12), (rose_cx, rose_cy), rose_r + 8)
        pygame.draw.circle(surf, (120, 40, 44), (rose_cx, rose_cy),
                           rose_r + 8, 3)
        pygame.draw.circle(surf, (60, 20, 22), (rose_cx, rose_cy),
                           rose_r + 2, 2)

        # Shattered petals — some intact (dark red), some knocked out (glowing)
        shattered_idx = {1, 4, 7, 10}  # indices of "missing" petals
        petal_cols = [
            (90, 20, 24), (110, 28, 28), (70, 12, 18), (100, 24, 26),
        ]
        for i in range(12):
            a1 = i * math.tau / 12
            a2 = (i + 1) * math.tau / 12
            if i in shattered_idx:
                # Missing petal — fill with intense red light instead
                pts = [(rose_cx, rose_cy)]
                steps = 6
                for s in range(steps + 1):
                    ang = a1 + (a2 - a1) * s / steps
                    pts.append((rose_cx + math.cos(ang) * rose_r,
                                rose_cy + math.sin(ang) * rose_r))
                pygame.draw.polygon(surf, (220, 40, 40), pts)
                # Extra bright core inside the missing petal
                mid_ang = (a1 + a2) / 2
                gx = rose_cx + math.cos(mid_ang) * rose_r * 0.6
                gy = rose_cy + math.sin(mid_ang) * rose_r * 0.6
                glow = pygame.Surface((60, 60), pygame.SRCALPHA)
                for rr in range(28, 0, -3):
                    aa = int(8 + (28 - rr) * 4)
                    pygame.draw.circle(glow, (255, 80, 60, aa),
                                       (30, 30), rr)
                surf.blit(glow, (int(gx) - 30, int(gy) - 30),
                          special_flags=pygame.BLEND_RGBA_ADD)
            else:
                col = petal_cols[i % len(petal_cols)]
                pts = [(rose_cx, rose_cy)]
                steps = 6
                for s in range(steps + 1):
                    ang = a1 + (a2 - a1) * s / steps
                    pts.append((rose_cx + math.cos(ang) * rose_r,
                                rose_cy + math.sin(ang) * rose_r))
                pygame.draw.polygon(surf, col, pts)

            # Divider ribs between petals (dark stone) — broken gaps
            dx = math.cos(a1) * rose_r
            dy = math.sin(a1) * rose_r
            if i not in shattered_idx and (i - 1) % 12 not in shattered_idx:
                pygame.draw.line(surf, (32, 14, 16),
                                 (rose_cx, rose_cy),
                                 (rose_cx + dx, rose_cy + dy), 3)

        # Jagged cracks fissuring across the rose
        for _ in range(10):
            ang1 = rng.uniform(0, math.tau)
            r1 = rng.uniform(rose_r * 0.2, rose_r)
            x1 = rose_cx + math.cos(ang1) * r1
            y1 = rose_cy + math.sin(ang1) * r1
            ang2 = ang1 + rng.uniform(-0.4, 0.4)
            r2 = rng.uniform(rose_r * 0.2, rose_r)
            x2 = rose_cx + math.cos(ang2) * r2
            y2 = rose_cy + math.sin(ang2) * r2
            pygame.draw.line(surf, (255, 100, 80),
                             (x1, y1), (x2, y2), 2)
            pygame.draw.line(surf, (255, 200, 160),
                             (x1, y1), (x2, y2), 1)

        # Broken inner ring
        for seg in range(8):
            if seg in (1, 4, 6):  # skip broken segments
                continue
            a1 = seg * math.tau / 8
            a2 = (seg + 1) * math.tau / 8
            pts = [(rose_cx + math.cos(a1) * rose_r // 3,
                    rose_cy + math.sin(a1) * rose_r // 3)]
            steps = 4
            for s in range(steps + 1):
                ang = a1 + (a2 - a1) * s / steps
                pts.append((rose_cx + math.cos(ang) * rose_r // 3,
                            rose_cy + math.sin(ang) * rose_r // 3))
            pygame.draw.lines(surf, (130, 40, 40), False, pts, 2)

        # Broken cross in center (tilted, snapped)
        pygame.draw.rect(surf, (60, 30, 30),
                         (rose_cx - 2, rose_cy - 10, 4, 20))
        pygame.draw.line(surf, (60, 30, 30),
                         (rose_cx - 12, rose_cy - 2),
                         (rose_cx + 5, rose_cy + 1), 3)

        # ── 5) Lower tracery — mullion and two sub-arches with quatrefoils
        lower_top = rose_cy + rose_r + 30
        pygame.draw.line(surf, (50, 34, 42),
                         (cx, lower_top), (cx, arch_bot), 3)
        for side in (-1, 1):
            mx = cx + side * (arch_w // 4)
            sub_top = lower_top + 30
            sub_points = [
                (mx - arch_w // 8, arch_bot),
                (mx - arch_w // 8, sub_top + 20),
                (mx, sub_top),
                (mx + arch_w // 8, sub_top + 20),
                (mx + arch_w // 8, arch_bot),
            ]
            pygame.draw.polygon(surf, (60, 40, 48), sub_points, 2)
            # Quatrefoil
            q_cx = mx
            q_cy = sub_top + 40
            for (qx, qy) in ((-7, 0), (7, 0), (0, -7), (0, 7)):
                pygame.draw.circle(surf, (100, 30, 34),
                                   (q_cx + qx, q_cy + qy), 5)
            pygame.draw.circle(surf, (40, 18, 22),
                               (q_cx, q_cy), 3)

        # ── 6) Side pillars with banding, capitals, bases & fluting
        for px in (40, w - 70):
            pygame.draw.rect(surf, (28, 20, 32, 255), (px, 0, 30, h))
            pygame.draw.rect(surf, (60, 48, 60), (px, 0, 30, h), 2)
            for y in range(0, h, 28):
                pygame.draw.line(surf, (16, 12, 20, 200),
                                 (px, y), (px + 30, y), 1)
            # Capital (top)
            pygame.draw.rect(surf, (70, 58, 66), (px - 8, 58, 46, 18))
            pygame.draw.rect(surf, (30, 22, 28), (px - 8, 58, 46, 18), 2)
            pygame.draw.rect(surf, (90, 70, 78), (px - 10, 50, 50, 6))
            # Base
            pygame.draw.rect(surf, (70, 58, 66), (px - 8, h - 76, 46, 18))
            pygame.draw.rect(surf, (30, 22, 28), (px - 8, h - 76, 46, 18), 2)
            pygame.draw.rect(surf, (90, 70, 78), (px - 10, h - 56, 50, 6))
            # Fluting lines on shaft
            for fy in range(90, h - 90, 60):
                pygame.draw.line(surf, (90, 70, 90, 160),
                                 (px + 10, fy), (px + 10, fy + 40), 1)
                pygame.draw.line(surf, (90, 70, 90, 160),
                                 (px + 20, fy), (px + 20, fy + 40), 1)

        # ── 7) Gargoyle silhouettes perched on top of each pillar capital
        def draw_gargoyle(gcx, gcy):
            # Hunched body
            body = [(gcx - 12, gcy), (gcx - 14, gcy - 14),
                    (gcx - 6, gcy - 22), (gcx, gcy - 20),
                    (gcx + 6, gcy - 22), (gcx + 14, gcy - 14),
                    (gcx + 12, gcy)]
            pygame.draw.polygon(surf, (18, 12, 20), body)
            pygame.draw.polygon(surf, (60, 48, 56), body, 1)
            # Horns
            pygame.draw.polygon(surf, (18, 12, 20),
                                [(gcx - 6, gcy - 22), (gcx - 10, gcy - 32),
                                 (gcx - 3, gcy - 24)])
            pygame.draw.polygon(surf, (18, 12, 20),
                                [(gcx + 6, gcy - 22), (gcx + 10, gcy - 32),
                                 (gcx + 3, gcy - 24)])
            # Glowing red eyes
            pygame.draw.circle(surf, (255, 40, 40),
                               (gcx - 4, gcy - 18), 2)
            pygame.draw.circle(surf, (255, 40, 40),
                               (gcx + 4, gcy - 18), 2)
            # Wings (folded, pointed)
            pygame.draw.polygon(surf, (28, 18, 28),
                                [(gcx - 14, gcy - 14),
                                 (gcx - 22, gcy - 6),
                                 (gcx - 14, gcy - 2)])
            pygame.draw.polygon(surf, (28, 18, 28),
                                [(gcx + 14, gcy - 14),
                                 (gcx + 22, gcy - 6),
                                 (gcx + 14, gcy - 2)])

        draw_gargoyle(55, 48)
        draw_gargoyle(w - 55, 48)

        # ── 8) Chains hanging from the ceiling on both sides of the arch
        for side in (-1, 1):
            cxh = cx + side * (arch_w // 2 + 70)
            for link_y in range(75, arch_bot - 140, 14):
                pygame.draw.ellipse(surf, (120, 100, 110),
                                    (cxh - 4, link_y, 8, 12), 2)
            # Broken hook at the bottom
            hook_y = arch_bot - 150
            pygame.draw.arc(surf, (120, 100, 110),
                            (cxh - 8, hook_y, 16, 18),
                            math.pi, 2 * math.pi, 2)

        # ── 9) Skull above the arch apex (replaces innocent cross)
        skull_cx = cx
        skull_cy = arch_apex - 26
        # Cranium
        pygame.draw.circle(surf, (200, 190, 180),
                           (skull_cx, skull_cy - 4), 18)
        pygame.draw.circle(surf, (80, 70, 60),
                           (skull_cx, skull_cy - 4), 18, 2)
        # Jaw
        pygame.draw.rect(surf, (200, 190, 180),
                         (skull_cx - 12, skull_cy + 8, 24, 10))
        pygame.draw.rect(surf, (80, 70, 60),
                         (skull_cx - 12, skull_cy + 8, 24, 10), 2)
        # Eye sockets (glowing red)
        pygame.draw.circle(surf, (20, 10, 10),
                           (skull_cx - 6, skull_cy - 4), 4)
        pygame.draw.circle(surf, (20, 10, 10),
                           (skull_cx + 6, skull_cy - 4), 4)
        pygame.draw.circle(surf, (255, 60, 60),
                           (skull_cx - 6, skull_cy - 4), 2)
        pygame.draw.circle(surf, (255, 60, 60),
                           (skull_cx + 6, skull_cy - 4), 2)
        # Nose triangle
        pygame.draw.polygon(surf, (20, 10, 10),
                            [(skull_cx, skull_cy),
                             (skull_cx - 2, skull_cy + 6),
                             (skull_cx + 2, skull_cy + 6)])
        # Teeth
        for tx in range(-8, 9, 4):
            pygame.draw.line(surf, (60, 50, 45),
                             (skull_cx + tx, skull_cy + 10),
                             (skull_cx + tx, skull_cy + 17), 1)

        # Blood streaks dripping from skull eye sockets
        for ox in (-6, 6):
            drip_start = skull_cy - 2
            drip_end = drip_start + rng.randint(40, 70)
            pygame.draw.line(surf, (150, 20, 20),
                             (skull_cx + ox, drip_start),
                             (skull_cx + ox, drip_end), 2)
            pygame.draw.circle(surf, (150, 20, 20),
                               (skull_cx + ox, drip_end), 2)

        # ── 10) Stepped tomb / altar silhouette at bottom center
        dais_w = arch_w + 120
        dais_top = arch_bot - 10
        for step in range(3):
            sw = dais_w - step * 60
            sx = cx - sw // 2
            sy = dais_top + step * 14
            pygame.draw.rect(surf, (22, 14, 22), (sx, sy, sw, 14))
            pygame.draw.rect(surf, (60, 45, 55), (sx, sy, sw, 14), 1)

        # Tombstones flanking the dais
        for side in (-1, 1):
            tx = cx + side * (dais_w // 2 - 30)
            ty = dais_top - 40
            # Rounded-top slab
            pygame.draw.rect(surf, (54, 48, 58), (tx - 18, ty, 36, 40))
            pygame.draw.circle(surf, (54, 48, 58), (tx, ty), 18)
            pygame.draw.rect(surf, (28, 22, 30), (tx - 18, ty, 36, 40), 2)
            pygame.draw.circle(surf, (28, 22, 30), (tx, ty), 18, 2)
            # Cross etching
            pygame.draw.rect(surf, (28, 22, 30), (tx - 1, ty + 6, 2, 18))
            pygame.draw.rect(surf, (28, 22, 30), (tx - 7, ty + 10, 14, 2))
            # Moss/stain patches
            pygame.draw.circle(surf, (40, 54, 32),
                               (tx - 8, ty + 28), 4)
            pygame.draw.circle(surf, (40, 54, 32),
                               (tx + 6, ty + 20), 3)

        # ── 11) Heavy radial vignette
        vcx, vcy = w // 2, int(h * 0.48)
        max_vr = int(math.hypot(vcx, vcy))
        vig = pygame.Surface((w, h), pygame.SRCALPHA)
        for r in range(max_vr, 0, -8):
            t = 1 - r / max_vr
            a = int(170 * t * t)
            pygame.draw.circle(vig, (0, 0, 0, a), (vcx, vcy), r)
        surf.blit(vig, (0, 0))

        # ── 12) Corner cracks + midfield cracks
        def draw_crack(ox, oy, length, angle, depth=0):
            if depth > 2 or length < 6:
                return
            ex = ox + math.cos(angle) * length
            ey = oy + math.sin(angle) * length
            pygame.draw.line(surf, (80, 62, 72),
                             (ox, oy), (ex, ey), 1)
            if rng.random() < 0.55:
                draw_crack(ex, ey, length * 0.55,
                           angle + rng.uniform(-0.8, 0.8), depth + 1)
            if rng.random() < 0.4:
                draw_crack(ex, ey, length * 0.45,
                           angle + rng.uniform(-1.5, 1.5), depth + 1)

        for (cx2, cy2, base_ang) in (
            (20, 20,      math.pi * 0.25),
            (w - 20, 20,  math.pi * 0.75),
            (20, h - 20, -math.pi * 0.25),
            (w - 20, h - 20, -math.pi * 0.75),
        ):
            for _ in range(4):
                draw_crack(cx2, cy2, rng.randint(70, 160),
                           base_ang + rng.uniform(-0.5, 0.5))

        for _ in range(8):
            scx = rng.randint(80, w - 80)
            scy = rng.randint(100, h - 100)
            draw_crack(scx, scy, rng.randint(30, 70),
                       rng.uniform(0, math.tau))

        # ── 13) Top & bottom blood-stained banners
        banner = pygame.Surface((w, 70), pygame.SRCALPHA)
        banner.fill((10, 2, 4, 230))
        surf.blit(banner, (0, 0))
        surf.blit(banner, (0, h - 70))
        # Blood trim
        pygame.draw.line(surf, (170, 30, 30), (0, 70), (w, 70), 3)
        pygame.draw.line(surf, (50, 10, 10), (0, 74), (w, 74), 1)
        pygame.draw.line(surf, (170, 30, 30), (0, h - 70), (w, h - 70), 3)
        pygame.draw.line(surf, (50, 10, 10), (0, h - 66), (w, h - 66), 1)

        # Ornamental thorns along the banners
        for dx in range(20, w, 40):
            pygame.draw.polygon(surf, (100, 20, 20),
                                [(dx, 74), (dx + 4, 82), (dx - 4, 82)])
            pygame.draw.polygon(surf, (100, 20, 20),
                                [(dx, h - 74), (dx + 4, h - 82),
                                 (dx - 4, h - 82)])

        # Blood drips from top banner (longer, more numerous)
        for _ in range(18):
            dx = rng.randint(20, w - 20)
            drip_len = rng.randint(10, 48)
            pygame.draw.line(surf, (130, 20, 20),
                             (dx, 70), (dx, 70 + drip_len), 2)
            pygame.draw.circle(surf, (130, 20, 20),
                               (dx, 70 + drip_len), 2)

        # Blood streaks running down the walls (long vertical smears)
        for _ in range(8):
            sxb = rng.randint(80, w - 80)
            # Avoid dead-center where the arch is
            if abs(sxb - cx) < arch_w // 2 + 10:
                continue
            start_y = rng.randint(75, 150)
            streak_len = rng.randint(80, 220)
            for yy in range(streak_len):
                fade = 1 - yy / streak_len
                alpha = int(180 * fade)
                a_col = (130, 20, 20, alpha)
                smear = pygame.Surface((4, 2), pygame.SRCALPHA)
                smear.fill(a_col)
                surf.blit(smear, (sxb, start_y + yy))

        # ── 14) Candles flanking the arch (static glow bases)
        for (cxp, cyp) in ((arch_left - 25, arch_bot - 60),
                           (arch_right + 25, arch_bot - 60)):
            # Candle stick (melted / crooked)
            pygame.draw.polygon(surf, (80, 70, 60),
                                [(cxp - 3, cyp),
                                 (cxp + 3, cyp),
                                 (cxp + 4, cyp + 30),
                                 (cxp - 4, cyp + 30)])
            # Wax drips
            pygame.draw.circle(surf, (100, 90, 80), (cxp - 4, cyp + 20), 2)
            pygame.draw.circle(surf, (100, 90, 80), (cxp + 5, cyp + 12), 2)
            # Warm glow halo
            halo = pygame.Surface((60, 60), pygame.SRCALPHA)
            for r in range(28, 0, -3):
                a = int(6 + (28 - r) * 3)
                pygame.draw.circle(halo, (255, 170, 70, a), (30, 30), r)
            surf.blit(halo, (cxp - 30, cyp - 30),
                      special_flags=pygame.BLEND_RGBA_ADD)

        # ── 15) Small skull-and-diamond corner finials
        for (fx, fy) in ((30, 30), (w - 30, 30),
                         (30, h - 30), (w - 30, h - 30)):
            pts = [(fx, fy - 11), (fx + 9, fy), (fx, fy + 11), (fx - 9, fy)]
            pygame.draw.polygon(surf, (150, 30, 30), pts)
            pygame.draw.polygon(surf, (55, 10, 10), pts, 1)
            # Tiny skull inside the diamond
            pygame.draw.circle(surf, (220, 210, 200), (fx, fy - 2), 4)
            pygame.draw.circle(surf, (20, 10, 10), (fx - 1, fy - 3), 1)
            pygame.draw.circle(surf, (20, 10, 10), (fx + 2, fy - 3), 1)
            pygame.draw.rect(surf, (220, 210, 200),
                             (fx - 3, fy + 1, 6, 3))

        return surf

    def _seed_particles(self, won):
        """Populate the particle field for victory or defeat."""
        self._go_particles.clear()
        if won:
            # Sparkles drifting upward with gold glow
            for _ in range(55):
                self._go_particles.append({
                    "x": random.uniform(0, self.screen_w),
                    "y": random.uniform(0, self.screen_h),
                    "vx": random.uniform(-8, 8),
                    "vy": random.uniform(-30, -10),
                    "r": random.uniform(1.2, 3.2),
                    "phase": random.uniform(0, math.tau),
                    "col": random.choice(((255, 230, 120),
                                          (255, 200, 80),
                                          (255, 245, 200))),
                })
        else:
            # Gothic defeat atmosphere:
            #  - Slow drifting red mist (big, dim)
            #  - Falling embers (small, orange-red)
            #  - Candle-flicker sparks (tiny, warm)
            for _ in range(28):  # red mist
                self._go_particles.append({
                    "x": random.uniform(0, self.screen_w),
                    "y": random.uniform(0, self.screen_h),
                    "vx": random.uniform(-6, 6),
                    "vy": random.uniform(-8, 8),
                    "r": random.uniform(4.0, 7.5),
                    "phase": random.uniform(0, math.tau),
                    "col": random.choice(((70, 12, 18),
                                          (90, 20, 24),
                                          (55, 8, 12))),
                    "kind": "mist",
                })
            for _ in range(38):  # falling embers
                self._go_particles.append({
                    "x": random.uniform(0, self.screen_w),
                    "y": random.uniform(-50, self.screen_h),
                    "vx": random.uniform(-8, 8),
                    "vy": random.uniform(18, 40),
                    "r": random.uniform(0.9, 2.2),
                    "phase": random.uniform(0, math.tau),
                    "col": random.choice(((210, 70, 40),
                                          (150, 40, 30),
                                          (235, 100, 50))),
                    "kind": "ember",
                })
            for _ in range(14):  # candle-flicker sparks
                self._go_particles.append({
                    "x": random.uniform(0, self.screen_w),
                    "y": random.uniform(0, self.screen_h),
                    "vx": random.uniform(-3, 3),
                    "vy": random.uniform(-18, -4),
                    "r": random.uniform(0.8, 1.8),
                    "phase": random.uniform(0, math.tau),
                    "col": random.choice(((255, 190, 90),
                                          (255, 150, 70),
                                          (255, 220, 150))),
                    "kind": "spark",
                })

    def _tick_particles(self, dt, won):
        """Advance the particle simulation and wrap around edges."""
        for p in self._go_particles:
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["phase"] += dt * 2.5
            kind = p.get("kind", "default")
            # Sparks drift up and burn out faster, so respawn at bottom
            if kind == "spark" and p["y"] < -10:
                p["y"] = self.screen_h + 10
                p["x"] = random.uniform(0, self.screen_w)
            elif won and p["y"] < -10:
                p["y"] = self.screen_h + 10
                p["x"] = random.uniform(0, self.screen_w)
            elif (not won) and kind in ("ember", "default") and p["y"] > self.screen_h + 10:
                p["y"] = -10
                p["x"] = random.uniform(0, self.screen_w)
            # Mist wraps everywhere
            if kind == "mist":
                if p["x"] < -20:
                    p["x"] = self.screen_w + 20
                elif p["x"] > self.screen_w + 20:
                    p["x"] = -20
                if p["y"] < -20:
                    p["y"] = self.screen_h + 20
                elif p["y"] > self.screen_h + 20:
                    p["y"] = -20
            else:
                # Horizontal wrap
                if p["x"] < -10:
                    p["x"] = self.screen_w + 10
                elif p["x"] > self.screen_w + 10:
                    p["x"] = -10

    def _draw_particles(self, surface):
        """Render all particles as glowing dots.  Mist particles render as
        wide, soft additive blobs; sparks get an intense warm halo."""
        for p in self._go_particles:
            twinkle = 0.5 + 0.5 * math.sin(p["phase"])
            kind = p.get("kind", "default")

            if kind == "mist":
                # Big soft additive blob, very dim
                r = max(2, int(p["r"] * (0.9 + 0.3 * twinkle)))
                glow_r = r * 5
                glow = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
                pygame.draw.circle(glow, (*p["col"], int(55 + 20 * twinkle)),
                                   (glow_r, glow_r), glow_r)
                surface.blit(glow, (int(p["x"]) - glow_r, int(p["y"]) - glow_r),
                             special_flags=pygame.BLEND_RGBA_ADD)
                continue

            r = max(1, int(p["r"] * (0.7 + 0.6 * twinkle)))
            # Outer glow
            glow_r = r * 3
            glow = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
            glow_alpha = int(80 * twinkle)
            if kind == "spark":
                glow_alpha = int(140 * twinkle)
            pygame.draw.circle(glow, (*p["col"], glow_alpha),
                               (glow_r, glow_r), glow_r)
            surface.blit(glow, (int(p["x"]) - glow_r, int(p["y"]) - glow_r),
                         special_flags=pygame.BLEND_RGBA_ADD
                         if kind == "spark" else 0)
            # Core
            pygame.draw.circle(surface, p["col"],
                               (int(p["x"]), int(p["y"])), r)

    def draw_game_over(self, surface, won, player, game_time):
        # Detect entering (or switching between) victory / defeat. Rebuild
        # the backdrop + particle field exactly once per cycle so we don't
        # regenerate on every frame.
        state_key = "victory" if won else "defeat"
        if self._go_last_state != state_key:
            self._go_last_state = state_key
            self._go_time = 0.0
            if won:
                self._go_bg_victory = self._build_victory_background()
            else:
                self._go_bg_defeat = self._build_defeat_background()
            self._seed_particles(won)

        # Advance internal timer (approximate dt from typical 60fps target).
        # Using a fixed small dt keeps the animation stable even if the
        # caller doesn't pass real dt — we don't need frame-accurate timing
        # for background particles.
        dt = 1.0 / 60.0
        self._go_time += dt
        self._tick_particles(dt, won)

        # 1) Backdrop
        bg = self._go_bg_victory if won else self._go_bg_defeat
        if bg is not None:
            surface.blit(bg, (0, 0))
        else:
            fallback = pygame.Surface(
                (self.screen_w, self.screen_h), pygame.SRCALPHA)
            fallback.fill((0, 0, 0, 220))
            surface.blit(fallback, (0, 0))

        # 2) Particles (behind the text)
        self._draw_particles(surface)

        # 3) Title — large, animated pulse, with layered drop-shadow
        pulse = 1.0 + 0.03 * math.sin(self._go_time * 2.4)
        if won:
            title_str = "VICTORY!"
            title_color = (255, 220, 80)
            shadow_color = (80, 50, 0)
            under_color = (255, 180, 40)
        else:
            title_str = "DEFEATED"
            title_color = (240, 70, 70)
            shadow_color = (40, 5, 5)
            under_color = (180, 20, 20)

        title_surf = self.font_huge.render(title_str, True, title_color)
        if abs(pulse - 1.0) > 0.001:
            new_size = (max(1, int(title_surf.get_width() * pulse)),
                        max(1, int(title_surf.get_height() * pulse)))
            title_surf = pygame.transform.smoothscale(title_surf, new_size)

        # Shadow stack for depth
        shadow = self.font_huge.render(title_str, True, shadow_color)
        if abs(pulse - 1.0) > 0.001:
            shadow = pygame.transform.smoothscale(shadow, new_size)
        title_y = 130
        cx = self.screen_w // 2
        for dx, dy in ((4, 4), (-3, 3), (3, -2)):
            rect = shadow.get_rect(center=(cx + dx, title_y + dy))
            surface.blit(shadow, rect)

        # Underline glow bar
        under_w = title_surf.get_width() + 60
        under_surf = pygame.Surface((under_w, 10), pygame.SRCALPHA)
        for i in range(5, 0, -1):
            alpha = int(40 + 30 * (5 - i))
            pygame.draw.rect(under_surf, (*under_color, alpha),
                             (i, i // 2 + 2, under_w - i * 2, 10 - i), border_radius=4)
        surface.blit(under_surf,
                     under_surf.get_rect(center=(cx, title_y + 50)))

        title_rect = title_surf.get_rect(center=(cx, title_y))
        surface.blit(title_surf, title_rect)

        # 4) Stats panel — a translucent parchment/slate block
        panel_w = 440
        panel_h = 170
        panel_x = (self.screen_w - panel_w) // 2
        panel_y = 215
        panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        if won:
            panel_surf.fill((36, 26, 10, 215))
            border_col = (230, 190, 90)
        else:
            panel_surf.fill((20, 6, 8, 220))
            border_col = (180, 40, 40)
        surface.blit(panel_surf, (panel_x, panel_y))
        pygame.draw.rect(surface, border_col,
                         (panel_x, panel_y, panel_w, panel_h), 2,
                         border_radius=6)
        # Inner highlight
        inner_col = (border_col[0] // 3, border_col[1] // 3, border_col[2] // 3)
        pygame.draw.rect(surface, inner_col,
                         (panel_x + 4, panel_y + 4,
                          panel_w - 8, panel_h - 8), 1, border_radius=4)

        # Stats title
        header = self.font_md.render(
            "— Run Summary —", True,
            (255, 230, 150) if won else (255, 150, 150))
        surface.blit(header, header.get_rect(center=(cx, panel_y + 22)))

        info_lines = [
            ("Level Reached", str(player.level)),
            ("Class",          player.class_type),
            ("Time",           f"{int(game_time // 60):02d}:{int(game_time % 60):02d}"),
        ]
        row_y = panel_y + 55
        for label, value in info_lines:
            label_surf = self.font_md.render(label + ":", True,
                                             (220, 220, 200) if won
                                             else (220, 180, 180))
            value_surf = self.font_md.render(value, True, self.WHITE)
            # Left-align label, right-align value within the panel
            surface.blit(label_surf, (panel_x + 40, row_y))
            surface.blit(value_surf,
                         (panel_x + panel_w - 40 - value_surf.get_width(), row_y))
            row_y += 34

        # 5) Prompt — blinking for subtle life
        blink = 0.6 + 0.4 * math.sin(self._go_time * 3.0)
        prompt_str = "Press [R] to Restart     |     [Q] to Quit"
        prompt_col = (int(200 * blink + 55), int(200 * blink + 55),
                      int(200 * blink + 55))
        prompt = self.font_md.render(prompt_str, True, prompt_col)
        surface.blit(prompt, prompt.get_rect(center=(cx, self.screen_h - 50)))

    def draw_start_screen(self, surface, player_name="", input_active=True, cursor_visible=True):
        # Background image
        if self.menu_background:
            surface.blit(self.menu_background, (0, 0))
            # Darken overlay for readability
            overlay = pygame.Surface((self.screen_w, self.screen_h), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 120))
            surface.blit(overlay, (0, 0))
        else:
            surface.fill((10, 10, 15))

        # Title with drop shadow for readability
        title_shadow = self.font_title.render("DEADLINE DUNGEON", True, (0, 0, 0))
        tr = title_shadow.get_rect(center=(self.screen_w // 2 + 3, 93))
        surface.blit(title_shadow, tr)
        title = self.font_title.render("DEADLINE DUNGEON", True, (230, 70, 70))
        tr = title.get_rect(center=(self.screen_w // 2, 90))
        surface.blit(title, tr)

        sub = self.font_md.render("Top-Down 2D Action RPG", True, (220, 220, 220))
        sr = sub.get_rect(center=(self.screen_w // 2, 135))
        surface.blit(sub, sr)

        # Name input label
        label = self.font_md.render("Enter your name:", True, (255, 220, 120))
        lr = label.get_rect(center=(self.screen_w // 2, 185))
        surface.blit(label, lr)

        # Name input box
        box_w, box_h = 360, 44
        box_x = (self.screen_w - box_w) // 2
        box_y = 205
        # Semi-transparent box
        box_surf = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        box_surf.fill((15, 15, 25, 220))
        surface.blit(box_surf, (box_x, box_y))
        border_color = (255, 220, 120) if input_active else (120, 120, 120)
        pygame.draw.rect(surface, border_color, (box_x, box_y, box_w, box_h), 2,
                         border_radius=4)

        # Display name text + blinking cursor
        display = player_name
        if input_active and cursor_visible:
            display = player_name + "_"
        if not display:
            display_text = self.font_md.render("(type name, then ENTER)", True, (120, 120, 120))
        else:
            display_text = self.font_md.render(display, True, self.WHITE)
        dr = display_text.get_rect(midleft=(box_x + 12, box_y + box_h // 2))
        surface.blit(display_text, dr)

        # Controls panel (translucent) — expanded to list ALL the buttons
        panel_w = 520
        panel_y = 275
        panel_h = 276
        panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel_surf.fill((10, 10, 20, 190))
        panel_x = (self.screen_w - panel_w) // 2
        surface.blit(panel_surf, (panel_x, panel_y))
        pygame.draw.rect(surface, (180, 140, 70),
                         (panel_x, panel_y, panel_w, panel_h), 2, border_radius=4)
        pygame.draw.rect(surface, (80, 60, 30),
                         (panel_x + 3, panel_y + 3,
                          panel_w - 6, panel_h - 6), 1, border_radius=4)

        # Section header
        hdr = self.font_md.render("— Controls —", True, (255, 220, 120))
        hr = hdr.get_rect(center=(panel_x + panel_w // 2, panel_y + 16))
        surface.blit(hdr, hr)

        # Two-column control list: (key, description, color)
        controls = [
            ("WASD",           "Move around",               (255, 230, 140)),
            ("Mouse",          "Aim attack direction",      (255, 230, 140)),
            ("Left Click / Q", "Basic attack",              (255, 230, 140)),
            ("Right Click / E","Use class skill",           (255, 230, 140)),
            ("ESC",            "Pause / Resume",            (200, 220, 255)),
            ("R",              "Restart after game over",   (200, 220, 255)),
            ("Q (game over)",  "Quit to desktop",           (200, 220, 255)),
            ("1 / 2 / 3",      "Pick class (when prompted)",(180, 255, 180)),
            ("ENTER",          "Confirm name / menu",       (180, 255, 180)),
        ]
        row_top = panel_y + 38
        row_h = 22
        key_col_x = panel_x + 24
        desc_col_x = panel_x + 200
        for i, (key, desc, color) in enumerate(controls):
            # Key label (left column, highlighted)
            key_surf = self.font_sm.render(key, True, color)
            surface.blit(key_surf, (key_col_x, row_top + i * row_h))
            # Separator dash
            dash = self.font_sm.render("—", True, (120, 110, 90))
            surface.blit(dash, (desc_col_x - 20, row_top + i * row_h))
            # Description (right column)
            desc_surf = self.font_sm.render(desc, True, (230, 225, 210))
            surface.blit(desc_surf, (desc_col_x, row_top + i * row_h))

        # Objective footer inside the panel
        obj_y = row_top + len(controls) * row_h + 4
        pygame.draw.line(surface, (120, 90, 40),
                         (panel_x + 20, obj_y),
                         (panel_x + panel_w - 20, obj_y), 1)
        obj = self.font_sm.render(
            "Goal: Reach Lv.30 and defeat the final boss within 10 minutes!",
            True, (255, 200, 120))
        or_ = obj.get_rect(center=(panel_x + panel_w // 2, obj_y + 14))
        surface.blit(obj, or_)

        # Start prompt (only enabled if name entered)
        prompt_y = panel_y + panel_h + 28
        if player_name.strip():
            prompt = self.font_lg.render("Press [ENTER] to Start", True, (255, 220, 80))
        else:
            prompt = self.font_md.render("(enter your name to begin)", True, (180, 180, 180))
        pr = prompt.get_rect(center=(self.screen_w // 2, prompt_y))
        surface.blit(prompt, pr)

    def draw_menu(self):
        pass

    # ──────────────────── Pause menu ────────────────────

    # Entries for the pause menu — (label, action key)
    PAUSE_ENTRIES = (
        ("Resume",       "resume"),
        ("Restart Game", "restart"),
        ("Quit",         "quit"),
    )

    def get_pause_button_rects(self):
        """Return list of (rect, action) tuples for the pause menu buttons,
        so main.py can hit-test mouse clicks against them."""
        button_w = 280
        button_h = 52
        gap = 16
        total_h = len(self.PAUSE_ENTRIES) * button_h + (len(self.PAUSE_ENTRIES) - 1) * gap
        start_x = (self.screen_w - button_w) // 2
        start_y = (self.screen_h - total_h) // 2 + 20
        rects = []
        for i, (_, action) in enumerate(self.PAUSE_ENTRIES):
            y = start_y + i * (button_h + gap)
            rects.append((pygame.Rect(start_x, y, button_w, button_h), action))
        return rects

    def draw_pause_menu(self, surface, selected_index=0, hover_action=None):
        """Draw the pause overlay and menu buttons.  selected_index is the
        keyboard cursor, hover_action (or None) is the button under the
        mouse.  Either highlight gives the button a gold border."""
        # Dim the game behind the menu
        overlay = pygame.Surface((self.screen_w, self.screen_h), pygame.SRCALPHA)
        overlay.fill((4, 4, 8, 200))
        surface.blit(overlay, (0, 0))

        # Decorative gold border frame
        frame_pad = 30
        pygame.draw.rect(surface, (160, 130, 60),
                         (frame_pad, frame_pad,
                          self.screen_w - frame_pad * 2,
                          self.screen_h - frame_pad * 2), 2, border_radius=6)
        pygame.draw.rect(surface, (80, 60, 20),
                         (frame_pad + 4, frame_pad + 4,
                          self.screen_w - frame_pad * 2 - 8,
                          self.screen_h - frame_pad * 2 - 8), 1, border_radius=6)

        # Title
        title_shadow = self.font_title.render("PAUSED", True, (0, 0, 0))
        surface.blit(title_shadow,
                     title_shadow.get_rect(center=(self.screen_w // 2 + 3,
                                                   110 + 3)))
        title = self.font_title.render("PAUSED", True, (255, 220, 120))
        surface.blit(title,
                     title.get_rect(center=(self.screen_w // 2, 110)))

        subtitle = self.font_sm.render(
            "The dungeon waits for no one...", True, (200, 180, 140))
        surface.blit(subtitle,
                     subtitle.get_rect(center=(self.screen_w // 2, 146)))

        # Buttons — exactly ONE button is highlighted at a time. If the
        # mouse is hovering a button, it takes priority over the keyboard
        # selection so we never get two arrows/highlights showing at once.
        rects = self.get_pause_button_rects()
        if hover_action is not None:
            active_index = next((i for i, (_, a) in enumerate(rects)
                                 if a == hover_action), selected_index)
        else:
            active_index = selected_index

        for i, (rect, action) in enumerate(rects):
            is_sel = (i == active_index)

            # Button face
            face_col = (42, 32, 20) if is_sel else (26, 22, 30)
            pygame.draw.rect(surface, face_col, rect, border_radius=6)
            # Border
            border_col = (255, 210, 90) if is_sel else (90, 70, 40)
            pygame.draw.rect(surface, border_col, rect, 2, border_radius=6)
            # Inner highlight line
            inner_col = (120, 90, 40) if is_sel else (50, 40, 30)
            pygame.draw.rect(surface, inner_col,
                             rect.inflate(-8, -8), 1, border_radius=5)

            label_str = self.PAUSE_ENTRIES[i][0]
            text_col = (255, 240, 180) if is_sel else (220, 210, 180)
            label = self.font_lg.render(label_str, True, text_col)
            surface.blit(label, label.get_rect(center=rect.center))

            # Selection arrow (only on the active button)
            if is_sel:
                arrow_y = rect.centery
                ax = rect.left - 16
                pts = [(ax, arrow_y - 8), (ax + 10, arrow_y), (ax, arrow_y + 8)]
                pygame.draw.polygon(surface, (255, 220, 120), pts)

        # Hint
        hint = self.font_sm.render(
            "[ESC] Resume     [↑/↓] Select     [ENTER] Confirm",
            True, (170, 160, 140))
        surface.blit(hint, hint.get_rect(
            center=(self.screen_w // 2, self.screen_h - 60)))

    def draw_stats_screen(self, surface, stats_dict):
        overlay = pygame.Surface((self.screen_w, self.screen_h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))

        title = self.font_lg.render("Session Statistics", True, self.WHITE)
        surface.blit(title, (40, 30))

        y = 80
        for name, count in stats_dict.items():
            text = self.font_md.render(f"{name}: {count} records", True, self.GRAY)
            surface.blit(text, (50, y))
            y += 28

    def update_display(self):
        pass