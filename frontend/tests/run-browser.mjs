// Runs every browser flow in tests/ against a running frontend (default http://localhost:3000)
// and reports each result. All API calls are mocked; no backend is needed. Exit code 1 if any fails.
//   cd frontend && npm run dev &   then   node tests/run-browser.mjs [name ...]
import { readdirSync } from "node:fs";
import { spawnSync } from "node:child_process";

const dir = new URL(".", import.meta.url).pathname;
const only = process.argv.slice(2);
const flows = readdirSync(dir).filter((f) => f.endsWith(".mjs") && !f.endsWith(".test.mjs") && !["mock-api.mjs", "run-browser.mjs"].includes(f))
  .filter((f) => !only.length || only.some((o) => f.startsWith(o))).sort();
let failed = 0;
for (const flow of flows) {
  const started = Date.now();
  const run = spawnSync(process.execPath, [dir + flow], { encoding: "utf8", timeout: 180000 });
  const ok = run.status === 0;
  failed += !ok;
  console.log(`${ok ? "ok  " : "FAIL"} ${flow} (${((Date.now() - started) / 1000).toFixed(1)} s)`);
  if (!ok) console.log((run.stdout + run.stderr).split("\n").filter((l) => !/^\s+at |MODULE_TYPELESS|Reparsing|To eliminate|trace-warnings/.test(l)).slice(-15).join("\n"));
}
console.log(`${flows.length - failed}/${flows.length} browser flows passed`);
process.exit(failed ? 1 : 0);
