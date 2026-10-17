# SBL

SBL is a collection of utility custom nodes for ComfyUI. Find all six nodes in the **SBL** category. Each node includes a description, and its fields show help text when hovered over in a current ComfyUI frontend.

## Included nodes

### Global Prompt (Pos/Neg)

Keep positive and negative text prompts together, then connect either string output to other text or conditioning nodes. The fields accept multiline prompts. The node passes the entered text through unchanged and is useful when several parts of a workflow share the same wording.

**Fields:** `positive` is the positive prompt text; `negative` is the negative prompt text. **Outputs:** `positive` and `negative` strings.

### Resolution

Pick common image dimensions from aspect-ratio groups (square, classic, photo, widescreen, ultrawide, phone and cinema) or enter custom width and height. Dimensions are snapped to `multiple_of`, which helps match the grid requirements of image and video models. The **Swap width↔height** button exchanges the orientation.

**Fields:** `aspect_group` filters the available `preset` choices. `width` and `height` are selected dimensions before any megapixel limit. `multiple_of` determines pixel-grid snapping. `max_megapixels` is the maximum output area, in millions of pixels. Use **0** for no cap.

If the snapped resolution already fits the megapixel limit, the output stays unchanged. Otherwise, the node scales down to an area as close to the limit as possible while keeping the original aspect ratio as closely as the pixel grid permits. It never upscales to reach the limit. The selected width and height stay intact when changing the cap, and the cap field previews the effective output dimensions. For very small caps, a 1-pixel grid may be used if the selected multiple can't fit below the limit.

**Outputs:** effective `width` and `height` as integers.

### Math Evaluator

Evaluate mathematical expressions and short Python-style programs using a restricted interpreter. Assign results to `a` and `b`. Connect optional numeric sockets `w` and `x` (floats) or `y` and `z` (integers); unconnected values default to zero. Common mathematical functions are available, including `math`, `statistics` and `cmath` operations.

**Fields:** `expressions` contains the program; optional sockets `w`, `x`, `y`, `z` provide inputs. **Outputs:** `a` and `b` as floats, and `a` and `b` as integers (four total outputs). Evaluation failures produce zero outputs and log an error.

Example (also the node's new default):

```python
a = w + x
b = y + z
```

The four optional sockets are Python-declared inputs and remain disconnected unless you connect a value. If a division is needed, use a nonzero divisor.

### Seed

Produce a numeric seed and a compatible ComfyUI random-noise object. Enter `seed` manually for reproducible sampling, or click **🎲 Randomize** to generate another seed.

**Field:** `seed` is a nonnegative integer from 0 through **9,007,199,254,740,991** (`2^53 - 1`), the exact-integer range supported by JavaScript. This prevents silent rounding of extremely large seeds in ComfyUI's frontend. The Randomize button continues to choose seeds below `2^50`. **Outputs:** integer `seed` and a `NOISE` object using that seed.

### Math Scratchpad

An interactive, resizable scratchpad for calculations. Type restricted Python-style expressions, variables, math calls, loops or `print()` statements into the upper area, then click **⚡ Evaluate**. Results and errors appear in the read-only area below. A standalone expression such as `2 * 24 + 1` now displays its answer without `print()`. Assignments still don't print unless requested. Drag the divider to change the amount of space available for results. This node is a utility panel and doesn't provide workflow output sockets or act as a queue output node. Clicking Evaluate runs it independently of workflow generation.

**Field:** `expressions` is the editable code area. **Controls:** Evaluate runs the code; the divider resizes the display; the lower field shows results.

### YuE2 Instrumental Prep

Prepare a YuE2 ABC music score for **instrumental** generation. The node now **transfers every pitched Vocal note into Ins**, preserving pitch, onset and duration, and leaves rests (plus any chord symbols) in Vocal. Existing Ins melody notes are preserved wherever they don't overlap Vocal notes. When the voices overlap, Vocal takes precedence and the overlapping portion of Ins is removed so the result remains monophonic. The node validates the finished score to prevent silent melody or chord changes. **When the Vocal voice already contains only rests and chord symbols, the ABC is returned exactly as supplied**, without rewriting any Ins notes or accidentals. Duration, section Lyrics and diagnostic outputs are still calculated as usual.

It supports YuE2's usual two-voice ABC notation, including standard note lengths, ties, simple key/meter changes, quoted chord symbols, multi-measure rests and section comments. Unsupported constructs, such as tuplets or simultaneous note chords, produce an explicit error rather than a misleading conversion. Use the original score if you need to make a manual adjustment. It also reads recognized standalone ABC section comments such as `% intro`, `% verse` and `% chorus` to create section-only Lyrics tags without sung words.

The node estimates score length from the ABC time signature, tempo and bar count, then generates an upward-rounded maximum duration that includes any requested padding. The generated maximum is a **ceiling**, not a promise of exact song length.

**Fields:** `abc` accepts an incoming ABC string; `padding_seconds` adds 0 to 30 seconds to the recommended ceiling. The `info` output reports Vocal notes transferred and Ins notes affected by overlaps. **Outputs:** `abc` (instrumental-ready score), `lyrics` (section tags), `max_duration` (rounded duration ceiling), `score_seconds` (theoretical duration), `bars`, `bpm` and `info` (diagnostics). Connect `abc`, `lyrics` and `max_duration` to the corresponding YuE2 generation inputs.

## Installation

Copy the entire `SBL` folder into `ComfyUI/custom_nodes/` and restart ComfyUI. Alternatively, use ComfyUI Manager if your installation supports SBL. Do not place the node files directly in `custom_nodes` without the enclosing `SBL` folder.

An old workflow using a retired, model-specific resolution node may display a missing-node warning. Replace that node with **SBL → Resolution** and reconnect its width and height outputs.

## Dependencies

SBL uses the Python standard library and components bundled with ComfyUI. It has no separate third-party Python dependencies. Recent ComfyUI frontend versions support hover descriptions supplied through each field's `tooltip` metadata.

## Math safety

Math Evaluator and Math Scratchpad run mathematical Python-style programs in a restricted AST interpreter instead of using unrestricted Python `exec()` or `eval()`. This prevents arbitrary code execution, imports outside the allowed math modules, filesystem operations, subprocess calls and object introspection. Execution and output size limits also apply, including checks on integer, Fraction and Decimal sizes, exponentiation, bit shifts, and formatted-string widths. These limits are resource safeguards, not a general-purpose sandbox guarantee for exposing ComfyUI to untrusted users on the public internet.

## License

Copyright © 2026 SoftByteLabs.

SBL is free software licensed under the **GNU General Public License v3.0 or later**. You may use, study, modify and redistribute SBL subject to the GPL terms. See [LICENSE](LICENSE) for details.
