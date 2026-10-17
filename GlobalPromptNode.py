class GlobalPromptNode:
    DESCRIPTION = "Store positive and negative prompt text in one node and share the strings across a workflow."
    OUTPUT_TOOLTIPS = ("Positive prompt text (STRING).", "Negative prompt text (STRING).")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "positive": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "tooltip": "Reusable positive prompt text to send to downstream prompt or text-encoding nodes."
                }),
                "negative": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "tooltip": "Reusable negative prompt text, for downstream nodes that accept negative conditioning."
                }),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("positive", "negative")
    FUNCTION = "process"
    CATEGORY = "SBL"

    def process(self, positive, negative):
        return (positive, negative)
