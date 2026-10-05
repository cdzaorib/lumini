"use client";

import { useId, useState, type FormEvent } from "react";

type Option = { id: string; name: string };
type State = { kind: "idle" | "sending" | "sent" } | { kind: "error"; text: string };

const focus = "focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-lumini-rose";
const input = `mt-1 block w-full border border-lumini-muted/50 bg-lumini-white px-3 py-3 text-base ${focus}`;

export function LeadForm({ apiOrigin, services, preselected }: { apiOrigin: string | null; services: Option[]; preselected?: string }) {
  const id = useId();
  const [state, setState] = useState<State>({ kind: "idle" });

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!apiOrigin) return;
    const data = new FormData(event.currentTarget);
    setState({ kind: "sending" });
    try {
      const response = await fetch(`${apiOrigin}/api/public/leads`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: String(data.get("name") ?? ""),
          phone: String(data.get("phone") ?? ""),
          city: String(data.get("city") ?? "").trim() || null,
          service_id: String(data.get("service_id") ?? "") || null,
          preferred_period: String(data.get("preferred_period") ?? "any"),
          contact_consent: data.get("contact_consent") === "on",
          marketing_consent: data.get("marketing_consent") === "on",
          website: String(data.get("website") ?? ""),
        }),
        credentials: "omit",
        cache: "no-store",
        redirect: "error",
        referrerPolicy: "no-referrer",
      });
      if (response.status === 201) {
        setState({ kind: "sent" });
        return;
      }
      setState({
        kind: "error",
        text:
          response.status === 422
            ? "Confira o nome (só letras) e o telefone com DDD, e marque a autorização de contato."
            : response.status === 429
              ? "Recebemos muitos envios agora. Tente de novo em alguns minutos."
              : "Não foi possível enviar agora. Tente novamente em instantes.",
      });
    } catch {
      setState({ kind: "error", text: "Não foi possível enviar agora. Confira sua conexão e tente novamente." });
    }
  }

  if (!apiOrigin) {
    return <p className="text-lumini-muted">O formulário de contato ainda não está disponível nesta versão do site.</p>;
  }
  if (state.kind === "sent") {
    return (
      <p role="status" className="border-l-4 border-lumini-gold bg-lumini-white px-5 py-4">
        Recebemos seu pedido. A equipe da Lumini vai falar com você pelo WhatsApp no telefone informado. Obrigada!
      </p>
    );
  }
  return (
    <form onSubmit={submit} className="grid gap-5 sm:grid-cols-2" noValidate={false}>
      <div>
        <label htmlFor={`${id}-name`} className="block text-sm font-medium">Seu nome</label>
        <input id={`${id}-name`} name="name" required minLength={2} maxLength={120} autoComplete="name" className={input} />
      </div>
      <div>
        <label htmlFor={`${id}-phone`} className="block text-sm font-medium">WhatsApp com DDD</label>
        <input id={`${id}-phone`} name="phone" required inputMode="tel" autoComplete="tel" placeholder="(21) 9XXXX-XXXX" maxLength={30} className={input} />
      </div>
      <div>
        <label htmlFor={`${id}-service`} className="block text-sm font-medium">Interesse (opcional)</label>
        <select id={`${id}-service`} name="service_id" defaultValue={preselected ?? ""} className={input}>
          <option value="">Ainda não sei / quero orientação</option>
          {services.map((service) => (
            <option key={service.id} value={service.id}>{service.name}</option>
          ))}
        </select>
      </div>
      <div>
        <label htmlFor={`${id}-period`} className="block text-sm font-medium">Melhor período para conversar</label>
        <select id={`${id}-period`} name="preferred_period" defaultValue="any" className={input}>
          <option value="any">Qualquer horário</option>
          <option value="morning">Manhã</option>
          <option value="afternoon">Tarde</option>
        </select>
      </div>
      <div>
        <label htmlFor={`${id}-city`} className="block text-sm font-medium">Cidade ou bairro (opcional)</label>
        <input id={`${id}-city`} name="city" maxLength={80} autoComplete="address-level2" className={input} />
      </div>
      {/* Trap for automated submissions: hidden from people and assistive technology. */}
      <div aria-hidden="true" className="absolute left-[-10000px] h-px w-px overflow-hidden">
        <label htmlFor={`${id}-website`}>Não preencha</label>
        <input id={`${id}-website`} name="website" tabIndex={-1} autoComplete="off" />
      </div>
      <div className="flex flex-col gap-3 sm:col-span-2">
        <label className="flex items-start gap-3 text-sm leading-relaxed">
          <input type="checkbox" name="contact_consent" required className="mt-1 size-5 shrink-0" />
          <span>
            Autorizo a Lumini a me contatar pelo WhatsApp sobre este pedido. Meus dados são usados só para isso e
            apagados em até 3 meses se eu não agendar (veja a <a className="underline" href="/privacidade">privacidade</a>).
          </span>
        </label>
        <label className="flex items-start gap-3 text-sm leading-relaxed">
          <input type="checkbox" name="marketing_consent" className="mt-1 size-5 shrink-0" />
          <span>Quero receber novidades e promoções (opcional; dá para cancelar a qualquer momento respondendo STOP).</span>
        </label>
        <p className="text-sm text-lumini-muted">
          Não envie informações de saúde por aqui: essas conversas são feitas diretamente com a profissional.
        </p>
      </div>
      {state.kind === "error" && (
        <p role="alert" className="text-sm text-lumini-rose sm:col-span-2">{state.text}</p>
      )}
      <div className="sm:col-span-2">
        <button
          type="submit"
          disabled={state.kind === "sending"}
          className={`inline-flex min-h-12 items-center justify-center bg-lumini-rose px-6 py-3 text-base font-medium text-lumini-white transition-colors hover:bg-lumini-ink disabled:opacity-60 ${focus}`}
        >
          {state.kind === "sending" ? "Enviando…" : "Quero ser contatada"}
        </button>
      </div>
    </form>
  );
}
