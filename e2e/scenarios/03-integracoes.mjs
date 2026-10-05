// Synthetic E2E for the panel's integrations tab. Run through e2e/run.mjs.
import { chromium } from "playwright-core";

const SITE = (process.env.E2E_SITE ?? "http://127.0.0.1:3100");
const API = process.env.E2E_API ?? "http://127.0.0.1:8100";
const HOOK = { Authorization: "Bearer e2e-synthetic-webhook-token-0123456789abcdef", "Content-Type": "application/json" };
const steps = [];
const problems = [];
function step(name, ok, detail = "") {
  steps.push(ok);
  console.log(`${ok ? "PASS" : "FAIL"} ${name}${detail ? ` — ${detail}` : ""}`);
}
async function hook(body) {
  const response = await fetch(`${API}/api/webhooks/evolution`, { method: "POST", headers: HOOK, body: JSON.stringify({ instance: "lumini-e2e", ...body }) });
  return response.status;
}
let ids = 0;
function message(text, fromMe = false) {
  ids += 1;
  return { event: "messages.upsert", data: { key: { remoteJid: "5521900000123@s.whatsapp.net", fromMe, id: `E2EIN${ids}` }, message: { conversation: text }, messageTimestamp: Math.floor(Date.now() / 1000) } };
}
const STUB = `window.google = { accounts: { id: {
  initialize(config) { window.__gsiConfig = config; },
  renderButton(parent) { const b = document.createElement("button"); b.type = "button"; b.textContent = "Entrar com Google (stub)";
    b.addEventListener("click", () => window.__gsiConfig.callback({ credential: "e2e.synthetic.token" })); parent.appendChild(b); },
  disableAutoSelect() {} } } };`;

const browser = await chromium.launch({ executablePath: process.env.E2E_CHROME ?? "/usr/bin/google-chrome", headless: true });
const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, locale: "pt-BR" });
await context.route("https://accounts.google.com/gsi/client", (route) => route.fulfill({ status: 200, contentType: "text/javascript", body: STUB }));
await context.addInitScript(() => { window.__csp = []; document.addEventListener("securitypolicyviolation", (e) => window.__csp.push(e.violatedDirective)); });
const page = await context.newPage();
page.on("console", (m) => m.type() === "error" && problems.push(m.text()));
page.on("pageerror", (e) => problems.push(e.message));
try {
  step("webhook sem token recusado", (await fetch(`${API}/api/webhooks/evolution`, { method: "POST", body: "{}" })).status === 401);
  step("queda da conexão registrada", (await hook({ event: "connection.update", data: { state: "close" } })) === 200);
  step("cliente fala com o bot", (await hook(message("oi"))) === 200);
  step("equipe responde pelo celular", (await hook(message("Oi! Aqui é a Munique.", true))) === 200);

  await page.goto(`${SITE}/admin`);
  await page.getByRole("button", { name: "Entrar com Google (stub)" }).click();
  await page.getByRole("heading", { name: "Reservas", level: 2 }).waitFor();
  const banner = page.getByText("O WhatsApp da clínica está sem conexão.");
  await banner.waitFor();
  step("aviso de desconexão no topo do painel", true);
  await page.getByRole("button", { name: "Ver integrações" }).click();
  await page.getByRole("heading", { name: "Integrações", level: 2 }).waitFor();
  const section = await page.locator("main").textContent();
  step("estado do WhatsApp e instruções", section.includes("Desconectado") && section.includes("QR Code") && section.includes("#bot"));
  step("conversa com a equipe contada", /bot pausado\):\s*1/.test(section), section.match(/bot pausado\):\s*\d+/)?.[0]);
  step("agenda e links configurados", section.includes("Conta de serviço configurada.") || section.includes("Não configurado: horários") );
  await page.screenshot({ path: (process.env.E2E_OUTPUT ?? new URL("../.output/", import.meta.url).pathname) + "integracoes-1280.png", fullPage: true });

  await hook({ event: "connection.update", data: { state: "open" } });
  await hook(message("#bot", true));
  await page.getByRole("button", { name: "Recarregar" }).click();
  await page.waitForFunction(() => document.body.textContent.includes("Conectado"));
  const after = await page.locator("body").textContent();
  step("reconexão some com o aviso e #bot devolve a conversa", !after.includes("está sem conexão") && /bot pausado\):\s*0/.test(after));
  await page.setViewportSize({ width: 390, height: 844 });
  step("390px sem rolagem horizontal", (await page.evaluate(() => document.documentElement.scrollWidth)) <= 390);
} catch (error) {
  step("roteiro", false, String(error).slice(0, 300));
}
const csp = await page.evaluate(() => window.__csp);
step("violações de CSP", csp.length === 0, csp.join(","));
step("erros de console", problems.length === 0, problems.join(" | ").slice(0, 300));
await browser.close();
console.log(`${steps.filter(Boolean).length}/${steps.length} etapas aprovadas`);
process.exitCode = steps.every((item) => item === true || item?.ok === true) ? 0 : 1;
