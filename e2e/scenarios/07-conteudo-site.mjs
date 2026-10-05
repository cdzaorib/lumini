// Synthetic E2E: clinic edits site content in the panel; the landing shows it. Run through e2e/run.mjs.
import { chromium } from "playwright-core";

const SITE = (process.env.E2E_SITE ?? "http://127.0.0.1:3100");
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
await context.addInitScript(() => { window.__csp = []; document.addEventListener("securitypolicyviolation", (e) => window.__csp.push(e.violatedDirective + " " + e.blockedURI)); });
const page = await context.newPage();
page.on("console", (m) => m.type() === "error" && !m.text().includes("422") && problems.push(m.text()));
page.on("pageerror", (e) => problems.push(e.message));
const notice = async (text) => page.waitForFunction((t) => [...document.querySelectorAll('[role="status"]')].some((n) => n.textContent.includes(t)), text, { timeout: 8000 });
try {
  await page.goto(`${SITE}/admin`);
  await page.getByRole("button", { name: "Entrar com Google (stub)" }).click();
  await page.getByRole("heading", { name: "Reservas", level: 2 }).waitFor();
  await page.getByRole("button", { name: "Site", exact: true }).click();
  await page.getByRole("button", { name: "Salvar conteúdo do site" }).waitFor();
  await page.getByLabel("Endereço (rua e número)").fill("Rua Sintética, 10");
  await page.getByLabel("Bairro e cidade").fill("Centro, Mangaratiba - RJ");
  await page.getByLabel("Link do Google Maps (https)").fill("https://maps.example.invalid/lumini");
  await page.getByLabel("WhatsApp da clínica com DDD").fill("(21) 98765-4321");
  await page.getByLabel("Horários de funcionamento (um por linha)").fill("Segunda a sexta, 9h às 18h\nSábado, 9h às 13h");
  await page.getByLabel("Diferenciais").fill("Atendimento individual e acolhedor\nResultado garantido em uma sessão");
  await page.getByLabel("Como pagar o sinal (ex.: chave Pix e titular)").fill("Pix sintético: chave-ficticia-e2e");
  await page.getByRole("button", { name: "Salvar conteúdo do site" }).click();
  await notice("promete resultado");
  step("promessa de resultado recusada com explicação", true);
  await page.getByLabel("Diferenciais").fill("Atendimento individual e acolhedor\nProfissionais identificadas e habilitadas");
  await page.getByRole("button", { name: "Adicionar pergunta" }).click();
  await page.getByLabel("Pergunta 1").fill("Preciso fazer avaliação?");
  await page.getByLabel("Resposta 1").fill("Alguns procedimentos começam com uma avaliação com a profissional.");
  step("depoimento exige confirmação de autorização", await page.getByRole("button", { name: "Adicionar depoimento autorizado" }).isDisabled());
  await page.getByLabel(/Tenho a autorização por escrito/).check();
  await page.getByRole("button", { name: "Adicionar depoimento autorizado" }).click();
  await page.getByLabel("Depoimento 1").fill("Fui muito bem acolhida.");
  await page.getByLabel(/Como assinar/).fill("Cliente S., Mangaratiba");
  await page.getByRole("button", { name: "Salvar conteúdo do site" }).click();
  await notice("Conteúdo do site salvo");
  step("conteúdo salvo no painel", true);

  let html = "";
  for (let attempt = 0; attempt < 15; attempt += 1) {
    await page.goto(`${SITE}/`);
    html = await page.content();
    if (html.includes("Atendimento individual e acolhedor")) break;
    await page.waitForTimeout(5000); // public content is cached for up to 60 s
  }
  const main = (await page.locator("main").textContent()).replace(/ /g, " ");
  step("diferenciais e depoimento no site", main.includes("Atendimento individual e acolhedor") && main.includes("Fui muito bem acolhida.") && main.includes("Cliente S., Mangaratiba"));
  step("perguntas frequentes no site", main.includes("Preciso fazer avaliação?"));
  step("endereço, mapa e horários", main.includes("Rua Sintética, 10") && main.includes("Sábado, 9h às 13h") && (await page.getByRole("link", { name: "Ver no mapa" }).getAttribute("href")) === "https://maps.example.invalid/lumini");
  const wa = await page.getByRole("link", { name: "Conversar no WhatsApp" }).getAttribute("href");
  step("botão de WhatsApp com mensagem inicial", wa?.startsWith("https://wa.me/5521987654321?text="), wa);
  step("pendências resolvidas somem", !main.includes("Pendente da clínica: endereço") && !main.includes("Pendente da clínica: perguntas"));
  step("instruções do sinal nunca no site", !html.includes("chave-ficticia-e2e"));
  const jsonld = await page.locator('script[type="application/ld+json"]').evaluate((node) => ({ nonce: node.nonce, text: node.textContent }));
  step("dados estruturados de negócio local com nonce", jsonld.nonce.length > 10 && JSON.parse(jsonld.text).address.streetAddress === "Rua Sintética, 10");
} catch (error) {
  step("roteiro", false, String(error).slice(0, 300));
}
const csp = await page.evaluate(() => window.__csp);
step("violações de CSP", csp.length === 0, csp.join(" | "));
step("erros de console (além do 422 intencional)", problems.length === 0, problems.join(" | ").slice(0, 300));
await browser.close();
console.log(`${steps.filter(Boolean).length}/${steps.length} etapas aprovadas`);
process.exitCode = steps.every((item) => item === true || item?.ok === true) ? 0 : 1;
