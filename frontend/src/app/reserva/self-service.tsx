"use client";

import { useCallback, useEffect, useId, useRef, useState, type FormEvent, type RefObject } from "react";

import { clinicDay, formatDate, formatLongDay, formatMoney, formatTime } from "@/lib/clinic-time";
import {
  LinkError,
  TOKEN_PATTERN,
  decodeBooking,
  decodeRescheduled,
  decodeSlots,
  linkErrorMessage,
  linkRequest,
  type PublicBooking,
} from "@/lib/public/booking";

const focus = "focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-lumini-rose";
const primary = `inline-flex min-h-12 items-center justify-center bg-lumini-rose px-5 py-3 text-base font-medium text-lumini-white transition-colors hover:bg-lumini-ink disabled:cursor-not-allowed disabled:opacity-50 ${focus}`;
const secondary = `inline-flex min-h-12 items-center justify-center border border-lumini-rose px-5 py-3 text-base font-medium text-lumini-rose transition-colors hover:bg-lumini-white disabled:cursor-not-allowed disabled:opacity-50 ${focus}`;

const STATUS_TEXT: Record<PublicBooking["status"], string> = {
  pending_calendar: "Estamos reservando o seu horário.",
  held: "Horário reservado, aguardando o sinal.",
  confirming: "Sinal recebido. Estamos confirmando na agenda.",
  confirmed: "Agendamento confirmado.",
  expired: "Esta reserva expirou e o horário foi liberado.",
  cancelled: "Esta reserva foi cancelada.",
  conflict: "A clínica vai falar com você sobre este horário.",
};

const BLOCKED: Record<string, string> = {
  within_24h: "Faltam 24 horas ou menos: alterações agora são combinadas diretamente com a clínica.",
  second_reschedule: "Você já reagendou uma vez. Um novo reagendamento é combinado com a clínica.",
  not_confirmed: "O reagendamento fica disponível depois que a clínica confirmar o sinal.",
  in_progress: "Sua reserva está sendo processada. Para mudanças, fale com a clínica.",
};

type State =
  | { kind: "loading" }
  | { kind: "invalid"; message: string }
  | { kind: "ready"; booking: PublicBooking };

