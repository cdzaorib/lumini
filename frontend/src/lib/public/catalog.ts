import { readApiOrigin } from "../api-origin";

// Published, approved catalog as served by GET /api/catalog/services. Anything unexpected makes
// the whole catalog unavailable rather than half-rendered.

export type PublicProfessional = { id: string; display_name: string; category: string; council_registration: string };
export type PublicService = {
  id: string;
  slug: string;
  name: string;
  category: string;
  description: string;
  content: {
    objectives: string[];
    audience: string;
    preparation: string[];
    aftercare: string[];
    human_guidance: string;
    price_kind: "fixed" | "from" | "on_evaluation";
  };
  duration_minutes: number;
  booking_mode: "evaluation" | "direct";
  price_brl: string | null;
  deposit_brl: string;
  professionals: PublicProfessional[];
};

export function serverApiOrigin(): string | null {
  // A private network address (e.g. Railway internal) may be configured for server-side calls.
  const internal = process.env.LUMINI_API_INTERNAL_URL;
  if (internal) {
    try {
      const url = new URL(internal);
      if (["http:", "https:"].includes(url.protocol) && !url.username && !url.password && url.pathname === "/") return url.origin;
    } catch {
      return null;
    }
    return null;
  }
  return readApiOrigin(process.env.NEXT_PUBLIC_API_BASE_URL, process.env.NODE_ENV);
}

const isString = (value: unknown): value is string => typeof value === "string";
const strings = (value: unknown): value is string[] => Array.isArray(value) && value.every(isString);

function valid(item: unknown): item is PublicService {
  if (!item || typeof item !== "object") return false;
  const data = item as Record<string, unknown>;
  const content = data.content as Record<string, unknown> | undefined;
  return (
    [data.id, data.slug, data.name, data.category, data.description, data.deposit_brl].every(isString) &&
    /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(data.slug as string) &&
    typeof data.duration_minutes === "number" &&
    (data.price_brl === null || isString(data.price_brl)) &&
    (data.booking_mode === "evaluation" || data.booking_mode === "direct") &&
    !!content &&
    strings(content.objectives) && strings(content.preparation) && strings(content.aftercare) &&
    isString(content.audience) && isString(content.human_guidance) &&
    ["fixed", "from", "on_evaluation"].includes(content.price_kind as string) &&
    Array.isArray(data.professionals) &&
    data.professionals.every((person) => {
      const row = person as Record<string, unknown>;
      return [row.id, row.display_name, row.category, row.council_registration].every(isString);
    })
  );
}

export async function getCatalog(): Promise<PublicService[] | null> {
  const origin = serverApiOrigin();
  if (!origin) return null;
  try {
    const response = await fetch(`${origin}/api/catalog/services`, {
      cache: "no-store",
      signal: AbortSignal.timeout(3000),
      redirect: "error",
    });
    if (!response.ok) return null;
    const data: unknown = await response.json();
    return Array.isArray(data) && data.every(valid) ? data : null;
  } catch {
    return null; // the site stays up without the catalog (plan: available during outages)
  }
}

const money = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

/** Plan §10: price, "a partir de", or value after evaluation — never anything else. */
export function priceText(service: PublicService): string {
  if (service.content.price_kind === "fixed" && service.price_brl) return money.format(Number(service.price_brl));
  if (service.content.price_kind === "from" && service.price_brl) return `A partir de ${money.format(Number(service.price_brl))}`;
  return "Valor definido após avaliação";
}

export function professionalsOf(services: PublicService[]): PublicProfessional[] {
  const seen = new Map<string, PublicProfessional>();
  for (const service of services) for (const person of service.professionals) seen.set(person.id, person);
  return [...seen.values()].sort((a, b) => a.display_name.localeCompare(b.display_name, "pt-BR"));
}
