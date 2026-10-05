"use client";

import Script from "next/script";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  AdminApiError,
  adminErrorMessage,
  adminRequest,
  decodeBookings,
  decodeIdentity,
  decodeIntegrations,
  decodeProfessionals,
  decodeServices,
} from "@/lib/admin/api";
import { GOOGLE_SCRIPT, googleAccountsId, type CredentialResponse } from "@/lib/admin/google";
import { AdminSession, type RequestTicket } from "@/lib/admin/session";
import type { AdminConfig } from "@/lib/admin/config";
import type { AdminIdentity, Booking, BookingScope, Catalog, Command, Integrations, Mutation, Query } from "@/lib/admin/types";

import { AgendaSection } from "./agenda";
import { BookingsSection } from "./bookings";
import { IntegrationsSection, attentionText } from "./integrations";
import { ProfessionalsSection } from "./professionals";
import { ServicesSection } from "./services";
import { ui } from "./ui";

type Notice = { kind: "success" | "error"; text: string } | null;
type View = "bookings" | "agenda" | "catalog" | "integrations";

const VIEWS: { id: View; label: string }[] = [
  { id: "bookings", label: "Reservas" },
  { id: "agenda", label: "Agenda" },
  { id: "catalog", label: "Catálogo" },
  { id: "integrations", label: "Integrações" },
];

export function AdminApp({ config, nonce }: { config: AdminConfig | null; nonce?: string }) {
  return (
    <div className="mx-auto flex min-h-svh w-[min(100%-2rem,1100px)] flex-col">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-lumini-gold/40 py-6">
        <p className="flex items-baseline gap-3">
          <span className="font-display text-3xl tracking-wide">lumini</span>
          <span className="text-xs uppercase tracking-[0.18em] text-lumini-muted">Painel interno</span>
        </p>
      </header>
      {config ? (
        <ConfiguredAdmin config={config} nonce={nonce} />
      ) : (
        <main id="conteudo" tabIndex={-1} className="py-10 focus:outline-none">
          <h1 className="font-display text-3xl">Painel não configurado</h1>
          <p className="mt-4 max-w-prose leading-relaxed text-lumini-muted">
            O login administrativo precisa de um Client ID do Google e do endereço HTTPS da API,
            definidos no ambiente de implantação. Sem eles o acesso permanece bloqueado.
          </p>
        </main>
      )}
    </div>
  );
}

