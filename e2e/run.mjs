// Runs every browser scenario against a fresh synthetic environment. Starts the E2E API (one fresh
// database per scenario) and `next dev`, and stops only the processes it started.
//
// Requires: local PostgreSQL and Redis for tests (LUMINI_E2E_ADMIN_DATABASE_URL,
// LUMINI_E2E_REDIS_URL), Google Chrome (E2E_CHROME), Node 22 and the backend virtualenv.
import { spawn } from "node:child_process";
import { mkdirSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..");
const site = process.env.E2E_SITE ?? "http://127.0.0.1:3100";
const api = process.env.E2E_API ?? "http://127.0.0.1:8100";
const output = process.env.E2E_OUTPUT ?? join(here, ".output") + "/";
const only = process.argv.slice(2);
for (const name of ["LUMINI_E2E_ADMIN_DATABASE_URL", "LUMINI_E2E_REDIS_URL"]) {
  if (!process.env[name]) {
    console.error(`${name} is required (local test services only).`);
    process.exit(2);
  }
}
mkdirSync(output, { recursive: true });

function start(command, args, options) {
  const child = spawn(command, args, { ...options, detached: true, stdio: ["ignore", "ignore", "pipe"] });
  let errors = "";
  child.stderr.on("data", (chunk) => { errors = (errors + chunk).slice(-4000); });
  child.lastErrors = () => errors;
  return child;
}

function stop(child) {
  if (child && child.exitCode === null) {
    try { process.kill(-child.pid, "SIGTERM"); } catch { /* already gone */ }
  }
}

async function waitFor(url, child, seconds) {
  for (let attempt = 0; attempt < seconds * 2; attempt += 1) {
    if (child.exitCode !== null) throw new Error(`process exited early:\n${child.lastErrors()}`);
    try {
      if ((await fetch(url)).status < 500) return;
    } catch { /* not up yet */ }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`timeout waiting for ${url}`);
}

const uv = join(root, ".tools", "bin", "uv");
function startApi() {
  return start(uv, ["run", "--frozen", "--project", join(root, "backend"), "python", join(here, "server.py")], {
    cwd: join(root, "backend"),
    env: { ...process.env, E2E_SITE: site, E2E_API_PORT: new URL(api).port || "8100" },
  });
}

const web = start("npx", ["next", "dev", "--hostname", "127.0.0.1", "--port", new URL(site).port || "3100"], {
  cwd: join(root, "frontend"),
  env: {
    ...process.env,
    NEXT_TELEMETRY_DISABLED: "1",
    NEXT_PUBLIC_GOOGLE_CLIENT_ID: "123456789-synthetic.apps.googleusercontent.com",
    NEXT_PUBLIC_API_BASE_URL: api,
  },
});

const scenarios = readdirSync(join(here, "scenarios"))
  .filter((name) => name.endsWith(".mjs") && (only.length === 0 || only.some((part) => name.includes(part))))
  .sort();
const results = [];
let server = null;
try {
  for (const scenario of scenarios) {
    stop(server);
    await new Promise((resolve) => setTimeout(resolve, 1000));
    server = startApi();
    await waitFor(`${api}/health/live`, server, 90);
    await waitFor(`${site}/admin`, web, 120);
    const code = await new Promise((resolve) => {
      const child = spawn(process.execPath, [join(here, "scenarios", scenario)], {
        env: { ...process.env, E2E_SITE: site, E2E_API: api, E2E_OUTPUT: output },
        stdio: "inherit",
      });
      child.on("exit", resolve);
    });
    results.push({ scenario, ok: code === 0 });
  }
} finally {
  stop(server);
  stop(web);
}
console.log("\nResumo E2E:");
for (const item of results) console.log(`${item.ok ? "PASS" : "FAIL"} ${item.scenario}`);
process.exitCode = results.length === scenarios.length && results.every((item) => item.ok) ? 0 : 1;
