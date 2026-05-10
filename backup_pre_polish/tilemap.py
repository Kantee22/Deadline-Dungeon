"""tilemap.py - Procedural dungeon map with rooms and corridors."""
import pygame
import random
import math
import os


class TileMap:
    """Procedural dungeon generated from a 10x10 tileset."""

    TILE_SIZE = 16
    SCALE = 3
    DISPLAY_TILE = 48

    # Named tile positions (col, row) in Dungeon_Tileset.png
    TILES = {
        "wall_top_a":    (1, 0),
        "wall_top_b":    (2, 0),
        "wall_top_c":    (3, 0),
        "wall_top_d":    (4, 0),
        "wall_face_a":   (1, 4),
        "wall_face_b":   (2, 4),
        "wall_face_c":   (3, 4),
        "wall_face_d":   (4, 4),
        "corner_tl":     (0, 0),
        "corner_tr":     (5, 0),
        "corner_bl":     (0, 4),
        "corner_br":     (5, 4),
        "wall_left":     (0, 1),
        "wall_right":    (5, 1),
        "floor_a":       (1, 1),
        "floor_b":       (2, 1),
        "floor_c":       (3, 1),
        "floor_d":       (4, 1),
        "floor_e":       (1, 2),
        "floor_f":       (2, 2),
        "floor_g":       (3, 2),
        "floor_h":       (4, 2),
        "floor_i":       (1, 3),
        "floor_j":       (2, 3),
        "floor_k":       (3, 3),
        "floor_l":       (4, 3),
    }

    FLOOR_TILES = [
        "floor_a", "floor_b", "floor_c", "floor_d",
        "floor_e", "floor_f", "floor_g", "floor_h",
        "floor_i", "floor_j", "floor_k", "floor_l",
    ]
    WALL_TOP_TILES = ["wall_top_a", "wall_top_b", "wall_top_c", "wall_top_d"]
    WALL_FACE_TILES = ["wall_face_a", "wall_face_b", "wall_face_c", "wall_face_d"]

    def __init__(self, map_w=42, map_h=42, tileset_path="Dungeon_Tileset.png"):
        self.map_w = map_w
        self.map_h = map_h
        self.world_w = map_w * self.DISPLAY_TILE
        self.world_h = map_h * self.DISPLAY_TILE

        # 0 = wall, 1 = floor.
        self.grid = [[0] * map_w for _ in range(map_h)]
        self.rooms = []

        self.tileset = None
        self.tile_cache = {}
        self._load_tileset(tileset_path)

        self._generate_dungeon()

        # Pre-rendered full map (blitted each frame as a single surface).
        self.map_surface = None
        self._render_map_surface()

        # Decorations: gothic candle stubs along walls. Each candle gets a
        # small per-instance flicker phase so they don't pulse in lockstep.
        self.candles = [
            (wx, wy, random.uniform(0, math.pi * 2),
                     random.uniform(0.85, 1.15))   # flicker speed
            for (wx, wy) in self.get_candle_positions(density=0.16)
        ]
        self._decor_time = 0.0

    # -- Tileset loading --

    def _load_tileset(self, path):
        """Load the tileset and cache every named tile at display scale."""
        search_paths = [
            path,
            os.path.join("images", path),
            os.path.join(os.path.dirname(__file__), path),
        ]
        for p in search_paths:
            if os.path.exists(p):
                try:
                    raw = pygame.image.load(p)
                    # Force RGBA32 (avoids black-tile bug on Mac/SCALED).
                    if raw.get_bitsize() != 32 or not (raw.get_flags() & pygame.SRCALPHA):
                        converted = pygame.Surface(raw.get_size(), pygame.SRCALPHA, 32)
                        converted.blit(raw, (0, 0))
                        self.tileset = converted
                    else:
                        try:
                            self.tileset = raw.convert_alpha()
                        except pygame.error:
                            self.tileset = raw
                    break
                except pygame.error:
                    continue

        if not self.tileset:
            print(f"[TileMap] Warning: Could not load tileset '{path}'")
            return

        # Cut each named tile out once and scale to display size.
        for name, (col, row) in self.TILES.items():
            x = col * self.TILE_SIZE
            y = row * self.TILE_SIZE
            tile_surf = pygame.Surface(
                (self.TILE_SIZE, self.TILE_SIZE), pygame.SRCALPHA)
            tile_surf.blit(self.tileset, (0, 0),
                           (x, y, self.TILE_SIZE, self.TILE_SIZE))
            scaled = pygame.transform.scale(
                tile_surf, (self.DISPLAY_TILE, self.DISPLAY_TILE))
            self.tile_cache[name] = scaled

    # -- Dungeon generation --

    def _generate_dungeon(self):
        """Carve 8-12 rooms, connect them with corridors, add a few loops."""
        for y in range(self.map_h):
            for x in range(self.map_w):
                self.grid[y][x] = 0

        num_rooms = random.randint(8, 12)
        for _ in range(num_rooms * 3):
            if len(self.rooms) >= num_rooms:
                break
            w = random.randint(5, 9)
            h = random.randint(5, 9)
            x = random.randint(2, self.map_w - w - 2)
            y = random.randint(2, self.map_h - h - 2)
            new_room = pygame.Rect(x, y, w, h)

            # Skip rooms that overlap (keep a 1-tile buffer).
            if any(new_room.inflate(2, 2).colliderect(r) for r in self.rooms):
                continue
            self._carve_room(new_room)
            self.rooms.append(new_room)

        # Chain rooms, close the loop, then add 3 extra random links.
        for i in range(len(self.rooms) - 1):
            self._carve_corridor(self.rooms[i], self.rooms[i + 1])
        if len(self.rooms) >= 3:
            self._carve_corridor(self.rooms[-1], self.rooms[0])
        for _ in range(3):
            if len(self.rooms) >= 2:
                a = random.choice(self.rooms)
                b = random.choice(self.rooms)
                if a != b:
                    self._carve_corridor(a, b)

    def _carve_room(self, room):
        """Mark every tile inside `room` as floor."""
        for y in range(room.top, room.bottom):
            for x in range(room.left, room.right):
                if 0 <= x < self.map_w and 0 <= y < self.map_h:
                    self.grid[y][x] = 1

    def _carve_corridor(self, room_a, room_b):
        """Carve an L-shaped 2-tile-wide corridor between two room centers."""
        cx1, cy1 = room_a.centerx, room_a.centery
        cx2, cy2 = room_b.centerx, room_b.centery
        if random.random() < 0.5:
            self._carve_h_tunnel(cx1, cx2, cy1)
            self._carve_v_tunnel(cy1, cy2, cx2)
        else:
            self._carve_v_tunnel(cy1, cy2, cx1)
            self._carve_h_tunnel(cx1, cx2, cy2)

    def _carve_h_tunnel(self, x1, x2, y):
        for x in range(min(x1, x2), max(x1, x2) + 1):
            for dy in range(2):
                ty = y + dy
                if 0 <= x < self.map_w and 0 <= ty < self.map_h:
                    self.grid[ty][x] = 1

    def _carve_v_tunnel(self, y1, y2, x):
        for y in range(min(y1, y2), max(y1, y2) + 1):
            for dx in range(2):
                tx = x + dx
                if 0 <= tx < self.map_w and 0 <= y < self.map_h:
                    self.grid[y][tx] = 1

    # -- Tile picking (deterministic variation per cell) --

    def _pick_floor_tile(self, x, y):
        """Pick a floor variant, weighted toward the first 4 plain tiles."""
        seed = (x * 73 + y * 137 + x * y) % len(self.FLOOR_TILES)
        r = (x * 31 + y * 53) % 100
        if r < 70:
            return self.FLOOR_TILES[seed % 4]
        return self.FLOOR_TILES[seed]

    def _pick_wall_tile(self, x, y):
        """Wall-face if there's floor below, else wall-top."""
        floor_below = (y + 1 < self.map_h and self.grid[y + 1][x] == 1)
        seed = (x * 53 + y * 97) % 4
        if floor_below:
            return self.WALL_FACE_TILES[seed]
        return self.WALL_TOP_TILES[seed]

    def _render_map_surface(self):
        """Rasterize the full dungeon into one surface for fast blitting."""
        self.map_surface = pygame.Surface((self.world_w, self.world_h))
        self.map_surface.fill((12, 8, 14))

        # Fallback: colored rectangles if the tileset failed to load.
        if not self.tile_cache:
            for y in range(self.map_h):
                for x in range(self.map_w):
                    px = x * self.DISPLAY_TILE
                    py = y * self.DISPLAY_TILE
                    color = (50, 45, 55) if self.grid[y][x] == 1 else (20, 15, 22)
                    pygame.draw.rect(self.map_surface, color,
                                     (px, py, self.DISPLAY_TILE, self.DISPLAY_TILE))
            return

        for y in range(self.map_h):
            for x in range(self.map_w):
                px = x * self.DISPLAY_TILE
                py = y * self.DISPLAY_TILE
                tile_name = (self._pick_floor_tile(x, y)
                             if self.grid[y][x] == 1
                             else self._pick_wall_tile(x, y))
                tile = self.tile_cache.get(tile_name)
                if tile:
                    self.map_surface.blit(tile, (px, py))

        # Soft shadow on floor tiles just below a wall, for depth.
        self._paint_wall_shadows()

    def _paint_wall_shadows(self):
        """Blend a top-down gradient shadow onto floors that sit under walls."""
        shadow = pygame.Surface((self.DISPLAY_TILE, 10), pygame.SRCALPHA)
        for a in range(10):
            shadow.fill((0, 0, 0, int(90 * (1 - a / 10))),
                        pygame.Rect(0, a, self.DISPLAY_TILE, 1))
        for y in range(self.map_h):
            for x in range(self.map_w):
                if self.grid[y][x] == 1:
                    if y > 0 and self.grid[y - 1][x] == 0:
                        self.map_surface.blit(
                            shadow, (x * self.DISPLAY_TILE,
                                     y * self.DISPLAY_TILE))

    # -- Queries / spawn helpers --

    def is_wall(self, world_x, world_y):
        """True if the tile at (world_x, world_y) is a wall or out of bounds."""
        tx = int(world_x // self.DISPLAY_TILE)
        ty = int(world_y // self.DISPLAY_TILE)
        if tx < 0 or tx >= self.map_w or ty < 0 or ty >= self.map_h:
            return True
        return self.grid[ty][tx] == 0

    def is_walkable(self, world_x, world_y):
        return not self.is_wall(world_x, world_y)

    def get_spawn_position(self):
        """Random floor tile inside any room (used for enemy spawns)."""
        if self.rooms:
            room = random.choice(self.rooms)
            x = random.randint(room.left + 1, room.right - 2)
            y = random.randint(room.top + 1, room.bottom - 2)
            return (x * self.DISPLAY_TILE + self.DISPLAY_TILE // 2,
                    y * self.DISPLAY_TILE + self.DISPLAY_TILE // 2)
        return (self.world_w // 2, self.world_h // 2)

    def get_start_position(self):
        """Center of the first room — player spawn point."""
        if self.rooms:
            room = self.rooms[0]
            return (room.centerx * self.DISPLAY_TILE,
                    room.centery * self.DISPLAY_TILE)
        return (self.world_w // 2, self.world_h // 2)

    def get_boss_spawn(self, player_x, player_y):
        """Pick the room farthest from the player for a dramatic boss spawn."""
        if len(self.rooms) < 2:
            return self.get_spawn_position()
        best_room = self.rooms[-1]
        best_dist = 0
        for room in self.rooms:
            rx = room.centerx * self.DISPLAY_TILE
            ry = room.centery * self.DISPLAY_TILE
            dist = ((rx - player_x) ** 2 + (ry - player_y) ** 2) ** 0.5
            if dist > best_dist:
                best_dist = dist
                best_room = room
        return (best_room.centerx * self.DISPLAY_TILE,
                best_room.centery * self.DISPLAY_TILE)

    def get_glyph_positions(self, count=5, min_separation=400, skip_first_rooms=1):
        """Return up to `count` floor positions for placing Sloth Glyphs.
        Skips the first `skip_first_rooms` rooms so the player can't be
        cursed before they've taken a step. Picks well-spaced points so
        glyph effects don't overlap into one death zone."""
        chosen = []
        candidates = self.rooms[skip_first_rooms:] if len(self.rooms) > skip_first_rooms else self.rooms[:]
        random.shuffle(candidates)
        for room in candidates:
            if len(chosen) >= count:
                break
            # Place near the room center but with some jitter so it's not
            # always dead-center. Use tile coords for the offset.
            for _ in range(8):
                jx = random.randint(-2, 2)
                jy = random.randint(-2, 2)
                tx = room.centerx + jx
                ty = room.centery + jy
                if not (0 <= tx < self.map_w and 0 <= ty < self.map_h):
                    continue
                if self.grid[ty][tx] != 1:
                    continue
                wx = tx * self.DISPLAY_TILE + self.DISPLAY_TILE // 2
                wy = ty * self.DISPLAY_TILE + self.DISPLAY_TILE // 2
                # Enforce minimum separation between glyphs.
                if any((wx - cx) ** 2 + (wy - cy) ** 2 < min_separation ** 2
                       for (cx, cy) in chosen):
                    continue
                chosen.append((wx, wy))
                break
        return chosen

    def get_candle_positions(self, density=0.18):
        """Return a list of (world_x, world_y) candle decoration spots.
        A candle is placed against the bottom of a wall (just above a wall
        face tile) so it sits on the floor with the wall behind. Density
        controls roughly what fraction of eligible spots get one."""
        positions = []
        for y in range(self.map_h):
            for x in range(self.map_w):
                # Floor tile with a wall directly above → candle sits at
                # the base of that wall, lit pixel-art style.
                if self.grid[y][x] != 1:
                    continue
                if y - 1 < 0 or self.grid[y - 1][x] != 0:
                    continue
                # Skip if there's another wall too close (avoid corners
                # where the candle would clip into geometry).
                if x - 1 >= 0 and self.grid[y][x - 1] == 0 and y - 1 >= 0 and self.grid[y - 1][x - 1] == 0:
                    if random.random() < 0.5:
                        continue
                # Deterministic-ish placement so we don't get a candle on
                # every wall tile.
                seed = (x * 41 + y * 71) % 100
                if seed >= int(density * 100):
                    continue
                wx = x * self.DISPLAY_TILE + self.DISPLAY_TILE // 2
                wy = y * self.DISPLAY_TILE + 6  # nudged up against wall
                positions.append((wx, wy))
        return positions

    def clamp_to_floor(self, x, y, margin=10):
        """If (x, y) is inside a wall, search outward for the nearest floor."""
        if self.is_walkable(x, y):
            return x, y
        for radius in range(1, 10):
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    nx = x + dx * self.DISPLAY_TILE
                    ny = y + dy * self.DISPLAY_TILE
                    if self.is_walkable(nx, ny):
                        return nx, ny
        return x, y

    # -- Draw --

    def update_decor(self, dt):
        """Advance the candle-flicker animation clock."""
        self._decor_time += dt

    def draw(self, surface, camera_x, camera_y, screen_w, screen_h):
        """Blit the visible slice of the cached map surface."""
        surface.fill((10, 8, 12))
        map_rect = pygame.Rect(0, 0, self.world_w, self.world_h)
        src_rect = pygame.Rect(int(camera_x), int(camera_y), screen_w, screen_h)
        clipped = src_rect.clip(map_rect)
        if clipped.width <= 0 or clipped.height <= 0:
            return
        dest_x = clipped.x - int(camera_x)
        dest_y = clipped.y - int(camera_y)
        surface.blit(self.map_surface, (dest_x, dest_y), clipped)

        # Candles drawn directly on top of the floor so they flicker live
        # without re-baking the whole map surface every frame.
        self._draw_candles(surface, camera_x, camera_y, screen_w, screen_h)

    def _draw_candles(self, surface, camera_x, camera_y, screen_w, screen_h):
        """Draw small gothic candles along eligible wall tiles."""
        if not self.candles:
            return
        cam_x_int = int(camera_x)
        cam_y_int = int(camera_y)
        # Cull margin — candles + their glow stay within ±48px of viewport.
        for (wx, wy, phase, speed) in self.candles:
            sx = wx - cam_x_int
            sy = wy - cam_y_int
            if sx < -32 or sx > screen_w + 32:
                continue
            if sy < -48 or sy > screen_h + 48:
                continue

            # Flicker: combine slow sin + fast jitter to feel like flame.
            t = self._decor_time * speed
            flicker = 0.7 + 0.18 * math.sin(t * 6.0 + phase) \
                          + 0.12 * math.sin(t * 17.0 + phase * 2.3)
            flicker = max(0.55, min(1.15, flicker))

            # 1) Candle stub — pale wax body, 4px wide, 9px tall.
            wax_top = sy - 4
            wax_col = (220, 210, 188)
            pygame.draw.rect(surface, wax_col, (sx - 2, wax_top, 4, 9))
            # Wax shadow line for shape.
            pygame.draw.line(surface, (140, 130, 110),
                             (sx - 2, wax_top + 8), (sx + 1, wax_top + 8))

            # 2) Wick.
            pygame.draw.line(surface, (40, 30, 25),
                             (sx, wax_top - 1), (sx, wax_top - 3))

            # 3) Outer glow halo (additive).
            halo_r = int(14 * flicker)
            halo = pygame.Surface((halo_r * 2, halo_r * 2), pygame.SRCALPHA)
            for i in range(4, 0, -1):
                a = int(40 * (i / 4) * flicker)
                pygame.draw.circle(halo, (255, 170, 70, a),
                                   (halo_r, halo_r),
                                   int(halo_r * (i / 4)))
            surface.blit(halo, (sx - halo_r, wax_top - 6 - halo_r),
                         special_flags=pygame.BLEND_RGBA_ADD)

            # 4) Flame body — small teardrop shape (yellow inside, orange out).
            fy = wax_top - 5
            outer_r = max(2, int(3 * flicker))
            inner_r = max(1, outer_r - 1)
            pygame.draw.circle(surface, (255, 130, 40),
                               (sx, fy), outer_r)
            pygame.draw.circle(surface, (255, 230, 140),
                               (sx, fy - 1), inner_r)
