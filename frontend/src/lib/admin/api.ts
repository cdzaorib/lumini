import type { RequestTicket } from "./session";
import type { AdminIdentity, Professional, Service, ServiceContent } from "./types";

export class AdminApiError extends Error {
  status: number;
  constructor(status: number) {
    super(adminErrorMessage(status));
    this.name = "AdminApiError";
    this.status = status;
  }
}

export function adminErrorMessage(status: number): string {
  switch (status) {
    case 401: return "Sua sessão expirou ou não é válida. Entre novamente com o Google.";
    case 403: return "Esta conta não tem permissão para esta ação. Confira a conta ou a atribuição de revisão.";
    case 409: return "A revisão mudou ou faltam requisitos para esta ação. Confira os campos e as aprovações. Para buscar a versão atual, descarte as alterações e recarregue.";
    case 422: return "Não foi possível salvar. Revise os campos, valores e profissionais selecionados.";
    case 503: return "O acesso está temporariamente indisponível. Tente novamente mais tarde.";
    default: return "Não foi possível concluir a solicitação. Confira sua conexão e tente novamente.";
  }
}

export async function adminRequest(
  origin: string,
  ticket: RequestTicket,
  path: string,
  method: "GET" | "POST" | "PATCH" = "GET",
  body?: unknown,
): Promise<unknown> {
  // Restrict internal calls so neither form input nor a returned URL can cause
  // the Authorization header to be forwarded to another destination.
  if (!/^\/api\/admin\/(me|professionals|services)(\/[a-zA-Z0-9-]+)?(\/(verify|revoke|approve|publish|unpublish))?$/.test(path)) throw new AdminApiError(0);
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
  if (!response.ok) throw new AdminApiError(response.status);
  return response.json();
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
