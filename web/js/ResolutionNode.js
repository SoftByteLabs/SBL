import { app } from "../../scripts/app.js";

// Expose Swap as a live, UI-only button on a Subgraph when at least one
// input belonging to an SBL Resolution node has been promoted. ComfyUI's
// projected subgraph widgets are the execution-time values: writing only
// to an inner Resolution widget would not update an exposed field.
const RESOLUTION_TYPE = "SBL_Resolution";
const SWAP_LABEL = "Swap width↔height";
const RESOLUTION_FIELDS = new Set([
    "aspect_group", "preset", "width", "height", "multiple_of", "max_megapixels",
]);

// Promoted Subgraph widgets are store-backed projections. ComfyUI currently
// copies widget options to the projection but not the source widget's tooltip.
// Keep fallbacks for restored workflows whose original node has not yet set up.
const RESOLUTION_TOOLTIPS = {
    aspect_group: "Select a family of aspect ratios to filter the preset list. Choose Custom for manual sizes.",
    preset: "Pick a named width × height preset, or Custom to enter your own dimensions.",
    width: "Selected width in pixels before the megapixel cap. Changing it manually switches to Custom.",
    height: "Selected height in pixels before the megapixel cap. Changing it manually switches to Custom.",
    multiple_of: "Snap dimensions to a pixel multiple (often 8, 16, 32, or 64). The MP-capped output also follows this grid when possible.",
    max_megapixels: "Maximum output area in millions of pixels. 0 disables the cap; smaller images are unchanged. Oversized images are downscaled while preserving aspect ratio as closely as possible.",
};

function restoreProjectedTooltip(projected, inner, field) {
    const source = resolutionWidget(inner, field);
    const tooltip = source?.tooltip || source?.options?.tooltip || RESOLUTION_TOOLTIPS[field];
    if (!tooltip) return;
    if (projected.tooltip !== tooltip) projected.tooltip = tooltip;
    // A projected widget's options are stored reactively by ComfyUI. Do not
    // mutate that store from the host.widgets getter during canvas rendering.
}

// Read projected values directly from the host input's cached projection, not
// host.widgets. A widgets getter can be reentrant if consulted from itself.
function resolutionPreview(group) {
    const values = {};
    for (const [field, input] of group.fields) {
        if (input._widget && input._widget.value !== undefined) {
            values[field] = input._widget.value;
        }
    }
    return group.inner.__sblResolutionPreview?.(values) ?? null;
}

function restoreProjectedMaxMpLabel(projected, group) {
    projected.__sblPreviewGroup = group;
    if (projected.__sblDynamicMaxMpLabel) return;
    // Override only this projected object's display label. Do not change the
    // input's stored label, since it would be stale after a reload or edit.
    const originalLabel = Object.getOwnPropertyDescriptor(projected, "label");
    if (originalLabel && !originalLabel.configurable) return;
    Object.defineProperty(projected, "label", {
        configurable: true,
        enumerable: true,
        get() {
            const preview = resolutionPreview(this.__sblPreviewGroup);
            if (!preview) return originalLabel?.get?.call(this) ?? "Max MP";
            return preview.capped ? `Max MP (${preview.w}×${preview.h})` : "Max MP";
        },
        set(value) { originalLabel?.set?.call(this, value); },
    });
    Object.defineProperty(projected, "__sblDynamicMaxMpLabel", { value: true, configurable: true });
}

function decorateResolutionFields(widgets, state) {
    for (const group of state.groups ?? []) {
        for (const [field, input] of group.fields) {
            // No widgetId getters here: a source widget can calculate its ID
            // by accessing host.widgets and reentering this decoration.
            const projected = widgets.find(widget => resolutionWidgetMatchesInput(widget, input));
            if (!projected) continue;
            restoreProjectedTooltip(projected, group.inner, field);
            if (field === "max_megapixels") restoreProjectedMaxMpLabel(projected, group);
        }
    }
}

function resolutionWidget(node, name) {
    return node.widgets?.find((widget) => widget.name === name);
}

