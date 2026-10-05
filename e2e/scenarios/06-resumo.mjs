// Synthetic E2E: metrics tab, attendance and booking history. Run through e2e/run.mjs.
import { chromium } from "playwright-core";

const SITE = (process.env.E2E_SITE ?? "http://127.0.0.1:3100");
const OUT = process.env.E2E_OUTPUT ?? new URL("../.output/", import.meta.url).pathname;
const steps = [];
const problems = [];
function step(name, ok, detail = "") {
  steps.push(ok);
  console.log(`${ok ? "PASS" : "FAIL"} ${name}${detail ? ` — ${detail}` : ""}`);
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
const tile = async (label) => Number((await page.locator("dt", { hasText: label }).locator("xpath=following-sibling::dd[1]").textContent()).replace(/\D/g, ""));
try {
  await page.goto(`${SITE}/admin`);
  await page.getByRole("button", { name: "Entrar com Google (stub)" }).click();
  await page.getByRole("heading", { name: "Reservas", level: 2 }).waitFor();
  await page.getByRole("button", { name: "Resumo", exact: true }).click();
  await page.getByText("Reservas pedidas").waitFor();
  const requested = await tile("Reservas pedidas");
  step("indicadores do período", requested === 5 && (await tile("Sinais confirmados")) === 2, `pedidas=${requested}`);
  const origin = await page.locator("table").first().textContent();
  step("origem e procura em tabelas", origin.includes("Outros/equipe") && (await page.locator("main").textContent()).includes("Synthetic procedure"));
  await page.getByRole("button", { name: "7 dias" }).click();
  await page.waitForFunction(() => document.querySelector('[aria-pressed="true"]')?.textContent === "7 dias");
  step("troca de período", (await tile("Reservas pedidas")) === 5);
  await page.screenshot({ path: `${OUT}resumo-1280.png`, fullPage: true });

  await page.getByRole("button", { name: "Reservas", exact: true }).click();
  await page.getByRole("button", { name: "Histórico" }).click();
  const past = page.locator("li", { hasText: "Cliente Sintética Passada" }).first();
  await past.waitFor();
  step("atendimento passado com origem", (await past.textContent()).includes("Origem: Equipe/outros"));
  await past.getByRole("button", { name: "Compareceu" }).click();
  await page.waitForFunction(() => document.body.textContent.includes("Comparecimento registrado."));
  const updated = page.locator("li", { hasText: "Cliente Sintética Passada" }).first();
  await updated.getByText("Comparecimento: Compareceu").waitFor();
  step("comparecimento registrado e botões somem", (await updated.getByRole("button", { name: "Faltou" }).count()) === 0);
  await updated.getByText("Histórico", { exact: true }).click();
  await updated.getByText("Compareceu · equipe").waitFor();
  const history = await updated.locator("ol").textContent();
  step("histórico com etapas e quem agiu", history.includes("Reserva pedida") && history.includes("Sinal conferido · equipe") && history.includes("Confirmada na agenda · sistema"));

  await page.getByRole("button", { name: "Resumo", exact: true }).click();
  await page.getByText("Compareceram").waitFor();
  step("resumo conta o comparecimento", (await tile("Compareceram")) === 1 && (await tile("Faltaram")) === 0);
  await page.setViewportSize({ width: 390, height: 844 });
  step("390px sem rolagem horizontal", (await page.evaluate(() => document.documentElement.scrollWidth)) <= 390);
} catch (error) {
  step("roteiro", false, String(error).slice(0, 300));
  await page.screenshot({ path: `${OUT}failure-resumo.png`, fullPage: true });
}
step("violações de CSP", (await page.evaluate(() => window.__csp)).length === 0);
step("erros de console", problems.length === 0, problems.join(" | ").slice(0, 300));
await browser.close();
console.log(`${steps.filter(Boolean).length}/${steps.length} etapas aprovadas`);
process.exitCode = steps.every((item) => item === true || item?.ok === true) ? 0 : 1;
