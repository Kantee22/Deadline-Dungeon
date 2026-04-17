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
        # Dimmer + shorter flash
        alpha = int(70 * min(1.0, timer))
        flash = pygame.Surface((self.screen_w, self.screen_h), pygame.SRCALPHA)
        flash.fill((255, 240, 180, alpha))
        surface.blit(flash, (0, 0))

        # Only show text for last 0.6s of the flash so it pops without blinding
        if timer < 0.7:
            text = self.font_lg.render("LEVEL UP!", True, (255, 220, 50))
            tr = text.get_rect(center=(self.screen_w // 2, self.screen_h // 2 - 50))
            surface.blit(text, tr)

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

    def draw_start_screen(self, surface):
        surface.fill((10, 10, 15))

        title = self.font_title.render("DEADLINE DUNGEON", True, (220, 50, 50))
        tr = title.get_rect(center=(self.screen_w // 2, 150))
        surface.blit(title, tr)

        sub = self.font_md.render("Top-Down 2D Action RPG", True, self.GRAY)
        sr = sub.get_rect(center=(self.screen_w // 2, 200))
        surface.blit(sub, sr)

        controls = [
            "WASD  -  Move",
            "Mouse  -  Aim direction",
            "Left Click  -  Attack",
            "Right Click  -  Skill",
            "",
            "Reach Lv.30 and defeat the Elite Orc",
            "before the 10-minute deadline!",
            "",
            "No items  -  Heal only on Level Up!",
        ]
        for i, line in enumerate(controls):
            color = self.WHITE if line else self.GRAY
            text = self.font_sm.render(line, True, color)
            tr = text.get_rect(center=(self.screen_w // 2, 270 + i * 24))
            surface.blit(text, tr)

        prompt = self.font_lg.render("Press [SPACE] to Start", True, (255, 220, 80))
        pr = prompt.get_rect(center=(self.screen_w // 2, 510))
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