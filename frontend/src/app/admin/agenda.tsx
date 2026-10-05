"use client";

import { useEffect, useId, useRef, useState, type FormEvent } from "react";

import { decodeSchedule, decodeSlots } from "@/lib/admin/api";
import { scheduleProblem, WEEKDAYS } from "@/lib/admin/schedule";
import type { Mutation, Professional, Query, Schedule, ScheduleRule, Service } from "@/lib/admin/types";

import { clinicDay, formatDay, formatTime, ui } from "./ui";

type Props = {
  professionals: Professional[];
  services: Service[];
  mutate: Mutation;
  query: Query;
  busy: boolean;
};

export function AgendaSection({ professionals, services, mutate, query, busy }: Props) {
  const id = useId();
  const [selected, setSelected] = useState("");
  const person = professionals.find((item) => item.id === selected);

  return (
    <section aria-labelledby="agenda" className="flex flex-col gap-4">
      <h2 id="agenda" className="font-display text-2xl">
        Agenda
      </h2>
      <p className="max-w-prose text-sm leading-relaxed text-lumini-muted">
        Horários de atendimento por profissional, em hora de Brasília. Os horários oferecidos às
        clientes são estas faixas, menos as reservas e os compromissos do Google Agenda dela.
        Alterar a agenda não muda a verificação de credenciais nem move reservas já feitas.
      </p>
      <div className="max-w-sm">
        <label htmlFor={`${id}-professional`} className={ui.label}>
          Profissional
        </label>
        <select
          id={`${id}-professional`}
          value={selected}
          onChange={(event) => setSelected(event.target.value)}
          className={ui.input}
        >
          <option value="">Escolha uma profissional</option>
          {professionals.map((item) => (
            <option key={item.id} value={item.id}>
              {item.display_name}
            </option>
          ))}
        </select>
      </div>
      {person && (
        <ScheduleEditor
          key={person.id}
          professional={person}
          services={services.filter((item) => item.professional_ids.includes(person.id))}
          mutate={mutate}
          query={query}
          busy={busy}
        />
      )}
    </section>
  );
}

type EditableRule = ScheduleRule & { key: number };

function ScheduleEditor({
  professional,
  services,
  mutate,
  query,
  busy,
}: {
  professional: Professional;
  services: Service[];
  mutate: Mutation;
  query: Query;
  busy: boolean;
}) {
  const id = useId();
  const path = `/api/admin/professionals/${professional.id}/schedule`;
  const nextKey = useRef(0);
  const [schedule, setSchedule] = useState<Schedule | null>(null);
  const [calendarId, setCalendarId] = useState("");
  const [rules, setRules] = useState<EditableRule[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loads, setLoads] = useState(0);

  useEffect(() => {
    let ignore = false;
    void query(path, decodeSchedule).then((found) => {
      if (ignore || !found) return;
      setSchedule(found);
      setCalendarId(found.calendar_id ?? "");
      setRules(found.rules.map((rule) => ({ ...rule, key: nextKey.current++ })));
    });
    return () => {
      ignore = true;
    };
  }, [path, query, loads]);

  function change(key: number, field: "start" | "end", value: string) {
    setRules((current) => current.map((rule) => (rule.key === key ? { ...rule, [field]: value } : rule)));
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!schedule) return;
    const payload = rules.map(({ weekday, start, end }) => ({ weekday, start, end }));
    const calendar = calendarId.trim();
    const problem = scheduleProblem(calendar, payload);
    setError(problem);
    if (problem) return;
    const saved = await mutate(
      path,
      "PUT",
      { expected_revision: schedule.revision, calendar_id: calendar || null, rules: payload },
      `Agenda de ${professional.display_name} salva.`,
    );
    if (saved) setLoads((count) => count + 1);
  }

  if (!schedule) return <p aria-busy="true">Carregando agenda…</p>;

  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={save} className={`${ui.card} flex flex-col gap-5`}>
        <h3 className="text-lg font-semibold">{professional.display_name}</h3>
        {schedule.revision === 0 && <p className={ui.hint}>Agenda ainda não configurada.</p>}
        <div className="max-w-xl">
          <label htmlFor={`${id}-calendar`} className={ui.label}>
            ID do Google Agenda
          </label>
          <input
            id={`${id}-calendar`}
            value={calendarId}
            onChange={(event) => setCalendarId(event.target.value)}
            maxLength={255}
            autoComplete="off"
            spellCheck={false}
            aria-describedby={`${id}-calendar-hint`}
            className={ui.input}
          />
          <p id={`${id}-calendar-hint`} className={ui.hint}>
            No Google Agenda: Configurações da agenda → Integrar agenda → ID da agenda. Não é
            possível trocar enquanto houver reservas ativas nele.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          {WEEKDAYS.map((name, weekday) => {
            const windows = rules.filter((rule) => rule.weekday === weekday);
            return (
              <fieldset key={name} className="border border-lumini-muted/30 p-3">
                <legend className="px-1 text-sm font-medium">{name}</legend>
                {windows.length === 0 && <p className={ui.hint}>Sem atendimento.</p>}
                <ul className="flex flex-col gap-2">
                  {windows.map((rule, index) => (
                    <li key={rule.key} className="flex flex-wrap items-end gap-2">
                      <TimeField
                        label={`${name}, faixa ${index + 1}: início`}
                        value={rule.start}
                        onChange={(value) => change(rule.key, "start", value)}
                      />
                      <TimeField
                        label={`${name}, faixa ${index + 1}: fim`}
                        value={rule.end}
                        onChange={(value) => change(rule.key, "end", value)}
                      />
                      <button
                        type="button"
                        className={ui.secondary}
                        aria-label={`Remover ${name}, faixa ${index + 1}`}
                        onClick={() => setRules((current) => current.filter((item) => item.key !== rule.key))}
                      >
                        Remover
                      </button>
                    </li>
                  ))}
                </ul>
                <button
                  type="button"
                  className={`${ui.summary} mt-2`}
                  onClick={() =>
                    setRules((current) => [
                      ...current,
                      { weekday, start: "09:00", end: "18:00", key: nextKey.current++ },
                    ])
                  }
                >
                  Adicionar faixa em {name.toLowerCase()}
                </button>
              </fieldset>
            );
          })}
        </div>
        {error && (
          <p role="alert" className="text-sm text-lumini-rose">
            {error}
          </p>
        )}
        <div className="flex flex-wrap items-center gap-3">
          <button type="submit" className={ui.button} disabled={busy}>
            Salvar agenda
          </button>
          <span className={ui.hint}>Horários em múltiplos de 15 minutos; faixas do mesmo dia não podem se sobrepor.</span>
        </div>
      </form>

      <Preview professional={professional} services={services} query={query} busy={busy} />
    </div>
  );
}

