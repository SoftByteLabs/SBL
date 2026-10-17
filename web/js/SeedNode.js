import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "SBL.SeedNode",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== "SBL_Seed") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
            const node = this;

            const getWidget = (name) => node.widgets?.find(w => w.name === name);

            const generateRandomSeed = () => {
                // ComfyUI uses 2^50 as the max seed value (1125899906842624)
                // Using the hex value for clarity: 0x4000000000000
                return Math.floor(Math.random() * 0x4000000000000);
            };

            setTimeout(() => {
                const seedWidget = getWidget("seed");
                if (!seedWidget) return;

                // Add randomize button
                const randomizeWidget = node.addWidget("button", "🎲 Randomize", null, () => {
                    if (!seedWidget) return;
                    seedWidget.value = generateRandomSeed();
                    node.setDirtyCanvas(true);
                });
                if (randomizeWidget) {
                    randomizeWidget.options = { ...randomizeWidget.options, tooltip: "Generate a new random seed for the next image or noise generation." };
                }

                node.computeSize();
                node.setDirtyCanvas(true, true);

            }, 100);

            return r;
        };
    }
});