export function SelfService({ apiOrigin, nonce }: { apiOrigin: string | null; nonce?: string }) {
  void nonce; // forces per-request rendering; no inline script here needs it
  const token = useRef<string | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const [state, setState] = useState<State>({ kind: "loading" });
  const [notice, setNotice] = useState<{ kind: "success" | "error"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  // After a refusal because the booking changed, show its current state; the notice explains why.
  const reload = useCallback(async () => {
    if (!apiOrigin || !token.current) return;
    try {
      setState({ kind: "ready", booking: decodeBooking(await linkRequest(apiOrigin, token.current, "")) });
    } catch {
      // Keep the current view; the notice already tells what happened.
    }
  }, [apiOrigin]);

  useEffect(() => {
    let ignore = false;
    // Opening another link while this page is open only changes the fragment: follow it.
    function open() {
      const fromFragment = window.location.hash.slice(1);
      if (!apiOrigin) {
        queueMicrotask(() => !ignore && setState({ kind: "invalid", message: linkErrorMessage(503, "self_service_unavailable") }));
        return;
      }
      if (!TOKEN_PATTERN.test(fromFragment)) {
        token.current = null;
        queueMicrotask(() => !ignore && setState({ kind: "invalid", message: linkErrorMessage(404, "link_invalid") }));
        return;
      }
      token.current = fromFragment;
      setNotice(null);
      void linkRequest(apiOrigin, fromFragment, "")
        .then((value) => !ignore && token.current === fromFragment && setState({ kind: "ready", booking: decodeBooking(value) }))
        .catch((error: unknown) => {
          if (ignore || token.current !== fromFragment) return;
          setState({ kind: "invalid", message: error instanceof LinkError ? error.message : linkErrorMessage(0, null) });
        });
    }
    open();
    window.addEventListener("hashchange", open);
    return () => {
      ignore = true;
      window.removeEventListener("hashchange", open);
    };
  }, [apiOrigin]);

  async function act(path: "/cancel" | "/reschedule", body: object, success: string) {
    if (!apiOrigin || !token.current || state.kind !== "ready") return false;
    setBusy(true);
    setNotice(null);
    try {
      const result = await linkRequest(apiOrigin, token.current, path, { expected_version: state.booking.version, ...body });
      if (path === "/reschedule") {
        const moved = decodeRescheduled(result);
        token.current = moved.token;
        // The new booking has its own link; keep it in the fragment so a reload shows it.
        window.history.replaceState(null, "", `#${moved.token}`);
        setState({ kind: "ready", booking: moved.booking });
      } else {
        setState({ kind: "ready", booking: decodeBooking(result) });
      }
      setNotice({ kind: "success", text: success });
      window.setTimeout(() => heading.current?.focus(), 0);
      return true;
    } catch (error) {
      setNotice({ kind: "error", text: error instanceof LinkError ? error.message : linkErrorMessage(0, null) });
      if (error instanceof LinkError && error.code === "stale") await reload();
      return false;
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-svh w-[min(100%-2rem,640px)] flex-col">
      <header className="flex items-baseline gap-3 border-b border-lumini-gold/40 py-6">
        <span className="font-display text-3xl tracking-wide">lumini</span>
        <span className="text-xs uppercase tracking-[0.18em] text-lumini-muted">Estética e Saúde</span>
      </header>
      <div
        role="status"
        aria-live="polite"
        className={notice ? `mt-6 border-l-4 bg-lumini-white px-4 py-3 ${notice.kind === "error" ? "border-lumini-rose" : "border-lumini-gold"}` : "sr-only"}
      >
        {notice?.text}
      </div>
      <main id="conteudo" tabIndex={-1} className="flex-1 py-8 focus:outline-none">
        {state.kind === "loading" && <p aria-busy="true">Carregando sua reserva…</p>}
        {state.kind === "invalid" && (
          <section aria-labelledby="link-invalido">
            <h1 id="link-invalido" className="font-display text-3xl">Não conseguimos abrir esta reserva</h1>
            <p className="mt-4 leading-relaxed text-lumini-muted">{state.message}</p>
          </section>
        )}
        {state.kind === "ready" && (
          <Booking booking={state.booking} busy={busy} heading={heading} act={act} apiOrigin={apiOrigin} token={token} />
        )}
      </main>
      <footer className="border-t border-lumini-gold/40 py-5 text-sm leading-relaxed text-lumini-muted">
        Dúvidas sobre o procedimento ou sobre sua saúde: fale com a profissional pela conversa da clínica no WhatsApp.
        Este link é pessoal; não o compartilhe.
      </footer>
    </div>
  );
}

type Act = (path: "/cancel" | "/reschedule", body: object, success: string) => Promise<boolean>;

// "quarta-feira, 7 de outubro" → "Quarta-feira, 7 de outubro" (CSS capitalize would title-case it).
function sentence(text: string): string {
  return text.charAt(0).toLocaleUpperCase("pt-BR") + text.slice(1);
}

function Booking({
  booking,
  busy,
  heading,
  act,
  apiOrigin,
  token,
}: {
  booking: PublicBooking;
  busy: boolean;
  heading: RefObject<HTMLHeadingElement | null>;
  act: Act;
  apiOrigin: string | null;
  token: RefObject<string | null>;
}) {
  const open = !["expired", "cancelled"].includes(booking.status);
  return (
    <article aria-labelledby="sua-reserva" className="flex flex-col gap-6">
      <div>
        <p className="text-xs uppercase tracking-[0.13em] text-lumini-muted">Sua reserva · código {booking.code}</p>
        <h1 id="sua-reserva" ref={heading} tabIndex={-1} className={`mt-2 font-display text-3xl leading-tight ${focus}`}>
          {booking.service}
        </h1>
        <p className="mt-3 text-lg">
          {sentence(formatLongDay(booking.starts_at))}, das {formatTime(booking.starts_at)} às{" "}
          {formatTime(booking.ends_at)}
        </p>
        <p className="text-lumini-muted">Com {booking.professional} · horário de Brasília</p>
      </div>

      <p className="border border-lumini-gold/40 bg-lumini-white/70 p-4">
        {STATUS_TEXT[booking.status]}
        {booking.status === "held" && booking.hold_expires_at && (
          <> O horário fica reservado até {formatDate(booking.hold_expires_at)}; as instruções do sinal ({formatMoney(booking.deposit_brl)}) chegam pelo WhatsApp.</>
        )}
      </p>

      {open && (booking.can_cancel || booking.can_reschedule) && (
        <p className="text-sm text-lumini-muted">
          Mudanças por aqui até {formatDate(booking.self_service_until)}. Depois disso, fale com a clínica.
        </p>
      )}

      {booking.can_reschedule && <Reschedule booking={booking} busy={busy} act={act} apiOrigin={apiOrigin} token={token} />}
      {open && !booking.can_reschedule && booking.reschedule_blocked && BLOCKED[booking.reschedule_blocked] && booking.status === "confirmed" && (
        <p className="text-sm leading-relaxed text-lumini-muted">{BLOCKED[booking.reschedule_blocked]}</p>
      )}
      {booking.can_cancel && <Cancel booking={booking} busy={busy} act={act} />}
      {open && !booking.can_cancel && booking.cancel_blocked && BLOCKED[booking.cancel_blocked] && (
        <p className="text-sm leading-relaxed text-lumini-muted">{BLOCKED[booking.cancel_blocked]}</p>
      )}
    </article>
  );
}

function Cancel({ booking, busy, act }: { booking: PublicBooking; busy: boolean; act: Act }) {
  const [confirming, setConfirming] = useState(false);
  return (
    <section aria-labelledby="cancelar" className="flex flex-col gap-3">
      <h2 id="cancelar" className="text-lg font-semibold">Cancelar</h2>
      <p className="text-sm leading-relaxed text-lumini-muted">
        {booking.deposit_confirmed
          ? "O horário volta a ficar livre. A devolução do sinal é tratada pela clínica, conforme a política combinada."
          : "O horário volta a ficar livre para outras pessoas."}
      </p>
      {confirming ? (
        <div className="flex flex-wrap gap-3">
          <button type="button" className={primary} disabled={busy} onClick={() => void act("/cancel", {}, "Reserva cancelada. Obrigada por avisar.")}>
            Confirmar cancelamento
          </button>
          <button type="button" className={secondary} disabled={busy} onClick={() => setConfirming(false)}>
            Manter reserva
          </button>
        </div>
      ) : (
        <div>
          <button type="button" className={secondary} disabled={busy} onClick={() => setConfirming(true)}>
            Quero cancelar
          </button>
        </div>
      )}
    </section>
  );
}

function Reschedule({
  booking,
  busy,
  act,
  apiOrigin,
  token,
}: {
  booking: PublicBooking;
  busy: boolean;
  act: Act;
  apiOrigin: string | null;
  token: RefObject<string | null>;
}) {
  const id = useId();
  const [day, setDay] = useState(() => clinicDay(booking.starts_at));
  const [slots, setSlots] = useState<string[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!apiOrigin || !token.current) return;
    setLoading(true);
    setError(null);
    try {
      setSlots(decodeSlots(await linkRequest(apiOrigin, token.current, `/availability?first_day=${day}&days=1`)));
    } catch (problem) {
      setSlots(null);
      setError(problem instanceof LinkError ? problem.message : linkErrorMessage(0, null));
    } finally {
      setLoading(false);
    }
  }

  async function choose(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const chosen = new FormData(event.currentTarget).get("starts_at");
    if (typeof chosen === "string" && chosen) {
      await act("/reschedule", { starts_at: chosen }, "Pronto! Seu novo horário está sendo confirmado na agenda. O sinal continua valendo.");
    }
  }

  return (
    <section aria-labelledby="reagendar" className="flex flex-col gap-3">
      <h2 id="reagendar" className="text-lg font-semibold">Reagendar</h2>
      <p className="text-sm leading-relaxed text-lumini-muted">Você pode reagendar uma vez por aqui; o sinal já pago continua valendo.</p>
      <form onSubmit={search} className="flex flex-wrap items-end gap-3">
        <div>
          <label htmlFor={`${id}-day`} className="block text-sm font-medium">Escolha o dia</label>
          <input
            id={`${id}-day`}
            type="date"
            required
            min={clinicDay()}
            value={day}
            onChange={(event) => {
              setDay(event.target.value);
              setSlots(null);
            }}
            className={`mt-1 block border border-lumini-muted/50 bg-lumini-white px-3 py-2 text-base ${focus}`}
          />
        </div>
        <button type="submit" className={secondary} disabled={busy || loading}>Ver horários livres</button>
      </form>
      {loading && <p aria-busy="true" className="text-sm text-lumini-muted">Consultando a agenda…</p>}
      {error && <p role="alert" className="text-sm text-lumini-rose">{error}</p>}
      {slots !== null &&
        (slots.length === 0 ? (
          <p className="text-sm text-lumini-muted">Nenhum horário livre nesse dia. Tente outra data.</p>
        ) : (
          <form onSubmit={choose} className="flex flex-col gap-3">
            <fieldset>
              <legend className="text-sm font-medium">Horários livres em {formatLongDay(slots[0])}</legend>
              <div className="mt-2 flex flex-wrap gap-2">
                {slots.map((slot) => (
                  <label key={slot} className="flex min-h-12 items-center gap-2 border border-lumini-muted/50 bg-lumini-white px-3">
                    <input type="radio" name="starts_at" value={slot} required className="size-4" />
                    {formatTime(slot)}
                  </label>
                ))}
              </div>
            </fieldset>
            <div>
              <button type="submit" className={primary} disabled={busy}>Confirmar novo horário</button>
            </div>
          </form>
        ))}
    </section>
  );
}
