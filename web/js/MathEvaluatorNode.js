import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "SBL.MathEvaluatorNode",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === "SBL_MathEvaluator") {
            const oldOnNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                const r = oldOnNodeCreated?.apply(this, arguments);
                const node = this;

                // Define all inputs directly in JS
                const typeMap = {
                    w: "FLOAT",
                    x: "FLOAT",
                    y: "INT",
                    z: "INT"
                };

                const labelMap = {
                    w: "w (float)",
                    x: "x (float)",
                    y: "y (int)",
                    z: "z (int)"
                };

                Object.entries(typeMap).forEach(([name, type]) => {
                    const input = node.addInput(name, type);
                    if (input && labelMap[name]) {
                        input.label = labelMap[name];
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
