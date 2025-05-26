import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { gzipSync } from "node:zlib";

const LIMIT_KB = 60;
let total = 0;
for (const file of ["widget.js", "widget-app.js"]) {
  const size = gzipSync(readFileSync(resolve(import.meta.dirname, "../dist", file))).length;
  total += size;
  console.log(`${file.padEnd(16)} ${(size / 1024).toFixed(1)} kB gzip`);
}
console.log(`total            ${(total / 1024).toFixed(1)} kB gzip (budget ${LIMIT_KB} kB)`);
if (total > LIMIT_KB * 1024) process.exit(1);