function subgraphTargetFields(host, input, depth = 0) {
    if (!host.subgraph || !input?._subgraphSlot || depth > 12) return [];
    const result = [];
    for (const linkId of input._subgraphSlot.linkIds ?? []) {
        const graph = host.subgraph;
        const link = graph.getLink?.(linkId) ?? graph.links?.get?.(linkId) ?? graph.links?.[linkId];
        if (!link) continue;
        const target = graph.getNodeById?.(link.target_id);
        const targetInput = target?.inputs?.[link.target_slot];
        if (!target || !targetInput) continue;
        if (target.type === RESOLUTION_TYPE && RESOLUTION_FIELDS.has(targetInput.widget?.name)) {
            result.push({ inner: target, field: targetInput.widget.name });
        } else if (target.subgraph) {
            result.push(...subgraphTargetFields(target, targetInput, depth + 1));
        }
    }
    return result;
}

function promotedResolutions(host) {
    const groups = new Map();
    for (const input of host.inputs ?? []) {
        if (!input._subgraphSlot) continue;
        for (const { inner, field } of subgraphTargetFields(host, input)) {
            let group = groups.get(inner);
            if (!group) {
                group = { inner, lastInput: input, fields: new Map() };
                groups.set(inner, group);
            }
            group.lastInput = input; // host.inputs is the user's current display order.
            group.fields.set(field, input);
        }
    }
    return [...groups.values()];
}

function exposedResolutionWidget(host, input) {
    return host.getWidgetFromSlot?.(input) ??
        host.widgets?.find((widget) =>
            (input.widgetId != null && widget.widgetId === input.widgetId) ||
            (input.widgetId == null && widget.widgetId == null && widget.name === input.name)
        );
}

function resolutionInputConnected(host, input) {
    return input.link != null || host.isInputConnected?.(host.inputs.indexOf(input));
}

function swapPromotedResolution(host, group) {
    const { inner, fields } = group;
    const nativeSwap = resolutionWidget(inner, SWAP_LABEL);
    if (typeof nativeSwap?.callback !== "function") return;

    // Never pretend to change a value supplied by an outside connection.
    // All four fields below can be modified by the native swap callback.
    for (const name of ["width", "height", "aspect_group", "preset"]) {
        const input = fields.get(name);
        if (input && resolutionInputConnected(host, input)) return;
    }

    // Synchronize the values currently shown on the outer Subgraph with the
    // inner node before invoking its existing Swap logic. Non-exposed fields
    // remain local to the inner Resolution node.
    const wasProgrammatic = inner.__res_isProgrammatic;
    inner.__res_isProgrammatic = true;
    try {
        for (const [field, input] of fields) {
            if (resolutionInputConnected(host, input)) continue;
            const outer = exposedResolutionWidget(host, input);
            const inside = resolutionWidget(inner, field);
            if (outer && inside && inside.value !== outer.value) inside.value = outer.value;
        }
    } finally {
        inner.__res_isProgrammatic = wasProgrammatic;
    }
    nativeSwap.callback();
    // Updating projected dimensions can fire their normal widget callbacks.
    // These are part of Swap, not manual edits, so keep the selected preset.
    inner.__res_isProgrammatic = true;
    try {
        for (const name of ["width", "height"]) {
            const input = fields.get(name);
            if (!input) continue;
            const outer = exposedResolutionWidget(host, input);
            const inside = resolutionWidget(inner, name);
            if (outer && inside && outer.value !== inside.value) outer.value = inside.value;
        }
    } finally {
        inner.__res_isProgrammatic = wasProgrammatic;
    }
    inner.setDirtyCanvas?.(true, true);
    host.setDirtyCanvas?.(true, true);
}

// This runs from SubgraphNode.widgets' getter. Never read widget.widgetId
// directly here: BaseWidget.widgetId reads node.widgets to check uniqueness,
// which would recursively invoke this getter until the call stack overflows.
function resolutionWidgetMatchesInput(widget, input) {
    if (!widget || !input) return false;
    if (widget === input._widget) return true;
    // Older Comfy builds and test doubles can store widgetId directly. Inspect
    // an *own data property* without invoking an inherited/accessor getter.
    const ownId = Object.getOwnPropertyDescriptor(widget, "widgetId");
    if (ownId && Object.hasOwn(ownId, "value") && input.widgetId != null) {
        return ownId.value === input.widgetId;
    }
    // Legacy fallback only when the input has no projected widget identifier.
    return !input.widgetId && !input._widget && widget.name === input.name;
}

