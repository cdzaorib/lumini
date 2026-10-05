"use client";

import { useState } from "react";

import { decodeLeads } from "@/lib/admin/api";
import type { Lead, LeadStatus, Mutation, Query } from "@/lib/admin/types";

import { formatDate, ui } from "./ui";

const FILTERS: { status: LeadStatus; label: string }[] = [
  { status: "new", label: "Novos" },
  { status: "contacted", label: "Contatados" },
  { status: "converted", label: "Convertidos" },
  { status: "discarded", label: "Descartados" },
];
const PERIOD: Record<Lead["preferred_period"], string> = { morning: "manhã", afternoon: "tarde", any: "qualquer horário" };
const ACTIONS: { status: LeadStatus; label: string }[] = [
  { status: "contacted", label: "Marcar como contatado" },
  { status: "converted", label: "Virou agendamento" },
  { status: "discarded", label: "Descartar" },
];

type Props = { initial: Lead[]; mutate: Mutation; query: Query; busy: boolean };

export function LeadsSection({ initial, mutate, query, busy }: Props) {
  const [filter, setFilter] = useState<LeadStatus>("new");
  const [items, setItems] = useState<Lead[]>(initial);
  const [shownFor, setShownFor] = useState<Lead[]>(initial);

  // Parent reloads (after any action) replace the "new" list.
  if (shownFor !== initial) {
    setShownFor(initial);
    if (filter === "new") setItems(initial);
  }

  async function show(status: LeadStatus) {
    const found = await query(`/api/admin/leads?status=${status}`, decodeLeads);
    if (found) {
      setFilter(status);
      setItems(found);
    }
  }

  async function change(lead: Lead, status: LeadStatus, label: string) {
    if (await mutate(`/api/admin/leads/${lead.id}/status`, "POST", { status }, `${label}: ${lead.name}.`)) {
      await show(filter);
    }
  }

  return (
    <section aria-labelledby="leads" className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h2 id="leads" className="font-display text-2xl">
          Pedidos de contato
        </h2>
        <div role="group" aria-label="Mostrar" className="flex flex-wrap gap-2">
          {FILTERS.map((item) => (
            <button
              key={item.status}
              type="button"
              aria-pressed={filter === item.status}
              className={filter === item.status ? ui.button : ui.secondary}
              disabled={busy}
              onClick={() => void show(item.status)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>
      <p className="max-w-prose text-sm leading-relaxed text-lumini-muted">
        Pessoas que pediram contato pelo site. Fale pelo WhatsApp da clínica e registre o andamento. Pedidos não
        convertidos são apagados automaticamente após 3 meses. Só envie promoções a quem marcou essa opção.
      </p>
      {items.length === 0 ? (
        <p className={ui.hint}>Nenhum pedido nesta lista.</p>
      ) : (
        <ul className="flex flex-col gap-4">
          {items.map((lead) => (
            <li key={lead.id} className={ui.card}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h3 className="text-lg font-semibold">{lead.name}</h3>
                  <p className="text-sm text-lumini-muted">
                    {lead.service ?? "Interesse não informado"} · prefere {PERIOD[lead.preferred_period]}
                    {lead.city ? ` · ${lead.city}` : ""}
                  </p>
                </div>
                <span className={`${ui.badge} border-lumini-muted text-lumini-muted`}>{formatDate(lead.created_at)}</span>
              </div>
              <p className="mt-3 text-sm">
                Telefone:{" "}
                <a
                  className="text-lumini-rose underline"
                  href={`https://wa.me/${lead.phone.replace(/\D/g, "")}`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {lead.phone}
                </a>{" "}
                · {lead.marketing_consent ? "aceitou receber novidades" : "não quer promoções"}
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                {ACTIONS.filter((action) => action.status !== lead.status).map((action) => (
                  <button
                    key={action.status}
                    type="button"
                    className={ui.secondary}
                    disabled={busy}
                    onClick={() => void change(lead, action.status, action.label)}
                  >
                    {action.label}
                  </button>
                ))}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
