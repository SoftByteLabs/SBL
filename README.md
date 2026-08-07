# SBL

SBL is a collection of utility custom nodes for ComfyUI.

## Included nodes

- **Global Prompt (Pos/Neg)** - Outputs reusable positive and negative prompt strings.
- **Resolution** - Resolution presets, aspect-ratio groups, custom dimensions, and multiple-of snapping.
- **Math Evaluator** - Evaluates simple mathematical expressions with float and integer outputs.
- **Seed** - Outputs a seed and ComfyUI noise object, with a frontend randomize button.
- **Qwen 2512 t2i resolutions** - Preset image resolutions for Qwen image generation workflows.
- **ZiT t2i resolutions** - Preset image resolutions for ZiT image generation workflows.
- **Math Scratchpad** - Interactive Python math scratchpad with displayed output.

All nodes appear under the **SBL** category in ComfyUI.

## Installation

Install through ComfyUI Manager once the package is published to the Comfy Registry, or clone the repository into your ComfyUI `custom_nodes` directory.

Restart ComfyUI after installation.

## Dependencies

SBL has no additional third-party Python dependencies beyond the packages included with ComfyUI.

## Security note

The **Math Scratchpad** intentionally executes Python code entered into the node. Use it only in a trusted ComfyUI environment and do not expose an instance containing this node to untrusted users.
