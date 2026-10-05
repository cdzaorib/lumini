// Client self-service API. The link token is a credential: it stays in memory and in the URL
// fragment, goes only in the Authorization header to the configured API, and is never logged.

export const TOKEN_PATTERN = /^[0-9a-f]{42}[A-Za-z0-9_-]{43}$/;

export type PublicBooking = {
  code: string;
  status: "pending_calendar" | "held" | "confirming" | "confirmed" | "expired" | "cancelled" | "conflict";
  version: number;
  service: string;
  professional: string;
  starts_at: string;
  ends_at: string;
  hold_expires_at: string | null;
  deposit_brl: string;
  deposit_confirmed: boolean;
  self_service_until: string;
  can_cancel: boolean;
  cancel_blocked: string | null;
  can_reschedule: boolean;
  reschedule_blocked: string | null;
};

export class LinkError extends Error {
  status: number;
  code: string | null;
  constructor(status: number, code: string | null) {
    super(linkErrorMessage(status, code));
    this.name = "LinkError";
    this.status = status;
    this.code = code;
  }
}

const MESSAGES: Record<string, string> = {
  link_invalid: "Este link não é válido ou já expirou. Peça um novo link à clínica pelo WhatsApp.",
  stale: "Sua reserva mudou desde que esta página foi aberta. Atualizamos os dados; confira antes de tentar de novo.",
  within_24h: "Faltam 24 horas ou menos para o atendimento: alterações agora são combinadas diretamente com a clínica.",
  second_reschedule: "Um novo reagendamento precisa ser combinado com a clínica.",
  not_confirmed: "O reagendamento fica disponível depois que a clínica confirmar o sinal.",
  in_progress: "Sua reserva está sendo processada pela clínica. Para mudanças, fale com a clínica pelo WhatsApp.",
  closed: "Esta reserva já foi encerrada.",
  slot_unavailable: "Esse horário acabou de ser ocupado. Escolha outro, por favor.",
  too_close: "Esse horário está próximo demais para ser marcado online. Escolha outro ou fale com a clínica.",
  rate_limited: "Muitas tentativas em pouco tempo. Aguarde alguns minutos e tente de novo.",
  calendar_unavailable: "A agenda não respondeu agora. Nada foi alterado; tente novamente em instantes.",
  calendar_not_configured: "A agenda online ainda não está disponível. Fale com a clínica pelo WhatsApp.",
  self_service_unavailable: "O autoatendimento está indisponível no momento. Fale com a clínica pelo WhatsApp.",
};

export function linkErrorMessage(status: number, code: string | null): string {
  if (code && MESSAGES[code]) return MESSAGES[code];
  if (status === 404) return MESSAGES.link_invalid;
  return "Não foi possível concluir agora. Confira sua conexão e tente novamente.";
}

export async function linkRequest(
  origin: string,
  token: string,
  path: "" | "/cancel" | "/reschedule" | `/availability?first_day=${string}&days=${number}`,
  body?: unknown,
  signal?: AbortSignal,
): Promise<unknown> {
  if (!TOKEN_PATTERN.test(token)) throw new LinkError(404, "link_invalid");
  const response = await fetch(`${origin}/api/public/booking${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: { Authorization: `Bearer ${token}`, ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
    cache: "no-store",
    credentials: "omit",
    redirect: "error",
    referrerPolicy: "no-referrer",
  });
  if (!response.ok) {
    let code: string | null = null;
    try {
      const value: unknown = ((await response.json()) as { code?: unknown }).code;
      code = typeof value === "string" && /^[a-z_]{1,40}$/.test(value) ? value : null;
    } catch {
      code = null;
    }
    throw new LinkError(response.status, code);
  }
  return response.json();
}

type Row = Record<string, unknown>;
function row(value: unknown): Row {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new LinkError(0, null);
  return value as Row;
}
function str(value: unknown): string {
  if (typeof value !== "string") throw new LinkError(0, null);
  return value;
}
function bool(value: unknown): boolean {
  if (typeof value !== "boolean") throw new LinkError(0, null);
  return value;
}
const STATUSES = ["pending_calendar", "held", "confirming", "confirmed", "expired", "cancelled", "conflict"] as const;

export function decodeBooking(value: unknown): PublicBooking {
  const data = row(value);
  const status = str(data.status);
  if (!(STATUSES as readonly string[]).includes(status)) throw new LinkError(0, null);
  const version = data.version;
  if (typeof version !== "number" || !Number.isSafeInteger(version)) throw new LinkError(0, null);
  const nullable = (item: unknown) => (item === null ? null : str(item));
  return {
    code: str(data.code), status: status as PublicBooking["status"], version, service: str(data.service),
    professional: str(data.professional), starts_at: str(data.starts_at), ends_at: str(data.ends_at),
    hold_expires_at: nullable(data.hold_expires_at), deposit_brl: str(data.deposit_brl),
    deposit_confirmed: bool(data.deposit_confirmed), self_service_until: str(data.self_service_until),
    can_cancel: bool(data.can_cancel), cancel_blocked: nullable(data.cancel_blocked),
    can_reschedule: bool(data.can_reschedule), reschedule_blocked: nullable(data.reschedule_blocked),
  };
}

export function decodeRescheduled(value: unknown): { booking: PublicBooking; token: string } {
  const data = row(value);
  const token = str(data.token);
  if (!TOKEN_PATTERN.test(token)) throw new LinkError(0, null);
  return { booking: decodeBooking(data.booking), token };
}

export function decodeSlots(value: unknown): string[] {
  const slots = row(value).slots;
  if (!Array.isArray(slots)) throw new LinkError(0, null);
  return slots.map(str);
}
