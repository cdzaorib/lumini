// Everything about time is shown in clinic time (Brasília), whatever the browser time zone.

const dateFormat = new Intl.DateTimeFormat("pt-BR", {
  dateStyle: "short",
  timeStyle: "short",
  timeZone: "America/Sao_Paulo",
});
const moneyFormat = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

export function formatDate(value: string): string {
  return dateFormat.format(new Date(value));
}

export function formatMoney(value: string): string {
  return moneyFormat.format(Number(value));
}

// Bookings are always shown in clinic time, whatever the browser's time zone.
const clinic = { timeZone: "America/Sao_Paulo" } as const;
const timeFormat = new Intl.DateTimeFormat("pt-BR", { ...clinic, hour: "2-digit", minute: "2-digit" });
const dayFormat = new Intl.DateTimeFormat("pt-BR", { ...clinic, weekday: "short", day: "2-digit", month: "2-digit" });
const isoDay = new Intl.DateTimeFormat("en-CA", { ...clinic, year: "numeric", month: "2-digit", day: "2-digit" });

export function formatTime(value: string): string {
  return timeFormat.format(new Date(value));
}

export function formatDay(value: string): string {
  return dayFormat.format(new Date(value));
}

/** YYYY-MM-DD of an instant in clinic time (for grouping and date inputs). */
export function clinicDay(value: string | Date = new Date()): string {
  return isoDay.format(typeof value === "string" ? new Date(value) : value);
}


const longDayFormat = new Intl.DateTimeFormat("pt-BR", { ...clinic, weekday: "long", day: "numeric", month: "long" });

export function formatLongDay(value: string): string {
  return longDayFormat.format(new Date(value));
}
