import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "SBL.MathEvaluatorNode",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === "SBL_MathEvaluator") {
            const oldOnNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                const r = oldOnNodeCreated?.apply(this, arguments);
                const node = this;

                // w/x/y/z are now real Python INPUT_TYPES sockets. Re-label
                // existing sockets only, avoiding duplicates when workflows load.
                const labels = {
                    w: "w (float)", x: "x (float)",
                    y: "y (int)", z: "z (int)"
                };
                const tips = {
                    w: "Optional float input w; 0 when disconnected.",
                    x: "Optional float input x; 0 when disconnected.",
                    y: "Optional integer input y; 0 when disconnected.",
                    z: "Optional integer input z; 0 when disconnected."
                };
                node.inputs?.forEach(input => {
                    if (labels[input.name]) {
                        input.label = labels[input.name];
                        input.tooltip = tips[input.name];
                    }
                });

                // Relabel outputs for clarity
                const outputNameOverrides = [
                    "a (float)",
                    "b (float)",
                    "a (int)",
                    "b (int)"
                ];

                node.outputs.forEach((output, i) => {
                    if (output && output.name && outputNameOverrides[i]) {
                        output.label = outputNameOverrides[i];
                    }
                });

                node.size = node.computeSize();
                app.graph.setDirtyCanvas(true, true);

                return r;
            };
        }
    }
});