// ComfyUI SubgraphNode.widgets can be a computed getter. Moving an item in
// the returned array doesn't survive redraw, so wrap the getter instead.
function installResolutionOrder(host, state) {
    const original = Object.getOwnPropertyDescriptor(host, "widgets");
    if (!original?.get || !original.configurable) return;
    Object.defineProperty(host, "widgets", {
        ...original,
        get() {
            const list = original.get.call(this);
            decorateResolutionFields(list, state);
            if (!state.placements.length) return list;
            const buttons = new Set(state.buttons);
            const ordered = [];
            const placed = new Set();
            for (const widget of list) {
                if (buttons.has(widget)) continue;
                ordered.push(widget);
                for (const { input, button } of state.placements) {
                    if (resolutionWidgetMatchesInput(widget, input)) {
                        ordered.push(button);
                        placed.add(button);
                    }
                }
            }
            for (const button of state.buttons) {
                if (!placed.has(button)) ordered.push(button);
            }
            return ordered;
        },
    });
    state.restoreOrder = () => Object.defineProperty(host, "widgets", original);
}

function positionResolutionButtons(host, state) {
    if (state.restoreOrder || !Array.isArray(host.widgets)) return;
    const widgets = host.widgets;
    for (const button of state.buttons) {
        const index = widgets.indexOf(button);
        if (index !== -1) widgets.splice(index, 1);
    }
    for (const { input, button } of state.placements) {
        const index = widgets.findIndex((widget) => resolutionWidgetMatchesInput(widget, input));
        widgets.splice(index === -1 ? widgets.length : index + 1, 0, button);
    }
}

// As with the SBL Seed button, an outdated projected-widget minimum can
// leave a large unshrinkable blank section below the last visible field.
function compactResolutionMinimum(host, stock) {
    const widgets = host.getLayoutWidgets?.() ?? host.widgets ?? [];
    if (!widgets.length) return stock;
    const visible = widgets.filter((widget) => host.isWidgetRowVisible?.(widget) !== false);
    if (!visible.length) return stock;
    let bottom = 0;
    for (let i = 0; i < visible.length; i++) {
        const w = visible[i];
        if (!Number.isFinite(w.y) || w.y < 0 || (i && w.y <= visible[i - 1].y)) return stock;
        let height = w.computedHeight;
        if (!Number.isFinite(height) || height <= 0) {
            height = (w.computeSize?.(stock[0])?.[1] ??
                w.computeLayoutSize?.(host)?.minHeight ?? 20) + 4;
        }
        if (!Number.isFinite(height) || height <= 0) return stock;
        bottom = Math.max(bottom, w.y + height);
    }
    const bareInputs = (host.inputs ?? []).filter((input) =>
        !input.widget && !input.widgetId && !input._widget
    );
    const sockets = [...bareInputs, ...(host.outputs ?? [])];
    const socketBottom = Math.max(0, ...sockets.map((socket, i) =>
        Number.isFinite(socket.pos?.[1]) ? socket.pos[1] + 14 : (i + 1) * 24 + 14
    ));
    const minimum = Math.max(60, bottom + 12, socketBottom + 10);
    return minimum < stock[1] ? [stock[0], minimum] : stock;
}

function installResolutionSizing(host, state) {
    const original = host.computeSize;
    if (typeof original !== "function") return;
    const previous = Object.getOwnPropertyDescriptor(host, "computeSize");
    host.computeSize = function (...args) {
        const result = original.apply(this, args);
        if (!state.placements.length || !Array.isArray(result)) return result;
        const compact = compactResolutionMinimum(this, result);
        if (compact !== result) result[1] = compact[1];
        return result;
    };
    state.restoreSizing = () => {
        if (previous) Object.defineProperty(host, "computeSize", previous);
        else delete host.computeSize;
    };
}

