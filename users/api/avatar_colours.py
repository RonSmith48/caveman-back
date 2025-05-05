import colorsys
import random

class AvatarColours:
    _cached_palette = None  # <- cache here

    @classmethod
    def get_palette(cls):
        if cls._cached_palette is None:
            cls._cached_palette = cls.generate_avatar_palette()
        return cls._cached_palette

    @staticmethod
    def generate_avatar_palette(n=64, s=0.75, v=0.65):
        palette = []
        for i in range(n):
            h = i / n
            r, g, b = colorsys.hsv_to_rgb(h, s, v)
            hex_color = '#{:02x}{:02x}{:02x}'.format(int(r * 255), int(g * 255), int(b * 255))
            palette.append((hex_color, r, g, b))
        return palette

    @staticmethod
    def get_contrast_color(r, g, b):
        luminance = 0.299 * r + 0.587 * g + 0.114 * b
        return '#000000' if luminance > 0.5 else '#ffffff'

    @classmethod
    def get_random_avatar_color(cls):
        palette = cls.get_palette()
        hex_color, r, g, b = random.choice(palette)
        contrast_color = cls.get_contrast_color(r, g, b)
        return hex_color, contrast_color
