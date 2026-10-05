import type { Metadata } from "next";
import Link from "next/link";
import { headers } from "next/headers";

import { site } from "@/content/site";
import { readApiOrigin } from "@/lib/api-origin";
import { getCatalog, priceText, professionalsOf, type PublicService } from "@/lib/public/catalog";
import { getSiteContent, whatsappLink, type SiteContent } from "@/lib/public/site";

import { ChatWidget } from "./_site/chat-widget";
import { LeadForm } from "./_site/lead-form";
import { Pending, Section, SiteFooter, SiteHeader, container, primaryLink, secondaryLink } from "./_site/chrome";

export const metadata: Metadata = {
  title: `${site.name} — ${site.region}`,
  description:
    "Estética facial e corporal, emagrecimento saudável e saúde integrativa. Tire suas dúvidas e agende sua avaliação.",
};

const STEPS = [
  ["Conte o que você procura", "Pelo formulário ou pelo atendimento, você escolhe um procedimento ou conta seu objetivo."],
  ["Tire suas dúvidas", "Explicamos o procedimento com informações aprovadas pelas profissionais. Questões de saúde vão direto para a profissional."],
  ["Reserve o horário", "O horário escolhido fica reservado por 2 horas enquanto você paga o sinal."],
  ["Confirmação pela clínica", "A equipe confere o sinal e confirma o agendamento. Você recebe tudo pelo WhatsApp."],
] as const;

const POLICIES = [
  "O horário fica reservado por 2 horas para o pagamento do sinal; sem confirmação nesse prazo, ele é liberado.",
  "O sinal é conferido pela equipe da clínica antes de confirmar o agendamento.",
  "Com mais de 24 horas de antecedência, você mesma cancela ou reagenda pelo link enviado no WhatsApp.",
  "Com 24 horas ou menos, alterações são combinadas diretamente com a clínica.",
  "O primeiro reagendamento mantém o sinal; um segundo reagendamento, exceções e reembolsos são decididos pela clínica.",
  "Horários com menos de 3 horas de antecedência são combinados diretamente com a equipe.",
];

// Structured data for local search, only with the address the clinic confirmed in the panel.
function LocalBusiness({ content, nonce }: { content: SiteContent; nonce?: string }) {
  const origin = process.env.LUMINI_PUBLIC_SITE_URL?.replace(/\/$/, "");
  const data = {
    "@context": "https://schema.org",
    "@type": "HealthAndBeautyBusiness",
    name: site.name,
    areaServed: site.region,
    address: { "@type": "PostalAddress", streetAddress: content.address?.street, addressLocality: content.address?.city, addressCountry: "BR" },
    ...(content.whatsapp ? { telephone: content.whatsapp } : {}),
    ...(content.hours.length ? { openingHours: content.hours } : {}),
    ...(origin ? { url: origin } : {}),
  };
  // JSON.stringify escapes quotes; "<" is escaped so text can never close the script element.
  const json = JSON.stringify(data).replace(/</g, "\\u003c");
  return <script type="application/ld+json" nonce={nonce} dangerouslySetInnerHTML={{ __html: json }} />;
}

function ServiceCard({ service }: { service: PublicService }) {
  return (
    <li className="flex flex-col border border-lumini-gold/40 bg-lumini-white/70 p-6">
      <p className="text-xs uppercase tracking-[0.13em] text-lumini-muted">{service.category}</p>
      <h3 className="mt-2 font-display text-2xl">{service.name}</h3>
      <p className="mt-3 line-clamp-3 flex-1 leading-relaxed text-lumini-muted">{service.description}</p>
      <p className="mt-4 text-sm">
        {priceText(service)} · cerca de {service.duration_minutes} min
        {service.booking_mode === "evaluation" ? " · começa com avaliação" : ""}
      </p>
      <Link className="mt-4 text-sm font-medium text-lumini-rose underline" href={`/procedimentos/${service.slug}`}>
        Saiba mais sobre {service.name}
      </Link>
    </li>
  );
}