function shrinkResolutionAfterLayout(host, state) {
    if (state.didCompact || state.compactionScheduled || !state.buttons.length) return;
    state.compactionScheduled = true;
    setTimeout(() => {
        state.compactionScheduled = false;
        if (state.removed || !state.buttons.length) return;
        const minimum = host.computeSize?.();
        if (!minimum || !host.size) return;
        if (!(host.getLayoutWidgets?.() ?? host.widgets ?? []).some((w) => Number.isFinite(w.y) && w.y > 0)) return;
        state.didCompact = true;
        if (host.size[1] > minimum[1] + 12) {
            host.setSize?.([host.size[0], minimum[1]]);
            host.setDirtyCanvas?.(true, true);
        }
    }, 150);
}

function syncResolutionButtons(host) {
    const state = host.__sblResolutionSwap;
    if (!state) return;
    const groups = promotedResolutions(host);
    const signature = groups.map(({ inner, lastInput, fields }) =>
        `${inner.id}:${host.inputs.indexOf(lastInput)}:${[...fields].map(([key, input]) => `${key}:${host.inputs.indexOf(input)}`).join(",")}`
    ).join("|");
    if (state.signature === signature) {
        positionResolutionButtons(host, state);
        return;
    }
    state.groups = groups;
    state.signature = signature;
    for (const button of state.buttons) host.removeWidget?.(button);
    state.buttons = [];
    state.placements = [];
    for (const [index, group] of groups.entries()) {
        const suffix = groups.length > 1 ? ` · #${group.inner.id ?? index + 1}` : "";
        const button = host.addWidget("button", SWAP_LABEL + suffix, null, () =>
            swapPromotedResolution(host, group)
        );
        button.tooltip = "Swap the width and height of this Resolution node. Exposed values update immediately.";
        button.options = { ...button.options, tooltip: button.tooltip, serialize: false };
        button.serialize = false;
        state.buttons.push(button);
        state.placements.push({ input: group.lastInput, button });
    }
    positionResolutionButtons(host, state);
    if (state.buttons.length) {
        const minimum = host.computeSize?.();
        if (minimum && host.size && host.setSize) {
            host.setSize([Math.max(host.size[0], minimum[0]), Math.max(host.size[1], minimum[1])]);
        }
        shrinkResolutionAfterLayout(host, state);
    }
    host.setDirtyCanvas?.(true, true);
}

function watchResolutionSubgraph(host) {
    if (!host?.subgraph || host.__sblResolutionSwap) return;
    const state = host.__sblResolutionSwap = {
        signature: null, buttons: [], placements: [], groups: [], scheduled: false, removed: false,
    };
    installResolutionOrder(host, state);
    installResolutionSizing(host, state);
    const controller = new AbortController();
    const schedule = () => {
        if (state.scheduled) return;
        state.scheduled = true;
        setTimeout(() => {
            state.scheduled = false;
            if (!state.removed) syncResolutionButtons(host);
        }, 0);
    };
    for (const eventName of ["widget-promoted", "widget-demoted", "input-added", "removing-input", "inputs-reordered"]) {
        host.subgraph.events?.addEventListener?.(eventName, schedule, { signal: controller.signal });
    }
    for (const methodName of ["onConfigure", "onConnectionsChange"]) {
        const previous = host[methodName];
        host[methodName] = function (...args) {
            const result = previous?.apply(this, args);
            schedule();
            return result;
        };
    }
    const previousRemoved = host.onRemoved;
    host.onRemoved = function (...args) {
        state.removed = true;
        controller.abort();
        state.restoreOrder?.();
        state.restoreSizing?.();
        return previousRemoved?.apply(this, args);
    };
    schedule();
}

function visitResolutionSubgraphs(graph) {
    for (const node of graph?.nodes ?? graph?._nodes ?? []) {
        if (node.subgraph) {
            watchResolutionSubgraph(node);
            visitResolutionSubgraphs(node.subgraph);
        }
    }
}

