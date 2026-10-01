import type { Professional, Service } from "./types";

// Mirrors the backend approval gate so reviewers see what is missing before
// trying. The backend remains authoritative and rechecks every rule.
export function contentGaps(service: Service): string[] {
  const missing: string[] = [];
  const { content } = service;
  if (!service.description) missing.push("descrição");
  if (content.objectives.length === 0) missing.push("objetivos");
  if (!content.audience) missing.push("para quem pode ser interessante");
  if (content.preparation.length === 0) missing.push("preparação");
  if (content.aftercare.length === 0) missing.push("recomendações posteriores");
  if (!content.human_guidance) missing.push("quando falar com a profissional");
  if (!service.duration_minutes) missing.push("duração");
  if (!service.booking_mode) missing.push("modo de agendamento");
  if (content.price_kind === "on_evaluation" && service.price_brl !== null) missing.push("preço deve ficar vazio em “valor após avaliação”");
  if (content.price_kind !== "on_evaluation" && service.price_brl === null) missing.push("preço");
  if (service.deposit_brl === null) missing.push("valor do sinal (zero é permitido)");
  else if (service.price_brl !== null && Number(service.deposit_brl) > Number(service.price_brl)) missing.push("sinal não pode ser maior que o preço");
  if (service.professional_ids.length === 0) missing.push("profissional responsável");
  return missing;
}

// Publication needs every linked professional verified; approval needs the approver's.
export function unverifiedProfessionals(service: Service, professionals: Professional[]): string[] {
  return service.professional_ids.flatMap((id) => {
    const person = professionals.find((item) => item.id === id);
    if (!person) return ["profissional removida"];
    return person.credentials_verified_at ? [] : [person.display_name];
  });
}
