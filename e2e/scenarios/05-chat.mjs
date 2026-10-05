// Synthetic E2E for the website chat. Run through e2e/run.mjs.
import { chromium } from "playwright-core";

const SITE = (process.env.E2E_SITE ?? "http://127.0.0.1:3100");
const API = process.env.E2E_API ?? "http://127.0.0.1:8100";
const OUT = process.env.E2E_OUTPUT ?? new URL("../.output/", import.meta.url).pathname;
const steps = [];
const problems = [];
const typed = [];
function step(name, ok, detail = "") {
  steps.push(ok);
  console.log(`${ok ? "PASS" : "FAIL"} ${name}${detail ? ` — ${detail}` : ""}`);
}
const browser = await chromium.launch({ executablePath: process.env.E2E_CHROME ?? "/usr/bin/google-chrome", headless: true });
const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, locale: "pt-BR", timezoneId: "America/New_York" });
await context.addInitScript(() => { window.__csp = []; document.addEventListener("securitypolicyviolation", (e) => window.__csp.push(e.violatedDirective + " " + e.blockedURI)); });
const page = await context.newPage();
page.on("console", (m) => m.type() === "error" && problems.push(m.text()));
page.on("pageerror", (e) => problems.push(e.message));
page.on("response", (r) => r.status() === 404 && console.log("HTTP404", r.request().method(), r.url().replace(/[A-Za-z0-9_-]{40,}/g, "…")));
page.on("request", (r) => r.url().includes("/api/public/chat/") && typed.push({ url: r.url(), auth: r.headers().authorization ?? "" }));
const lastBot = async () => (await page.locator('[role="log"] li.self-start').last().textContent()) ?? "";
async function quick(label) {
  const before = await page.locator('[role="log"] li').count();
  await page.getByRole("group", { name: "Respostas rápidas" }).getByRole("button", { name: label }).first().click();
  await page.waitForFunction((n) => document.querySelectorAll('[role="log"] li').length >= n + 2, before);
}
async function type(text) {
  const before = await page.locator('[role="log"] li').count();
  await page.getByLabel("Sua mensagem").fill(text);
  await page.getByRole("button", { name: "Enviar" }).click();
  await page.waitForFunction((n) => document.querySelectorAll('[role="log"] li').length >= n + 2, before);
}

try {
  await page.goto(`${SITE}/atendimento`);
  await page.getByRole("button", { name: /Agendar um horário/ }).waitFor();
  step("menu do atendimento com respostas rápidas", (await lastBot()).includes("atendimento automático da Lumini"));
  await quick(/Agendar um horário/);
  step("lista de procedimentos", (await lastBot()).includes("Synthetic procedure"));
  await quick(/Synthetic procedure/);
  await quick(/^1\. Agendar/);
  step("pergunta sobre condição de saúde", (await lastBot()).includes("condição de saúde"));
  await quick(/Não, quero ver os horários/);
  const days = await lastBot();
  step("dias com horários em Brasília", days.includes("Escolha o dia"), days.split("\n")[1]);
  await quick(/^2\./);
  await quick(/^1\./);
  step("pergunta o nome", (await lastBot()).includes("qual nome"));
  await type("Clara Sintética");
  step("pede WhatsApp com aviso de uso", (await lastBot()).includes("WhatsApp com DDD") && (await lastBot()).includes("privacidade"));
  await type("(21) 96666-5555");
  const summary = await lastBot();
  step("resumo com sinal antes de confirmar", summary.includes("Confirmando: Synthetic procedure") && summary.includes("R$ 50,00"));
  await quick(/Confirmar reserva/);
  step("reserva pedida", (await lastBot()).includes("Estou reservando seu horário"));
  const bookings = await (await fetch(`${API}/api/admin/bookings?scope=upcoming`, { headers: { Authorization: "Bearer e2e.synthetic.token" } })).json();
  const created = bookings.find((item) => item.contact.name === "Clara Sintética");
  step("reserva aparece para a equipe com o WhatsApp informado", created?.contact.phone === "+5521966665555" && created?.status === "pending_calendar");

  await type("estou grávida, posso fazer?");
  step("saúde vai para a equipe sem perguntas", (await lastBot()).includes("diretamente com a profissional"));
  step("token só no cabeçalho, nunca na URL", typed.every((call) => !call.url.includes("token")) && typed.filter((c) => c.url.endsWith("/messages")).every((c) => /^Bearer [A-Za-z0-9_-]{43}$/.test(c.auth)));
  await page.screenshot({ path: `${OUT}chat-1280.png`, fullPage: true });

  await page.goto(`${SITE}/`);
  await page.getByRole("button", { name: "Atendimento" }).click();
  const dialog = page.getByRole("dialog", { name: "Atendimento Lumini" });
  await dialog.getByRole("button", { name: /Conhecer os procedimentos/ }).waitFor();
  step("widget abre o atendimento na landing", true);
  await dialog.getByRole("button", { name: "Fechar" }).click();
  step("widget fecha", !(await dialog.isVisible()));

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${SITE}/atendimento`);
  await page.getByRole("button", { name: /Agendar um horário/ }).waitFor();
  const width = await page.evaluate(() => document.documentElement.scrollWidth);
  await page.screenshot({ path: `${OUT}chat-390.png` });
  step("390px sem rolagem horizontal", width <= 390, String(width));
} catch (error) {
  step("roteiro", false, String(error).slice(0, 300));
  await page.screenshot({ path: `${OUT}failure-chat.png`, fullPage: true });
}
const csp = await page.evaluate(() => window.__csp);
step("violações de CSP", csp.length === 0, csp.join(" | "));
step("erros de console", problems.length === 0, problems.join(" | ").slice(0, 300));
await browser.close();
console.log(`${steps.filter(Boolean).length}/${steps.length} etapas aprovadas`);
process.exitCode = steps.every((item) => item === true || item?.ok === true) ? 0 : 1;
