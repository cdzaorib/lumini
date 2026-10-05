// Shared admin styles: 44px targets, visible focus and text contrast on the paper tone.
export const focus =
  "focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-lumini-rose";

export const ui = {
  button: `inline-flex min-h-11 items-center justify-center gap-2 bg-lumini-rose px-4 py-2 text-sm font-medium text-lumini-white transition-colors hover:bg-lumini-ink disabled:cursor-not-allowed disabled:opacity-50 ${focus}`,
  secondary: `inline-flex min-h-11 items-center justify-center gap-2 border border-lumini-rose px-4 py-2 text-sm font-medium text-lumini-rose transition-colors hover:bg-lumini-white disabled:cursor-not-allowed disabled:opacity-50 ${focus}`,
  input: `mt-1 block w-full border border-lumini-muted/50 bg-lumini-white px-3 py-2 text-base text-lumini-ink ${focus}`,
  label: "block text-sm font-medium",
  hint: "mt-1 text-sm text-lumini-muted",
  card: "border border-lumini-gold/40 bg-lumini-white/70 p-5",
  summary: `min-h-11 cursor-pointer py-2 text-sm font-medium text-lumini-rose ${focus}`,
  badge: "inline-block border px-2 py-0.5 text-xs uppercase tracking-wider",
};

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

// Actions such as "Publicar" remove their own button; keep keyboard users on the
// affected card instead of dropping focus back to the top of the page.
export function rescueFocus(target: HTMLElement | null): void {
  window.setTimeout(() => {
    const active = document.activeElement;
    if (target?.isConnected && (!active || active === document.body)) target.focus();
  }, 0);
}

export const cardHeading = `text-lg font-semibold ${focus}`;
