"use client";

import type { Integrations } from "@/lib/admin/types";

import { formatDate, ui } from "./ui";

const WHATSAPP_STATE: Record<string, string> = {
  open: "Conectado",
  connecting: "Conectando…",
  close: "Desconectado",
  qr_required: "Precisa ler um novo QR Code",
  unknown: "Estado desconhecido",
};

export function attentionText(integrations: Integrations): string | null {
  const whatsapp = integrations.whatsapp;
  if (!whatsapp.configured || !whatsapp.needs_attention) return null;
  return whatsapp.state === "qr_required"
    ? "O WhatsApp da clínica precisa ser reconectado com um novo QR Code. Enquanto isso o bot não responde e os avisos ficam na fila."
    : "O WhatsApp da clínica está sem conexão. Enquanto isso o bot não responde e os avisos ficam na fila.";
}

export function IntegrationsSection({ integrations }: { integrations: Integrations }) {
  const whatsapp = integrations.whatsapp;
  return (
    <section aria-labelledby="integracoes" className="flex flex-col gap-6">
      <h2 id="integracoes" className="font-display text-2xl">
        Integrações
      </h2>

      <article className={ui.card} aria-labelledby="int-whatsapp">
        <h3 id="int-whatsapp" className="text-lg font-semibold">WhatsApp (Evolution)</h3>
        {whatsapp.configured ? (
          <>
            <p className="mt-2">
              {whatsapp.state ? WHATSAPP_STATE[whatsapp.state] ?? whatsapp.state : "Sem notícias da instância ainda"}
              {whatsapp.changed_at && <span className="text-lumini-muted"> · desde {formatDate(whatsapp.changed_at)}</span>}
            </p>
            {whatsapp.needs_attention && (
              <p className={`${ui.hint} mt-2`}>
                Reconexão: alguém autorizado abre o gerenciador da Evolution e lê o QR Code com o celular da
                clínica (WhatsApp → Aparelhos conectados). O passo a passo está no manual de operação.
              </p>
            )}
            <p className="mt-4">
              Conversas com a equipe (bot pausado): <strong>{whatsapp.human_mode_conversations}</strong>
            </p>
            <p className={ui.hint}>
              Quando alguém da equipe responde pelo WhatsApp, o bot para naquela conversa. Para devolver ao
              bot, envie <code>#bot</code> na própria conversa. Para pausar sem responder, envie <code>#pausa</code>.
            </p>
          </>
        ) : (
          <p className={`${ui.hint} mt-2`}>Não configurado: o bot e os avisos automáticos estão desligados.</p>
        )}
      </article>

      <article className={ui.card} aria-labelledby="int-agenda">
        <h3 id="int-agenda" className="text-lg font-semibold">Google Agenda</h3>
        <p className="mt-2">
          {integrations.calendar_configured
            ? "Conta de serviço configurada."
            : "Não configurado: horários e reservas online ficam indisponíveis."}
        </p>
      </article>

      <article className={ui.card} aria-labelledby="int-links">
        <h3 id="int-links" className="text-lg font-semibold">Links de autoatendimento</h3>
        <p className="mt-2">
          {integrations.self_service_configured
            ? "Configurados: clientes podem ver, cancelar e reagendar pelo link."
            : "Não configurados: alterações só pela equipe."}
        </p>
      </article>
    </section>
  );
}
