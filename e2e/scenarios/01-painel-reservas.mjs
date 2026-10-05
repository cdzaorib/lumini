// Synthetic E2E for /admin Reservas + Agenda. Run through e2e/run.mjs.
import { chromium } from "playwright-core";

const BASE = (process.env.E2E_SITE ?? "http://127.0.0.1:3100") + "/admin";
const OUT = process.env.E2E_OUTPUT ?? new URL("../.output/", import.meta.url).pathname;
const steps = [];
const problems = [];

function step(name, ok, detail = "") {
  steps.push({ name, ok, detail });
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
  disableAutoSelect() { window.__disabled = true; },
} } };`;

const browser = await chromium.launch({ executablePath: process.env.E2E_CHROME ?? "/usr/bin/google-chrome", headless: true });
const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, locale: "pt-BR", timezoneId: "Europe/Lisbon" });
await context.route("https://accounts.google.com/gsi/client", (route) =>
  route.fulfill({ status: 200, contentType: "text/javascript", body: STUB }),
);
await context.addInitScript(() => {
  window.__csp = [];
  document.addEventListener("securitypolicyviolation", (event) => window.__csp.push(event.violatedDirective + " " + event.blockedURI));
});
const page = await context.newPage();
let refusals = 0; // intended API refusals are logged by Chrome as failed resource loads
page.on("console", (message) => {
  if (message.type() !== "error") return;
  if (message.text().includes("status of 409 (Conflict)")) refusals += 1;
  else problems.push(`console: ${message.text()}`);
});
page.on("pageerror", (error) => problems.push(`pageerror: ${error.message}`));

const notice = page.locator('[role="status"]');
async function expectNotice(text, name) {
  try {
    await page.waitForFunction(
      (expected) => document.querySelector('[role="status"]')?.textContent?.includes(expected),
      text,
      { timeout: 8000 },
    );
    step(name, true);
  } catch {
    step(name, false, `notice="${await notice.textContent()}"`);
  }
}
const card = (name) => page.locator("li", { hasText: name }).first();

try {
  await page.goto(BASE);
  await page.getByRole("button", { name: "Entrar com Google (stub)" }).click();
  await page.getByRole("heading", { name: "Reservas", level: 2 }).waitFor();
  const current = await page.locator('nav[aria-label="Seções do painel"] [aria-current="page"]').textContent();
  step("login abre Reservas por padrão", current === "Reservas", current);
  const groups = await page.locator("section[aria-label] h3").allTextContents();
  step(
    "grupos de pendências",
    JSON.stringify(groups) === JSON.stringify(["Precisam de decisão (1)", "Aguardando sinal (2)", "Confirmadas (1)"]),
    groups.join(" | "),
  );
  const waiting = card("Cliente Sintética Aguardando");
  step("contato e prazo visíveis para a equipe", (await waiting.textContent()).includes("+5521900000001") && (await waiting.textContent()).includes("Prazo do sinal"));
  // Times must be in Brasília even with a browser in another time zone.
  step("horário em Brasília", (await waiting.locator("h4").textContent()).includes("10:00–11:00"), await waiting.locator("h4").textContent());
  await page.screenshot({ path: `${OUT}reservas-1280.png`, fullPage: true });

  // Deposit: wrong value refused by the API, exact value accepted.
  await waiting.getByText("Confirmar sinal recebido").click();
  await waiting.getByLabel("Valor que entrou na conta (R$)").fill("49,99");
  await waiting.getByRole("checkbox").check();
  await waiting.getByRole("button", { name: "Confirmar sinal" }).click();
  await expectNotice("diferente do sinal previsto", "valor divergente recusado");
  await waiting.getByLabel("Valor que entrou na conta (R$)").fill("50,00");
  await waiting.getByRole("button", { name: "Confirmar sinal" }).click();
  await expectNotice("Sinal confirmado", "sinal exato confirmado");
  await page.locator("section[aria-label='Atualizando o Google Agenda']").getByText("Cliente Sintética Aguardando").waitFor();
  step("reserva passa para atualização da agenda", true);
  const focused = await page.evaluate(() => document.activeElement?.id || document.activeElement?.tagName);
  step("foco não cai no body após ação", focused !== "BODY", focused);

  // Conflict released by staff.
  const conflict = card("Cliente Sintética Conflito");
  step("motivo do conflito explicado", (await conflict.textContent()).includes("Outro compromisso apareceu"));
  await conflict.getByText("Liberar horário").click();
  await conflict.getByRole("button", { name: "Confirmar liberação" }).click();
  await expectNotice("Horário liberado", "conflito liberado");

  // Cancellation.
  const cancel = card("Cliente Sintética Cancelar");
  await cancel.getByText("Cancelar reserva").click();
  await cancel.getByRole("button", { name: "Confirmar cancelamento" }).click();
  await expectNotice("Reserva cancelada", "reserva cancelada");

  // Reschedule a confirmed booking through the availability preview.
  const paid = card("Cliente Sintética Confirmada");
  await paid.getByText("Reagendar").click();
  const target = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Sao_Paulo" }).format(new Date(Date.now() + 3 * 86400000));
  await paid.getByLabel("Dia").fill(target);
  await paid.getByRole("button", { name: "Ver horários livres" }).click();
  const radios = paid.getByRole("radio");
  await radios.first().waitFor();
  step("horários livres para reagendar", (await radios.count()) > 10, `${await radios.count()} opções`);
  await radios.nth(4).check();
  await paid.getByRole("button", { name: "Reagendar para o horário escolhido" }).click();
  await expectNotice("Reserva reagendada", "reagendamento pela equipe");

  await page.getByRole("button", { name: "Histórico" }).click();
  await page.getByText("Histórico recente").waitFor();
  const history = await page.locator("main").textContent();
  step(
    "histórico com motivos",
    ["Horário liberado após conflito.", "Cancelada pela equipe.", "Reagendada; a nova reserva aparece na lista."].every((text) => history.includes(text)),
  );
  await page.getByRole("button", { name: "Pendentes e próximas" }).click();
  await page.getByText("Atualizando o Google Agenda").waitFor();

  // Agenda.
  await page.getByRole("button", { name: "Agenda", exact: true }).click();
  await page.getByLabel("Profissional").selectOption({ label: "Synthetic professional" });
  await page.getByRole("button", { name: "Salvar agenda" }).waitFor();
  const calendarField = page.getByLabel("ID do Google Agenda");
  step("agenda carregada", (await calendarField.inputValue()) === "synthetic-calendar@group.calendar.google.com");
  step("sete dias com uma faixa", (await page.locator('input[type="time"]').count()) === 14);
  await page.getByRole("button", { name: "Adicionar faixa em segunda" }).click();
  await page.getByRole("button", { name: "Salvar agenda" }).click();
  const alert = page.locator('form [role="alert"]');
  await alert.waitFor();
  step("sobreposição barrada no navegador", (await alert.textContent()) === "Segunda: há faixas sobrepostas.", await alert.textContent());
  await page.getByRole("button", { name: "Remover Segunda, faixa 2" }).click();
  await page.getByLabel("Domingo, faixa 1: fim").fill("12:00");
  await page.getByRole("button", { name: "Salvar agenda" }).click();
  const reloaded = page.waitForResponse((response) => response.url().endsWith("/schedule") && response.request().method() === "GET");
  await expectNotice("Agenda de Synthetic professional salva", "agenda salva");
  await reloaded;
  await page.waitForTimeout(200);
  step("agenda recarregada com a alteração", (await page.getByLabel("Domingo, faixa 1: fim").inputValue()) === "12:00");
  await calendarField.fill("synthetic-other@group.calendar.google.com");
  await page.getByRole("button", { name: "Salvar agenda" }).click();
  await expectNotice("reservas ativas ou remoções pendentes", "troca de calendário bloqueada com reservas ativas");

  await page.getByRole("button", { name: "Ver prévia" }).click();
  await page.locator("dl dt").first().waitFor();
  const days = await page.locator("dl dt").count();
  step("prévia de horários", days >= 6, `${days} dias com horários`);
  await page.screenshot({ path: `${OUT}agenda-1280.png`, fullPage: true });

  // Narrow viewport.
  await page.setViewportSize({ width: 390, height: 844 });
  const agendaWidth = await page.evaluate(() => document.documentElement.scrollWidth);
  await page.screenshot({ path: `${OUT}agenda-390.png`, fullPage: true });
  await page.getByRole("button", { name: "Reservas", exact: true }).click();
  await page.getByRole("heading", { name: "Reservas", level: 2 }).waitFor();
  const bookingsWidth = await page.evaluate(() => document.documentElement.scrollWidth);
  await page.screenshot({ path: `${OUT}reservas-390.png`, fullPage: true });
  step("390px sem rolagem horizontal", agendaWidth <= 390 && bookingsWidth <= 390, `${agendaWidth}/${bookingsWidth}`);

  await page.getByRole("button", { name: "Sair" }).click();
  await page.getByRole("heading", { name: "Entrar no painel" }).waitFor();
  const stored = await page.evaluate(() => [localStorage.length, sessionStorage.length, document.cookie, window.__disabled === true]);
  step("sair limpa a sessão", stored[0] === 0 && stored[1] === 0 && stored[2] === "" && stored[3], JSON.stringify(stored));
} catch (error) {
  step("roteiro", false, String(error).slice(0, 400));
  await page.screenshot({ path: `${OUT}failure.png`, fullPage: true });
}

const csp = await page.evaluate(() => window.__csp);
step("violações de CSP", csp.length === 0, csp.join(" | "));
step("409 só nas recusas intencionais (2)", refusals === 2, String(refusals));
step("erros de console", problems.length === 0, problems.join(" | ").slice(0, 600));
await browser.close();
console.log(`${steps.filter((item) => item.ok).length}/${steps.length} etapas aprovadas`);
process.exitCode = steps.every((item) => item === true || item?.ok === true) ? 0 : 1;
