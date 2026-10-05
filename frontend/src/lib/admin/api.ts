import type { RequestTicket } from "./session";
import { BOOKING_STATUSES, LEAD_STATUSES, type AdminIdentity, type Booking, type BookingEvent, type Count, type Integrations, type Lead, type Metrics, type Professional, type Schedule, type Service, type ServiceContent, type SiteSettings } from "./types";

export class AdminApiError extends Error {
  status: number;
  code: string | null;
  constructor(status: number, code: string | null = null) {
    super(adminErrorMessage(status, code));
    this.name = "AdminApiError";
    this.status = status;
    this.code = code;
  }
}

// Stable codes from the booking API. Unknown codes fall back to the status message.
const CODE_MESSAGES: Record<string, string> = {
  stale: "Este registro mudou desde que a tela foi carregada. Recarregue e confira antes de repetir.",
  invalid_state: "A reserva não está mais nessa situação. Recarregue a lista para ver o estado atual.",
  deposit_mismatch: "O valor informado é diferente do sinal previsto para esta reserva. Nada foi confirmado.",
  hold_expired: "O prazo do sinal já venceu e o horário pode ter sido liberado. Combine um novo horário com a cliente.",
  calendar_in_use: "Esta agenda do Google tem reservas ativas ou remoções pendentes. Resolva-as antes de trocar o calendário.",
  calendar_unavailable: "O Google Agenda não respondeu. Nada foi alterado; tente novamente em instantes.",
  calendar_not_configured: "A integração com o Google Agenda ainda não foi configurada no servidor.",
  evaluation_required: "Este procedimento começa por avaliação e não é reservável diretamente.",
  agenda_not_configured: "A agenda desta profissional ainda não tem calendário e horários configurados.",
  not_bookable: "Procedimento ou profissional indisponível para reserva online: confira publicação, vínculo e credencial verificada.",
  too_close: "Horários com menos de 3 horas de antecedência não são marcados pelo sistema.",
  slot_unavailable: "Esse horário não está mais disponível. Atualize a prévia e escolha outro.",
  not_found: "Registro não encontrado. Recarregue a página.",
  advertising_rule: "Algum texto promete resultado (por exemplo “garantido”, “definitivo”, “sem dor”, “antes e depois”). Publicidade em saúde não pode prometer resultados: ajuste o texto.",
};

export function adminErrorMessage(status: number, code: string | null = null): string {
  if (code && CODE_MESSAGES[code]) return CODE_MESSAGES[code];
  switch (status) {
    case 401: return "Sua sessão expirou ou não é válida. Entre novamente com o Google.";
    case 403: return "Esta conta não tem permissão para esta ação. Confira a conta ou a atribuição de revisão.";
    case 409: return "A revisão mudou ou faltam requisitos para esta ação. Confira os campos e as aprovações. Para buscar a versão atual, descarte as alterações e recarregue.";
    case 422: return "Não foi possível salvar. Revise os campos, valores e profissionais selecionados.";
    case 503: return "O acesso está temporariamente indisponível. Tente novamente mais tarde.";
    default: return "Não foi possível concluir a solicitação. Confira sua conexão e tente novamente.";
  }
}

const ID = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}";
const ADMIN_PATHS = [
  /^\/api\/admin\/(me|professionals|services)(\/[a-zA-Z0-9-]+)?(\/(verify|revoke|approve|publish|unpublish))?$/,
  new RegExp(`^/api/admin/professionals/${ID}/schedule$`),
  /^\/api\/admin\/integrations$/,
  /^\/api\/admin\/site$/,
  /^\/api\/admin\/leads\?status=(new|contacted|converted|discarded)$/,
  new RegExp(`^/api/admin/leads/${ID}/status$`),
  /^\/api\/admin\/bookings\?scope=(upcoming|history)$/,
  new RegExp(`^/api/admin/bookings/${ID}/(deposit|cancel|resolve|reschedule|manage-link|attendance|events)$`),
  /^\/api\/admin\/metrics\?days=(7|30|90|365)$/,
  new RegExp(`^/api/admin/availability\\?service_id=${ID}&professional_id=${ID}&first_day=\\d{4}-\\d{2}-\\d{2}&days=\\d{1,2}$`),
];

