"use client";

import { useCallback, useEffect, useId, useRef, useState, type FormEvent } from "react";

// Website chat. The session token and the transcript live only in this component's memory:
// closing or reloading the page ends the conversation.

type Line = { from: "bot" | "you"; text: string };
type Answer = { replies: string[]; options: string[] };

const focus = "focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-lumini-rose";

async function post(url: string, token: string | null, body?: unknown): Promise<Response> {
  return fetch(url, {
    method: "POST",
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials: "omit",
    cache: "no-store",
    redirect: "error",
    referrerPolicy: "no-referrer",
  });
}

function answer(value: unknown): Answer {
  const data = value as Partial<Answer> | null;
  const strings = (list: unknown) => Array.isArray(list) && list.every((item) => typeof item === "string");
  if (!data || !strings(data.replies) || !strings(data.options)) throw new Error("invalid");
  return data as Answer;
}

export function Chat({ apiOrigin, autoStart = true }: { apiOrigin: string | null; autoStart?: boolean }) {
  const id = useId();
  const token = useRef<string | null>(null);
  const started = useRef(false);
  const end = useRef<HTMLDivElement>(null);
  const [lines, setLines] = useState<Line[]>([]);
  const [options, setOptions] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");

  const start = useCallback(async () => {
    if (!apiOrigin) return false;
    const response = await post(`${apiOrigin}/api/public/chat/session`, null);
    if (response.status !== 201) throw new Error(String(response.status));
    const data = (await response.json()) as { token?: unknown } & Answer;
    if (typeof data.token !== "string") throw new Error("invalid");
    token.current = data.token;
    const first = answer(data);
    setLines((current) => [...current, ...first.replies.map((text) => ({ from: "bot" as const, text }))]);
    setOptions(first.options);
    return true;
  }, [apiOrigin]);

  useEffect(() => {
    if (!autoStart || started.current || !apiOrigin) return;
    started.current = true;
    void start().catch(() => setError("O atendimento não está disponível agora. Tente novamente em instantes."));
  }, [apiOrigin, autoStart, start]);

  useEffect(() => {
    end.current?.scrollIntoView({ block: "nearest" });
  }, [lines]);

  async function send(text: string) {
    const clean = text.trim();
    if (!apiOrigin || !clean || busy) return;
    setBusy(true);
    setError(null);
    setDraft("");
    setLines((current) => [...current, { from: "you", text: clean }]);
    try {
      if (!token.current) await start();
      let response = await post(`${apiOrigin}/api/public/chat/messages`, token.current, { text: clean });
      if (response.status === 409) {
        response = await post(`${apiOrigin}/api/public/chat/messages`, token.current, { text: clean });
      }
      if (response.status === 404) {
        token.current = null;
        setLines((current) => [...current, { from: "bot", text: "Esta conversa expirou. Vamos recomeçar:" }]);
        await start();
        return;
      }
      if (response.status === 429) {
        setError("Muitas mensagens em pouco tempo. Aguarde alguns minutos.");
        return;
      }
      if (!response.ok) throw new Error(String(response.status));
      const data = answer(await response.json());
      setLines((current) => [...current, ...data.replies.map((reply) => ({ from: "bot" as const, text: reply }))]);
      setOptions(data.options);
    } catch {
      setError("Não foi possível enviar agora. Confira sua conexão e tente novamente.");
    } finally {
      setBusy(false);
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void send(draft);
  }

  if (!apiOrigin) {
    return <p className="text-lumini-muted">O atendimento online ainda não está disponível nesta versão do site.</p>;
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div role="log" aria-live="polite" aria-label="Conversa" className="min-h-0 flex-1 overflow-y-auto overscroll-contain border border-lumini-gold/40 bg-lumini-white/70 p-4">
        <ul className="flex flex-col gap-3">
          {lines.map((line, index) => (
            <li key={index} className={line.from === "you" ? "self-end" : "self-start"}>
              <span className="sr-only">{line.from === "you" ? "Você:" : "Lumini:"}</span>
              <p
                className={`max-w-[34ch] whitespace-pre-line break-words px-4 py-3 leading-relaxed sm:max-w-[48ch] ${
                  line.from === "you" ? "bg-lumini-rose text-lumini-white" : "border border-lumini-gold/40 bg-lumini-paper"
                }`}
              >
                {line.text}
              </p>
            </li>
          ))}
        </ul>
        {busy && <p className="mt-3 text-sm text-lumini-muted" aria-busy="true">Digitando…</p>}
        <div ref={end} />
      </div>
      {options.length > 0 && (
        <div role="group" aria-label="Respostas rápidas" className="flex flex-wrap gap-2">
          {options.map((option, index) => (
            <button
              key={`${index}-${option}`}
              type="button"
              disabled={busy}
              onClick={() => void send(String(index + 1))}
              className={`min-h-11 border border-lumini-rose px-3 py-2 text-left text-sm text-lumini-rose hover:bg-lumini-white disabled:opacity-50 ${focus}`}
            >
              {index + 1}. {option}
            </button>
          ))}
        </div>
      )}
      {error && <p role="alert" className="text-sm text-lumini-rose">{error}</p>}
      <form onSubmit={submit} className="flex gap-2">
        <label htmlFor={`${id}-text`} className="sr-only">Sua mensagem</label>
        <input
          id={`${id}-text`}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          maxLength={1000}
          autoComplete="off"
          name="message"
          placeholder="Escreva aqui ou toque numa opção…"
          className={`min-h-12 flex-1 border border-lumini-muted/50 bg-lumini-white px-3 text-base ${focus}`}
        />
        <button type="submit" disabled={busy} className={`min-h-12 bg-lumini-rose px-5 text-lumini-white hover:bg-lumini-ink disabled:opacity-50 ${focus}`}>
          Enviar
        </button>
      </form>
      <p className="text-xs leading-relaxed text-lumini-muted">
        Atendimento automático: não faz diagnóstico. Não envie informações de saúde por aqui. Veja a{" "}
        <a className="underline" href="/privacidade">privacidade</a>.
      </p>
    </div>
  );
}
