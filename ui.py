"""
ui.py - UI class for Deadline Dungeon
Handles HUD, menus, class selection, and game over screens.
"""
import pygame


class UI:
    def __init__(self, screen_w, screen_h):
        self.screen_w = screen_w
        self.screen_h = screen_h

        pygame.font.init()
        self.font_lg = pygame.font.SysFont("consolas", 28, bold=True)
        self.font_md = pygame.font.SysFont("consolas", 20)
        self.font_sm = pygame.font.SysFont("consolas", 15)
        self.font_title = pygame.font.SysFont("consolas", 48, bold=True)

        self.WHITE = (255, 255, 255)
        self.GRAY = (160, 160, 160)

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
        y = 50

        name_text = self.font_md.render(boss.boss_name, True, (255, 200, 50))
        nr = name_text.get_rect(center=(self.screen_w // 2, y - 12))
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

    def draw_game_over(self, surface, won, player, game_time):
        overlay = pygame.Surface((self.screen_w, self.screen_h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        surface.blit(overlay, (0, 0))

        if won:
            title = self.font_title.render("VICTORY!", True, (255, 220, 50))
        else:
            title = self.font_title.render("DEFEATED", True, (220, 50, 50))
        tr = title.get_rect(center=(self.screen_w // 2, 120))
        surface.blit(title, tr)

        info_lines = [
            f"Level Reached: {player.level}",
            f"Class: {player.class_type}",
            f"Time: {int(game_time // 60):02d}:{int(game_time % 60):02d}",
        ]
        for i, line in enumerate(info_lines):
            text = self.font_md.render(line, True, self.WHITE)
            tr = text.get_rect(center=(self.screen_w // 2, 200 + i * 35))
            surface.blit(text, tr)

        prompt = self.font_md.render("Press [R] to Restart  |  [Q] to Quit",
                                      True, self.GRAY)
        pr = prompt.get_rect(center=(self.screen_w // 2, 360))
        surface.blit(prompt, pr)

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

        # Controls panel (translucent)
        panel_y = 275
        panel_h = 180
        panel_surf = pygame.Surface((440, panel_h), pygame.SRCALPHA)
        panel_surf.fill((10, 10, 20, 180))
        panel_x = (self.screen_w - 440) // 2
        surface.blit(panel_surf, (panel_x, panel_y))
        pygame.draw.rect(surface, (80, 80, 100),
                         (panel_x, panel_y, 440, panel_h), 1, border_radius=4)

        controls = [
            "WASD               -  Move",
            "Mouse              -  Aim direction",
            "Left Click / Q     -  Attack",
            "Right Click / E    -  Skill",
            "",
            "Reach Lv.30 and defeat the Elite Orc",
            "before the 10-minute deadline!",
        ]
        for i, line in enumerate(controls):
            color = self.WHITE if line else self.GRAY
            text = self.font_sm.render(line, True, color)
            tr = text.get_rect(midleft=(panel_x + 20, panel_y + 20 + i * 22))
            surface.blit(text, tr)

        # Start prompt (only enabled if name entered)
        if player_name.strip():
            prompt = self.font_lg.render("Press [ENTER] to Start", True, (255, 220, 80))
        else:
            prompt = self.font_md.render("(enter your name to begin)", True, (180, 180, 180))
        pr = prompt.get_rect(center=(self.screen_w // 2, 490))
        surface.blit(prompt, pr)

    def draw_menu(self):
        pass

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