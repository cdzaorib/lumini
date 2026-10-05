// Synthetic E2E for the client self-service page. Run through e2e/run.mjs.
import { chromium } from "playwright-core";

const SITE = (process.env.E2E_SITE ?? "http://127.0.0.1:3100");
const API = process.env.E2E_API ?? "http://127.0.0.1:8100";
const OUT = process.env.E2E_OUTPUT ?? new URL("../.output/", import.meta.url).pathname;
const AUTH = { Authorization: "Bearer e2e.synthetic.token" };
const steps = [];
const problems = [];
const apiCalls = [];

function step(name, ok, detail = "") {
  steps.push({ name, ok });
  console.log(`${ok ? "PASS" : "FAIL"} ${name}${detail ? ` — ${detail}` : ""}`);
}

const STUB = `
window.google = { accounts: { id: {
  initialize(config) { window.__gsiConfig = config; },
  renderButton(parent) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = "Entrar com Google (stub)";
    button.addEventListener("click", () => window.__gsiConfig.callback({ credential: "e2e.synthetic.token" }));
    parent.appendChild(button);
  },
  disableAutoSelect() {},
} } };`;

async function bookings() {
  const response = await fetch(`${API}/api/admin/bookings?scope=upcoming`, { headers: AUTH });
  return response.json();
}
async function linkFor(id) {
  const response = await fetch(`${API}/api/admin/bookings/${id}/manage-link`, { method: "POST", headers: AUTH });
  return (await response.json()).url;
}

const browser = await chromium.launch({ executablePath: process.env.E2E_CHROME ?? "/usr/bin/google-chrome", headless: true });
const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, locale: "pt-BR", timezoneId: "Asia/Tokyo" });
await context.route("https://accounts.google.com/gsi/client", (route) => route.fulfill({ status: 200, contentType: "text/javascript", body: STUB }));
await context.addInitScript(() => {
  window.__csp = [];
  document.addEventListener("securitypolicyviolation", (event) => window.__csp.push(event.violatedDirective + " " + event.blockedURI));
});
const page = await context.newPage();
page.on("console", (message) => message.type() === "error" && problems.push(message.text()));
page.on("pageerror", (error) => problems.push(error.message));
page.on("request", (request) => {
  if (request.url().startsWith(`${API}/api/public/`)) apiCalls.push({ url: request.url(), auth: request.headers().authorization ?? "" });
});
const notice = page.locator('[role="status"][aria-live="polite"]');
async function expectNotice(text, name) {
  try {
    await page.waitForFunction((expected) => [...document.querySelectorAll('[role="status"]')].some((node) => node.textContent?.includes(expected)), text, { timeout: 8000 });
    step(name, true);
  } catch {
    step(name, false, `notice="${await notice.first().textContent()}"`);
  }
}

