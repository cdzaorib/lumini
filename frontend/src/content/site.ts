// Fixed identity of the site. Everything the clinic provides (address, hours, WhatsApp, FAQ,
// testimonials...) is edited in the panel and read from the API (lib/public/site.ts).

export const site = {
  name: "Lumini Estética e Saúde",
  region: "Mangaratiba e Costa Verde (RJ)", // SEO target approved in the plan
} as const;

/** Preview (default) shows what is missing; production hides it. */
export function sitePreview(): boolean {
  return process.env.LUMINI_SITE_STAGE !== "production";
}

/** Search engines stay out until the launch gate (LUMINI_SITE_PUBLIC=true). */
export function siteIndexable(): boolean {
  return process.env.LUMINI_SITE_PUBLIC === "true";
}