function TimeField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      <input
        id={id}
        type="time"
        step={900}
        required
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={`${ui.input} mt-0 w-32`}
      />
    </div>
  );
}

function Preview({
  professional,
  services,
  query,
  busy,
}: {
  professional: Professional;
  services: Service[];
  query: Query;
  busy: boolean;
}) {
  const id = useId();
  const direct = services.filter((item) => item.booking_mode === "direct");
  const [serviceId, setServiceId] = useState(direct[0]?.id ?? "");
  const [day, setDay] = useState(() => clinicDay());
  const [slots, setSlots] = useState<string[] | null>(null);

  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSlots(
      await query(
        `/api/admin/availability?service_id=${serviceId}&professional_id=${professional.id}&first_day=${day}&days=7`,
        decodeSlots,
      ),
    );
  }

  const byDay = new Map<string, string[]>();
  for (const slot of slots ?? []) {
    const key = clinicDay(slot);
    byDay.set(key, [...(byDay.get(key) ?? []), slot]);
  }

  return (
    <section aria-labelledby={`${id}-title`} className={ui.card}>
      <h3 id={`${id}-title`} className="text-lg font-semibold">
        Prévia de horários livres
      </h3>
      <p className={ui.hint}>
        Mostra o que uma cliente veria nos próximos 7 dias a partir da data: agenda salva, mínimo de
        3 horas de antecedência, reservas e compromissos do Google Agenda. Só procedimentos
        publicados, com agendamento direto e credencial verificada podem ser reservados.
      </p>
      {direct.length === 0 ? (
        <p className={`${ui.hint} mt-3`}>
          Nenhum procedimento de agendamento direto vinculado a esta profissional.
        </p>
      ) : (
        <form onSubmit={search} className="mt-3 flex flex-wrap items-end gap-3">
          <div>
            <label htmlFor={`${id}-service`} className={ui.label}>
              Procedimento
            </label>
            <select
              id={`${id}-service`}
              value={serviceId}
              onChange={(event) => {
                setServiceId(event.target.value);
                setSlots(null);
              }}
              className={ui.input}
            >
              {direct.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor={`${id}-day`} className={ui.label}>
              A partir de
            </label>
            <input
              id={`${id}-day`}
              type="date"
              required
              value={day}
              onChange={(event) => {
                setDay(event.target.value);
                setSlots(null);
              }}
              className={ui.input}
            />
          </div>
          <button type="submit" className={ui.secondary} disabled={busy || !serviceId}>
            Ver prévia
          </button>
        </form>
      )}
      {slots !== null &&
        (slots.length === 0 ? (
          <p className={`${ui.hint} mt-3`}>Nenhum horário livre neste período.</p>
        ) : (
          <dl className="mt-4 flex flex-col gap-2 text-sm">
            {[...byDay.entries()].map(([key, items]) => (
              <div key={key}>
                <dt className="font-medium">{formatDay(items[0])}</dt>
                <dd className="text-lumini-muted">{items.map(formatTime).join(" · ")}</dd>
              </div>
            ))}
          </dl>
        ))}
    </section>
  );
}
