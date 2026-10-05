import type { ScheduleRule } from "./types";

// Index = API weekday (0 = Monday), as stored by the backend.
export const WEEKDAYS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"] as const;

const CALENDAR_ID = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/;

/** Mirrors the backend checks so the most common mistakes get a specific message. */
export function scheduleProblem(calendarId: string, rules: ScheduleRule[]): string | null {
  if (calendarId && (calendarId.length > 255 || !CALENDAR_ID.test(calendarId))) {
    return "O ID do Google Agenda tem formato de e-mail (ex.: nome@group.calendar.google.com).";
  }
  for (const rule of rules) {
    if (!/^\d{2}:\d{2}$/.test(rule.start) || !/^\d{2}:\d{2}$/.test(rule.end)) return "Preencha início e fim de cada faixa.";
    if (Number(rule.start.slice(3)) % 15 || Number(rule.end.slice(3)) % 15) return "Use horários em múltiplos de 15 minutos (ex.: 08:00, 08:15, 08:30).";
    if (rule.start >= rule.end) return `${WEEKDAYS[rule.weekday]}: o início de cada faixa deve vir antes do fim.`;
  }
  for (let day = 0; day < 7; day += 1) {
    const sorted = rules.filter((rule) => rule.weekday === day).sort((a, b) => a.start.localeCompare(b.start));
    if (sorted.some((rule, index) => index > 0 && rule.start < sorted[index - 1].end)) return `${WEEKDAYS[day]}: há faixas sobrepostas.`;
  }
  return rules.length > 28 ? "Use no máximo 28 faixas na semana." : null;
}
