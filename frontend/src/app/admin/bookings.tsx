"use client";

import { useId, useRef, useState, type FormEvent, type ReactNode, type RefObject } from "react";

import { decodeEvents, decodeManageLink, decodeSlots } from "@/lib/admin/api";
import { amount } from "@/lib/admin/forms";
import type { Booking, BookingEvent, BookingScope, BookingStatus, Command, Mutation, Query } from "@/lib/admin/types";

import { clinicDay, focus, formatDate, formatDay, formatMoney, formatTime, rescueFocus, ui } from "./ui";

const STATUS: Record<BookingStatus, string> = {
  pending_calendar: "Criando evento na agenda",
  held: "Aguardando sinal",
  confirming: "Sinal conferido · atualizando agenda",
  confirmed: "Confirmada",
  expired: "Expirada",
  cancelled: "Cancelada",
  conflict: "Conflito · decisão da equipe",
};

const ORIGIN: Record<Booking["origin"], string> = {
  whatsapp: "WhatsApp",
  site: "Chat do site",
  reschedule: "Reagendamento",
  other: "Equipe/outros",
};

const ACTIONS: Record<string, string> = {
  hold_requested: "Reserva pedida",
  held: "Horário reservado",
  deposit_confirmed: "Sinal conferido",
  confirmed: "Confirmada na agenda",
  expired: "Expirou",
  cancelled: "Cancelada",
  rescheduled: "Reagendada",
  rescheduled_from: "Criada por reagendamento",
  calendar_conflict: "Conflito na agenda",
  calendar_rejected: "Agenda recusou",
  conflict_released: "Horário liberado",
  conflict_retry: "Nova tentativa na agenda",
  calendar_drift: "Agenda corrigida (alteração manual no Google)",
  calendar_overlap: "Outro compromisso no Google neste horário",
  calendar_overlap_cleared: "Compromisso sobreposto saiu do Google",
  manage_link_issued: "Link gerado pela equipe",
  attended: "Compareceu",
  no_show: "Faltou",
};
const ACTORS: Record<BookingEvent["actor"], string> = { system: "sistema", staff: "equipe", client: "cliente" };

function History({ path, query }: { path: string; query: Query }) {
  const [events, setEvents] = useState<BookingEvent[] | null>(null);
  return (
    <details
      className="mt-3"
      onToggle={(event) => {
        if (event.currentTarget.open && events === null) void query(path, decodeEvents).then((found) => setEvents(found ?? []));
      }}
    >
      <summary className={ui.summary}>Histórico</summary>
      {events === null ? (
        <p className={ui.hint} aria-busy="true">Carregando…</p>
      ) : (
        <ol className="mt-2 flex flex-col gap-1 text-sm">
          {events.map((item, index) => (
            <li key={`${item.at}-${index}`}>
              {formatDate(item.at)} · {ACTIONS[item.action] ?? item.action} · {ACTORS[item.actor]}
            </li>
          ))}
        </ol>
      )}
    </details>
  );
}

const REASONS: Record<string, string> = {
  deposit_timeout: "O prazo do sinal venceu.",
  calendar_timeout: "O Google Agenda não confirmou o horário a tempo.",
  cancelled_by_staff: "Cancelada pela equipe.",
  cancelled_by_client: "Cancelada pela cliente.",
  rescheduled: "Reagendada; a nova reserva aparece na lista.",
  conflict_released: "Horário liberado após conflito.",
  calendar_conflict: "Outro compromisso apareceu no Google Agenda neste horário.",
  calendar_rejected: "O Google Agenda recusou o evento (calendário inexistente ou sem permissão).",
};

type Props = {
  bookings: Booking[];
  scope: BookingScope;
  onScope: (scope: BookingScope) => void;
  mutate: Mutation;
  query: Query;
  command: Command;
  busy: boolean;
};

