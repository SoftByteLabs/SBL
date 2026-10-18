import { app } from "../../scripts/app.js";

const SEED_NODE_TYPE = "SBL_Seed";
const BUTTON_LABEL = "🎲 Randomize";

const SEED_TOOLTIP = "Random seed used to initialize noise. The same seed reproduces the same noise for the same generation settings. Limited to JavaScript-safe integers (2^53 - 1).";

function decorateSeedFields(widgets, state) {
    for (const { inner, input } of state.promoted ?? []) {
        // Never access a computed widgetId while building host.widgets.
        const projected = widgets.find(widget => isWidgetForInput(widget, input));
        if (!projected) continue;
        const source = findWidget(inner, "seed");
        const tooltip = source?.tooltip || source?.options?.tooltip || SEED_TOOLTIP;
        if (projected.tooltip !== tooltip) projected.tooltip = tooltip;
        // Avoid modifying ComfyUI's reactive projected options in a getter.
    }
}

// Preserve the existing, manual-only randomization range (0 through 2^50 - 1).
function randomSeed() {
    return Math.floor(Math.random() * 0x4000000000000);
}

function findWidget(node, name) {
    return node.widgets?.find((widget) => widget.name === name);
}

function addRandomButton(owner, getSeedWidget, suffix = "") {
    const widget = owner.addWidget("button", BUTTON_LABEL + suffix, null, () => {
        const seedWidget = getSeedWidget();
        if (!seedWidget) return;
        seedWidget.value = randomSeed();
        owner.setDirtyCanvas?.(true, true);
    });
    widget.tooltip = "Generate a new seed immediately. It stays fixed for subsequent runs.";
    widget.options = { ...widget.options, tooltip: widget.tooltip, serialize: false };
    widget.serialize = false; // UI-only control; the actual seed widget is saved.
    return widget;
}

function expandToFit(node) {
    const minimum = node.computeSize?.();
    if (minimum && node.size && node.setSize) {
        node.setSize([Math.max(node.size[0], minimum[0]), Math.max(node.size[1], minimum[1])]);
    }
    node.setDirtyCanvas?.(true, true);
}

// Follow a promoted subgraph input to the actual seed input. This also works
// when a subgraph is nested inside another subgraph.
function targetsOfInput(host, input, depth = 0) {
    const innerGraph = host.subgraph;
    const slot = input?._subgraphSlot;
    if (!innerGraph || !slot || depth > 12) return [];

    const targets = [];
    for (const linkId of slot.linkIds ?? []) {
        const link = innerGraph.getLink?.(linkId) ?? innerGraph.links?.get?.(linkId) ?? innerGraph.links?.[linkId];
        if (!link) continue;
        const inner = innerGraph.getNodeById?.(link.target_id);
        const targetInput = inner?.inputs?.[link.target_slot];
        if (!inner || !targetInput) continue;

        if (inner.type === SEED_NODE_TYPE && targetInput.widget?.name === "seed") {
            targets.push(inner);
        } else if (inner.subgraph) {
            targets.push(...targetsOfInput(inner, targetInput, depth + 1));
        }
    }
    return targets;
}

function promotedSeeds(host) {
    const result = [];
    for (const input of host.inputs ?? []) {
        if (!input._subgraphSlot) continue;
        for (const inner of targetsOfInput(host, input)) {
            result.push({ inner, input });
        }
    }
    return result;
}

// A promoted input uses a store-backed widget on the *outer* subgraph node.
// Changing the original inner widget would not change the seed sent to execution.
function outerSeedWidget(host, input) {
    return host.getWidgetFromSlot?.(input) ??
        host.widgets?.find((widget) =>
            (input.widgetId != null && widget.widgetId === input.widgetId) || widget.name === input.name
        );
}

// The SubgraphNode frontend projects promoted inputs before custom widgets.
// Its `widgets` property is a getter, so reordering a returned array would be
// discarded on the next redraw. Compose the display order from that getter
// instead, placing each UI-only button directly after its promoted seed.
// Called from SubgraphNode.widgets' getter. Accessing a BaseWidget.widgetId
// accessor in here can recurse into node.widgets and overflow the call stack.
function isWidgetForInput(widget, input) {
    if (!widget || !input) return false;
    if (widget === input._widget) return true;
    const ownId = Object.getOwnPropertyDescriptor(widget, "widgetId");
    if (ownId && Object.hasOwn(ownId, "value") && input.widgetId != null) {
        return ownId.value === input.widgetId;
    }
    // Compatibility with older frontend builds without projected IDs.
    return !input.widgetId && !input._widget && widget.name === input.name;
}

