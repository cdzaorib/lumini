// Synthetic E2E for the public site + contact requests in the panel. Run through e2e/run.mjs.
import { chromium } from "playwright-core";

const SITE = (process.env.E2E_SITE ?? "http://127.0.0.1:3100");
const OUT = process.env.E2E_OUTPUT ?? new URL("../.output/", import.meta.url).pathname;
const steps = [];
const problems = [];
const leadPosts = [];
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
await context.addInitScript(() => { window.__csp = []; document.addEventListener("securitypolicyviolation", (e) => window.__csp.push(e.violatedDirective + " " + e.blockedURI)); });
const page = await context.newPage();
page.on("console", (m) => m.type() === "error" && problems.push(m.text()));
page.on("pageerror", (e) => problems.push(e.message));
page.on("request", (r) => r.url().endsWith("/api/public/leads") && leadPosts.push(r.postData()));

try {
  const response = await page.goto(SITE + "/");
  const headers = response.headers();
  step("site fechado para buscadores e com CSP", (headers["x-robots-tag"] ?? "").includes("noindex") && (headers["content-security-policy"] ?? "").includes("nonce-"));
  await page.getByRole("heading", { level: 1, name: "Tire suas dúvidas e agende sua avaliação" }).waitFor();
  const main = (await page.locator("main").textContent()).replace(/ /g, " ");
  step("procedimento publicado com regra de preço", main.includes("Synthetic procedure") && main.includes("Valor definido após avaliação"));
  step("profissional verificada com registro", main.includes("Synthetic professional") && main.includes("Registro: SYNTHETIC-REG"));
  step("pendências visíveis só como aviso de prévia", main.includes("Pendente da clínica: endereço e horários") && main.includes("diferenciais"));
  step("políticas de agendamento", main.includes("reservado por 2 horas") && main.includes("Com mais de 24 horas"));
  step("nenhum telefone, preço ou depoimento inventado", !/\(\d{2}\)\s?\d{4,5}-\d{4}/.test(main) && !main.includes("depoimento"));
  await page.screenshot({ path: `${OUT}site-1280.png`, fullPage: true });

  await page.getByRole("link", { name: "Saiba mais sobre Synthetic procedure" }).click();
  await page.getByRole("heading", { level: 1, name: "Synthetic procedure" }).waitFor();
  const detail = await page.locator("main").textContent();
  step("página do procedimento com conteúdo aprovado", detail.includes("Synthetic approved description") && detail.includes("Cuidados depois") && detail.includes("A indicação para você é sempre definida pela profissional"));
  const selected = await page.locator('select[name="service_id"]').inputValue();
  step("formulário já com o procedimento", selected.length === 36);

  await page.getByLabel("Seu nome").fill("Ana Sintética");
  await page.getByLabel("WhatsApp com DDD").fill("(21) 98877-6655");
  await page.getByRole("button", { name: "Quero ser contatada" }).click();
  await page.waitForTimeout(300);
  step("sem autorização de contato o envio não sai", leadPosts.length === 0);
  await page.getByRole("checkbox").first().check();
  await page.getByRole("button", { name: "Quero ser contatada" }).click();
  await page.getByText("Recebemos seu pedido.").waitFor();
  const sent = JSON.parse(leadPosts[0] ?? "{}");
  step("pedido enviado com consentimento e sem campo livre", sent.contact_consent === true && sent.marketing_consent === false && sent.website === "" && !("message" in sent));

  await page.goto(SITE + "/privacidade");
  step("privacidade marcada como rascunho", (await page.locator("main").textContent()).includes("Rascunho em revisão jurídica"));

  await page.goto(SITE + "/admin");
  await page.getByRole("button", { name: "Entrar com Google (stub)" }).click();
  await page.getByRole("heading", { name: "Reservas", level: 2 }).waitFor();
  await page.getByRole("button", { name: "Contatos", exact: true }).click();
  await page.getByRole("heading", { name: "Pedidos de contato", level: 2 }).waitFor();
  const card = page.locator("li", { hasText: "Ana Sintética" });
  await card.waitFor();
  const cardText = await card.textContent();
  step("pedido aparece para a equipe com WhatsApp", cardText.includes("+5521988776655") && cardText.includes("Synthetic procedure") && cardText.includes("não quer promoções"));
  const wa = await card.getByRole("link", { name: "+5521988776655" }).getAttribute("href");
  step("link abre conversa no WhatsApp", wa === "https://wa.me/5521988776655");
  await card.getByRole("button", { name: "Marcar como contatado" }).click();
  await page.getByText("Nenhum pedido nesta lista.").waitFor();
  await page.getByRole("button", { name: "Contatados" }).click();
  await page.locator("li", { hasText: "Ana Sintética" }).waitFor();
  step("status atualizado e filtrável", true);

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(SITE + "/");
  await page.getByRole("heading", { level: 1 }).waitFor();
  const widthHome = await page.evaluate(() => document.documentElement.scrollWidth);
  await page.screenshot({ path: `${OUT}site-390.png`, fullPage: true });
  await page.goto(SITE + "/procedimentos/nao-existe");
  const notFound = await page.getByRole("heading", { name: "Página não encontrada." }).isVisible();
  step("390px sem rolagem e 404 amigável", widthHome <= 390 && notFound, String(widthHome));
} catch (error) {
  step("roteiro", false, String(error).slice(0, 300));
  await page.screenshot({ path: `${OUT}failure-site.png`, fullPage: true });
}
const csp = await page.evaluate(() => window.__csp);
step("violações de CSP", csp.length === 0, csp.join(" | "));
const unexpected = problems.filter((text) => !text.includes("404 (Not Found)"));
step("erros de console", unexpected.length === 0, unexpected.join(" | ").slice(0, 300));
await browser.close();
console.log(`${steps.filter(Boolean).length}/${steps.length} etapas aprovadas`);
process.exitCode = steps.every((item) => item === true || item?.ok === true) ? 0 : 1;
