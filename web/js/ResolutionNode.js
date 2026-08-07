import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "SBL.ResolutionNode",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== "SBL_Resolution") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
            const node = this;

            // Programmatic-change guard used to distinguish UI-driven changes from code-driven ones.
            node.__res_isProgrammatic = false;
            const withProgrammatic = (fn) => {
                node.__res_isProgrammatic = true;
                try { fn(); } finally { node.__res_isProgrammatic = false; }
            };


            const clampDimension = (value, step) =>
                Math.max(step, Math.min(8192, value));

            // Snap a single manually edited dimension to its nearest valid multiple.
            const snapToMultiple = (value, multiple) => {
                const step = Math.max(1, parseInt(multiple, 10) || 1);
                return clampDimension(Math.round(value / step) * step, step);
            };

            const getMultipleCandidates = (value, multiple) => {
                const step = Math.max(1, parseInt(multiple, 10) || 1);
                const floorValue = clampDimension(Math.floor(value / step) * step, step);
                const ceilValue = clampDimension(Math.ceil(value / step) * step, step);
                return [...new Set([floorValue, ceilValue])];
            };

            // Test floor/ceil combinations for both dimensions and select the pair
            // whose aspect ratio is closest to the requested ratio. Dimension change
            // is used only as a tie-breaker when two pairs have the same ratio error.
            const snapDimensionsToClosestRatio = (width, height, multiple, targetRatio = null) => {
                const step = Math.max(1, parseInt(multiple, 10) || 1);
                const wantedRatio = targetRatio && targetRatio > 0
                    ? targetRatio
                    : width / height;
                const widthCandidates = getMultipleCandidates(width, step);
                const heightCandidates = getMultipleCandidates(height, step);
                const epsilon = 1e-12;
                let best = null;

                for (const w of widthCandidates) {
                    for (const h of heightCandidates) {
                        const ratio = w / h;
                        const ratioError = Math.abs(ratio - wantedRatio);
                        const dimensionError =
                            Math.abs(w - width) / Math.max(1, width) +
                            Math.abs(h - height) / Math.max(1, height);

                        if (
                            !best ||
                            ratioError < best.ratioError - epsilon ||
                            (Math.abs(ratioError - best.ratioError) <= epsilon &&
                                dimensionError < best.dimensionError)
                        ) {
                            best = { w, h, ratioError, dimensionError };
                        }
                    }
                }

                return best || {
                    w: snapToMultiple(width, step),
                    h: snapToMultiple(height, step),
                };
            };

            const getWidget = (name) => node.widgets?.find(w => w.name === name);

            const getCurrentMultiple = () => {
                const w = getWidget("multiple_of");
                return w ? w.value : "8";
            };

            const getCurrentStep = () =>
                Math.max(1, parseInt(getCurrentMultiple(), 10) || 1);

            const parsePreset = (presetStr) => {
                // Accept "1920x1080 (label)", "1920 x 1080", and ZiT-style "1024 | 1024×1024 (1:1)"
                // Handles both ASCII 'x'/'X' and Unicode '×' (U+00D7) as separators.
                const m = String(presetStr).match(/(\d+)\s*[xX×]\s*(\d+)/i);
                if (!m) return null;
                return { w: parseInt(m[1], 10), h: parseInt(m[2], 10) };
            };

            const pushDimensionWidget = (triggeringWidget) => {
                if (!triggeringWidget) return;

                const correspondingOutput = node.outputs?.find(output => output.name === triggeringWidget.name);
                if (!correspondingOutput) return;

                if (correspondingOutput.links && correspondingOutput.links.length > 0) {
                    for (const linkId of correspondingOutput.links) {
                        const link = app.graph.links[linkId];
                        if (!link) continue;

                        const targetNode = app.graph.getNodeById(link.target_id);
                        if (!targetNode) continue;

                        const targetInput = targetNode.inputs?.[link.target_slot];
                        if (!targetInput) continue;

                        const foundWidget = targetNode.widgets?.find(w => w.name === targetInput.name);
                        if (!foundWidget) continue;

                        foundWidget.value = triggeringWidget.value;
                        targetNode.setDirtyCanvas(true);

                        if (foundWidget.callback) {
                            try {
                                foundWidget.callback.call(foundWidget, foundWidget.value, app.graph, targetNode);
                            } catch (e) {
                                console.error("Error calling target widget callback:", e);
                            }
                        }
                    }
                }
            };

            const updateDimensionWidget = (triggeringWidget, force = false) => {
                if (!triggeringWidget) return;

                const snapped = snapToMultiple(triggeringWidget.value, getCurrentMultiple());

                if (force || triggeringWidget.value !== snapped) {
                    triggeringWidget.value = snapped;
                    node.setDirtyCanvas(true);
                }

                triggeringWidget.prevValue = triggeringWidget.value;
                pushDimensionWidget(triggeringWidget);
            };

            const updateDimensionsForClosestRatio = (
                widthWidget,
                heightWidget,
                targetRatio = null,
            ) => {
                if (!widthWidget || !heightWidget) return;

                const snapped = snapDimensionsToClosestRatio(
                    widthWidget.value,
                    heightWidget.value,
                    getCurrentMultiple(),
                    targetRatio,
                );

                withProgrammatic(() => {
                    widthWidget.value = snapped.w;
                    heightWidget.value = snapped.h;
                    widthWidget.prevValue = snapped.w;
                    heightWidget.prevValue = snapped.h;
                });

                pushDimensionWidget(widthWidget);
                pushDimensionWidget(heightWidget);
                node.setDirtyCanvas(true);
            };

            // Preset groups and options (UI-side filtering)
            const PRESET_GROUPS = {
                "Custom": ["Custom"],
                "Qwen2512": [
                    "1328x1328 (1:1)", "1664x928 (16:9)", "928x1664 (9:16)",
                    "1472x1104 (4:3)", "1104x1472 (3:4)", "1584x1056 (3:2)", "1056x1584 (2:3)",
                ],
                "ZiT": [
                    "1024x1024 (1:1)", "1152x896 (9:7)", "896x1152 (7:9)",
                    "1152x864 (4:3)", "864x1152 (3:4)", "1248x832 (3:2)",
                    "832x1248 (2:3)", "1280x720 (16:9)", "720x1280 (9:16)",
                    "1344x576 (21:9)", "576x1344 (9:21)",
                    "1280x1280 (1:1)", "1440x1120 (9:7)", "1120x1440 (7:9)",
                    "1472x1104 (4:3)", "1104x1472 (3:4)", "1536x1024 (3:2)",
                    "1024x1536 (2:3)", "1600x896 (16:9)", "896x1600 (9:16)",
                    "1680x720 (21:9)", "720x1680 (9:21)",
                ],
                "1:1 (Square)": [
                    "64x64", "128x128", "192x192", "256x256", "320x320", "384x384", "448x448", 
                    "512x512", "640x640", "768x768", "1024x1024", "1536x1536", "2048x2048", "4096x4096",
                ],
                "4:3 (Classic)": [
                    "320x240", "512x384", "640x480 (VGA)", "800x600 (SVGA)", "1024x768 (XGA)", 
                    "1152x864", "1280x960", "1400x1050", "1600x1200 (UXGA)", "2048x1536 (QXGA)", 
                    "2732x2048 (iPad Pro 12.9)",
                ],
                "3:2 (Photo)": [
                    "384x256", "576x384", "768x512", "1152x768", "1536x1024", "1620x1080", 
                    "2160x1440", "2736x1824 (Surface Pro)", "3000x2000", "3240x2160",
                ],
                "16:9 (Widescreen)": [
                    "512x288", "640x360", "768x432", "854x480 (480p)", "896x504", "960x540 (qHD)", 
                    "1024x576", "1280x720 (720p)", "1600x900 (HD+)", "1920x1080 (1080p)", 
                    "2560x1440 (1440p)", "3840x2160 (4K UHD)", "7680x4320 (8K UHD)",
                ],
                "16:10 (Widescreen+)": [
                    "512x320", "768x480", "1024x640", "1280x800", "1440x900", "1680x1050", 
                    "1920x1200 (WUXGA)", "2560x1600 (WQXGA)", "2880x1800 (Retina 15)", "3840x2400 (WQUXGA)",
                ],
                "21:9 (Ultrawide)": [
                    "1024x438", "1792x768", "2560x1080", "3440x1440", "3840x1600", "5120x2160 (5K2K)",
                ],
                "32:9 (Super Ultrawide)": [
                    "1792x504", "2560x720", "3840x1080", "5120x1440", "7680x2160",
                ],
                "7:4 (Photo Wide)": [
                    "448x256", "896x512", "1344x768", "1792x1024", "2240x1280", "3136x1792",
                ],
                "Phones (Tall)": [
                    "2280x1080 (19:9)", "2400x1080 (20:9)", "2436x1125 (19.5:9 iPhone X/XS)", 
                    "2532x1170 (19.5:9 iPhone 12/13/14)", "2778x1284 (19.5:9 iPhone Pro Max)", 
                    "2960x1440 (18.5:9)",
                ],
                "Cinema (DCI)": [
                    "2048x1080 (1.90:1 DCI 2K Flat)", "2048x858 (2.39:1 DCI 2K Scope)", 
                    "4096x2160 (1.90:1 DCI 4K Flat)", "4096x1716 (2.39:1 DCI 4K Scope)",
                ],
            };

            const applyPreset = (presetWidget) => {
                const widthWidget = getWidget("width");
                const heightWidget = getWidget("height");
                const multipleOfWidget = getWidget("multiple_of");
                if (!presetWidget || !widthWidget || !heightWidget) return;

                if (presetWidget.value === "Custom") return;

                const parsed = parsePreset(presetWidget.value);
                if (!parsed) return;

                // Load the exact preset dimensions before applying multiple-aware snapping.
                withProgrammatic(() => {
                    widthWidget.value = parsed.w;
                    heightWidget.value = parsed.h;
                    widthWidget.prevValue = widthWidget.value;
                    heightWidget.prevValue = heightWidget.value;
                });

                node.__res_targetRatio = parsed.w / parsed.h;

                // Map-based groups (Qwen2512, ZiT) have exact dims — skip snapping,
                // just push the raw values downstream directly.
                const aspectGroupWidget = getWidget("aspect_group");
                const currentGroup = aspectGroupWidget ? aspectGroupWidget.value : "";
                const mapGroups = ["Qwen2512", "ZiT"];

                // Auto-set multiple_of to match the model's native multiple.
                const groupMultiple = { "Qwen2512": "28", "ZiT": "32" };
                if (groupMultiple[currentGroup] && multipleOfWidget) {
                    withProgrammatic(() => {
                        multipleOfWidget.value = groupMultiple[currentGroup];
                    });
                }

                if (mapGroups.includes(currentGroup)) {
                    for (const dimWidget of [widthWidget, heightWidget]) {
                        const correspondingOutput = node.outputs?.find(o => o.name === dimWidget.name);
                        if (!correspondingOutput?.links?.length) continue;
                        for (const linkId of correspondingOutput.links) {
                            const link = app.graph.links[linkId];
                            if (!link) continue;
                            const targetNode = app.graph.getNodeById(link.target_id);
                            if (!targetNode) continue;
                            const targetInput = targetNode.inputs?.[link.target_slot];
                            if (!targetInput) continue;
                            const foundWidget = targetNode.widgets?.find(w => w.name === targetInput.name);
                            if (!foundWidget) continue;
                            foundWidget.value = dimWidget.value;
                            targetNode.setDirtyCanvas(true);
                        }
                    }
                } else {
                    updateDimensionsForClosestRatio(
                        widthWidget,
                        heightWidget,
                        node.__res_targetRatio,
                    );
                }

                node.setDirtyCanvas(true);
            };

            const setPresetOptions = (presetWidget, options, keepValue = false) => {
                if (!presetWidget) return;
                presetWidget.options = presetWidget.options || {};
                presetWidget.options.values = options;

                if (!options.includes(presetWidget.value)) {
                    presetWidget.value = options[0];
                }

                node.computeSize();
                node.setDirtyCanvas(true, true);
            };

            setTimeout(() => {
                const aspectGroupWidget = getWidget("aspect_group");
                const presetWidget = getWidget("preset");
                const multipleOfWidget = getWidget("multiple_of");
                const widthWidget = getWidget("width");
                const heightWidget = getWidget("height");

                const setCustomIfManual = () => {
                    if (node.__res_isProgrammatic) return;

                    let changed = false;

                    if (presetWidget && presetWidget.value !== "Custom") {
                        presetWidget.value = "Custom";
                        changed = true;
                    }
                    if (aspectGroupWidget && aspectGroupWidget.value !== "Custom") {
                        aspectGroupWidget.value = "Custom";
                        changed = true;
                    }

                    if (changed) {
                        node.setDirtyCanvas(true);

                        // Refresh preset options when group is forced to Custom.
                        if (aspectGroupWidget && aspectGroupWidget.callback) {
                            try { aspectGroupWidget.callback.call(aspectGroupWidget, aspectGroupWidget.value); } catch (e) { }
                        }
                    }
                };


                // Add swap button — ZiT-aware: after swap, find the matching ZiT preset if applicable.
                node.addWidget("button", "Swap width↔height", null, () => {
                    if (!widthWidget || !heightWidget) return;

                    // Swap the values first.
                    withProgrammatic(() => {
                        const tmp = widthWidget.value;
                        widthWidget.value = heightWidget.value;
                        heightWidget.value = tmp;
                        widthWidget.prevValue = widthWidget.value;
                        heightWidget.prevValue = heightWidget.value;
                    });
                    node.__res_targetRatio = widthWidget.value / heightWidget.value;

                    // If current group is ZiT or Qwen2512, search for a matching preset by swapped dims.
                    const currentGroup = aspectGroupWidget ? aspectGroupWidget.value : "";
                    if ((currentGroup === "ZiT" || currentGroup === "Qwen2512") && presetWidget) {
                        const swappedW = widthWidget.value;
                        const swappedH = heightWidget.value;
                        const groupOptions = PRESET_GROUPS[currentGroup] || [];
                        const match = groupOptions.find(label => {
                            const p = parsePreset(label);
                            return p && p.w === swappedW && p.h === swappedH;
                        });
                        if (match) {
                            withProgrammatic(() => {
                                presetWidget.value = match;
                                presetWidget.options = presetWidget.options || {};
                                presetWidget.options.values = groupOptions;
                            });
                            // Fire callback inside withProgrammatic so setCustomIfManual
                            // doesn't reset the group back to Custom.
                            withProgrammatic(() => {
                                if (presetWidget.callback) {
                                    try { presetWidget.callback.call(presetWidget, match); } catch (e) { }
                                }
                            });
                            node.setDirtyCanvas(true);
                            return;
                        }
                    }

                    // Fallback: no ZiT match — just push the raw swapped dims downstream.
                    updateDimensionWidget(widthWidget, true);
                    updateDimensionWidget(heightWidget, true);
                    node.setDirtyCanvas(true);
                });

                node.computeSize();
                node.setDirtyCanvas(true, true);

                // A selected preset keeps its ratio when multiple_of changes.
                // Custom dimensions are snapped independently, with no ratio lock.
                if (multipleOfWidget) {
                    const originalCallback = multipleOfWidget.callback;
                    multipleOfWidget.callback = function (value) {
                        if (originalCallback) originalCallback.call(this, value);

                        const preservePresetRatio =
                            presetWidget && presetWidget.value !== "Custom";
                        const currentRatio =
                            widthWidget && heightWidget && heightWidget.value > 0
                                ? widthWidget.value / heightWidget.value
                                : 1;
                        const targetRatio = node.__res_targetRatio || currentRatio;

                        // A manual multiple change switches the node to Custom.
                        setCustomIfManual();

                        if (preservePresetRatio) {
                            updateDimensionsForClosestRatio(
                                widthWidget,
                                heightWidget,
                                targetRatio,
                            );
                        } else {
                            updateDimensionWidget(widthWidget, true);
                            updateDimensionWidget(heightWidget, true);
                        }
                    };
                }

                // Manual text entry snaps only the edited dimension. Arrow clicks are
                // handled explicitly as +/- multiple_of and then switch to Custom.
                const hookDim = (dimWidget) => {
                    if (!dimWidget) return;

                    // Keep ComfyUI's native INT normalization at one-unit precision.
                    // Using multiple_of as step2 also changes text-entry rounding and
                    // applies a min-value offset, which corrupts valid values such as 960.
                    dimWidget.options = dimWidget.options || {};
                    dimWidget.options.step = 10;
                    dimWidget.options.step2 = 1;

                    const originalCallback = dimWidget.callback;
                    dimWidget.callback = function (value, canvas, callbackNode, pos, event) {
                        // Arrow clicks already produce an exact +/- multiple_of value.
                        // Do not run the normal text-entry snap or any ratio logic here.
                        if (node.__res_arrowEdit) {
                            const exactValue = Math.max(
                                16,
                                Math.min(8192, Math.round(Number(value))),
                            );

                            if (this.value !== exactValue) {
                                this.value = exactValue;
                            }

                            setCustomIfManual();
                            this.prevValue = exactValue;
                            pushDimensionWidget(this);
                            node.setDirtyCanvas(true);

                            if (widthWidget && heightWidget && heightWidget.value > 0) {
                                node.__res_targetRatio = widthWidget.value / heightWidget.value;
                            }
                            return;
                        }

                        if (originalCallback) {
                            originalCallback.call(
                                this,
                                value,
                                canvas,
                                callbackNode,
                                pos,
                                event,
                            );
                        }

                        // Manual text entry leaves preset mode and snaps only the
                        // dimension that was edited to its nearest valid multiple.
                        setCustomIfManual();
                        updateDimensionWidget(this);

                        if (widthWidget && heightWidget && heightWidget.value > 0) {
                            node.__res_targetRatio = widthWidget.value / heightWidget.value;
                        }
                    };

                    const originalOnClick = dimWidget.onClick;
                    if (typeof originalOnClick === "function") {
                        dimWidget.onClick = function (eventOptions) {
                            const event = eventOptions?.e;
                            const eventNode = eventOptions?.node || node;
                            const widgetWidth =
                                this.width || eventNode?.size?.[0] || eventNode?.width;

                            const isArrowClick =
                                event &&
                                typeof event.canvasX === "number" &&
                                eventNode?.pos &&
                                widgetWidth &&
                                (() => {
                                    const x = event.canvasX - eventNode.pos[0];
                                    return x < 40 || x > widgetWidth - 40;
                                })();

                            if (!isArrowClick) {
                                return originalOnClick.call(this, eventOptions);
                            }

                            // Let ComfyUI's own NumberWidget determine left versus right
                            // and update the value. Supply multiple_of only during this
                            // arrow click, then restore one-unit precision immediately.
                            const previousStep2 = this.options?.step2;
                            this.options = this.options || {};
                            this.options.step2 = getCurrentStep();
                            node.__res_arrowEdit = true;

                            try {
                                return originalOnClick.call(this, eventOptions);
                            } finally {
                                this.options.step2 = previousStep2 ?? 1;
                                node.__res_arrowEdit = false;
                            }
                        };
                    }
                };

                hookDim(widthWidget);
                hookDim(heightWidget);

                if (widthWidget) widthWidget.prevValue = widthWidget.value;
                if (heightWidget) heightWidget.prevValue = heightWidget.value;
                if (widthWidget && heightWidget && heightWidget.value > 0) {
                    node.__res_targetRatio = widthWidget.value / heightWidget.value;
                }

                // Initialize preset options based on group
                if (aspectGroupWidget && presetWidget) {
                    const initOptions = PRESET_GROUPS[aspectGroupWidget.value] || ["Custom"];
                    setPresetOptions(presetWidget, initOptions, false);
                }

                // Group change -> filter preset dropdown
                if (aspectGroupWidget && presetWidget) {
                    const originalGroupCb = aspectGroupWidget.callback;
                    aspectGroupWidget.callback = function (value) {
                        if (originalGroupCb) originalGroupCb.call(this, value);
                        const options = PRESET_GROUPS[value] || ["Custom"];
                        setPresetOptions(presetWidget, options, false);
                        if (presetWidget.value !== "Custom") {
                            applyPreset(presetWidget);
                        }
                    };
                }

                // Preset change -> set width/height and preserve the closest valid ratio
                if (presetWidget) {
                    const originalPresetCb = presetWidget.callback;
                    presetWidget.callback = function (value) {
                        if (originalPresetCb) originalPresetCb.call(this, value);
                        applyPreset(this);
                    };
                }

            }, 100);

            return r;
        };
    }
});