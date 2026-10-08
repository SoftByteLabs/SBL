import math
import re


class YuE2Instrumental:
    """
    Takes a generated YuE2 ABC score and:
      1) silences the Vocal voice by replacing pitched notes with equal-length rests,
         while preserving chord annotations and score timing;
      2) builds section-only lyrics from ABC comments such as % intro / % verse;
      3) calculates a safe max_duration from meter, tempo, and the Ins voice bar count.

    The final outputs are intended to connect directly to YuE2 Generate Music:
      abc          -> abc
      lyrics       -> lyrics
      max_duration -> max_duration
    """

    SECTION_ALIASES = {
        "prechorus": "pre-chorus",
        "pre chorus": "pre-chorus",
        "pre_chorus": "pre-chorus",
    }

    KNOWN_SECTIONS = {
        "intro",
        "verse",
        "pre-chorus",
        "chorus",
        "bridge",
        "interlude",
        "instrumental",
        "breakdown",
        "solo",
        "hook",
        "refrain",
        "outro",
    }

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "abc": (
                    "STRING",
                    {
                        "multiline": True,
                        "forceInput": True,
                    },
                ),
                "padding_seconds": (
                    "FLOAT",
                    {
                        "default": 0.0,
                        "min": 0.0,
                        "max": 30.0,
                        "step": 0.1,
                    },
                ),
            }
        }

    RETURN_TYPES = (
        "STRING",  # cleaned ABC
        "STRING",  # section lyrics
        "FLOAT",   # max duration
        "FLOAT",   # theoretical score duration
        "INT",     # bars
        "FLOAT",   # BPM
        "STRING",  # info/debug
    )

    RETURN_NAMES = (
        "abc",
        "lyrics",
        "max_duration",
        "score_seconds",
        "bars",
        "bpm",
        "info",
    )

    FUNCTION = "process"
    CATEGORY = "SBL"

    # -------------------------------------------------------------------------
    # Header / structure parsing
    # -------------------------------------------------------------------------

    @staticmethod
    def _parse_header(abc):
        # YuE2 normally emits M:4/4 and Q:1/4=NN, but keep this generic.
        meter_num, meter_den = 4, 4
        beat_num, beat_den, bpm = 1, 4, 120.0

        meter = re.search(
            r"(?mi)^\s*M:\s*(\d+)\s*/\s*(\d+)\s*$",
            abc,
        )
        if meter:
            meter_num = int(meter.group(1))
            meter_den = int(meter.group(2))

        tempo = re.search(
            r"(?mi)^\s*Q:\s*(?:(\d+)\s*/\s*(\d+)\s*=\s*)?"
            r"([0-9]+(?:\.[0-9]+)?)\s*$",
            abc,
        )
        if tempo:
            if tempo.group(1) and tempo.group(2):
                beat_num = int(tempo.group(1))
                beat_den = int(tempo.group(2))
            bpm = float(tempo.group(3))

        if meter_num <= 0 or meter_den <= 0:
            raise ValueError("H3 Instrumental: invalid M: meter in ABC.")
        if beat_num <= 0 or beat_den <= 0 or bpm <= 0:
            raise ValueError("H3 Instrumental: invalid Q: tempo in ABC.")

        return meter_num, meter_den, beat_num, beat_den, bpm

    @classmethod
    def _extract_sections(cls, abc):
        sections = []

        for line in abc.splitlines():
            match = re.match(
                r"^\s*%\s*([A-Za-z][A-Za-z _-]*)\s*$",
                line,
            )
            if not match:
                continue

            name = re.sub(r"\s+", " ", match.group(1).strip().lower())
            name = cls.SECTION_ALIASES.get(name, name)

            # Only consume section-like comments. This prevents unrelated ABC
            # comments from becoming lyric tags.
            if name in cls.KNOWN_SECTIONS:
                sections.append(name)

        # A generated YuE2 ABC normally has section comments. If one does not,
        # give Generate Music harmless structural conditioning instead of using
        # the user's old/manual lyric text.
        if not sections:
            sections = ["intro", "outro"]

        return sections

    # -------------------------------------------------------------------------
    # Vocal muting
    # -------------------------------------------------------------------------

    @staticmethod
    def _mask_non_note_groups(text):
        """Mask things that may contain A-G letters but are not note events."""
        placeholders = {}
        counter = 0

        def store(match):
            nonlocal counter
            token = f"\x00Q{counter}Q\x00"
            placeholders[token] = match.group(0)
            counter += 1
            return token

        # Chord annotations: "Dm", "Fmaj7", etc.
        text = re.sub(r'"(?:\\.|[^"\\])*"', store, text)

        # Inline ABC fields: [K:Dm], [M:4/4], [Q:1/4=68], etc.
        text = re.sub(r"\[[A-Za-z]:[^\]]*\]", store, text)

        # ABC decorations.
        text = re.sub(r"![^!]*!", store, text)
        text = re.sub(r"\+[^+]*\+", store, text)

        return text, placeholders

    @staticmethod
    def _restore_masked(text, placeholders):
        for token, original in placeholders.items():
            text = text.replace(token, original)
        return text

    @classmethod
    def _mute_vocal_music(cls, music):
        """
        Replace pitched Vocal events with rests while preserving their written
        durations, barlines, chord annotations, tuplets, and other timing marks.

        Examples:
          "Dm"A8z16A2G2F2G2-  ->  "Dm"z8z16z2z2z2z2
          "Bb"F8..."C"E4...   ->  chord annotations remain intact.
        """
        masked, placeholders = cls._mask_non_note_groups(music)

        # Grace notes have no measured duration. Removing them is safer than
        # leaving pitched grace notes in the Vocal voice.
        masked = re.sub(r"\{[^{}]*\}", "", masked)

        # ABC note chords such as [CEG]2 are a single pitched event. Convert
        # them to an equal-length rest. Inline fields were masked above.
        chord_pattern = re.compile(r"\[([^\]]+)\]((?:\d+)?(?:/\d*)?)")

        def mute_note_chord(match):
            inside = match.group(1)
            length = match.group(2) or ""
            if re.search(r"[A-Ga-g]", inside):
                return "z" + length
            return match.group(0)

        masked = chord_pattern.sub(mute_note_chord, masked)

        # Replace every ordinary pitched note with an equal-duration rest.
        # No word-boundary is used because ABC commonly writes notes directly
        # adjacent to one another, e.g. A2G2F2G2.
        note_pattern = re.compile(
            r"(?:\^{1,2}|_{1,2}|=)?"       # accidental
            r"[A-Ga-g]"                    # pitch
            r"[,']*"                       # octave marks
            r"((?:\d+)?(?:/\d*)?)"       # written duration
        )
        masked = note_pattern.sub(
            lambda match: "z" + (match.group(1) or ""),
            masked,
        )

        # A tie after a note is meaningless once both events are rests.
        masked = re.sub(r"(z(?:\d+)?(?:/\d*)?)-", r"\1", masked)

        return cls._restore_masked(masked, placeholders)

    @classmethod
    def _mute_vocal_voice(cls, abc):
        output = []
        in_body = False
        current_voice = None
        changed_lines = 0

        for line in abc.splitlines():
            stripped = line.strip()

            # K: terminates the ABC header. V: lines after this point are voice
            # selectors rather than just voice definitions.
            if stripped.startswith("K:"):
                in_body = True
                output.append(line)
                continue

            voice = re.match(r"^\s*V:\s*([^\s]+)", line)
            if voice:
                if in_body:
                    current_voice = voice.group(1).lower()
                output.append(line)
                continue

            if (
                in_body
                and current_voice == "vocal"
                and stripped
                and not stripped.startswith("%")
            ):
                muted = cls._mute_vocal_music(line)
                if muted != line:
                    changed_lines += 1
                output.append(muted)
            else:
                output.append(line)

        return "\n".join(output), changed_lines

    # -------------------------------------------------------------------------
    # Duration
    # -------------------------------------------------------------------------

    @staticmethod
    def _remove_quoted_annotations(text):
        return re.sub(r'"(?:\\.|[^"\\])*"', "", text)

    @classmethod
    def _count_voice_bars(cls, abc, target_voice):
        """
        Count written measures in a YuE2 voice.

        Normal measures are separated by |. ABC multi-measure rests such as Z3
        count as three measures even though they occupy one textual field.
        """
        in_body = False
        current_voice = None
        bars = 0
        saw_target = False

        for line in abc.splitlines():
            stripped = line.strip()

            if stripped.startswith("K:"):
                in_body = True
                continue

            voice = re.match(r"^\s*V:\s*([^\s]+)", line)
            if voice:
                if in_body:
                    current_voice = voice.group(1).lower()
                    if current_voice == target_voice.lower():
                        saw_target = True
                continue

            if (
                not in_body
                or current_voice != target_voice.lower()
                or not stripped
                or stripped.startswith("%")
            ):
                continue

            # Strip trailing ABC comment text if any.
            music = stripped.split("%", 1)[0]

            # YuE2 output uses ordinary | bar separators. Repeated | characters
            # are treated as one separator here.
            for segment in re.split(r"\|+", music):
                segment = cls._remove_quoted_annotations(segment).strip()
                if not segment:
                    continue

                # Full/multi-measure rests: Z, Z2, Z3, ...
                multi_rest = re.fullmatch(r"Z(\d*)", segment)
                if multi_rest:
                    bars += int(multi_rest.group(1) or "1")
                else:
                    bars += 1

        return bars if saw_target else 0

    @classmethod
    def _count_bars(cls, abc):
        # YuE2 uses V: Ins for the instrumental plan. That is the best duration
        # reference. Fall back to Vocal for unusual scores without an Ins voice.
        bars = cls._count_voice_bars(abc, "ins")
        if bars <= 0:
            bars = cls._count_voice_bars(abc, "vocal")
        return bars

    # -------------------------------------------------------------------------
    # ComfyUI node entry point
    # -------------------------------------------------------------------------

    @classmethod
    def process(cls, abc, padding_seconds):
        if not abc or not abc.strip():
            raise ValueError("H3 Instrumental: ABC input is empty.")

        clean_abc, muted_lines = cls._mute_vocal_voice(abc)

        sections = cls._extract_sections(clean_abc)
        lyrics = "\n".join(f"[{section}]" for section in sections)

        meter_num, meter_den, beat_num, beat_den, bpm = cls._parse_header(clean_abc)
        bars = cls._count_bars(clean_abc)

        if bars <= 0:
            raise ValueError(
                "H3 Instrumental: could not determine the ABC bar count. "
                "Expected a V: Ins or V: Vocal body voice."
            )

        # Measure length expressed in the Q: tempo unit.
        # Example: M:4/4 + Q:1/4=66 -> 4 quarter-note tempo units per bar.
        measure_whole_notes = meter_num / meter_den
        tempo_unit_whole_notes = beat_num / beat_den
        tempo_units_per_measure = measure_whole_notes / tempo_unit_whole_notes
        seconds_per_measure = tempo_units_per_measure * (60.0 / bpm)
        score_seconds = bars * seconds_per_measure

        # max_duration is a CEILING in YuE2, not a forced duration. Round upward
        # to the next whole second so fractional score lengths are never clipped.
        max_duration = math.ceil(score_seconds + float(padding_seconds))
        max_duration = float(max(0.04, min(900.0, max_duration)))

        info = (
            f"{meter_num}/{meter_den}, {bpm:g} BPM | "
            f"{bars} bars | theoretical {score_seconds:.2f}s | "
            f"max_duration {max_duration:.1f}s | "
            f"sections: {' > '.join(sections)} | "
            f"vocal lines muted: {muted_lines}"
        )

        return (
            clean_abc,
            lyrics,
            max_duration,
            float(score_seconds),
            int(bars),
            float(bpm),
            info,
        )