function installSubgraphWidgetOrder(host, state) {
    const descriptor = Object.getOwnPropertyDescriptor(host, "widgets");
    if (!descriptor?.get || !descriptor.configurable) return;

    Object.defineProperty(host, "widgets", {
        ...descriptor,
        get() {
            const widgets = descriptor.get.call(this);
            decorateSeedFields(widgets, state);
            if (!state.placements.length) return widgets;

            const buttons = new Set(state.widgets);
            const ordered = [];
            const placed = new Set();
            for (const widget of widgets) {
                if (buttons.has(widget)) continue;
                ordered.push(widget);
                for (const { input, button } of state.placements) {
                    if (isWidgetForInput(widget, input)) {
                        ordered.push(button);
                        placed.add(button);
                    }
                }
            }
            // If a promoted widget is temporarily unavailable during a
            // reload, keep its button visible until the next synchronization.
            for (const button of state.widgets) {
                if (!placed.has(button)) ordered.push(button);
            }
            return ordered;
        },
    });
    state.restoreWidgetOrder = () => Object.defineProperty(host, "widgets", descriptor);
}

// The subgraph's computed minimum can include space for slots or projected
// widgets that are no longer rendered at that position. The classic canvas
// clamps manual resizing to computeSize(), producing an unshrinkable blank
// area below the last visible widget. Use actual laid-out widget positions
// to lower only that minimum; retain normal width and all output/real slots.
// When layout has not run yet, defer to the stock ComfyUI calculation.
function compactSubgraphMinimum(host, stockSize) {
    const widgets = host.getLayoutWidgets?.() ?? host.widgets ?? [];
    if (!widgets.length) return stockSize;

    let widgetBottom = 0;
    let visibleCount = 0;
    for (const widget of widgets) {
        if (host.isWidgetRowVisible?.(widget) === false) continue;
        const y = widget.y;
        if (!Number.isFinite(y) || y < 0) return stockSize;
        let height = widget.computedHeight;
        if (!Number.isFinite(height) || height <= 0) {
            const calculated = widget.computeSize?.(stockSize[0])?.[1] ??
                widget.computeLayoutSize?.(host)?.minHeight ?? 20;
            height = calculated + 4;
        }
        if (!Number.isFinite(height) || height <= 0) return stockSize;
        widgetBottom = Math.max(widgetBottom, y + height);
        visibleCount++;
    }
    if (!visibleCount) return stockSize;

    // A just-created widget can have its default y=0 before Comfy arranges it.
    // We only compact once all rows have their own ascending layout positions.
    const visible = widgets.filter((widget) => host.isWidgetRowVisible?.(widget) !== false);
    if (visible.length > 1 && visible.some((widget, i) => i > 0 && widget.y <= visible[i - 1].y)) {
        return stockSize;
    }

    // Protect conventional (non-widget) slots and outputs, including subgraphs
    // with additional data links below their promoted seed controls.
    const bareInputs = (host.inputs ?? []).filter((input) =>
        !input.widget && !input.widgetId && !input._widget
    );
    const outputSlots = host.outputs ?? [];
    const slots = [...bareInputs, ...outputSlots];
    const slotBottom = Math.max(0, ...slots.map((slot, index) =>
        Number.isFinite(slot.pos?.[1]) ? slot.pos[1] + 14 : (index + 1) * 24 + 14
    ));

    // Margin below the last visible control, not below phantom widget rows.
    const minHeight = Math.max(60, widgetBottom + 12, slotBottom + 10);
    if (minHeight >= stockSize[1]) return stockSize;
    return [stockSize[0], minHeight];
}

function installCompactSubgraphSizing(host, state) {
    const original = host.computeSize;
    if (typeof original !== "function") return;
    const previousDescriptor = Object.getOwnPropertyDescriptor(host, "computeSize");
    host.computeSize = function (...args) {
        const result = original.apply(this, args);
        if (!state.placements.length || !Array.isArray(result)) return result;
        const compact = compactSubgraphMinimum(this, result);
        if (compact !== result) result[1] = compact[1];
        return result;
    };
    state.restoreSizing = () => {
        if (previousDescriptor) Object.defineProperty(host, "computeSize", previousDescriptor);
        else delete host.computeSize;
    };
}

// Once the frontend has laid out the newly-added button, remove the extra
// blank area from an existing subgraph, not only from subsequent drag-resizes.
// Run this once per instance; later user-initiated size changes are respected.
function compactAfterLayout(host, state) {
    if (state.didCompact || state.compactionScheduled || !state.widgets.length) return;
    state.compactionScheduled = true;
    setTimeout(() => {
        state.compactionScheduled = false;
        if (state.removed || !state.widgets.length) return;
        const minimum = host.computeSize?.();
        if (!minimum || !host.size) return;
        const laidOut = (host.getLayoutWidgets?.() ?? host.widgets ?? []).some((w) =>
            Number.isFinite(w.y) && w.y > 0
        );
        if (!laidOut) return;
        state.didCompact = true;
        if (host.size[1] > minimum[1] + 12) {
            host.setSize?.([host.size[0], minimum[1]]);
            host.setDirtyCanvas?.(true, true);
        }
    }, 150);
}