export async function adminRequest(
  origin: string,
  ticket: RequestTicket,
  path: string,
  method: "GET" | "POST" | "PATCH" | "PUT" = "GET",
  body?: unknown,
): Promise<unknown> {
  // Restrict internal calls so neither form input nor a returned URL can cause
  // the Authorization header to be forwarded to another destination.
  if (!ADMIN_PATHS.some((pattern) => pattern.test(path))) throw new AdminApiError(0);
  const response = await fetch(`${origin}${path}`, {
    method,
    headers: { Authorization: `Bearer ${ticket.credential}`, ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: ticket.signal,
    cache: "no-store",
    credentials: "omit",
    redirect: "error",
    referrerPolicy: "no-referrer",
  });
  if (!response.ok) throw new AdminApiError(response.status, await errorCode(response));
  return response.status === 204 ? null : response.json();
}

async function errorCode(response: Response): Promise<string | null> {
  try {
    const body = (await response.json()) as { code?: unknown; detail?: unknown };
    if (Array.isArray(body.detail) && body.detail.some((item) => typeof item?.msg === "string" && item.msg.includes("Advertising rule"))) {
      return "advertising_rule";
    }
    const code = body.code;
    return typeof code === "string" && /^[a-z_]{1,40}$/.test(code) ? code : null;
  } catch {
    return null;
  }
}

type Row = Record<string, unknown>;
function row(value: unknown): Row {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new AdminApiError(0);
  return value as Row;
}
function str(value: unknown): string {
  if (typeof value !== "string") throw new AdminApiError(0);
  return value;
}
function nullable(value: unknown): string | null { return value === null ? null : str(value); }
function integer(value: unknown): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0) throw new AdminApiError(0);
  return value;
}
function list<T>(value: unknown, decode: (item: unknown) => T): T[] {
  if (!Array.isArray(value)) throw new AdminApiError(0);
  return value.map(decode);
}
function oneOf<T extends string>(value: unknown, options: readonly T[]): T {
  if (typeof value !== "string" || !options.includes(value as T)) throw new AdminApiError(0);
  return value as T;
}

export function decodeIdentity(value: unknown): AdminIdentity {
  const data = row(value);
  return { subject: str(data.subject), email: str(data.email), reviewer_professional_ids: list(data.reviewer_professional_ids, str) };
}

export function decodeProfessionals(value: unknown): Professional[] {
  return list(value, (item) => {
    const data = row(item);
    return {
      id: str(data.id), display_name: str(data.display_name), category: nullable(data.category),
      council_registration: nullable(data.council_registration), credentials_verified_at: nullable(data.credentials_verified_at),
      revision: integer(data.revision),
    };
  });
}

function decodeContent(value: unknown): ServiceContent {
  const data = row(value);
  return {
    objectives: list(data.objectives, str), audience: nullable(data.audience), preparation: list(data.preparation, str),
    aftercare: list(data.aftercare, str), human_guidance: nullable(data.human_guidance),
    price_kind: oneOf(data.price_kind, ["fixed", "from", "on_evaluation"] as const),
    communication_restrictions: list(data.communication_restrictions, str),
  };
}

export function decodeServices(value: unknown): Service[] {
  return list(value, (item) => {
    const data = row(item);
    return {
      id: str(data.id), slug: str(data.slug), name: str(data.name), category: str(data.category), description: nullable(data.description),
      content: decodeContent(data.content), duration_minutes: data.duration_minutes === null ? null : integer(data.duration_minutes),
      buffer_minutes: integer(data.buffer_minutes), booking_mode: data.booking_mode === null ? null : oneOf(data.booking_mode, ["evaluation", "direct"] as const),
      price_brl: nullable(data.price_brl), deposit_brl: nullable(data.deposit_brl), professional_ids: list(data.professional_ids, str),
      status: oneOf(data.status, ["draft", "approved", "published"] as const), revision: integer(data.revision),
      approved_at: nullable(data.approved_at), published_at: nullable(data.published_at),
      approvals: list(data.approvals, (approval) => {
        const item = row(approval);
        return { professional_id: str(item.professional_id), approved_at: str(item.approved_at) };
      }),
    };
  });
}

function money(value: unknown): string {
  const text = str(value);
  if (!/^\d{1,8}(\.\d{1,2})?$/.test(text)) throw new AdminApiError(0);
  return text;
}

export function decodeBookings(value: unknown): Booking[] {
  return list(value, (item) => {
    const data = row(item);
    const service = row(data.service);
    const professional = row(data.professional);
    const contact = row(data.contact);
    return {
      id: str(data.id), code: str(data.code), status: oneOf(data.status, BOOKING_STATUSES), version: integer(data.version),
      starts_at: str(data.starts_at), ends_at: str(data.ends_at), expires_at: nullable(data.expires_at),
      service: { id: str(service.id), name: str(service.name) },
      professional: { id: str(professional.id), name: str(professional.name) },
      contact: { name: str(contact.name), phone: str(contact.phone) },
      deposit_brl: money(data.deposit_brl), deposit_confirmed_at: nullable(data.deposit_confirmed_at),
      calendar_status: str(data.calendar_status), reschedule_count: integer(data.reschedule_count),
      rescheduled_from_id: nullable(data.rescheduled_from_id), closed_reason: nullable(data.closed_reason),
      attendance: data.attendance === null || data.attendance === undefined ? null : oneOf(data.attendance, ["attended", "no_show"] as const),
      origin: oneOf(data.origin ?? "other", ["whatsapp", "site", "reschedule", "other"] as const),
    };
  });
}

