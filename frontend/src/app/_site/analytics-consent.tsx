"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef, useSyncExternalStore } from "react";

import { ANALYTICS_CONSENT_KEY, PLAUSIBLE_EVENT_URL, type AnalyticsChoice } from "@/lib/public/analytics";

const CHANGE_EVENT = "lumini:analytics-consent";
let sessionChoice: AnalyticsChoice | undefined;

function readChoice(): AnalyticsChoice | null {
  if (sessionChoice !== undefined) return sessionChoice;
  try {
    const value = window.localStorage.getItem(ANALYTICS_CONSENT_KEY);
    return value === "accepted" || value === "rejected" ? value : null;
  } catch {
    return null;
  }
}

function subscribe(onChange: () => void) {
  const onStorage = (event: StorageEvent) => {
    if (event.key === null || event.key === ANALYTICS_CONSENT_KEY) {
      sessionChoice = undefined;
      onChange();
    }
  };
  window.addEventListener("storage", onStorage);
  window.addEventListener(CHANGE_EVENT, onChange);
  return () => {
    window.removeEventListener("storage", onStorage);
    window.removeEventListener(CHANGE_EVENT, onChange);
  };
}

function saveChoice(choice: AnalyticsChoice) {
  sessionChoice = choice;
  try {
    window.localStorage.setItem(ANALYTICS_CONSENT_KEY, choice);
    sessionChoice = undefined;
  } catch {
    // Storage can be blocked: the explicit choice then applies only to this tab.
    // Quota errors can prevent writing while still allowing deletion of an older grant.
    if (choice === "rejected") {
      try { window.localStorage.removeItem(ANALYTICS_CONSENT_KEY); } catch { /* storage fully blocked */ }
    }
  }
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

const button = "min-h-11 border border-lumini-rose px-4 py-2 text-sm text-lumini-rose hover:bg-lumini-paper focus-visible:outline-3 focus-visible:outline-offset-4 focus-visible:outline-lumini-rose disabled:cursor-not-allowed disabled:opacity-60";

export function AnalyticsConsent({ domain }: { domain: string | null }) {
  const choice = useSyncExternalStore(subscribe, readChoice, () => null);
  const pathname = usePathname();
  const sent = useRef(false);
  const summary = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!domain || choice !== "accepted" || pathname !== "/" || sent.current) return;
    const controller = new AbortController();
    // Deferring also avoids duplicate requests during React's development effect replay.
    const timer = window.setTimeout(() => {
      if (readChoice() !== "accepted" || window.location.pathname !== "/") return;
      sent.current = true;
      void fetch(PLAUSIBLE_EVENT_URL, {
        method: "POST",
        headers: { "Content-Type": "text/plain" },
        body: JSON.stringify({ name: "pageview", domain, url: `${window.location.origin}/` }),
        credentials: "omit",
        referrerPolicy: "no-referrer",
        signal: controller.signal,
      }).catch(() => {
        // Optional measurement must never interfere with the clinic's service or log user data.
      });
    }, 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [choice, domain, pathname]);

  function choose(nextChoice: AnalyticsChoice) {
    saveChoice(nextChoice);
    summary.current?.focus();
  }

  const status = !domain
    ? "Estatísticas desativadas."
    : choice === "accepted"
      ? "Estatísticas autorizadas neste navegador."
      : choice === "rejected"
        ? "Estatísticas recusadas neste navegador."
        : "Estatísticas aguardam sua autorização.";

  return (
    <details className="basis-full border-t border-lumini-gold/40 pt-4" open={Boolean(domain && choice === null)}>
      <summary ref={summary} className="min-h-11 cursor-pointer py-2 text-lumini-rose underline focus-visible:outline-3 focus-visible:outline-offset-4 focus-visible:outline-lumini-rose">
        Preferências de privacidade
      </summary>
      <div className="max-w-2xl space-y-4 pb-2">
        <p className="leading-relaxed">
          A medição de visitas é opcional. Quando configurada e autorizada, envia ao Plausible uma visita à página
          inicial e dados técnicos do navegador. Nome, telefone, formulários, chat e reservas ficam fora da medição.
          Sua escolha fica salva neste navegador e pode ser revogada aqui.
        </p>
        <p role="status">{status}</p>
        <div className="flex flex-wrap gap-3">
          {choice === "accepted" ? (
            <button className={button} type="button" onClick={() => choose("rejected")}>Revogar autorização</button>
          ) : (
            <>
              <button className={button} type="button" onClick={() => choose("accepted")} disabled={!domain}>Aceitar estatísticas</button>
              <button className={button} type="button" onClick={() => choose("rejected")}>Recusar estatísticas</button>
            </>
          )}
        </div>
      </div>
    </details>
  );
}