app.registerExtension({
    name: "SBL.ResolutionNode",
    setup() {
        app.canvas?.canvas?.addEventListener?.("subgraph-converted", (event) => {
            watchResolutionSubgraph(event.detail?.subgraphNode);
        });
    },
    nodeCreated(node) {
        if (node.subgraph) watchResolutionSubgraph(node);
    },
    afterConfigureGraph() {
        visitResolutionSubgraphs(app.rootGraph ?? app.graph);
    },
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
                // Accept "1920x1080 (label)" and "1920 x 1080".
                // Handles both ASCII 'x'/'X' and Unicode '×' (U+00D7) as separators.
                const m = String(presetStr).match(/(\d+)\s*[xX×]\s*(\d+)/i);
                if (!m) return null;
                return { w: parseInt(m[1], 10), h: parseInt(m[2], 10) };
            };

            // Compute the actual output without modifying the user's selected size.
            // This matches ResolutionNode._limit_megapixels in Python.
            const limitMegapixels = (width, height, multiple, maxMP) => {
                const limit = (Number(maxMP) || 0) * 1_000_000;
                if (limit <= 0 || width * height <= limit) return { w: width, h: height };

                const ratio = width / height;
                const scale = Math.sqrt(limit / (width * height));
                const targetW = width * scale;
                const targetH = height * scale;

                const findBest = (step) => {
                    const baseW = Math.floor(targetW / step);
                    const baseH = Math.floor(targetH / step);
                    const widthCenters = [baseW];
                    const heightCenters = [baseH];
                    if (targetH < Math.max(16, step)) {
                        widthCenters.push(Math.floor(Math.min(width, limit / Math.max(16, step)) / step));
                        heightCenters.push(Math.ceil(16 / step));
                    }
                    if (targetW < Math.max(16, step)) {
                        heightCenters.push(Math.floor(Math.min(height, limit / Math.max(16, step)) / step));
                        widthCenters.push(Math.ceil(16 / step));
                    }
                    const nearby = centers => [...new Set(centers.flatMap(base =>
                        Array.from({ length: 6 }, (_, i) => Math.max(1, base - 2 + i))
                    ))].sort((a, b) => a - b);
                    const widthSteps = nearby(widthCenters);
                    const heightSteps = nearby(heightCenters);
                    let best = null;
                    for (const x of widthSteps) {
                        const w = x * step;
                        if (w < 16 || w > width) continue;
                        for (const y of heightSteps) {
                            const h = y * step;
                            if (h < 16 || h > height) continue;
                            const pixels = w * h;
                            if (pixels > limit) continue;
                            const ratioError = Math.log((w / h) / ratio);
                            const areaGap = (limit - pixels) / limit;
                            const score = (2 * ratioError) ** 2 + areaGap ** 2;
                            const key = [score, Math.abs(ratioError), areaGap];
                            if (!best || key.some((v, i) =>
                                v < best.key[i] && key.slice(0, i).every((a, j) => a === best.key[j])
                            )) best = { w, h, key };
                        }
                    }
                    return best ? { w: best.w, h: best.h } : null;
                };

                const step = Math.max(1, parseInt(multiple, 10) || 1);
                return findBest(step) || findBest(1) || { w: 16, h: 16 };
            };

            // Exposed Subgraph controls are separate from the inner node's
            // values. Compute the preview from those values without modifying
            // either widget or triggering callbacks during canvas drawing.
            node.__sblResolutionPreview = (overrides = {}) => {
                const value = (name) => overrides[name] ?? getWidget(name)?.value;
                const multiple = value("multiple_of") ?? "8";
                let width = Number(value("width"));
                let height = Number(value("height"));
                if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) return null;
                const preset = value("preset");
                if (preset && preset !== "Custom") {
                    const dimensions = parsePreset(preset);
                    if (dimensions) {
                        const snapped = snapDimensionsToClosestRatio(
                            width, height, multiple, dimensions.w / dimensions.h
                        );
                        width = snapped.w;
                        height = snapped.h;
                    } else {
                        width = snapToMultiple(width, multiple);
                        height = snapToMultiple(height, multiple);
                    }
                } else {
                    width = snapToMultiple(width, multiple);
                    height = snapToMultiple(height, multiple);
                }
                const effective = limitMegapixels(width, height, multiple, value("max_megapixels"));
                return { ...effective, capped: effective.w !== width || effective.h !== height };
            };

            const getEffectiveDimensions = () => {
                const widthWidget = getWidget("width");
                const heightWidget = getWidget("height");
                if (!widthWidget || !heightWidget) return null;
                return limitMegapixels(
                    Number(widthWidget.value),
                    Number(heightWidget.value),
                    getCurrentMultiple(),
                    getWidget("max_megapixels")?.value,
                );
            };

            const updateOutputLabel = (effective) => {
                const widget = getWidget("max_megapixels");
                if (!widget || !effective) return;
                widget.label = `Max MP (out ${effective.w}×${effective.h})`;
                node.setDirtyCanvas(true);
            };

            const pushDimensionWidget = (_triggeringWidget) => {
                const effective = getEffectiveDimensions();
                if (!effective) return;
                updateOutputLabel(effective);

                // Both effective outputs may change when just one input changes.
                for (const outputName of ["width", "height"]) {
                    const correspondingOutput = node.outputs?.find(o => o.name === outputName);
                    if (!correspondingOutput?.links?.length) continue;
                    const outputValue = outputName === "width" ? effective.w : effective.h;
                    for (const linkId of correspondingOutput.links) {
                        const link = app.graph.links[linkId];
                        if (!link) continue;
                        const targetNode = app.graph.getNodeById(link.target_id);
                        const targetInput = targetNode?.inputs?.[link.target_slot];
                        if (!targetInput) continue;
                        const foundWidget = targetNode.widgets?.find(w => w.name === targetInput.name);
                        if (!foundWidget) continue;
                        foundWidget.value = outputValue;
                        targetNode.setDirtyCanvas(true);
                        if (foundWidget.callback) {
                            try {
                                foundWidget.callback.call(foundWidget, outputValue, app.graph, targetNode);
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

                updateDimensionsForClosestRatio(
                    widthWidget,
                    heightWidget,
                    node.__res_targetRatio,
                );

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
                const maxMegapixelsWidget = getWidget("max_megapixels");
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


                // Swap only the dimensions. The selected group and preset are
                // the user's choices and must not be reset to Custom.
                const swapWidget = node.addWidget("button", "Swap width↔height", null, () => {
                    if (!widthWidget || !heightWidget) return;
                    withProgrammatic(() => {
                        const tmp = widthWidget.value;
                        widthWidget.value = heightWidget.value;
                        heightWidget.value = tmp;
                        widthWidget.prevValue = widthWidget.value;
                        heightWidget.prevValue = heightWidget.value;
                    });
                    node.__res_targetRatio = widthWidget.value / heightWidget.value;
                    pushDimensionWidget(widthWidget);
                    node.setDirtyCanvas(true);
                });
                if (swapWidget) {
                    swapWidget.options = { ...swapWidget.options, tooltip: "Exchange the selected width and height, preserving the pixel grid and recomputing capped outputs." };
                }

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

                // Altering the limit recalculates outputs, never the selected size.
                if (maxMegapixelsWidget) {
                    const originalCallback = maxMegapixelsWidget.callback;
                    maxMegapixelsWidget.callback = function (value) {
                        if (originalCallback) originalCallback.call(this, value);
                        pushDimensionWidget(widthWidget);
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

                // Previously saved workflows may contain retired model groups.
                // Convert only those old selections to Custom on load.
                if (aspectGroupWidget && presetWidget) {
                    if (!Object.prototype.hasOwnProperty.call(PRESET_GROUPS, aspectGroupWidget.value)) {
                        aspectGroupWidget.value = "Custom";
                        presetWidget.value = "Custom";
                    }
                    const initOptions = PRESET_GROUPS[aspectGroupWidget.value];
                    setPresetOptions(presetWidget, initOptions, false);
                }

                // Reflect the effective output immediately on load, including 0 MP.
                const initialEffective = getEffectiveDimensions();
                updateOutputLabel(initialEffective);
                if (widthWidget) pushDimensionWidget(widthWidget);

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