function clock(value: unknown): string {
  const match = /^(\d{2}):(\d{2})(:00)?$/.exec(str(value));
  if (!match) throw new AdminApiError(0);
  return `${match[1]}:${match[2]}`;
}

export function decodeSchedule(value: unknown): Schedule {
  const data = row(value);
  return {
    professional_id: str(data.professional_id), calendar_id: nullable(data.calendar_id), revision: integer(data.revision),
    rules: list(data.rules, (item) => {
      const rule = row(item);
      const weekday = integer(rule.weekday);
      if (weekday > 6) throw new AdminApiError(0);
      return { weekday, start: clock(rule.start), end: clock(rule.end) };
    }),
  };
}

export function decodeSlots(value: unknown): string[] {
  return list(row(value).slots, str);
}

export function decodeManageLink(value: unknown): { url: string; expires_at: string } {
  const data = row(value);
  const url = str(data.url);
  // Only links to this site's own self-service page are shown for copying.
  if (!/^https?:\/\/[^/#?]+\/reserva#[0-9a-f]{42}[A-Za-z0-9_-]{43}$/.test(url)) throw new AdminApiError(0);
  return { url, expires_at: str(data.expires_at) };
}

function flag(value: unknown): boolean {
  if (typeof value !== "boolean") throw new AdminApiError(0);
  return value;
}

export function decodeIntegrations(value: unknown): Integrations {
  const data = row(value);
  const whatsapp = row(data.whatsapp);
  return {
    whatsapp: {
      configured: flag(whatsapp.configured), state: nullable(whatsapp.state), needs_attention: flag(whatsapp.needs_attention),
      changed_at: nullable(whatsapp.changed_at), human_mode_conversations: integer(whatsapp.human_mode_conversations),
    },
    calendar_configured: flag(data.calendar_configured),
    self_service_configured: flag(data.self_service_configured),
  };
}

export function decodeLeads(value: unknown): Lead[] {
  return list(value, (item) => {
    const data = row(item);
    return {
      id: str(data.id), name: str(data.name), phone: str(data.phone), city: nullable(data.city), service: nullable(data.service),
      preferred_period: oneOf(data.preferred_period, ["morning", "afternoon", "any"] as const), source: str(data.source),
      status: oneOf(data.status, LEAD_STATUSES), marketing_consent: flag(data.marketing_consent),
      created_at: str(data.created_at), retain_until: str(data.retain_until),
    };
  });
}

export function decodeSiteSettings(value: unknown): SiteSettings {
  const data = row(value);
  const content = row(data.content);
  const address = content.address === null ? null : row(content.address);
  return {
    revision: integer(data.revision),
    content: {
      address: address && { street: str(address.street), city: str(address.city), maps_url: nullable(address.maps_url) },
      hours: list(content.hours, str), whatsapp: nullable(content.whatsapp), instagram: nullable(content.instagram),
      differentiators: list(content.differentiators, str),
      faq: list(content.faq, (item) => { const entry = row(item); return { question: str(entry.question), answer: str(entry.answer) }; }),
      testimonials: list(content.testimonials, (item) => {
        const entry = row(item);
        return { quote: str(entry.quote), author: str(entry.author), authorized_on: str(entry.authorized_on), authorization_confirmed: true as const };
      }),
      legal_contact: nullable(content.legal_contact), deposit_instructions: nullable(content.deposit_instructions),
    },
  };
}

export function decodeEvents(value: unknown): BookingEvent[] {
  return list(value, (item) => {
    const data = row(item);
    return {
      action: str(data.action), from_status: nullable(data.from_status), to_status: str(data.to_status),
      actor: oneOf(data.actor, ["system", "staff", "client"] as const), at: str(data.at),
    };
  });
}

function counts(value: unknown): Count[] {
  return list(value, (item) => { const data = row(item); return { key: str(data.key), count: integer(data.count) }; });
}

export function decodeMetrics(value: unknown): Metrics {
  const data = row(value);
  return {
    days: integer(data.days), leads_total: integer(data.leads_total), leads_by_status: counts(data.leads_by_status),
    leads_marketing_consent: integer(data.leads_marketing_consent), bookings_requested: integer(data.bookings_requested),
    bookings_by_origin: counts(data.bookings_by_origin), deposits_confirmed: integer(data.deposits_confirmed),
    appointments: integer(data.appointments), attended: integer(data.attended), no_show: integer(data.no_show),
    attendance_unmarked: integer(data.attendance_unmarked), cancellations: counts(data.cancellations),
    reschedules: integer(data.reschedules), expired: counts(data.expired), demand_by_service: counts(data.demand_by_service),
    handoffs_by_reason: counts(data.handoffs_by_reason), upcoming_confirmed_7d: integer(data.upcoming_confirmed_7d),
  };
}
