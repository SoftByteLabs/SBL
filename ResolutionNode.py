import math
import re

class ResolutionNode:
    DESCRIPTION = (
        "Choose a resolution preset or custom dimensions, snap to a pixel multiple, "
        "and optionally cap output megapixels without upscaling."
    )
    OUTPUT_TOOLTIPS = (
        "Effective output width after snapping and optional max-megapixel downscaling.",
        "Effective output height after snapping and optional max-megapixel downscaling.",
    )

    # Backend superset of the frontend aspect-ratio groups.
    ALL_PRESETS = [
        "Custom",
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

    GROUPS = [
        "Custom",
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
                "aspect_group": (cls.GROUPS, {"default": "Custom", "tooltip": "Select a family of aspect ratios to filter the preset list. Choose Custom for manual sizes."}),
                "preset": (cls.ALL_PRESETS, {"default": "Custom", "tooltip": "Pick a named width × height preset, or Custom to enter your own dimensions."}),
                "width": ("INT", {"default": 1024, "min": 16, "max": 8192, "step": 1, "tooltip": "Selected width in pixels before the megapixel cap. Changing it manually switches to Custom."}),
                "height": ("INT", {"default": 1024, "min": 16, "max": 8192, "step": 1, "tooltip": "Selected height in pixels before the megapixel cap. Changing it manually switches to Custom."}),
                "multiple_of": (["1", "2", "4", "8", "16", "28", "32", "64", "128"], {"default": "8", "tooltip": "Snap dimensions to a pixel multiple (often 8, 16, 32, or 64). The MP-capped output also follows this grid when possible."}),
                "max_megapixels": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 100.0, "step": 0.01, "round": 0.01, "tooltip": "Maximum output area in millions of pixels. 0 disables the cap; smaller images are unchanged. Oversized images are downscaled while preserving aspect ratio as closely as possible."}),
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

    @staticmethod
    def _limit_megapixels(width, height, multiple_of, max_megapixels):
        """Cap area without upscaling, preserving ratio as closely as grid permits.

        The base dimensions remain independent of the cap. A zero cap, or one
        at least as large as the base area, returns the dimensions unchanged.
        """
        width, height = int(width), int(height)
        limit = float(max_megapixels or 0) * 1_000_000
        if limit <= 0 or width * height <= limit:
            return width, height

        ratio = width / height
        scale = math.sqrt(limit / (width * height))
        target_width = width * scale
        target_height = height * scale

        def find_best(step):
            # Explore the nearest grid points on both sides of the ideal size.
            # The neighboring points also allow a closer ratio/area tradeoff.
            base_w = math.floor(target_width / step)
            base_h = math.floor(target_height / step)
            width_centers = [base_w]
            height_centers = [base_h]
            if target_height < max(16, step):
                width_centers.append(math.floor(min(width, limit / max(16, step)) / step))
                height_centers.append(math.ceil(16 / step))
            if target_width < max(16, step):
                height_centers.append(math.floor(min(height, limit / max(16, step)) / step))
                width_centers.append(math.ceil(16 / step))
            width_steps = sorted({x for base in width_centers for x in range(max(1, base - 2), base + 4)})
            height_steps = sorted({y for base in height_centers for y in range(max(1, base - 2), base + 4)})
            best = None
            for x in width_steps:
                candidate_w = x * step
                if candidate_w < 16 or candidate_w > width:
                    continue
                for y in height_steps:
                    candidate_h = y * step
                    if candidate_h < 16 or candidate_h > height:
                        continue
                    pixels = candidate_w * candidate_h
                    if pixels > limit:
                        continue
                    ratio_error = math.log((candidate_w / candidate_h) / ratio)
                    area_gap = (limit - pixels) / limit
                    # The ratio matters more than a marginal area gain.
                    score = (2 * ratio_error) ** 2 + area_gap ** 2
                    key = (score, abs(ratio_error), area_gap)
                    if best is None or key < best[0]:
                        best = (key, candidate_w, candidate_h)
            return (best[1], best[2]) if best else None

        step = max(1, int(multiple_of))
        result = find_best(step)
        if result is None:
            # For very small MP limits, even one full multiple may not fit.
            # Honor the hard pixel cap instead of returning too many pixels.
            result = find_best(1)
        return result if result else (16, 16)

    def process(self, aspect_group, preset, width, height, multiple_of, max_megapixels=0.0):
        # Presets retain their aspect ratio when snapped to the requested multiple.
        if preset and preset != "Custom":
            target_dimensions = self._parse_preset_dimensions(preset)
            if target_dimensions:
                target_width, target_height = target_dimensions
                width, height = self._snap_dimensions_closest_ratio(
                    width, height, multiple_of, target_width, target_height,
                )
            else:
                width = self._snap_dimension(width, multiple_of)
                height = self._snap_dimension(height, multiple_of)
        else:
            # Manual dimensions have no ratio lock and snap independently.
            width = self._snap_dimension(width, multiple_of)
            height = self._snap_dimension(height, multiple_of)

        return self._limit_megapixels(
            width, height, multiple_of, max_megapixels,
        )