export function BookingsSection({ bookings, scope, onScope, mutate, query, command, busy }: Props) {
  const heading = useRef<HTMLHeadingElement>(null);
  const groups =
    scope === "history"
      ? [{ title: "Histórico recente", hint: null, items: bookings }]
      : [
          {
            title: "Precisam de decisão",
            hint: "O horário segue bloqueado até alguém da equipe decidir.",
            items: bookings.filter((item) => item.status === "conflict"),
          },
          {
            title: "Aguardando sinal",
            hint: "Confirme somente depois de ver o crédito na conta da clínica. Comprovante enviado pela cliente não basta.",
            items: bookings.filter((item) => item.status === "held"),
          },
          {
            title: "Atualizando o Google Agenda",
            hint: "O processamento automático cria ou confirma o evento. Enquanto ele não estiver ativo, as reservas ficam aqui.",
            items: bookings.filter((item) => item.status === "pending_calendar" || item.status === "confirming"),
          },
          {
            title: "Confirmadas",
            hint: null,
            items: bookings.filter((item) => item.status === "confirmed"),
          },
        ];

  return (
    <section aria-labelledby="reservas" className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h2 id="reservas" ref={heading} tabIndex={-1} className={`font-display text-2xl ${focus}`}>
          Reservas
        </h2>
        <div role="group" aria-label="Mostrar" className="flex gap-2">
          {(["upcoming", "history"] as const).map((option) => (
            <button
              key={option}
              type="button"
              aria-pressed={scope === option}
              className={scope === option ? ui.button : ui.secondary}
              disabled={busy}
              onClick={() => onScope(option)}
            >
              {option === "upcoming" ? "Pendentes e próximas" : "Histórico"}
            </button>
          ))}
        </div>
      </div>
      <p className="max-w-prose text-sm leading-relaxed text-lumini-muted">
        Horários em Brasília. Nome e telefone aparecem só para a equipe autenticada; não copie esses
        dados para outros sistemas.
      </p>
      {bookings.length === 0 ? (
        <p className={ui.hint}>
          {scope === "history" ? "Nenhuma reserva encerrada." : "Nenhuma reserva pendente ou futura."}
        </p>
      ) : (
        groups
          .filter((group) => group.items.length > 0)
          .map((group) => (
            <section key={group.title} aria-label={group.title} className="flex flex-col gap-3">
              <h3 className="text-lg font-semibold">
                {group.title} <span className="text-lumini-muted">({group.items.length})</span>
              </h3>
              {group.hint && <p className={ui.hint}>{group.hint}</p>}
              <ul className="flex flex-col gap-4">
                {group.items.map((item) => (
                  <BookingCard
                    key={item.id}
                    booking={item}
                    mutate={mutate}
                    query={query}
                    command={command}
                    busy={busy}
                    sectionHeading={heading}
                  />
                ))}
              </ul>
            </section>
          ))
      )}
    </section>
  );
}

