class Qwen2512ResT2I:
    RESOLUTIONS = [
        "1328×1328  (1:1)",
        "1664×928   (16:9)",
        "928×1664   (9:16)",
        "1472×1104  (4:3)",
        "1104×1472  (3:4)",
        "1584×1056  (3:2)",
        "1056×1584  (2:3)",
    ]

    # Map display string -> (width, height)
    _RES_MAP = {
        "1328×1328  (1:1)":  (1328, 1328),
        "1664×928   (16:9)": (1664,  928),
        "928×1664   (9:16)": ( 928, 1664),
        "1472×1104  (4:3)":  (1472, 1104),
        "1104×1472  (3:4)":  (1104, 1472),
        "1584×1056  (3:2)":  (1584, 1056),
        "1056×1584  (2:3)":  (1056, 1584),
    }

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "resolution": (cls.RESOLUTIONS, {"default": cls.RESOLUTIONS[0]}),
            }
        }

    RETURN_TYPES = ("INT", "INT")
    RETURN_NAMES = ("Width", "Height")
    FUNCTION = "get_resolution"
    CATEGORY = "SBL"

    def get_resolution(self, resolution):
        w, h = self._RES_MAP[resolution]
        return (w, h)