function ConfiguredAdmin({ config, nonce }: { config: AdminConfig; nonce?: string }) {
  const [session] = useState(() => new AdminSession());
  const [identity, setIdentity] = useState<AdminIdentity | null>(null);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [bookings, setBookings] = useState<Booking[] | null>(null);
  const [integrations, setIntegrations] = useState<Integrations | null>(null);
  const [scope, setScope] = useState<BookingScope>("upcoming");
  const scopeRef = useRef<BookingScope>("upcoming");
  const [view, setView] = useState<View>("bookings");
  const [notice, setNotice] = useState<Notice>(null);
  const [busy, setBusy] = useState(false);
  const [scriptReady, setScriptReady] = useState(false);
  const buttonRef = useRef<HTMLDivElement>(null);

  useEffect(() => () => session.clear(), [session]);

  const signOut = useCallback(
    (message: Notice) => {
      session.clear();
      googleAccountsId()?.disableAutoSelect();
      setIdentity(null);
      setCatalog(null);
      setBookings(null);
      setIntegrations(null);
      setNotice(message);
    },
    [session],
  );

  const report = useCallback(
    (error: unknown) => {
      if (error instanceof DOMException && error.name === "AbortError") return;
      if (error instanceof AdminApiError && error.status === 401) {
        signOut({ kind: "error", text: adminErrorMessage(401) });
        return;
      }
      setNotice({
        kind: "error",
        text: error instanceof AdminApiError ? error.message : adminErrorMessage(0),
      });
    },
    [signOut],
  );

  const loadCatalog = useCallback(
    async (ticket: RequestTicket) => {
      const [professionals, services, booked, status] = await Promise.all([
        adminRequest(config.apiOrigin, ticket, "/api/admin/professionals"),
        adminRequest(config.apiOrigin, ticket, "/api/admin/services"),
        adminRequest(config.apiOrigin, ticket, `/api/admin/bookings?scope=${scopeRef.current}`),
        adminRequest(config.apiOrigin, ticket, "/api/admin/integrations"),
      ]);
      if (!ticket.isCurrent()) return;
      setCatalog({
        professionals: decodeProfessionals(professionals),
        services: decodeServices(services),
      });
      setBookings(decodeBookings(booked));
      setIntegrations(decodeIntegrations(status));
    },
    [config.apiOrigin],
  );

  const handleCredential = useCallback(
    async (response: CredentialResponse) => {
      if (!response.credential) {
        setNotice({ kind: "error", text: "O Google não concluiu o login. Tente novamente." });
        return;
      }
      const ticket = session.start(response.credential);
      setNotice(null);
      setBusy(true);
      try {
        const me = decodeIdentity(await adminRequest(config.apiOrigin, ticket, "/api/admin/me"));
        if (!ticket.isCurrent()) return;
        setIdentity(me);
        await loadCatalog(ticket);
      } catch (error) {
        if (ticket.isCurrent()) session.clear();
        report(error);
      } finally {
        setBusy(false);
      }
    },
    [config.apiOrigin, loadCatalog, report, session],
  );

  useEffect(() => {
    if (!scriptReady || identity) return;
    const google = googleAccountsId();
    if (!google || !buttonRef.current) return;
    google.initialize({
      client_id: config.clientId,
      callback: (response) => void handleCredential(response),
      auto_select: false,
      cancel_on_tap_outside: true,
      ux_mode: "popup",
      use_fedcm_for_button: true,
    });
    google.renderButton(buttonRef.current, {
      type: "standard",
      theme: "outline",
      size: "large",
      text: "signin_with",
      shape: "rectangular",
      locale: "pt-BR",
    });
  }, [scriptReady, identity, config.clientId, handleCredential]);

  const mutate: Mutation = useCallback(
    async (path, method, body, success) => {
      const ticket = session.capture();
      if (!ticket) {
        signOut({ kind: "error", text: adminErrorMessage(401) });
        return false;
      }
      setBusy(true);
      try {
        await adminRequest(config.apiOrigin, ticket, path, method, body);
        if (!ticket.isCurrent()) return false;
        await loadCatalog(ticket);
        setNotice({ kind: "success", text: success });
        return true;
      } catch (error) {
        report(error);
        return false;
      } finally {
        setBusy(false);
      }
    },
    [config.apiOrigin, loadCatalog, report, session, signOut],
  );

  const query: Query = useCallback(
    async (path, decode) => {
      const ticket = session.capture();
      if (!ticket) {
        signOut({ kind: "error", text: adminErrorMessage(401) });
        return null;
      }
      try {
        const result = decode(await adminRequest(config.apiOrigin, ticket, path));
        return ticket.isCurrent() ? result : null;
      } catch (error) {
        report(error);
        return null;
      }
    },
    [config.apiOrigin, report, session, signOut],
  );

  const command: Command = useCallback(
    async (path, body, decode) => {
      const ticket = session.capture();
      if (!ticket) {
        signOut({ kind: "error", text: adminErrorMessage(401) });
        return null;
      }
      setBusy(true);
      try {
        const result = decode(await adminRequest(config.apiOrigin, ticket, path, "POST", body));
        return ticket.isCurrent() ? result : null;
      } catch (error) {
        report(error);
        return null;
      } finally {
        setBusy(false);
      }
    },
    [config.apiOrigin, report, session, signOut],
  );

  const changeScope = useCallback(
    async (next: BookingScope) => {
      const ticket = session.capture();
      if (!ticket) return;
      setBusy(true);
      try {
        const booked = decodeBookings(
          await adminRequest(config.apiOrigin, ticket, `/api/admin/bookings?scope=${next}`),
        );
        if (!ticket.isCurrent()) return;
        // Switch the heading and the list together, never one before the other.
        scopeRef.current = next;
        setScope(next);
        setBookings(booked);
      } catch (error) {
        report(error);
      } finally {
        setBusy(false);
      }
    },
    [config.apiOrigin, report, session],
  );

  const reload = useCallback(async () => {
    const ticket = session.capture();
    if (!ticket) return;
    setBusy(true);
    try {
      await loadCatalog(ticket);
      setNotice({ kind: "success", text: "Dados atualizados." });
    } catch (error) {
      report(error);
    } finally {
      setBusy(false);
    }
  }, [loadCatalog, report, session]);

  return (
    <>
      <Script
        src={GOOGLE_SCRIPT}
        strategy="afterInteractive"
        nonce={nonce}
        onReady={() => setScriptReady(true)}
        onError={() =>
          setNotice({ kind: "error", text: "Não foi possível carregar o login do Google." })
        }
      />
      {identity && (
        <div className="flex flex-wrap items-center justify-end gap-3 pt-4 text-sm">
          <span className="text-lumini-muted">
            Conta: <strong className="text-lumini-ink">{identity.email}</strong>
          </span>
          <button type="button" className={ui.secondary} disabled={busy} onClick={() => void reload()}>
            Recarregar
          </button>
          <button
            type="button"
            className={ui.secondary}
            onClick={() => signOut({ kind: "success", text: "Você saiu do painel." })}
          >
            Sair
          </button>
        </div>
      )}
      <div
        role="status"
        aria-live="polite"
        className={
          notice
            ? `mt-4 border-l-4 px-4 py-3 text-sm ${
                notice.kind === "error"
                  ? "border-lumini-rose bg-lumini-white text-lumini-ink"
                  : "border-lumini-gold bg-lumini-white text-lumini-ink"
              }`
            : "sr-only"
        }
      >
        {notice?.text}
      </div>
      <main id="conteudo" tabIndex={-1} className="flex-1 py-8 focus:outline-none">
        {!identity ? (
          <section aria-labelledby="entrar" className="max-w-prose">
            <h1 id="entrar" className="font-display text-3xl">
              Entrar no painel
            </h1>
            <p className="mt-4 leading-relaxed text-lumini-muted">
              Acesso restrito a e-mails autorizados da clínica. Use uma conta Gmail ou Google
              Workspace. O login vale enquanto esta aba estiver aberta.
            </p>
            <div ref={buttonRef} className="mt-6 min-h-11" />
            {!scriptReady && <p className={ui.hint}>Carregando o login do Google…</p>}
          </section>
        ) : !catalog || !bookings || !integrations ? (
          <p aria-busy="true">Carregando dados…</p>
        ) : (
          <>
            <h1 className="sr-only">Painel da clínica</h1>
            {attentionText(integrations) && (
              <p className="mb-6 border-l-4 border-lumini-rose bg-lumini-white px-4 py-3 text-sm">
                {attentionText(integrations)}{" "}
                <button type="button" className="underline" onClick={() => setView("integrations")}>
                  Ver integrações
                </button>
              </p>
            )}
            <nav aria-label="Seções do painel" className="mb-8 flex flex-wrap gap-2 border-b border-lumini-gold/40 pb-4">
              {VIEWS.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  aria-current={view === item.id ? "page" : undefined}
                  className={view === item.id ? ui.button : ui.secondary}
                  onClick={() => setView(item.id)}
                >
                  {item.label}
                </button>
              ))}
            </nav>
            {view === "bookings" && (
              <BookingsSection
                bookings={bookings}
                scope={scope}
                onScope={(next) => void changeScope(next)}
                mutate={mutate}
                query={query}
                command={command}
                busy={busy}
              />
            )}
            {view === "agenda" && (
              <AgendaSection
                professionals={catalog.professionals}
                services={catalog.services}
                mutate={mutate}
                query={query}
                busy={busy}
              />
            )}
            {view === "integrations" && <IntegrationsSection integrations={integrations} />}
            {view === "catalog" && (
              <div className="flex flex-col gap-12">
                <ProfessionalsSection professionals={catalog.professionals} mutate={mutate} busy={busy} />
                <ServicesSection
                  catalog={catalog}
                  identity={identity}
                  mutate={mutate}
                  busy={busy}
                />
              </div>
            )}
          </>
        )}
      </main>
    </>
  );
}
