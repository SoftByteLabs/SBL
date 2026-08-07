import math
import re

class ResolutionNode:
    # Keep this list broad (superset) so the backend accepts any dropdown value the UI offers.
    # JS will filter this list per group.
    ALL_PRESETS = [
        "Custom",
        # Qwen2512
        "1328x1328 (1:1)", "1664x928 (16:9)", "928x1664 (9:16)",
        "1472x1104 (4:3)", "1104x1472 (3:4)", "1584x1056 (3:2)", "1056x1584 (2:3)",
        # ZiT
        "1024x1024 (1:1)", "1152x896 (9:7)", "896x1152 (7:9)",
        "1152x864 (4:3)", "864x1152 (3:4)", "1248x832 (3:2)",
        "832x1248 (2:3)", "1280x720 (16:9)", "720x1280 (9:16)",
        "1344x576 (21:9)", "576x1344 (9:21)",
        "1280x1280 (1:1)", "1440x1120 (9:7)", "1120x1440 (7:9)",
        "1472x1104 (4:3)", "1104x1472 (3:4)", "1536x1024 (3:2)",
        "1024x1536 (2:3)", "1600x896 (16:9)", "896x1600 (9:16)",
        "1680x720 (21:9)", "720x1680 (9:21)",
        # 1:1 (Square)
        "64x64", "128x128", "192x192", "256x256", "320x320", "384x384", "448x448", 
        "512x512", "640x640", "768x768", "1024x1024", "1536x1536", "2048x2048", "4096x4096",
        # 4:3 (Classic)
        "320x240", "512x384", "640x480 (VGA)", "800x600 (SVGA)", "1024x768 (XGA)", 
        "1152x864", "1280x960", "1400x1050", "1600x1200 (UXGA)", "2048x1536 (QXGA)", 
        "2732x2048 (iPad Pro 12.9)",
        # 3:2 (Photo)
        "384x256", "576x384", "768x512", "1152x768", "1536x1024", "1620x1080", 
        "2160x1440", "2736x1824 (Surface Pro)", "3000x2000", "3240x2160",
        # 16:9 (Widescreen)
        "512x288", "640x360", "768x432", "854x480 (480p)", "896x504", "960x540 (qHD)", 
        "1024x576", "1280x720 (720p)", "1600x900 (HD+)", "1920x1080 (1080p)", 
        "2560x1440 (1440p)", "3840x2160 (4K UHD)", "7680x4320 (8K UHD)",
        # 16:10 (Widescreen+)
        "512x320", "768x480", "1024x640", "1280x800", "1440x900", "1680x1050", 
        "1920x1200 (WUXGA)", "2560x1600 (WQXGA)", "2880x1800 (Retina 15)", "3840x2400 (WQUXGA)",
        # 21:9 (Ultrawide)
        "1024x438", "1792x768", "2560x1080", "3440x1440", "3840x1600", "5120x2160 (5K2K)",
        # 32:9 (Super Ultrawide)
        "1792x504", "2560x720", "3840x1080", "5120x1440", "7680x2160",
        # 7:4 (Photo Wide)
        "448x256", "896x512", "1344x768", "1792x1024", "2240x1280", "3136x1792",
        # Phones (20:9, 19:9, 19.5:9, 18.5:9)
        "2280x1080 (19:9)", "2400x1080 (20:9)", "2436x1125 (19.5:9 iPhone X/XS)", 
        "2532x1170 (19.5:9 iPhone 12/13/14)", "2778x1284 (19.5:9 iPhone Pro Max)", 
        "2960x1440 (18.5:9)",
        # Cinema (≈1.90:1, ≈2.39:1)
        "2048x1080 (1.90:1 DCI 2K Flat)", "2048x858 (2.39:1 DCI 2K Scope)", 
        "4096x2160 (1.90:1 DCI 4K Flat)", "4096x1716 (2.39:1 DCI 4K Scope)",
    ]

    QWEN2512_MAP = {
        "1328x1328 (1:1)":  (1328, 1328),
        "1664x928 (16:9)":  (1664,  928),
        "928x1664 (9:16)":  ( 928, 1664),
        "1472x1104 (4:3)":  (1472, 1104),
        "1104x1472 (3:4)":  (1104, 1472),
        "1584x1056 (3:2)":  (1584, 1056),
        "1056x1584 (2:3)":  (1056, 1584),
    }

    # Lookup map for ZiT presets (keyed by exact label string)
    ZIT_MAP = {
        "1024x1024 (1:1)":  (1024, 1024),
        "1152x896 (9:7)":   (1152,  896),
        "896x1152 (7:9)":   ( 896, 1152),
        "1152x864 (4:3)":   (1152,  864),
        "864x1152 (3:4)":   ( 864, 1152),
        "1248x832 (3:2)":   (1248,  832),
        "832x1248 (2:3)":   ( 832, 1248),
        "1280x720 (16:9)":  (1280,  720),
        "720x1280 (9:16)":  ( 720, 1280),
        "1344x576 (21:9)":  (1344,  576),
        "576x1344 (9:21)":  ( 576, 1344),
        "1280x1280 (1:1)":  (1280, 1280),
        "1440x1120 (9:7)":  (1440, 1120),
        "1120x1440 (7:9)":  (1120, 1440),
        "1472x1104 (4:3)":  (1472, 1104),
        "1104x1472 (3:4)":  (1104, 1472),
        "1536x1024 (3:2)":  (1536, 1024),
        "1024x1536 (2:3)":  (1024, 1536),
        "1600x896 (16:9)":  (1600,  896),
        "896x1600 (9:16)":  ( 896, 1600),
        "1680x720 (21:9)":  (1680,  720),
        "720x1680 (9:21)":  ( 720, 1680),
    }

    GROUPS = [
        "Custom",
        "Qwen2512",
        "ZiT",
        "1:1 (Square)",
        "4:3 (Classic)",
        "3:2 (Photo)",
        "16:9 (Widescreen)",
        "16:10 (Widescreen+)",
        "21:9 (Ultrawide)",
        "32:9 (Super Ultrawide)",
        "7:4 (Photo Wide)",
        "Phones (Tall)",
        "Cinema (DCI)",
    ]

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "aspect_group": (cls.GROUPS, {"default": "Custom"}),
                "preset": (cls.ALL_PRESETS, {"default": "Custom"}),
                "width": ("INT", {"default": 1024, "min": 16, "max": 8192, "step": 1}),
                "height": ("INT", {"default": 1024, "min": 16, "max": 8192, "step": 1}),
                "multiple_of": (["1", "2", "4", "8", "16", "28", "32", "64", "128"], {"default": "8"}),
            }
        }

    RETURN_TYPES = ("INT", "INT")
    RETURN_NAMES = ("width", "height")
    FUNCTION = "process"
    CATEGORY = "SBL"

    @staticmethod
    def _parse_preset_dimensions(preset):
        match = re.search(r"(\d+)\s*[xX×]\s*(\d+)", str(preset))
        if not match:
            return None
        return int(match.group(1)), int(match.group(2))

    @staticmethod
    def _multiple_candidates(value, step):
        floor_value = max(step, min(8192, (value // step) * step))
        ceil_value = max(step, min(8192, math.ceil(value / step) * step))
        return tuple(dict.fromkeys((floor_value, ceil_value)))

    @classmethod
    def _snap_dimensions_closest_ratio(
        cls,
        width,
        height,
        multiple_of,
        target_width=None,
        target_height=None,
    ):
        step = max(1, int(multiple_of))
        width = int(width)
        height = int(height)

        if step == 1:
            return width, height

        if target_width is None or target_height is None or target_height <= 0:
            target_width, target_height = width, height

        target_ratio = target_width / target_height
        width_candidates = cls._multiple_candidates(width, step)
        height_candidates = cls._multiple_candidates(height, step)
        best = None
        epsilon = 1e-12

        for candidate_width in width_candidates:
            for candidate_height in height_candidates:
                candidate_ratio = candidate_width / candidate_height
                ratio_error = abs(candidate_ratio - target_ratio)
                dimension_error = (
                    abs(candidate_width - width) / max(1, width)
                    + abs(candidate_height - height) / max(1, height)
                )

                if (
                    best is None
                    or ratio_error < best[0] - epsilon
                    or (
                        abs(ratio_error - best[0]) <= epsilon
                        and dimension_error < best[1]
                    )
                ):
                    best = (
                        ratio_error,
                        dimension_error,
                        candidate_width,
                        candidate_height,
                    )

        return best[2], best[3]

    @staticmethod
    def _snap_dimension(value, multiple_of):
        step = max(1, int(multiple_of))
        value = int(value)
        if step == 1:
            return max(16, min(8192, value))

        # Values are positive, so floor(x + 0.5) gives normal nearest rounding
        # rather than Python's banker's rounding on exact half steps.
        snapped = math.floor(value / step + 0.5) * step
        return max(step, min(8192, snapped))

    def process(self, aspect_group, preset, width, height, multiple_of):
        # Qwen2512 presets: override width/height from the map, bypass multiple_of snapping.
        if preset in self.QWEN2512_MAP:
            w, h = self.QWEN2512_MAP[preset]
            return (w, h)

        # ZiT presets: override width/height from the map, bypass multiple_of snapping.
        if preset in self.ZIT_MAP:
            w, h = self.ZIT_MAP[preset]
            return (w, h)

        # A selected preset uses floor/ceil pair testing to preserve its ratio.
        if preset and preset != "Custom":
            target_dimensions = self._parse_preset_dimensions(preset)
            if target_dimensions:
                target_width, target_height = target_dimensions
                return self._snap_dimensions_closest_ratio(
                    width,
                    height,
                    multiple_of,
                    target_width,
                    target_height,
                )

        # Custom mode has no ratio lock. Each dimension is validated independently.
        return (
            self._snap_dimension(width, multiple_of),
            self._snap_dimension(height, multiple_of),
        )
