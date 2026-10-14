// Run with a local frontend configured with NEXT_PUBLIC_PLAUSIBLE_DOMAIN=synthetic.invalid.
// Uses the existing E2E browser dependency. Every analytics request is intercepted: no provider call.
// E2E_SITE=http://127.0.0.1:3117 node frontend/checks/analytics-consent.mjs
import assert from "node:assert/strict";
import { chromium } from "../../e2e/node_modules/playwright-core/index.mjs";

const site = process.env.E2E_SITE ?? "http://127.0.0.1:3117";
assert.ok(["127.0.0.1", "localhost"].includes(new URL(site).hostname), "Use a local synthetic frontend only");
const key = "lumini.analytics-consent.v1";
const events = [];
const cspErrors = [];
const browser = await chromium.launch({ executablePath: process.env.E2E_CHROME ?? "/usr/bin/google-chrome", headless: true });
const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
await context.addCookies([{ name: "synthetic_cookie", value: "must_not_send", domain: "plausible.io", path: "/", secure: true }]);
await context.route("https://plausible.io/api/event", (route) => {
  events.push({ payload: route.request().postDataJSON(), headers: route.request().headers() });
  return route.fulfill({ status: 202, contentType: "application/json", body: "{}", headers: { "access-control-allow-origin": "*" } });
});
await context.addInitScript(() => {
  window.__analyticsCsp = [];
  document.addEventListener("securitypolicyviolation", (event) => {
    window.__analyticsCsp.push(`${event.violatedDirective} ${event.blockedURI}`);
  });
});
const page = await context.newPage();
async function settle() { await page.waitForTimeout(250); }
async function preferences() {
  const details = page.locator("details", { has: page.getByText("Preferências de privacidade", { exact: true }) });
  if (!(await details.getAttribute("open")) && !(await details.evaluate((element) => element.open))) {
    await details.getByText("Preferências de privacidade", { exact: true }).click();
  }
  return details;
}
try {
  const response = await page.goto(`${site}/?synthetic_email=not-sent%40invalid.test#synthetic-token`);
  assert.ok(response.headers()["content-security-policy"].includes("https://plausible.io/api/event"));
  await page.getByRole("button", { name: "Aceitar estatísticas" }).waitFor();
  await settle();
  assert.equal(events.length, 0, "No requests before consent");
  assert.equal(await page.locator('script[src*="plausible"],script[src*="facebook"],img[src*="facebook"]').count(), 0);

  await page.getByRole("button", { name: "Recusar estatísticas" }).click();
  assert.equal(await page.evaluate((storageKey) => localStorage.getItem(storageKey), key), "rejected");
  await page.reload();
  await settle();
  assert.equal(events.length, 0, "Refusal survives reload");

  await preferences();
  await page.getByRole("button", { name: "Aceitar estatísticas" }).click();
  await page.waitForFunction((storageKey) => localStorage.getItem(storageKey) === "accepted", key);
  await settle();
  assert.equal(events.length, 1, "One pageview after explicit consent");
  assert.deepEqual(events[0].payload, { name: "pageview", domain: "synthetic.invalid", url: `${site}/` });
  assert.equal(events[0].headers.cookie, undefined, "No analytics cookies sent");
  assert.equal(events[0].headers.referer, undefined, "No referrer URL sent");
  await preferences();
  await page.getByRole("button", { name: "Revogar autorização" }).click();
  await page.reload();
  await settle();
  assert.equal(events.length, 1, "Revocation survives reload and stops measurement");
  assert.ok((await page.evaluate(() => document.documentElement.scrollWidth)) <= 390, "Mobile panel has no horizontal overflow");

  // Existing consent is insufficient on sensitive pages; their CSP is closed to the provider.
  await page.evaluate((storageKey) => localStorage.setItem(storageKey, "accepted"), key);
  for (const path of ["/atendimento", "/reserva#synthetic-token", "/admin", "/privacidade"]) {
    const privateResponse = await page.goto(`${site}${path}`);
    assert.ok(!privateResponse.headers()["content-security-policy"].includes("plausible.io"), `Closed CSP on ${path}`);
    await settle();
    assert.equal(events.length, 1, `No measurement on ${path}`);
    cspErrors.push(...await page.evaluate(() => window.__analyticsCsp));
  }
  assert.deepEqual(cspErrors, []);

  // Revocation in a second tab updates the first without another request.
  await page.goto(`${site}/`);
  await settle();
  assert.equal(events.length, 2, "Stored consent permits the next landing visit");
  const second = await context.newPage();
  await second.goto(`${site}/privacidade`);
  await second.getByText("Preferências de privacidade", { exact: true }).click();
  await second.getByRole("button", { name: "Revogar autorização" }).click();
  await preferences();
  await page.getByRole("status").filter({ hasText: "Estatísticas recusadas" }).waitFor();
  await page.reload();
  await settle();
  assert.equal(events.length, 2, "Cross-tab revocation persists");
  await second.close();

  // A previously saved grant cannot defeat a new refusal when persistence becomes unwritable.
  await page.evaluate((storageKey) => localStorage.setItem(storageKey, "accepted"), key);
  await page.reload();
  await settle();
  await page.evaluate(() => {
    Storage.prototype.setItem = () => { throw new DOMException("Synthetic quota", "QuotaExceededError"); };
  });
  await preferences();
  await page.getByRole("button", { name: "Revogar autorização" }).click();
  await preferences();
  await page.getByRole("status").filter({ hasText: "Estatísticas recusadas" }).waitFor();
  assert.notEqual(await page.evaluate((storageKey) => localStorage.getItem(storageKey), key), "accepted", "Quota failure removes an older grant");
  const afterQuotaRevocation = events.length;
  await page.reload();
  await settle();
  assert.equal(events.length, afterQuotaRevocation, "Quota failure cannot restore an older grant on reload");
  assert.deepEqual(await page.evaluate(() => window.__analyticsCsp), []);
  console.log("PASS: consent gate, refusal/revocation/reload/cross-tab, storage failure, safe payload, sensitive routes, CSP and 390px.");
} finally {
  await browser.close();
}
