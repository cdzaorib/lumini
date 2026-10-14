"use client";

import { useEffect, useState } from "react";

import { decodeMetrics } from "@/lib/admin/api";
import type { Count, Metrics, Query } from "@/lib/admin/types";

import { ui } from "./ui";

const PERIODS = [7, 30, 90, 365] as const;
const LABELS: Record<string, string> = {
  whatsapp: "WhatsApp", site: "Site", reschedule: "Reagendamento", other: "Outros/equipe",
  new: "Novos", contacted: "Contatados", converted: "Convertidos", discarded: "Descartados",
  cancelled_by_client: "Pela cliente", cancelled_by_staff: "Pela equipe", conflict_released: "Conflito liberado",
  deposit_timeout: "Sinal não pago a tempo", calendar_timeout: "Agenda não respondeu",
  health_condition: "Assunto de saúde", requested: "Pediu atendente", manual_reply: "Equipe respondeu",
  pause_command: "Pausa (#pausa)", booking_handoff: "Problema no horário", evaluation: "Procedimento com avaliação",
  agenda_unavailable: "Agenda indisponível", calendar_not_configured: "Agenda não configurada",
  booking_refused: "Reserva recusada", no_phone: "Sem telefone", no_catalog: "Sem catálogo", unknown: "Sem motivo",
};

// Headline counts are stat tiles: the number is the chart. Text stays in ink tokens.
function Tile({ label, value, note }: { label: string; value: number; note?: string }) {
  return (
    <div className={ui.card}>
      <dt className="text-sm text-lumini-muted">{label}</dt>
      <dd className="mt-1 text-4xl font-medium tabular-nums">{value.toLocaleString("pt-BR")}</dd>
      {note && <dd className="mt-1 text-xs text-lumini-muted">{note}</dd>}
    </div>
  );
}

function Breakdown({ title, items, empty }: { title: string; items: Count[]; empty: string }) {
  return (
    <div className={ui.card}>
      <h3 className="font-semibold">{title}</h3>
      {items.length === 0 ? (
        <p className={ui.hint}>{empty}</p>
      ) : (
        <table className="mt-3 w-full text-sm">
          <thead className="sr-only">
            <tr><th scope="col">Item</th><th scope="col">Quantidade</th></tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.key} className="border-t border-lumini-gold/30">
                <th scope="row" className="py-2 text-left font-normal">{LABELS[item.key] ?? item.key}</th>
                <td className="py-2 text-right tabular-nums">{item.count.toLocaleString("pt-BR")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export function MetricsSection({ query, busy }: { query: Query; busy: boolean }) {
  const [days, setDays] = useState<(typeof PERIODS)[number]>(30);
  const [metrics, setMetrics] = useState<Metrics | null>(null);

  useEffect(() => {
    let ignore = false;
    void query(`/api/admin/metrics?days=${days}`, decodeMetrics).then((found) => {
      if (!ignore && found) setMetrics(found);
    });
    return () => {
      ignore = true;
    };
  }, [days, query]);

  return (
    <section aria-labelledby="resumo" className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h2 id="resumo" className="font-display text-2xl">Resumo</h2>
        <div role="group" aria-label="Período" className="flex flex-wrap gap-2">
          {PERIODS.map((option) => (
            <button key={option} type="button" aria-pressed={days === option} disabled={busy}
              className={days === option ? ui.button : ui.secondary} onClick={() => setDays(option)}>
              {option === 365 ? "12 meses" : `${option} dias`}
            </button>
          ))}
        </div>
      </div>
      {!metrics || metrics.days !== days ? (
        <p aria-busy="true">Calculando…</p>
      ) : (
        <>
          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Tile label="Pedidos de contato" value={metrics.leads_total} note={`${metrics.leads_marketing_consent} aceitaram novidades`} />
            <Tile label="Reservas pedidas" value={metrics.bookings_requested} />
            <Tile label="Sinais confirmados" value={metrics.deposits_confirmed} />
            <Tile label="Confirmados nos próximos 7 dias" value={metrics.upcoming_confirmed_7d} />
            <Tile label="Atendimentos no período" value={metrics.appointments} note={metrics.attendance_unmarked ? `${metrics.attendance_unmarked} sem comparecimento marcado` : undefined} />
            <Tile label="Compareceram" value={metrics.attended} />
            <Tile label="Faltaram" value={metrics.no_show} />
            <Tile label="Reagendamentos" value={metrics.reschedules} />
          </dl>
          <div className="grid gap-4 md:grid-cols-2">
            <Breakdown title="Origem das reservas" items={metrics.bookings_by_origin} empty="Nenhuma reserva no período." />
            <Breakdown title="Procura por procedimento" items={metrics.demand_by_service} empty="Nenhuma reserva no período." />
            <Breakdown title="Pedidos de contato por situação" items={metrics.leads_by_status} empty="Nenhum pedido no período." />
            <Breakdown title="Cancelamentos" items={metrics.cancellations} empty="Nenhum cancelamento no período." />
            <Breakdown title="Reservas expiradas" items={metrics.expired} empty="Nenhuma expiração no período." />
            <Breakdown title="Encaminhamentos no WhatsApp (motivo)" items={metrics.handoffs_by_reason} empty="Nenhum encaminhamento no WhatsApp no período." />
          </div>
          <p className={ui.hint}>Contagens sem dados pessoais. Faltas dependem da marcação de comparecimento em cada reserva.</p>
        </>
      )}
    </section>
  );
}
