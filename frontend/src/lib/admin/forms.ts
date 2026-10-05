import type { ServiceDraft } from "./types";

function text(data: FormData, key: string): string { return String(data.get(key) ?? "").trim(); }
function optional(data: FormData, key: string): string | null { return text(data, key) || null; }
function lines(data: FormData, key: string): string[] { return text(data, key).split(/\r?\n/).map((line) => line.trim()).filter(Boolean); }
export function amount(data: FormData, key: string): string | null {
  const value = optional(data, key);
  if (value === null) return null;
  // Do not convert money to binary float or silently treat a blank as zero.
  const normalized = value.replace(",", ".");
  if (!/^\d{1,8}(\.\d{1,2})?$/.test(normalized)) throw new Error("Informe valores em reais, com até duas casas decimais e sem separador de milhar.");
  return normalized;
}
function minutes(data: FormData, key: string, minimum: number): number | null {
  const value = optional(data, key);
  if (value === null) return null;
  if (!/^\d+$/.test(value) || !Number.isSafeInteger(Number(value)) || Number(value) < minimum) throw new Error("Revise a duração e o intervalo. Use minutos inteiros; o intervalo mínimo é de 15 minutos.");
  return Number(value);
}

export function professionalFields(data: FormData) {
  return { display_name: text(data, "display_name"), category: optional(data, "category"), council_registration: optional(data, "council_registration") };
}

export function serviceFields(data: FormData): ServiceDraft {
  const priceKind = text(data, "price_kind");
  const mode = optional(data, "booking_mode");
  if (!["fixed", "from", "on_evaluation"].includes(priceKind) || (mode !== null && mode !== "evaluation" && mode !== "direct")) throw new Error("Revise o formato de preço e o modo de agendamento.");
  return {
    slug: text(data, "slug"), name: text(data, "name"), category: text(data, "category"), description: optional(data, "description"),
    content: {
      objectives: lines(data, "objectives"), audience: optional(data, "audience"), preparation: lines(data, "preparation"),
      aftercare: lines(data, "aftercare"), human_guidance: optional(data, "human_guidance"),
      price_kind: priceKind as ServiceDraft["content"]["price_kind"],
      communication_restrictions: lines(data, "communication_restrictions"),
    },
    duration_minutes: minutes(data, "duration_minutes", 1), buffer_minutes: minutes(data, "buffer_minutes", 15) ?? 15,
    booking_mode: mode as ServiceDraft["booking_mode"], price_brl: priceKind === "on_evaluation" ? null : amount(data, "price_brl"),
    deposit_brl: amount(data, "deposit_brl"), professional_ids: data.getAll("professional_ids").map(String),
  };
}
