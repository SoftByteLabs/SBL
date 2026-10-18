"""Prepare native two-voice YuE2 ABC scores for instrumental synthesis.

Supported notation covers YuE2's usual monophonic note/rest, chord-label,
bar, tie, meter and key vocabulary. Unsupported constructs fail explicitly so
that a score is never silently changed into a different composition.
"""

import math
import re
from fractions import Fraction


class YuE2Instrumental:
    DESCRIPTION = (
        "Transfer pitched Vocal notes to YuE2's Ins melody voice, preserving timing "
        "and chord symbols. Vocal takes priority wherever the two melodies overlap. "
        "Empty ABC returns zero numeric outputs and empty strings."
    )
    OUTPUT_TOOLTIPS = (
        "ABC with the Vocal melody transferred to Ins and the Vocal part replaced by rests; chord symbols are preserved.",
        "Section tags read from ABC comments, without sung words.",
        "Suggested maximum duration (seconds), including optional padding; not an exact generation length.",
        "Theoretical duration of the ABC score in seconds.",
        "Number of measures in the two-voice score.",
        "Tempo from the Q: field (beats per minute).",
        "Transfer summary, including the number of Vocal notes and overlapping Ins events.",
    )
    SECTION_ALIASES = {"prechorus": "pre-chorus", "pre chorus": "pre-chorus", "pre_chorus": "pre-chorus"}
    KNOWN_SECTIONS = {
        "intro", "verse", "pre-chorus", "chorus", "bridge", "interlude",
        "instrumental", "breakdown", "solo", "hook", "refrain", "outro",
    }
    # Native YuE2 uses a limited ABC dialect. Keep spellings exact in time and pitch.
    NOTE = re.compile(r"(?P<acc>\^\^|__|\^|_|=)?(?P<note>[A-Ga-gz])(?P<oct>[,']*)(?P<dur>\d*(?:/\d*)?)(?P<tie>-?)")
    BAR_REST = re.compile(r"Z(\d*)$")
    DURATIONS = (48, 32, 24, 16, 12, 8, 6, 4, 3, 2, 1)
    NATURAL = dict(zip("CDEFGAB", (0, 2, 4, 5, 7, 9, 11)))
    MAJOR_KEYS = dict(zip(
        ("Cb", "Gb", "Db", "Ab", "Eb", "Bb", "F", "C", "G", "D", "A", "E", "B", "F#", "C#"),
        range(-7, 8),
    ))
    MINOR_KEYS = dict(zip(
        ("Abm", "Ebm", "Bbm", "Fm", "Cm", "Gm", "Dm", "Am", "Em", "Bm", "F#m", "C#m", "G#m", "D#m", "A#m"),
        range(-7, 8),
    ))

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "abc": ("STRING", {"multiline": True, "forceInput": True,
                "tooltip": "Connect a native YuE2 two-voice ABC score. Transfers the Vocal melody to Ins, keeping pitches, note timing and chord symbols. Empty or whitespace-only input returns zero numbers and empty strings."}),
            "padding_seconds": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 30.0, "step": 0.1,
                "tooltip": "Add 0–30 seconds to the calculated score length before rounding up the recommended maximum duration."}),
        }}

    RETURN_TYPES = ("STRING", "STRING", "FLOAT", "FLOAT", "INT", "FLOAT", "STRING")
    RETURN_NAMES = ("abc", "lyrics", "max_duration", "score_seconds", "bars", "bpm", "info")
    FUNCTION = "process"
    CATEGORY = "SBL"

    @classmethod
    def _extract_sections(cls, abc):
        sections = []
        for line in abc.splitlines():
            match = re.fullmatch(r"\s*%\s*([A-Za-z][A-Za-z _-]*)\s*", line)
            if match:
                name = re.sub(r"\s+", " ", match.group(1).strip().lower())
                name = cls.SECTION_ALIASES.get(name, name)
                if name in cls.KNOWN_SECTIONS:
                    sections.append(name)
        return sections or ["intro", "outro"]

    @classmethod
    def _key_signature(cls, key):
        if key not in cls.MAJOR_KEYS and key not in cls.MINOR_KEYS:
            raise ValueError(f"YuE2 Instrumental: unsupported ABC key {key!r}.")
        count = {**cls.MAJOR_KEYS, **cls.MINOR_KEYS}[key]
        accidentals = {letter: 0 for letter in cls.NATURAL}
        for letter in ("FCGDAEB" if count > 0 else "BEADGCF")[:abs(count)]:
            accidentals[letter] = 1 if count > 0 else -1
        return accidentals

    @staticmethod
    def _units(length_text):
        if not length_text:
            return Fraction(1)
        if "/" not in length_text:
            return Fraction(int(length_text))
        numerator, denominator = length_text.split("/", 1)
        denominator = int(denominator) if denominator else 2
        if denominator <= 0:
            raise ValueError("YuE2 Instrumental: zero note duration denominator.")
        return Fraction(int(numerator or "1"), denominator)

    @staticmethod
    def _bar_units(meter, base):
        result = Fraction(meter[0] * base, meter[1])
        if result.denominator != 1 or result <= 0:
            raise ValueError("YuE2 Instrumental: L: must divide each M: measure exactly.")
        return result

    @classmethod
    def _parse_bar(cls, music, start, length, key, pending):
        """Parse measured events with precise absolute L: units and MIDI pitches."""
        notes, chords = [], []
        if cls.BAR_REST.fullmatch(music):
            if pending is not None:
                raise ValueError("YuE2 Instrumental: tied note runs into a rest.")
            return notes, chords, pending
        cursor, offset, local = 0, Fraction(0), {}
        while cursor < len(music):
            if music[cursor].isspace():
                cursor += 1
                continue
            if music[cursor] == '"':
                match = re.match(r'"(?:\\.|[^"\\])*"', music[cursor:])
                if not match:
                    raise ValueError("YuE2 Instrumental: unterminated chord symbol.")
                chords.append((start + offset, match.group()))
                cursor += len(match.group())
                continue
            if music.startswith("[K:", cursor):
                raise ValueError("YuE2 Instrumental: inline key changes aren't supported; place K: at a measure boundary.")
            match = cls.NOTE.match(music, cursor)
            if not match:
                raise ValueError(f"YuE2 Instrumental: unsupported ABC notation near {music[cursor:cursor+16]!r}.")
            cursor = match.end()
            note, octaves, accidental, tied = (match.group(k) for k in ("note", "oct", "acc", "tie"))
            duration = cls._units(match.group("dur"))
            if duration <= 0 or offset + duration > length:
                raise ValueError("YuE2 Instrumental: note lengths exceed the measure.")
            if note == "z":
                if accidental or octaves or tied or pending is not None:
                    raise ValueError("YuE2 Instrumental: invalid rest or unresolved tie.")
            else:
                if "," in octaves and "'" in octaves:
                    raise ValueError("YuE2 Instrumental: invalid octave marks.")
                letter = note.upper()
                natural = 60 + cls.NATURAL[letter] + (12 if note.islower() else 0)
                natural += 12 * (octaves.count("'") - octaves.count(","))
                if accidental:
                    local[letter] = {"=": 0, "^": 1, "^^": 2, "_": -1, "__": -2}[accidental]
                alter = local.get(letter, cls._key_signature(key)[letter])
                pitch = natural + alter
                # ABC ties carry an altered pitch over a barline even when the
                # continuation omits its accidental (e.g. ^F2-|F2).
                if pending is not None and accidental is None:
                    old_pitch, old_event = pending
                    old_base = re.sub(r"^(?:\^\^|__|\^|_|=)", "", old_event[2])
                    if old_base == note + octaves:
                        pitch = old_pitch
                        alter = pitch - natural
                if not 0 <= pitch <= 127:
                    raise ValueError("YuE2 Instrumental: note pitch outside MIDI range.")
                explicit = {0: "=", 1: "^", 2: "^^", -1: "_", -2: "__"}[alter] + note + octaves
                if pending is not None:
                    former, old_event = pending
                    if pitch != former or old_event[0] + old_event[1] != start + offset:
                        raise ValueError("YuE2 Instrumental: tied notes change pitch or onset.")
                    old_event[1] += duration
                else:
                    old_event = [start + offset, duration, explicit, pitch]
                    notes.append(old_event)
                pending = (pitch, old_event) if tied else None
            offset += duration
        if offset != length:
            raise ValueError(f"YuE2 Instrumental: a measure has {offset} units but requires {length}.")
        return notes, chords, pending

    @classmethod
    def _read_score(cls, abc):
        lines = abc.splitlines()
        headers = {}
        header_end = None
        for index, line in enumerate(lines):
            match = re.match(r"^\s*([A-Za-z]):\s*(.*?)\s*$", line)
            if match and match.group(1) in ("M", "L", "Q", "K"):
                headers[match.group(1)] = match.group(2)
                if match.group(1) == "K":
                    header_end = index
                    break
        if header_end is None or any(k not in headers for k in ("M", "L", "Q", "K")):
            raise ValueError("YuE2 Instrumental: missing M:, L:, Q: or K: in the ABC header.")
        meter_match = re.fullmatch(r"(\d+)\s*/\s*(\d+)", headers["M"])
        unit_match = re.fullmatch(r"1\s*/\s*(\d+)", headers["L"])
        tempo_match = re.fullmatch(r"(?:(\d+)\s*/\s*(\d+)\s*=\s*)?(\d+(?:\.\d+)?)", headers["Q"])
        if not meter_match or not unit_match or not tempo_match:
            raise ValueError("YuE2 Instrumental: unsupported ABC meter, note unit, or tempo.")
        meter = tuple(map(int, meter_match.groups()))
        base = int(unit_match.group(1))
        q_unit = Fraction(int(tempo_match.group(1) or 1), int(tempo_match.group(2) or 4))
        bpm = float(tempo_match.group(3))
        if min(*meter, base) <= 0 or q_unit <= 0 or bpm <= 0:
            raise ValueError("YuE2 Instrumental: meter, unit and tempo must be positive.")
        cls._key_signature(headers["K"])
        voice_state = {
            name: {"meter": meter, "key": headers["K"], "at": Fraction(0), "bars": [],
                   "notes": [], "chords": [], "pending": None} for name in ("vocal", "ins")
        }
        records = []
        active = None
        for index in range(header_end + 1, len(lines)):
            line = lines[index]
            stripped = line.strip()
            if not stripped or stripped.startswith("%"):
                continue
            match = re.fullmatch(r"V:\s*(Vocal|Ins)\s*", stripped, re.I)
            if match:
                active = match.group(1).lower()
                continue
            if re.match(r"^[A-Za-z]:", stripped):
                key, val = stripped[0], stripped[2:].strip()
                if active and key == "M":
                    m = re.fullmatch(r"(\d+)\s*/\s*(\d+)", val)
                    if not m:
                        raise ValueError("YuE2 Instrumental: unsupported meter change.")
                    voice_state[active]["meter"] = tuple(map(int, m.groups()))
                elif active and key == "K":
                    cls._key_signature(val)
                    voice_state[active]["key"] = val
                else:
                    raise ValueError(f"YuE2 Instrumental: unsupported body field {stripped[:2]}.")
                continue
            if active is None:
                raise ValueError("YuE2 Instrumental: expected V: Vocal or V: Ins before music.")
            code, marker, comment = line.partition("%")
            code = code.strip()
            if not code.endswith("|"):
                raise ValueError("YuE2 Instrumental: each voice music line must end in |.")
            state = voice_state[active]
            line_bars = []
            for text in code[:-1].split("|"):
                text = text.strip()
                if not text:
                    raise ValueError("YuE2 Instrumental: empty ABC measure.")
                rest = cls.BAR_REST.fullmatch(text)
                count = int(rest.group(1) or 1) if rest else 1
                if count <= 0 or count > 1000:
                    raise ValueError("YuE2 Instrumental: invalid multi-measure rest.")
                for _ in range(count):
                    at = state["at"]
                    width = cls._bar_units(state["meter"], base)
                    bar_info = (at, width, state["meter"], state["key"])
                    state["bars"].append(bar_info)
                    line_bars.append(len(state["bars"]) - 1)
                    if not rest:
                        notes, chords, state["pending"] = cls._parse_bar(text, at, width, state["key"], state["pending"])
                        state["notes"].extend(notes)
                        state["chords"].extend(chords)
                    elif state["pending"] is not None:
                        raise ValueError("YuE2 Instrumental: note tie enters a multi-measure rest.")
                    state["at"] += width
            records.append((index, active, line_bars, comment if marker else None))
        vocal, ins = voice_state["vocal"], voice_state["ins"]
        if not vocal["bars"] or vocal["bars"] != ins["bars"]:
            raise ValueError("YuE2 Instrumental: Vocal and Ins must have matching measures, meter and key changes.")
        if vocal["pending"] is not None or ins["pending"] is not None:
            raise ValueError("YuE2 Instrumental: unfinished tied note at the end of a voice.")
        if ins["chords"]:
            raise ValueError("YuE2 Instrumental: chord symbols belong in Vocal, not Ins.")
        if not (vocal["notes"] or ins["notes"]):
            raise ValueError("YuE2 Instrumental: score contains no pitched notes.")
        if len(vocal["bars"]) > 1000:
            raise ValueError("YuE2 Instrumental: score is too long to convert safely.")
        return lines, records, vocal, ins, base, bpm, q_unit

    @classmethod
    def _render_length(cls, amount, symbol, tied_after=False):
        """Use YuE2's supported duration tokens, splitting long events into ties."""
        if amount.denominator != 1 or amount <= 0:
            raise ValueError("YuE2 Instrumental: fractional note-unit timing needs manual ABC adjustment.")
        remaining = int(amount)
        parts = []
        while remaining:
            length = next(n for n in cls.DURATIONS if n <= remaining)
            remaining -= length
            parts.append(symbol + (str(length) if length != 1 else "") + ("-" if symbol != "z" and (remaining or tied_after) else ""))
        return "".join(parts)

    @classmethod
    def _render_bar(cls, start, width, events, chord_events=None):
        end = start + width
        notes = sorted((max(a, start), min(a + d, end), spelling, a + d > end)
                       for a, d, spelling, _ in events if a < end and a + d > start)
        chords = sorted((at, symbol) for at, symbol in (chord_events or []) if start <= at < end)
        if not notes and not chords:
            return "Z"
        points = {start, end}
        for a, b, _, _ in notes:
            points.update((a, b))
        for at, _ in chords:
            points.add(at)
        boundaries = sorted(points)
        current_chords = {}
        for at, name in chords:
            current_chords.setdefault(at, []).append(name)
        result = []
        for a, b in zip(boundaries, boundaries[1:]):
            result.extend(current_chords.get(a, []))
            note = next(((n_a, n_b, name, longer) for n_a, n_b, name, longer in notes if n_a <= a < n_b), None)
            if note is None:
                result.append(cls._render_length(b - a, "z"))
            else:
                _, n_b, spelling, longer = note
                result.append(cls._render_length(b - a, spelling, tied_after=(b < n_b or (b == n_b and longer))))
        return "".join(result)

    @classmethod
    def _transfer(cls, abc):
        lines, records, vocal, ins, base, bpm, q_unit = cls._read_score(abc)
        # Instrumental YuE2 scores commonly have no pitched Vocal notes, only
        # rests and chord symbols.  They are already suitable for instrumental
        # generation.  Return their ABC byte-for-byte: reserializing even an
        # equivalent melody would replace native pitches with explicit
        # accidentals, which can unnecessarily perturb score conditioning.
        if not vocal["notes"]:
            total_whole_notes = vocal["at"] / base
            seconds = float(total_whole_notes / q_unit) * 60.0 / bpm
            return abc, len(vocal["bars"]), bpm, seconds, 0, 0

        occupied = [(at, at + duration) for at, duration, _, _ in vocal["notes"]]
        merged = list(vocal["notes"])
        affected = 0
        for start, duration, spelling, pitch in ins["notes"]:
            pieces = [(start, start + duration)]
            for va, vb in occupied:
                remaining = []
                for pa, pb in pieces:
                    if vb <= pa or va >= pb:
                        remaining.append((pa, pb))
                    else:
                        if pa < va:
                            remaining.append((pa, va))
                        if vb < pb:
                            remaining.append((vb, pb))
                pieces = remaining
            if pieces != [(start, start + duration)]:
                affected += 1
            merged.extend([a, b - a, spelling, pitch] for a, b in pieces if b > a)
        merged.sort(key=lambda n: n[0])
        for line_index, active, indices, comment in records:
            render = []
            for bar_idx in indices:
                at, width, _, _ = vocal["bars"][bar_idx]
                if active == "vocal":
                    render.append(cls._render_bar(at, width, [], vocal["chords"]))
                else:
                    render.append(cls._render_bar(at, width, merged))
            # Keep the native compressed notation for adjacent entirely silent measures.
            compressed = []
            pos = 0
            while pos < len(render):
                if render[pos] != "Z":
                    compressed.append(render[pos]); pos += 1
                else:
                    stop = pos + 1
                    while stop < len(render) and render[stop] == "Z":
                        stop += 1
                    count = stop - pos
                    compressed.append("Z" + (str(count) if count > 1 else ""))
                    pos = stop
            lines[line_index] = "|".join(compressed) + "|" + ((" %" + comment) if comment is not None else "")
        result = "\n".join(lines) + ("\n" if abc.endswith("\n") else "")
        # Verify that the finished score has exactly the intended sounding notes.
        _, _, vocal_after, ins_after, _, _, _ = cls._read_score(result)
        actual = [(a, d, p) for a, d, _, p in ins_after["notes"]]
        expected = [(a, d, p) for a, d, _, p in merged]
        if vocal_after["notes"] or actual != expected or vocal_after["chords"] != vocal["chords"]:
            raise ValueError("YuE2 Instrumental: converted score failed note or chord verification.")
        total_whole_notes = vocal["at"] / base
        seconds = float(total_whole_notes / q_unit) * 60.0 / bpm
        return result, len(vocal["bars"]), bpm, seconds, len(vocal["notes"]), affected

    @classmethod
    def process(cls, abc, padding_seconds):
        # An empty upstream Generate ABC result is a valid no-op.  Keep all
        # output types consistent with RETURN_TYPES and ignore padding when
        # there is no score to measure.
        if not abc or not abc.strip():
            return "", "", 0.0, 0.0, 0, 0.0, ""
        instrumental, bars, bpm, score_seconds, moved, affected = cls._transfer(abc)
        sections = cls._extract_sections(instrumental)
        lyrics = "\n".join(f"[{section}]" for section in sections)
        max_duration = float(max(0.04, min(900.0, math.ceil(score_seconds + float(padding_seconds)))))
        info = (
            f"{bpm:g} BPM | {bars} bars | theoretical {score_seconds:.2f}s | "
            f"max_duration {max_duration:.1f}s | sections: {' > '.join(sections)} | "
            f"Vocal notes transferred: {moved} | overlapping Ins notes reduced: {affected}"
        )
        return instrumental, lyrics, max_duration, float(score_seconds), int(bars), float(bpm), info
