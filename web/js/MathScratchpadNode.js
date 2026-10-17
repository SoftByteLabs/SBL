import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "SBL.MathScratchpadNode",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== "SBL_MathScratchpadNode") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
            const node = this;

            // Remove the auto-created STRING widget - we replace it with a DOM widget
            const autoWidget = node.widgets?.find(w => w.name === "expressions");
            if (autoWidget) {
                node.widgets.splice(node.widgets.indexOf(autoWidget), 1);
            }

            // Persisted state lives on node.properties (auto-serialized by litegraph)
            node.properties = node.properties || {};
            if (typeof node.properties.outputHeight !== "number") {
                node.properties.outputHeight = 120;
            }

            // Build the DOM: input textarea + splitter + output textarea
            const container = document.createElement("div");
            Object.assign(container.style, {
                display:       "flex",
                flexDirection: "column",
                width:         "100%",
                height:        "100%",
                boxSizing:     "border-box",
                gap:           "0px",
            });

            // Input textarea
            const inputEl = document.createElement("textarea");
            inputEl.spellcheck = false;
            inputEl.title = "Write restricted Python-style math, variables, loops and print() statements. Click Evaluate to see results.";
            inputEl.value = "import math\nt = 12\nrawframes = t * 24 + 1\nltxframes = 8 * math.floor((rawframes - 1) / 8)\nprint(ltxframes + 1)\nprint(ltxframes / 24)\nprint(ltxframes / 8)";
            Object.assign(inputEl.style, {
                flex:        "1 1 auto",
                resize:      "none",
                boxSizing:   "border-box",
                fontFamily:  "monospace",
                fontSize:    "12px",
                background:  "#1e1e1e",
                color:       "#d4d4d4",
                border:      "1px solid #555",
                borderRadius:"3px 3px 0 0",
                padding:     "4px 6px",
                outline:     "none",
            });

            // Splitter
            const splitter = document.createElement("div");
            Object.assign(splitter.style, {
                height:     "6px",
                background: "#444",
                cursor:     "ns-resize",
                flexShrink: "0",
                borderTop:  "1px solid #666",
                borderBottom: "1px solid #666",
            });

            splitter.title = "Drag up or down to resize the output area.";

            // Output textarea
            const outputEl = document.createElement("textarea");
            outputEl.readOnly = true;
            outputEl.title = "Read-only output from Evaluate, including printed values or error messages.";
            outputEl.value = "Click ⚡ Evaluate...";
            Object.assign(outputEl.style, {
                flex:        `0 0 ${node.properties.outputHeight}px`,
                resize:      "none",
                boxSizing:   "border-box",
                fontFamily:  "monospace",
                fontSize:    "12px",
                background:  "#1a1a2e",
                color:       "#00ff88",
                border:      "1px solid #555",
                borderRadius:"0 0 3px 3px",
                padding:     "4px 6px",
                outline:     "none",
            });

            container.appendChild(inputEl);
            container.appendChild(splitter);
            container.appendChild(outputEl);

            // Splitter drag - persists height to node.properties
            let dragging = false;
            let startY = 0;
            let startOutputH = 0;

            splitter.addEventListener("mousedown", (e) => {
                dragging     = true;
                startY       = e.clientY;
                startOutputH = outputEl.getBoundingClientRect().height;
                e.preventDefault();
                e.stopPropagation();
            });
            document.addEventListener("mousemove", (e) => {
                if (!dragging) return;
                const dy     = e.clientY - startY;
                const minH   = 40;
                const newOut = Math.max(minH, startOutputH - dy);
                outputEl.style.flex = `0 0 ${newOut}px`;
                node.properties.outputHeight = newOut;
            });
            document.addEventListener("mouseup", () => {
                if (dragging) {
                    dragging = false;
                    node.setDirtyCanvas(true, true);
                }
            });

            // Register as a DOM widget - ComfyUI handles sizing and serialization
            const domWidget = node.addDOMWidget("expressions", "customtext", container, {
                getValue() { return inputEl.value; },
                setValue(val) { inputEl.value = val ?? ""; },
            });

            if (domWidget) {
                domWidget.options = { ...domWidget.options, tooltip: "Math expression editor and results panel. Evaluate runs the calculations without queueing a generation." };
            }

            // Keep widget value in sync as user types (for workflow save/load)
            inputEl.addEventListener("input", () => {
                if (domWidget) domWidget.value = inputEl.value;
            });

            // Native ComfyUI button widget — same pattern as ResolutionNode's Swap button.
            // Renders on canvas, no pointer-event issues.
            const evaluateWidget = node.addWidget("button", "⚡ Evaluate", null, async () => {
                outputEl.value = "Running...";
                outputEl.style.color = "#aaa";
                try {
                    const resp = await fetch("/sbl/scratchpad/evaluate", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ expressions: inputEl.value || "" }),
                    });
                    const data = await resp.json();
                    outputEl.value = data.error ? `ERROR: ${data.error}` : (data.output || "(no output)");
                    outputEl.style.color = data.error ? "#ff4444" : "#00ff88";
                } catch (err) {
                    outputEl.value = `FETCH ERROR: ${err}`;
                    outputEl.style.color = "#ff4444";
                }
            });
            if (evaluateWidget) {
                evaluateWidget.options = { ...evaluateWidget.options, tooltip: "Run the scratchpad expressions and show the result below without queueing ComfyUI." };
            }

            // Restore splitter position after workflow load
            const onConfigure = node.onConfigure;
            node.onConfigure = function (info) {
                const ret = onConfigure ? onConfigure.apply(this, arguments) : undefined;
                const h = node.properties?.outputHeight;
                if (typeof h === "number") {
                    outputEl.style.flex = `0 0 ${h}px`;
                }
                return ret;
            };

            node.setDirtyCanvas(true, true);
            return r;
        };
    }
});