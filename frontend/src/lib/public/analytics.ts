export const PLAUSIBLE_EVENT_URL = "https://plausible.io/api/event";
export const ANALYTICS_CONSENT_KEY = "lumini.analytics-consent.v1";

export type AnalyticsChoice = "accepted" | "rejected";

/** The registered site domain is public configuration, never an API credential. */
export function readAnalyticsDomain(value: string | undefined): string | null {
  if (!value || value.length > 253) return null;
  const domain = value.trim().toLowerCase();
  return /^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(domain)
    ? domain
    : null;
}

/** Prepared only: enabling a campaign still requires its separate privacy/consent review. */
export function readMetaPixelConfig(id: string | undefined, campaignEnabled: string | undefined) {
  if (campaignEnabled !== "true" || !id || !/^\d{5,25}$/.test(id)) return null;
  return { pixelId: id };
}
