// The API serves the widget from its static folder, so a local build lands there too.
import { copyFileSync, mkdirSync } from "node:fs";
import { resolve } from "node:path";

const target = resolve(import.meta.dirname, "../../api/static");
mkdirSync(target, { recursive: true });
for (const file of ["widget.js", "widget-app.js"]) {
  copyFileSync(resolve(import.meta.dirname, "../dist", file), resolve(target, file));
}
console.log(`widget copied to ${target}`);