// Compatibility with frontends that expose a plain mutable widget array.
function positionMutableSubgraphButtons(host, state) {
    if (state.restoreWidgetOrder || !Array.isArray(host.widgets)) return;
    const widgets = host.widgets;
    for (const button of state.widgets) {
        const index = widgets.indexOf(button);
        if (index !== -1) widgets.splice(index, 1);
    }
    for (const { input, button } of state.placements) {
        const index = widgets.findIndex((widget) => isWidgetForInput(widget, input));
        widgets.splice(index === -1 ? widgets.length : index + 1, 0, button);
    }
}

function syncSubgraphButtons(host) {
    const state = host.__sblSeedButtons;
    if (!state) return;
    const promoted = promotedSeeds(host);
    const signature = promoted.map(({ inner, input }) => `${inner.id}:${host.inputs.indexOf(input)}:${input.name}`).join("|");
    if (state.signature === signature) {
        positionMutableSubgraphButtons(host, state);
        return;
    }
    state.signature = signature;
    state.promoted = promoted;

    for (const widget of state.widgets) host.removeWidget?.(widget);
    state.widgets = [];
    state.placements = [];

    for (const [index, { inner, input }] of promoted.entries()) {
        const labelSuffix = promoted.length > 1 ? ` · #${inner.id ?? index + 1}` : "";
        const getSeed = () => {
            // A linked subgraph input overrides the promoted value, so the button
            // must not pretend to change the supplied seed.
            if (input.link != null || host.isInputConnected?.(host.inputs.indexOf(input))) return null;
            return outerSeedWidget(host, input);
        };
        const button = addRandomButton(host, getSeed, labelSuffix);
        state.widgets.push(button);
        state.placements.push({ input, button });
    }
    positionMutableSubgraphButtons(host, state);
    if (state.widgets.length) {
        expandToFit(host);
        compactAfterLayout(host, state);
    } else host.setDirtyCanvas?.(true, true);
}

function watchSubgraph(host) {
    if (!host?.subgraph || host.__sblSeedButtons) return;
    const state = host.__sblSeedButtons = { signature: null, widgets: [], placements: [], scheduled: false };
    installSubgraphWidgetOrder(host, state);
    installCompactSubgraphSizing(host, state);
    const controller = new AbortController();

    const schedule = () => {
        if (state.scheduled) return;
        state.scheduled = true;
        setTimeout(() => {
            state.scheduled = false;
            if (!state.removed) syncSubgraphButtons(host);
        }, 0);
    };

    for (const eventName of ["widget-promoted", "widget-demoted", "input-added", "removing-input", "inputs-reordered"]) {
        host.subgraph.events?.addEventListener?.(eventName, schedule, { signal: controller.signal });
    }
    for (const methodName of ["onConfigure", "onConnectionsChange"]) {
        const original = host[methodName];
        host[methodName] = function (...args) {
            const result = original?.apply(this, args);
            schedule();
            return result;
        };
    }
    const originalRemoved = host.onRemoved;
    host.onRemoved = function (...args) {
        state.removed = true;
        controller.abort();
        state.restoreWidgetOrder?.();
        state.restoreSizing?.();
        return originalRemoved?.apply(this, args);
    };
    schedule();
}

function visitSubgraphs(graph) {
    for (const node of graph?.nodes ?? graph?._nodes ?? []) {
        if (node.subgraph) {
            watchSubgraph(node);
            visitSubgraphs(node.subgraph);
        }
    }
}

app.registerExtension({
    name: "SBL.SeedNode",
    setup() {
        // Covers conversion of an existing selection into a new subgraph.
        app.canvas?.canvas?.addEventListener?.("subgraph-converted", (event) => {
            watchSubgraph(event.detail?.subgraphNode);
        });
    },
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== SEED_NODE_TYPE) return;
        const originalCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function (...args) {
            const result = originalCreated?.apply(this, args);
            // The seed widget is created by ComfyUI after node construction.
            setTimeout(() => {
                if (findWidget(this, "seed") && !findWidget(this, BUTTON_LABEL)) {
                    addRandomButton(this, () => findWidget(this, "seed"));
                    expandToFit(this);
                }
            }, 100);
            return result;
        };
    },
    nodeCreated(node) {
        if (node.subgraph) watchSubgraph(node);
    },
    afterConfigureGraph() {
        // Restore buttons after loading a saved workflow with promoted widgets.
        visitSubgraphs(app.rootGraph ?? app.graph);
    },
});