export default async function HomePage() {
  const nonce = (await headers()).get("x-nonce") ?? undefined; // per request: CSP nonce
  const [catalog, content] = await Promise.all([getCatalog(), getSiteContent()]);
  const apiOrigin = readApiOrigin(process.env.NEXT_PUBLIC_API_BASE_URL, process.env.NODE_ENV);
  const services = catalog ?? [];
  const categories = [...new Set(services.map((service) => service.category))].sort((a, b) => a.localeCompare(b, "pt-BR"));
  const professionals = professionalsOf(services);

  return (
    <>
      <SiteHeader />
      <main id="conteudo" tabIndex={-1} className="focus:outline-none">
        <section className={`${container} grid items-center gap-12 py-16 md:grid-cols-[1.3fr_1fr] md:py-24`}>
          <div>
            <p className="mb-6 text-xs uppercase tracking-[0.13em] text-lumini-muted">{site.region}</p>
            <h1 className="max-w-[14ch] font-display text-5xl leading-[1.05] tracking-tight sm:text-6xl">
              Tire suas dúvidas e agende sua avaliação
            </h1>
            <p className="mt-6 max-w-[42ch] text-lg leading-relaxed text-lumini-muted">
              Estética facial e corporal, emagrecimento saudável e saúde integrativa, com atendimento acolhedor e
              profissionais identificadas.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link className={primaryLink} href="#contato">Quero ser contatada</Link>
              {content.whatsapp && (
                <a className={secondaryLink} href={whatsappLink(content.whatsapp, "Olá! Vim pelo site da Lumini.")} target="_blank" rel="noopener noreferrer">
                  Conversar no WhatsApp
                </a>
              )}
              <Link className={secondaryLink} href="/atendimento">Tirar dúvidas agora</Link>
            </div>
          </div>
          <div className="light-study" aria-hidden="true">
            <div className="light-outline" />
            <div className="light-doorway" />
            <span className="light-caption">lumini</span>
          </div>
        </section>

        <Section id="procedimentos" eyebrow="Procedimentos" title="O que você procura?">
          {catalog === null ? (
            <p className="text-lumini-muted">
              A lista de procedimentos está temporariamente indisponível. Deixe seu contato que a equipe te ajuda.
            </p>
          ) : services.length === 0 ? (
            <Pending what="procedimentos aprovados e publicados no painel" />
          ) : (
            <>
              <ul aria-label="Áreas" className="mb-8 flex flex-wrap gap-2">
                {categories.map((category) => (
                  <li key={category} className="border border-lumini-rose/40 px-3 py-1 text-sm text-lumini-rose">{category}</li>
                ))}
              </ul>
              <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                {services.map((service) => <ServiceCard key={service.id} service={service} />)}
              </ul>
            </>
          )}
        </Section>

        <Section id="como-funciona" eyebrow="Atendimento" title="Como funciona">
          <ol className="grid gap-6 md:grid-cols-4">
            {STEPS.map(([title, text], index) => (
              <li key={title} className="border-t border-lumini-gold/60 pt-4">
                <span className="font-display text-3xl text-lumini-gold">{index + 1}</span>
                <h3 className="mt-2 font-medium">{title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-lumini-muted">{text}</p>
              </li>
            ))}
          </ol>
        </Section>

        <Section id="profissionais" eyebrow="Equipe" title="Profissionais responsáveis">
          {professionals.length === 0 ? (
            <Pending what="profissionais com credenciais verificadas no painel" />
          ) : (
            <ul className="grid gap-5 sm:grid-cols-2">
              {professionals.map((person) => (
                <li key={person.id} className="border border-lumini-gold/40 bg-lumini-white/70 p-6">
                  <h3 className="font-display text-2xl">{person.display_name}</h3>
                  <p className="mt-1 text-lumini-muted">{person.category}</p>
                  <p className="mt-1 text-sm">Registro: {person.council_registration}</p>
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section id="diferenciais" eyebrow="A Lumini" title="Por que a Lumini">
          {content.differentiators.length > 0 ? (
            <ul className="grid gap-4 sm:grid-cols-2">
              {content.differentiators.map((item) => <li key={item} className="border-l-2 border-lumini-gold pl-4">{item}</li>)}
            </ul>
          ) : (
            <Pending what="diferenciais da clínica (aba Site do painel) e fotos autorizadas" />
          )}
          {content.testimonials.length > 0 && (
            <ul className="mt-10 grid gap-5 sm:grid-cols-2" aria-label="Depoimentos autorizados">
              {content.testimonials.map((item) => (
                <li key={item.quote} className="border border-lumini-gold/40 bg-lumini-white/70 p-6">
                  <blockquote className="font-display text-xl leading-snug">“{item.quote}”</blockquote>
                  <p className="mt-3 text-sm text-lumini-muted">— {item.author}</p>
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section id="politicas" eyebrow="Regras claras" title="Políticas de agendamento">
          <ul className="grid max-w-3xl gap-3">
            {POLICIES.map((item) => <li key={item} className="border-l-2 border-lumini-gold pl-4 leading-relaxed">{item}</li>)}
          </ul>
        </Section>

        {content.faq.length > 0 ? (
          <Section id="duvidas" eyebrow="Dúvidas" title="Perguntas frequentes">
            <div className="max-w-3xl">
              {content.faq.map((item) => (
                <details key={item.question} className="border-b border-lumini-gold/40 py-4">
                  <summary className="cursor-pointer font-medium">{item.question}</summary>
                  <p className="mt-3 leading-relaxed text-lumini-muted">{item.answer}</p>
                </details>
              ))}
            </div>
          </Section>
        ) : (
          <Section id="duvidas" eyebrow="Dúvidas" title="Perguntas frequentes">
            <Pending what="perguntas frequentes (aba Site do painel)" />
          </Section>
        )}

        <Section id="localizacao" eyebrow="Onde estamos" title="Localização e horários">
          {content.address ? (
            <div className="grid gap-6 sm:grid-cols-2">
              <div>
                <p className="leading-relaxed">{content.address.street}<br />{content.address.city}</p>
                {content.address.maps_url && (
                  <a className="mt-3 inline-block text-lumini-rose underline" href={content.address.maps_url} target="_blank" rel="noopener noreferrer">
                    Ver no mapa
                  </a>
                )}
              </div>
              {content.hours.length > 0 ? <ul>{content.hours.map((line) => <li key={line}>{line}</li>)}</ul> : <Pending what="horários de funcionamento" />}
            </div>
          ) : (
            <Pending what="endereço e horários de funcionamento (aba Site do painel)" />
          )}
        </Section>

        <Section id="contato" eyebrow="Fale com a clínica" title="Quer conversar com a gente?">
          <p className="mb-8 max-w-2xl leading-relaxed text-lumini-muted">
            Deixe seu nome e WhatsApp: a equipe da Lumini entra em contato para tirar dúvidas e combinar sua avaliação.
          </p>
          <LeadForm apiOrigin={apiOrigin} services={services.map(({ id, name }) => ({ id, name }))} />
        </Section>
        {content.address && <LocalBusiness content={content} nonce={nonce} />}
      </main>
      <SiteFooter content={content} />
      <ChatWidget apiOrigin={apiOrigin} />
    </>
  );
}