try {
  // Staff generate the link from the panel.
  await page.goto(`${SITE}/admin`);
  await page.getByRole("button", { name: "Entrar com Google (stub)" }).click();
  await page.getByRole("heading", { name: "Reservas", level: 2 }).waitFor();
  const paid = page.locator("li", { hasText: "Cliente Sintética Confirmada" }).first();
  await paid.getByText("Link de autoatendimento para a cliente").click();
  await paid.getByRole("button", { name: "Gerar link" }).click();
  const field = paid.locator('input[readonly]');
  await field.waitFor();
  const link = await field.inputValue();
  step("painel gera link com token no fragmento", link.startsWith(`${SITE}/reserva#`) && /#[0-9a-f]{42}[A-Za-z0-9_-]{43}$/.test(link), link.replace(/#.*/, "#…"));

  // Client opens it (browser in Tokyo: times must still be Brasília).
  await page.goto(link);
  await page.getByRole("heading", { name: "Synthetic procedure", level: 1 }).waitFor();
  const body = await page.locator("main").textContent();
  step("resumo da reserva confirmada", body.includes("Agendamento confirmado.") && body.includes("das 10:00 às 11:00") && body.includes("Com Synthetic professional"), body.slice(0, 160));
  step("sem dados de contato na página", !body.includes("Cliente Sintética") && !body.includes("+55219"));
  await page.screenshot({ path: `${OUT}reserva-1280.png`, fullPage: true });

  const target = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Sao_Paulo" }).format(new Date(Date.now() + 3 * 86400000));
  await page.getByLabel("Escolha o dia").fill(target);
  await page.getByRole("button", { name: "Ver horários livres" }).click();
  const radios = page.getByRole("radio");
  await radios.first().waitFor();
  step("horários livres para reagendar", (await radios.count()) > 10, `${await radios.count()} opções`);
  await radios.nth(6).check();
  await page.getByRole("button", { name: "Confirmar novo horário" }).click();
  await expectNotice("O sinal continua valendo", "reagendamento pela cliente");
  const newHash = await page.evaluate(() => window.location.hash);
  step("link trocado para a nova reserva", newHash.length === 86 && link.split("#")[1] !== newHash.slice(1));
  const after = await page.locator("main").textContent();
  step("nova reserva sem novo reagendamento nem cancelamento online", after.includes("Estamos reservando o seu horário.") && !after.includes("Reagendar") && after.includes("fale com a clínica"));
  await page.reload();
  await page.getByRole("heading", { name: "Synthetic procedure", level: 1 }).waitFor();
  step("recarregar mantém a nova reserva", (await page.locator("main").textContent()).includes("Estamos reservando"));

  await page.goto(link);
  await page.getByText("Esta reserva foi cancelada.").waitFor();
  step("link antigo mostra a reserva original encerrada", true);

  // Unpaid hold: the client can give it back.
  const waiting = (await bookings()).find((item) => item.contact.name === "Cliente Sintética Cancelar");
  await page.goto(await linkFor(waiting.id));
  await page.getByText("Horário reservado, aguardando o sinal.").waitFor();
  const held = (await page.locator("main").textContent()).replace(/\u00a0/g, " ");
  step("reserva aguardando sinal: prazo e valor, sem reagendar", held.includes("R$ 50,00") && held.includes("reservado até") && !held.includes("Reagendar"), held.slice(0, 260));
  await page.getByRole("button", { name: "Quero cancelar" }).click();
  await page.getByRole("button", { name: "Confirmar cancelamento" }).click();
  await expectNotice("Reserva cancelada", "cancelamento pela cliente");
  const focused = await page.evaluate(() => document.activeElement?.id);
  step("foco no título após a ação", focused === "sua-reserva", focused);

  await page.goto(`${SITE}/reserva#nao-e-um-token`);
  await page.getByRole("heading", { name: "Não conseguimos abrir esta reserva" }).waitFor();
  step("link inválido explicado sem consultar a API", apiCalls.length > 0);
  const callsBefore = apiCalls.length;
  await page.waitForTimeout(300);
  step("nenhuma chamada para token malformado", apiCalls.length === callsBefore);

  step(
    "token só no cabeçalho Authorization, nunca na URL da API",
    apiCalls.every((call) => !/[0-9a-f]{42}[A-Za-z0-9_-]{43}/.test(call.url) && /^Bearer [0-9a-f]{42}/.test(call.auth)),
    `${apiCalls.length} chamadas`,
  );

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(newHash ? `${SITE}/reserva${newHash}` : link);
  await page.getByRole("heading", { name: "Synthetic procedure", level: 1 }).waitFor();
  const width = await page.evaluate(() => document.documentElement.scrollWidth);
  await page.screenshot({ path: `${OUT}reserva-390.png`, fullPage: true });
  step("390px sem rolagem horizontal", width <= 390, String(width));
} catch (error) {
  step("roteiro", false, String(error).slice(0, 400));
  await page.screenshot({ path: `${OUT}failure-reserva.png`, fullPage: true });
}

const csp = await page.evaluate(() => window.__csp);
step("violações de CSP", csp.length === 0, csp.join(" | "));
step("erros de console", problems.length === 0, problems.join(" | ").slice(0, 400));
await browser.close();
console.log(`${steps.filter((item) => item.ok).length}/${steps.length} etapas aprovadas`);
process.exitCode = steps.every((item) => item === true || item?.ok === true) ? 0 : 1;
