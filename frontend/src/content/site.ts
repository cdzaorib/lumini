// Clinic facts for the public site. `null` = not provided yet: the section shows as pending in the
// preview and is hidden in production. Never fill these with guesses (AGENTS.md): only data the
// clinic sent and approved.

export type SiteContent = {
  name: string;
  region: string; // SEO target approved in the plan (Mangaratiba e Costa Verde/RJ)
  address: { street: string; city: string; mapsUrl: string | null } | null;
  hours: string[] | null;
  whatsapp: string | null; // E.164 of the clinic's number, for the WhatsApp button
  instagram: string | null;
  differentiators: string[] | null;
  faq: { question: string; answer: string }[] | null;
  testimonials: { quote: string; author: string; authorized: true }[] | null; // authorized only
  legalContact: string | null; // channel for privacy requests (LGPD)
};

export const site: SiteContent = {
  name: "Lumini Estética e Saúde",
  region: "Mangaratiba e Costa Verde (RJ)",
  address: null,
  hours: null,
  whatsapp: null,
  instagram: null,
  differentiators: null,
  faq: null,
  testimonials: null,
  legalContact: null,
};

/** Preview (default) shows what is missing; production hides it. */
export function sitePreview(): boolean {
  return process.env.LUMINI_SITE_STAGE !== "production";
}

/** Search engines stay out until the launch gate (LUMINI_SITE_PUBLIC=true). */
export function siteIndexable(): boolean {
  return process.env.LUMINI_SITE_PUBLIC === "true";
}
