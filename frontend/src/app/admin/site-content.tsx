"use client";

import { useEffect, useId, useState, type FormEvent } from "react";

import { decodeSiteSettings } from "@/lib/admin/api";
import type { Mutation, Query, SiteSettings } from "@/lib/admin/types";

import { ui } from "./ui";
import { SiteBotTexts } from "./site-bot-texts";
import { SitePhotos, type PhotoDraft } from "./site-photos";

type Content = SiteSettings["content"];
type Faq = Content["faq"][number] & { key: number };
type Quote = Content["testimonials"][number] & { key: number };

const lines = (text: string) => text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
const optional = (text: string) => text.trim() || null;

export function SiteContentSection({ mutate, query, busy }: { mutate: Mutation; query: Query; busy: boolean }) {
  const id = useId();
  const [settings, setSettings] = useState<SiteSettings | null>(null);
  const [loads, setLoads] = useState(0);
  const [faq, setFaq] = useState<Faq[]>([]);
  const [quotes, setQuotes] = useState<Quote[]>([]);
  const [photos, setPhotos] = useState<PhotoDraft[]>([]);
  const [dirty, setDirty] = useState(false);
  const [nextKey, setNextKey] = useState(0);

  useEffect(() => {
    let ignore = false;
    void query("/api/admin/site", decodeSiteSettings).then((found) => {
      if (ignore || !found) return;
      setSettings(found);
      setFaq(found.content.faq.map((item, index) => ({ ...item, key: index })));
      setQuotes(found.content.testimonials.map((item, index) => ({ ...item, key: index })));
      setPhotos(found.content.photos.map((item, index) => ({ ...item, key: index })));
      setNextKey(found.content.faq.length + found.content.testimonials.length + found.content.photos.length);
      setDirty(false);
    });
    return () => {
      ignore = true;
    };
  }, [query, loads]);

  if (!settings) return <p aria-busy="true">Carregando conteúdo do site…</p>;
  const content = settings.content;

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!settings) return;
    const data = new FormData(event.currentTarget);
    const text = (name: string) => String(data.get(name) ?? "");
    const street = text("street").trim();
    const body = {
      expected_revision: settings.revision,
      content: {
        address: street ? { street, city: text("city").trim(), maps_url: optional(text("maps_url")) } : null,
        hours: lines(text("hours")),
        whatsapp: optional(text("whatsapp")),
        instagram: optional(text("instagram").replace(/^@/, "")),
        differentiators: lines(text("differentiators")),
        faq: faq.filter((item) => item.question.trim() && item.answer.trim()).map(({ question, answer }) => ({ question, answer })),
        testimonials: quotes.map(({ quote, author, authorized_on }) => ({ quote, author, authorized_on, authorization_confirmed: true })),
        legal_contact: optional(text("legal_contact")),
        deposit_instructions: optional(text("deposit_instructions")),
        photos: photos.map(({ url, alt, width, height, authorized_on }) => ({ url, alt, width, height, authorized_on, authorization_confirmed: true })),
        bot_texts: Object.fromEntries(settings.bot_text_options.map(({ key }) => [key, text(`bot-${key}`).trim()]).filter(([, value]) => value)),
      },
    };
    if (await mutate("/api/admin/site", "PUT", body, "Conteúdo do site salvo como rascunho. Aguarda revisão antes de aparecer no site e no atendimento.")) {
      setLoads((count) => count + 1);
    }
  }

  async function review(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!settings || dirty) return;
    const data = new FormData(event.currentTarget);
    if (data.get("review_confirmed") !== "on") return;
    const action = ((event.nativeEvent as SubmitEvent).submitter as HTMLButtonElement | null)?.value ?? "approve";
    if (!['approve', 'publish'].includes(action)) return;
    if (await mutate(`/api/admin/site/${action}`, "POST", {
      expected_revision: settings.revision,
      professional_id: String(data.get("professional_id")),
      review_confirmed: true,
    }, action === "approve" ? "Sua aprovação foi registrada. A publicação exige a revisão de todas as profissionais." : "Conteúdo revisado publicado no site e no atendimento.")) setLoads((count) => count + 1);
  }

  const field = (name: string, label: string, value: string | null | undefined, extra: Record<string, unknown> = {}) => (
    <div>
      <label htmlFor={`${id}-${name}`} className={ui.label}>{label}</label>
      <input id={`${id}-${name}`} name={name} defaultValue={value ?? ""} className={ui.input} {...extra} />
    </div>
  );

  return (
    <section aria-labelledby="site" className="flex flex-col gap-6">
      <h2 id="site" className="font-display text-2xl">Conteúdo do site</h2>
      <p className="max-w-prose text-sm leading-relaxed text-lumini-muted">
        As mudanças ficam em rascunho. Todas as profissionais verificadas precisam revisar antes da publicação no site e no atendimento. Seções vazias ficam escondidas.
        Publicidade em saúde não pode prometer resultados nem mostrar antes e depois; textos assim são recusados.
      </p>
      <div className={ui.card}>
        <p className="font-semibold">Revisão {settings.revision}: {settings.status === "published" ? "publicada" : settings.status === "approved" ? "aprovada, aguardando publicação" : "rascunho, aguardando aprovação"}</p>
        {settings.required_reviewers.map((person) => <p key={person.professional_id} className={ui.hint}>{person.display_name}: {person.approved ? "revisão aprovada" : "aprovação pendente"}</p>)}
        {!settings.required_reviewers.length && <p className={ui.hint}>Cadastre e verifique as credenciais das profissionais antes de aprovar o conteúdo.</p>}
      </div>
      <form key={settings.revision} onSubmit={save} onChange={() => setDirty(true)} className="flex flex-col gap-8">
        <fieldset className={`${ui.card} grid gap-4 sm:grid-cols-2`}>
          <legend className="px-1 font-semibold">Localização e contato</legend>
          {field("street", "Endereço (rua e número)", content.address?.street, { maxLength: 200 })}
          {field("city", "Bairro e cidade", content.address?.city, { maxLength: 200 })}
          {field("maps_url", "Link do Google Maps (https)", content.address?.maps_url, { maxLength: 500, inputMode: "url" })}
          {field("whatsapp", "WhatsApp da clínica com DDD", content.whatsapp, { maxLength: 30, inputMode: "tel" })}
          {field("instagram", "Instagram (sem @)", content.instagram, { maxLength: 31 })}
          {field("legal_contact", "Contato para pedidos de privacidade (LGPD)", content.legal_contact, { maxLength: 200 })}
          <div className="sm:col-span-2">
            <label htmlFor={`${id}-hours`} className={ui.label}>Horários de funcionamento (um por linha)</label>
            <textarea id={`${id}-hours`} name="hours" rows={3} defaultValue={content.hours.join("\n")} className={ui.input} />
          </div>
        </fieldset>

        <fieldset className={`${ui.card} flex flex-col gap-3`}>
          <legend className="px-1 font-semibold">Diferenciais (um por linha, até 8)</legend>
          <textarea name="differentiators" rows={4} aria-label="Diferenciais" defaultValue={content.differentiators.join("\n")} className={ui.input} />
        </fieldset>

        <fieldset className={`${ui.card} flex flex-col gap-4`}>
          <legend className="px-1 font-semibold">Perguntas frequentes</legend>
          {faq.map((item, index) => (
            <div key={item.key} className="grid gap-2 border-b border-lumini-gold/30 pb-4">
              <label className={ui.label} htmlFor={`${id}-q-${item.key}`}>Pergunta {index + 1}</label>
              <input id={`${id}-q-${item.key}`} value={item.question} maxLength={200} className={ui.input}
                onChange={(event) => setFaq((list) => list.map((entry) => (entry.key === item.key ? { ...entry, question: event.target.value } : entry)))} />
              <label className={ui.label} htmlFor={`${id}-a-${item.key}`}>Resposta {index + 1}</label>
              <textarea id={`${id}-a-${item.key}`} value={item.answer} maxLength={1000} rows={3} className={ui.input}
                onChange={(event) => setFaq((list) => list.map((entry) => (entry.key === item.key ? { ...entry, answer: event.target.value } : entry)))} />
              <div>
                <button type="button" className={ui.secondary} onClick={() => { setFaq((list) => list.filter((entry) => entry.key !== item.key)); setDirty(true); }}>
                  Remover pergunta {index + 1}
                </button>
              </div>
            </div>
          ))}
          <div>
            <button type="button" className={ui.secondary} disabled={faq.length >= 20}
              onClick={() => { setFaq((list) => [...list, { question: "", answer: "", key: nextKey }]); setNextKey((key) => key + 1); setDirty(true); }}>
              Adicionar pergunta
            </button>
          </div>
        </fieldset>

        <fieldset className={`${ui.card} flex flex-col gap-4`}>
          <legend className="px-1 font-semibold">Depoimentos (somente com autorização por escrito)</legend>
          {quotes.map((item, index) => (
            <div key={item.key} className="grid gap-2 border-b border-lumini-gold/30 pb-4 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <label className={ui.label} htmlFor={`${id}-t-${item.key}`}>Depoimento {index + 1}</label>
                <textarea id={`${id}-t-${item.key}`} value={item.quote} maxLength={400} rows={2} className={ui.input}
                  onChange={(event) => setQuotes((list) => list.map((entry) => (entry.key === item.key ? { ...entry, quote: event.target.value } : entry)))} />
              </div>
              <div>
                <label className={ui.label} htmlFor={`${id}-ta-${item.key}`}>Como assinar (ex.: “Ana, Mangaratiba”)</label>
                <input id={`${id}-ta-${item.key}`} value={item.author} maxLength={80} className={ui.input}
                  onChange={(event) => setQuotes((list) => list.map((entry) => (entry.key === item.key ? { ...entry, author: event.target.value } : entry)))} />
              </div>
              <div>
                <label className={ui.label} htmlFor={`${id}-td-${item.key}`}>Data da autorização</label>
                <input id={`${id}-td-${item.key}`} type="date" value={item.authorized_on} className={ui.input}
                  onChange={(event) => setQuotes((list) => list.map((entry) => (entry.key === item.key ? { ...entry, authorized_on: event.target.value } : entry)))} />
              </div>
              <div>
                <button type="button" className={ui.secondary} onClick={() => { setQuotes((list) => list.filter((entry) => entry.key !== item.key)); setDirty(true); }}>
                  Remover depoimento {index + 1}
                </button>
              </div>
            </div>
          ))}
          <AddQuote onAdd={(quote) => { setQuotes((list) => [...list, { ...quote, key: nextKey }]); setNextKey((key) => key + 1); setDirty(true); }} disabled={quotes.length >= 10} />
        </fieldset>

        <SitePhotos photos={photos} onChange={(items) => { setPhotos(items); setDirty(true); }} origins={settings.media_origins} nextKey={nextKey} onAdded={() => setNextKey((key) => key + 1)} />

        <SiteBotTexts settings={settings} id={id} />

        <fieldset className={`${ui.card} flex flex-col gap-3`}>
          <legend className="px-1 font-semibold">Instruções do sinal</legend>
          <label htmlFor={`${id}-deposit`} className={ui.label}>Como pagar o sinal (ex.: chave Pix e titular)</label>
          <textarea id={`${id}-deposit`} name="deposit_instructions" rows={3} maxLength={1000} defaultValue={content.deposit_instructions ?? ""} className={ui.input} />
          <p className={ui.hint}>
            Enviadas pelo WhatsApp depois da reserva somente após a revisão e publicação. Nunca aparecem no site. Sem instruções aprovadas, a equipe manda os dados.
          </p>
        </fieldset>

        <div>
          <button type="submit" className={ui.button} disabled={busy}>Salvar conteúdo do site</button>
        </div>
      </form>
      <form key={`review-${settings.revision}-${settings.status}`} onSubmit={review} className={`${ui.card} flex flex-col gap-4`}>
        <h3 className="font-semibold">Revisão e publicação</h3>
        {dirty && <p className={ui.hint}>Salve o rascunho antes de aprovar ou publicar.</p>}
        <label htmlFor={`${id}-reviewer`} className={ui.label}>Profissional cuja área você pode revisar</label>
        <select id={`${id}-reviewer`} name="professional_id" className={ui.input} required disabled={!settings.eligible_reviewers.length}>
          {settings.eligible_reviewers.map((person) => <option key={person.professional_id} value={person.professional_id}>{person.display_name}</option>)}
        </select>
        {!settings.eligible_reviewers.length && <p className={ui.hint}>Sua conta não está atribuída à revisão de uma profissional com credenciais verificadas.</p>}
        <label htmlFor={`${id}-review-confirmed`} className="flex items-start gap-3 text-sm">
          <input id={`${id}-review-confirmed`} name="review_confirmed" type="checkbox" required className="mt-1 size-5" />
          Revisei os textos da minha área, contatos, instruções, mensagens e autorizações de uso de imagem e depoimentos nesta revisão.
        </label>
        <div className="flex flex-wrap gap-3">
          <button type="submit" name="action" value="approve" className={ui.secondary} disabled={busy || dirty || settings.revision === 0 || !settings.eligible_reviewers.length}>Aprovar minha revisão</button>
          <button type="submit" name="action" value="publish" className={ui.button} disabled={busy || dirty || settings.status !== "approved" || !settings.eligible_reviewers.length}>Publicar conteúdo revisado</button>
          {settings.status === "published" && <button type="button" className={ui.secondary} disabled={busy} onClick={async () => {
            if (await mutate("/api/admin/site/unpublish", "POST", { expected_revision: settings.revision }, "Conteúdo retirado de publicação. Novas aprovações serão necessárias.")) setLoads((count) => count + 1);
          }}>Retirar de publicação</button>}
        </div>
      </form>
    </section>
  );
}

function AddQuote({ onAdd, disabled }: { onAdd: (quote: Omit<Quote, "key">) => void; disabled: boolean }) {
  const id = useId();
  const [confirmed, setConfirmed] = useState(false);
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={`${id}-ok`} className="flex items-start gap-3 text-sm">
        <input id={`${id}-ok`} type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} className="mt-1 size-5" />
        Tenho a autorização por escrito da cliente para publicar o depoimento e o nome como será assinado.
      </label>
      <div>
        <button type="button" className={ui.secondary} disabled={disabled || !confirmed}
          onClick={() => { onAdd({ quote: "", author: "", authorized_on: new Date().toISOString().slice(0, 10), authorization_confirmed: true }); setConfirmed(false); }}>
          Adicionar depoimento autorizado
        </button>
      </div>
    </div>
  );
}