function BookingCard({
  booking,
  mutate,
  query,
  command,
  busy,
  sectionHeading,
}: {
  booking: Booking;
  mutate: Mutation;
  query: Query;
  command: Command;
  busy: boolean;
  sectionHeading: RefObject<HTMLHeadingElement | null>;
}) {
  const path = `/api/admin/bookings/${booking.id}`;
  const version = { expected_version: booking.version };
  const active = !["expired", "cancelled"].includes(booking.status);

  // The card usually moves to another group after an action; keep focus in the section.
  async function act(action: string, body: object, success: string) {
    const done = await mutate(`${path}/${action}`, "POST", { ...version, ...body }, success);
    if (done) rescueFocus(sectionHeading.current);
    return done;
  }

  return (
    <li className={ui.card}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h4 className="text-lg font-semibold">
            {formatDay(booking.starts_at)} · {formatTime(booking.starts_at)}–{formatTime(booking.ends_at)}
          </h4>
          <p className="text-sm text-lumini-muted">
            {booking.service.name} · {booking.professional.name}
          </p>
        </div>
        <span
          className={`${ui.badge} ${
            booking.status === "conflict" || booking.status === "held"
              ? "border-lumini-rose text-lumini-rose"
              : "border-lumini-muted text-lumini-muted"
          }`}
        >
          {STATUS[booking.status]}
        </span>
      </div>

      {booking.calendar_overlap_at && active && (
        <p role="note" className="mt-4 border-l-4 border-lumini-rose bg-lumini-white px-4 py-3 text-sm">
          Atenção: há outro compromisso no Google Agenda neste horário (visto em {formatDate(booking.calendar_overlap_at)}).
          A reserva continua valendo; confira com a profissional e, se for o caso, reagende ou cancele por aqui.
        </p>
      )}
      <dl className="mt-4 grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
        <Detail term="Cliente">{booking.contact.name}</Detail>
        <Detail term="Telefone">{booking.contact.phone}</Detail>
        <Detail term="Código">{booking.code}</Detail>
        <Detail term="Sinal">
          {formatMoney(booking.deposit_brl)}
          {booking.deposit_confirmed_at
            ? ` · conferido em ${formatDate(booking.deposit_confirmed_at)}`
            : " · não conferido"}
        </Detail>
        {booking.status === "held" && booking.expires_at && (
          <Detail term="Prazo do sinal">{formatDate(booking.expires_at)}</Detail>
        )}
        {booking.reschedule_count > 0 && (
          <Detail term="Reagendamentos">{booking.reschedule_count}</Detail>
        )}
        {booking.closed_reason && (
          <Detail term="Situação">{REASONS[booking.closed_reason] ?? booking.closed_reason}</Detail>
        )}
        <Detail term="Origem">{ORIGIN[booking.origin]}</Detail>
        {booking.attendance && <Detail term="Comparecimento">{booking.attendance === "attended" ? "Compareceu" : "Faltou"}</Detail>}
      </dl>
      {booking.status === "confirmed" && !booking.attendance && new Date(booking.starts_at) <= new Date() && (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className="text-sm">Comparecimento:</span>
          <button type="button" className={ui.secondary} disabled={busy}
            onClick={() => void act("attendance", { attendance: "attended" }, "Comparecimento registrado.")}>
            Compareceu
          </button>
          <button type="button" className={ui.secondary} disabled={busy}
            onClick={() => void act("attendance", { attendance: "no_show" }, "Falta registrada. Recomendações pós-procedimento não serão enviadas.")}>
            Faltou
          </button>
        </div>
      )}
      <History path={`${path}/events`} query={query} />

      {active && (
        <div className="mt-4 flex flex-col gap-3">
          {booking.status === "held" && <DepositForm booking={booking} busy={busy} act={act} />}
          {booking.status === "conflict" && (
            <div className="flex flex-col gap-2">
              <p className={ui.hint}>
                Para tentar de novo, primeiro remova ou mova no Google Agenda o compromisso que
                ocupou o horário. O sistema confere a agenda outra vez antes de manter a reserva.
              </p>
              <div>
                <button
                  type="button"
                  className={ui.button}
                  disabled={busy}
                  onClick={() => void act("resolve", { resolution: "retry" }, "Nova tentativa registrada.")}
                >
                  Tentar de novo no Google Agenda
                </button>
              </div>
            </div>
          )}
          {booking.status === "confirmed" && (
            <RescheduleForm booking={booking} busy={busy} query={query} act={act} />
          )}
          {(booking.status === "held" || booking.status === "confirmed") && (
            <ManageLink path={`${path}/manage-link`} busy={busy} command={command} />
          )}
          <details>
            <summary className={ui.summary}>
              {booking.status === "conflict" ? "Liberar horário" : "Cancelar reserva"}
            </summary>
            <p className={ui.hint}>
              O horário volta a ficar livre. A cliente é avisada pelo canal de mensagens quando ele
              estiver ativo. Devolução ou retenção do sinal segue a política da clínica, fora do
              sistema.
            </p>
            <button
              type="button"
              className={`${ui.secondary} mt-3`}
              disabled={busy}
              onClick={() =>
                void (booking.status === "conflict"
                  ? act("resolve", { resolution: "release" }, "Horário liberado.")
                  : act("cancel", {}, "Reserva cancelada."))
              }
            >
              {booking.status === "conflict" ? "Confirmar liberação" : "Confirmar cancelamento"}
            </button>
          </details>
        </div>
      )}
    </li>
  );
}

function Detail({ term, children }: { term: string; children: ReactNode }) {
  return (
    <div>
      <dt className="inline text-lumini-muted">{term}: </dt>
      <dd className="inline">{children}</dd>
    </div>
  );
}

type Act = (action: string, body: object, success: string) => Promise<boolean>;

function DepositForm({ booking, busy, act }: { booking: Booking; busy: boolean; act: Act }) {
  const id = useId();
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    let value: string | null;
    try {
      value = amount(new FormData(event.currentTarget), "amount_brl");
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : "Valor inválido.");
      return;
    }
    if (value === null) {
      setError("Informe o valor recebido.");
      return;
    }
    await act("deposit", { amount_brl: value }, "Sinal confirmado. A reserva será confirmada na agenda.");
  }

  return (
    <details>
      <summary className={ui.summary}>Confirmar sinal recebido</summary>
      <form onSubmit={submit} className="mt-3 flex flex-col gap-3">
        <div className="max-w-xs">
          <label htmlFor={`${id}-amount`} className={ui.label}>
            Valor que entrou na conta (R$)
          </label>
          <input
            id={`${id}-amount`}
            name="amount_brl"
            inputMode="decimal"
            autoComplete="off"
            required
            aria-describedby={`${id}-expected`}
            className={ui.input}
          />
          <p id={`${id}-expected`} className={ui.hint}>
            Previsto: {formatMoney(booking.deposit_brl)}. Valor diferente não é aceito.
          </p>
        </div>
        <label htmlFor={`${id}-check`} className="flex items-start gap-3 text-sm">
          <input id={`${id}-check`} type="checkbox" required className="mt-1 size-5" />
          Conferi o crédito na conta da clínica. Comprovante ou mensagem da cliente não bastam.
        </label>
        {error && (
          <p role="alert" className="text-sm text-lumini-rose">
            {error}
          </p>
        )}
        <div>
          <button type="submit" className={ui.button} disabled={busy}>
            Confirmar sinal
          </button>
        </div>
      </form>
    </details>
  );
}

