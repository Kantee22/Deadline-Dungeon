"""animation.py - Sprite animation loader (folder-based, auto-cropped)."""
import pygame
import os


# Legacy folder names mapped to the new names.
OLD_NAME_ALIASES = {
    "attack_melee": "attack",
    "attack_bow":   "skill",
}


class Animation:
    """One animation sequence (frames + timing)."""

    def __init__(self, frames, frame_duration=0.12, loop=True):
        self.frames = frames
        self.frame_duration = frame_duration
        self.loop = loop
        self.timer = 0.0
        self.current_frame = 0
        self.finished = False

    def reset(self):
        self.timer = 0.0
        self.current_frame = 0
        self.finished = False

    def update(self, dt):
        if self.finished or not self.frames:
            return
        self.timer += dt
        if self.timer >= self.frame_duration:
            self.timer -= self.frame_duration
            self.current_frame += 1
            if self.current_frame >= len(self.frames):
                if self.loop:
                    self.current_frame = 0
                else:
                    self.current_frame = len(self.frames) - 1
                    self.finished = True

    def get_frame(self):
        if not self.frames:
            return None
        return self.frames[self.current_frame]


class SpriteAnimator:
    """Holds all animations for one character (multiple actions + directions)."""

    DEFAULT_DURATIONS = {
        "idle":    0.15,
        "walk":    0.10,
        "attack":  0.08,
        "skill":   0.08,
        "hurt":    0.12,
        "death":   0.14,
        "special": 0.10,
    }

    # Actions that play once instead of looping.
    NO_LOOP = {"attack", "skill", "hurt", "death", "special"}

    def __init__(self, sprite_folder, scale=None, pixel_scale=None, auto_crop=True):
        """pixel_scale (preferred) scales by multiplier; scale forces fixed size."""
        self.animations = {}
        self.current_action = "idle"
        self.current_direction = "right"
        self.scale = scale
        self.pixel_scale = pixel_scale
        self.auto_crop = auto_crop
        self.loaded = False
        self.frame_size = (0, 0)

        if os.path.isdir(sprite_folder):
            self._load_from_folder(sprite_folder)
            self.loaded = len(self.animations) > 0

    def _apply_scale(self, frames):
        """Return frames resized by pixel_scale (or fixed scale)."""
        if not frames:
            return frames
        if self.pixel_scale:
            out = []
            for f in frames:
                w = max(1, int(f.get_width() * self.pixel_scale))
                h = max(1, int(f.get_height() * self.pixel_scale))
                out.append(pygame.transform.scale(f, (w, h)))
            return out
        if self.scale:
            return [pygame.transform.scale(f, self.scale) for f in frames]
        return frames

    def _load_from_folder(self, folder):
        """Load animations from either action_direction subfolders or a flat folder."""
        entries = os.listdir(folder)

        # Flat folder = images directly inside (single shared anim).
        has_direct_images = any(
            f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp"))
            for f in entries
            if os.path.isfile(os.path.join(folder, f))
        )

        if has_direct_images:
            frames = self._load_raw_frames(folder)
            if frames:
                if self.auto_crop:
                    bbox = None
                    for f in frames:
                        rect = f.get_bounding_rect(min_alpha=1)
                        if rect.width == 0 or rect.height == 0:
                            continue
                        bbox = rect if bbox is None else bbox.union(rect)
                    if bbox is not None and bbox.width > 0:
                        bbox.inflate_ip(4, 4)
                        full_rect = pygame.Rect(0, 0, *frames[0].get_size())
                        bbox = bbox.clip(full_rect)
                        cropped = []
                        for f in frames:
                            new_surf = pygame.Surface(
                                (bbox.width, bbox.height), pygame.SRCALPHA)
                            new_surf.blit(f, (0, 0), bbox)
                            cropped.append(new_surf)
                        frames = cropped
                frames = self._apply_scale(frames)
                if frames:
                    self.frame_size = frames[0].get_size()
                anim = Animation(frames, 0.10, loop=True)
                self.animations["idle_left"] = anim
                self.animations["idle_right"] = anim
            return

        # Parse action_direction subfolder names.
        parsed = {}
        for entry in entries:
            full_path = os.path.join(folder, entry)
            if not os.path.isdir(full_path):
                continue

            if entry.endswith("_left"):
                action_part = entry[:-5]
                direction = "left"
            elif entry.endswith("_right"):
                action_part = entry[:-6]
                direction = "right"
            else:
                continue

            action = OLD_NAME_ALIASES.get(action_part, action_part)
            key = f"{action}_{direction}"
            if key in parsed and action_part in OLD_NAME_ALIASES:
                continue
            parsed[key] = full_path

        # Pass 1: read raw frames from every subfolder.
        raw_anims = {}
        for key, folder_path in parsed.items():
            frames = self._load_raw_frames(folder_path)
            if frames:
                raw_anims[key] = frames

        # Pass 2: compute a shared bounding box so all actions stay the same size.
        shared_bbox = None
        if self.auto_crop:
            for frames in raw_anims.values():
                for f in frames:
                    rect = f.get_bounding_rect(min_alpha=1)
                    if rect.width == 0 or rect.height == 0:
                        continue
                    if shared_bbox is None:
                        shared_bbox = rect
                    else:
                        shared_bbox = shared_bbox.union(rect)

            if shared_bbox is not None:
                padding = 2
                shared_bbox.inflate_ip(padding * 2, padding * 2)
                any_frame = next(iter(raw_anims.values()))[0]
                full_rect = pygame.Rect(0, 0, *any_frame.get_size())
                shared_bbox = shared_bbox.clip(full_rect)

        # Pass 3: crop, scale, wrap in Animation.
        for key, frames in raw_anims.items():
            action = key.rsplit("_", 1)[0]
            if self.auto_crop and shared_bbox is not None and shared_bbox.width > 0:
                cropped = []
                for f in frames:
                    new_surf = pygame.Surface(
                        (shared_bbox.width, shared_bbox.height), pygame.SRCALPHA)
                    new_surf.blit(f, (0, 0), shared_bbox)
                    cropped.append(new_surf)
                frames = cropped

            frames = self._apply_scale(frames)

            if frames and self.frame_size == (0, 0):
                self.frame_size = frames[0].get_size()

            duration = self.DEFAULT_DURATIONS.get(action, 0.12)
            loop = action not in self.NO_LOOP
            self.animations[key] = Animation(frames, duration, loop)

    def _load_raw_frames(self, folder_path):
        """Load frame images from a folder sorted numerically."""
        extensions = (".png", ".jpg", ".jpeg", ".bmp")
        files = []
        for f in os.listdir(folder_path):
            if f.lower().endswith(extensions):
                files.append(os.path.join(folder_path, f))

        def sort_key(filepath):
            name = os.path.splitext(os.path.basename(filepath))[0]
            try:
                return (0, int(name))
            except ValueError:
                return (1, name)
        files.sort(key=sort_key)

        raw_frames = []
        for filepath in files:
            try:
                img = pygame.image.load(filepath)
                # Force explicit RGBA32 (avoids black-sprite bug on Mac/SCALED).
                if img.get_bitsize() != 32 or not (img.get_flags() & pygame.SRCALPHA):
                    converted = pygame.Surface(img.get_size(), pygame.SRCALPHA, 32)
                    converted.blit(img, (0, 0))
                    img = converted
                else:
                    try:
                        img = img.convert_alpha()
                    except pygame.error:
                        pass
                raw_frames.append(img)
            except pygame.error:
                continue
        return raw_frames

    def set_action(self, action, force=False):
        """Switch to a new action (won't interrupt non-looping actions unless force=True)."""
        if action == self.current_action and not force:
            key = f"{self.current_action}_{self.current_direction}"
            anim = self.animations.get(key)
            if anim and not anim.loop and not anim.finished:
                return

        self.current_action = action
        for d in ("left", "right"):
            key = f"{action}_{d}"
            if key in self.animations:
                self.animations[key].reset()

    def set_direction(self, direction):
        if direction in ("left", "right"):
            self.current_direction = direction

    def update(self, dt):
        key = f"{self.current_action}_{self.current_direction}"
        anim = self.animations.get(key)
        if anim:
            anim.update(dt)

    def is_action_finished(self):
        key = f"{self.current_action}_{self.current_direction}"
        anim = self.animations.get(key)
        if anim:
            return anim.finished
        return True

    def get_frame(self):
        """Return current frame; flip from the opposite direction if missing."""
        key = f"{self.current_action}_{self.current_direction}"
        anim = self.animations.get(key)
        if anim:
            return anim.get_frame()
        other = "right" if self.current_direction == "left" else "left"
        key = f"{self.current_action}_{other}"
        anim = self.animations.get(key)
        if anim:
            frame = anim.get_frame()
            if frame:
                return pygame.transform.flip(frame, True, False)
        return None

    def has_action(self, action):
        return (f"{action}_left" in self.animations or
                f"{action}_right" in self.animations)

    def draw(self, surface, x, y, camera_x=0, camera_y=0):
        """Blit current frame centered at world coord (x, y)."""
        frame = self.get_frame()
        if frame:
            sx = x - camera_x - frame.get_width() // 2
            sy = y - camera_y - frame.get_height() // 2
            surface.blit(frame, (int(sx), int(sy)))
            return True
        return False