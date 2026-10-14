import { serverApiOrigin } from "./catalog";
import { mediaOrigins } from "@/lib/media";

// Clinic facts edited in the panel (GET /api/public/site). Missing or invalid data = empty
// content: sections show as pending in the preview and stay hidden in production.

export type SiteContent = {
  address: { street: string; city: string; maps_url: string | null } | null;
  hours: string[];
  whatsapp: string | null;
  instagram: string | null;
  differentiators: string[];
  faq: { question: string; answer: string }[];
  testimonials: { quote: string; author: string }[];
  legal_contact: string | null;
  photos: { url: string; alt: string; width: number; height: number }[];
};

export const EMPTY_SITE: SiteContent = {
  address: null, hours: [], whatsapp: null, instagram: null, differentiators: [], faq: [], testimonials: [], legal_contact: null, photos: [],
};

const isString = (value: unknown): value is string => typeof value === "string";
const strings = (value: unknown): value is string[] => Array.isArray(value) && value.every(isString);
const pairs = (value: unknown, a: string, b: string) =>
  Array.isArray(value) && value.every((item) => item && typeof item === "object" && isString((item as Record<string, unknown>)[a]) && isString((item as Record<string, unknown>)[b]));

function valid(data: unknown): data is SiteContent {
  if (!data || typeof data !== "object") return false;
  const row = data as Record<string, unknown>;
  const address = row.address as Record<string, unknown> | null;
  return (
    (address === null || (!!address && isString(address.street) && isString(address.city) && (address.maps_url === null || (isString(address.maps_url) && address.maps_url.startsWith("https://"))))) &&
    strings(row.hours) && strings(row.differentiators) &&
    (row.whatsapp === null || (isString(row.whatsapp) && /^\+\d{10,15}$/.test(row.whatsapp))) &&
    (row.instagram === null || (isString(row.instagram) && /^[A-Za-z0-9._]{1,30}$/.test(row.instagram))) &&
    (row.legal_contact === null || isString(row.legal_contact)) &&
    pairs(row.faq, "question", "answer") && pairs(row.testimonials, "quote", "author") &&
    Array.isArray(row.photos) && row.photos.every((value: unknown) => {
      if (!value || typeof value !== "object") return false;
      const photo = value as Record<string, unknown>;
      if (!isString(photo.url) || !isString(photo.alt)) return false;
      try {
        const url = new URL(photo.url);
        return url.protocol === "https:" && !url.username && !url.password && !url.search && !url.hash &&
          typeof photo.width === "number" && Number.isInteger(photo.width) && photo.width >= 100 && photo.width <= 6000 &&
          typeof photo.height === "number" && Number.isInteger(photo.height) && photo.height >= 100 && photo.height <= 6000;
      } catch { return false; }
    })
  );
}

export async function getSiteContent(): Promise<SiteContent> {
  const origin = serverApiOrigin();
  if (!origin) return EMPTY_SITE;
  try {
    const response = await fetch(`${origin}/api/public/site`, { cache: "no-store", signal: AbortSignal.timeout(3000), redirect: "error" });
    if (!response.ok) return EMPTY_SITE;
    const data: unknown = await response.json();
    if (!valid(data)) return EMPTY_SITE;
    const permitted = new Set(mediaOrigins(process.env.LUMINI_MEDIA_ORIGINS).map((url) => url.origin));
    return { ...data, photos: data.photos.filter((photo) => permitted.has(new URL(photo.url).origin)) };
  } catch {
    return EMPTY_SITE;
  }
}

export function whatsappLink(phone: string, text?: string): string {
  return `https://wa.me/${phone.replace(/\D/g, "")}${text ? `?text=${encodeURIComponent(text)}` : ""}`;
}