function RescheduleForm({
  booking,
  busy,
  query,
  act,
}: {
  booking: Booking;
  busy: boolean;
  query: Query;
  act: Act;
}) {
  const id = useId();
  const [day, setDay] = useState(() => clinicDay());
  const [slots, setSlots] = useState<string[] | null>(null);
  const [loading, setLoading] = useState(false);

  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    const found = await query(
      `/api/admin/availability?service_id=${booking.service.id}&professional_id=${booking.professional.id}&first_day=${day}&days=1`,
      decodeSlots,
    );
    setLoading(false);
    setSlots(found);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const chosen = new FormData(event.currentTarget).get("starts_at");
    if (typeof chosen === "string" && chosen) {
      await act("reschedule", { starts_at: chosen }, "Reserva reagendada. O sinal foi mantido.");
    }
  }

  return (
    <details>
      <summary className={ui.summary}>Reagendar</summary>
      <p className={ui.hint}>
        Mantém o sinal já conferido. A nova reserva passa pela confirmação no Google Agenda.
      </p>
      <form onSubmit={search} className="mt-3 flex flex-wrap items-end gap-3">
        <div>
          <label htmlFor={`${id}-day`} className={ui.label}>
            Dia
          </label>
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
            className={ui.input}
          />
        </div>
        <button type="submit" className={ui.secondary} disabled={busy || loading}>
          Ver horários livres
        </button>
      </form>
      {loading && <p aria-busy="true" className={ui.hint}>Consultando horários…</p>}
      {slots !== null &&
        (slots.length === 0 ? (
          <p className={`${ui.hint} mt-3`}>Nenhum horário livre nesse dia.</p>
        ) : (
          <form onSubmit={submit} className="mt-3 flex flex-col gap-3">
            <fieldset>
              <legend className={ui.label}>Horários livres em {formatDay(slots[0])}</legend>
              <div className="mt-2 flex flex-wrap gap-2">
                {slots.map((slot) => (
                  <label
                    key={slot}
                    className="flex min-h-11 items-center gap-2 border border-lumini-muted/50 px-3 text-sm"
                  >
                    <input type="radio" name="starts_at" value={slot} required className="size-4" />
                    {formatTime(slot)}
                  </label>
                ))}
              </div>
            </fieldset>
            <div>
              <button type="submit" className={ui.button} disabled={busy}>
                Reagendar para o horário escolhido
              </button>
            </div>
          </form>
        ))}
    </details>
  );
}

function ManageLink({ path, busy, command }: { path: string; busy: boolean; command: Command }) {
  const id = useId();
  const [link, setLink] = useState<{ url: string; expires_at: string } | null>(null);
  const [copied, setCopied] = useState(false);

  async function copy() {
    if (!link) return;
    try {
      await navigator.clipboard.writeText(link.url);
      setCopied(true);
    } catch {
      setCopied(false); // clipboard blocked: the field stays selectable
    }
  }

  return (
    <details>
      <summary className={ui.summary}>Link de autoatendimento para a cliente</summary>
      <p className={ui.hint}>
        A cliente vê a reserva e, com mais de 24 horas de antecedência, cancela ou reagenda uma vez
        sem falar com a equipe. O link é pessoal: envie só para ela, pela conversa da clínica.
      </p>
      {link ? (
        <div className="mt-3 flex flex-col gap-2">
          <label htmlFor={`${id}-url`} className={ui.label}>
            Link (vale até {formatDate(link.expires_at)})
          </label>
          <input
            id={`${id}-url`}
            readOnly
            value={link.url}
            onFocus={(event) => event.currentTarget.select()}
            className={ui.input}
          />
          <div className="flex items-center gap-3">
            <button type="button" className={ui.secondary} onClick={() => void copy()}>
              Copiar link
            </button>
            <span role="status" className={ui.hint}>{copied ? "Copiado." : ""}</span>
          </div>
        </div>
      ) : (
        <button
          type="button"
          className={`${ui.secondary} mt-3`}
          disabled={busy}
          onClick={() => void command(path, {}, decodeManageLink).then((found) => found && setLink(found))}
        >
          Gerar link
        </button>
      )}
    </details>
  );
}
