import type { Metadata } from "next";
import { headers } from "next/headers";
import { notFound } from "next/navigation";

import { site } from "@/content/site";
import { readApiOrigin } from "@/lib/api-origin";
import { getSiteContent } from "@/lib/public/site";
import { getCatalog, priceText } from "@/lib/public/catalog";

import { LeadForm } from "../../_site/lead-form";
import { SiteFooter, SiteHeader, container } from "../../_site/chrome";

type Props = { params: Promise<{ slug: string }> };

async function find(slug: string) {
  const catalog = await getCatalog();
  return { catalog, service: catalog?.find((item) => item.slug === slug) ?? null };
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { service } = await find((await params).slug);
  if (!service) return { title: `Procedimento — ${site.name}` };
  return { title: `${service.name} — ${site.name}`, description: service.description.slice(0, 160) };
}

function List({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <section className="mt-10">
      <h2 className="font-display text-2xl">{title}</h2>
      <ul className="mt-4 grid gap-2">
        {items.map((item) => <li key={item} className="border-l-2 border-lumini-gold pl-4 leading-relaxed">{item}</li>)}
      </ul>
    </section>
  );
}

export default async function ServicePage({ params }: Props) {
  await headers();
  const { catalog, service } = await find((await params).slug);
  if (!service) notFound();
  const apiOrigin = readApiOrigin(process.env.NEXT_PUBLIC_API_BASE_URL, process.env.NODE_ENV);
  return (
    <>
      <SiteHeader />
      <main id="conteudo" tabIndex={-1} className={`${container} py-14 focus:outline-none`}>
        <p className="text-xs uppercase tracking-[0.13em] text-lumini-muted">{service.category}</p>
        <h1 className="mt-3 max-w-[20ch] font-display text-5xl leading-tight text-balance break-words">{service.name}</h1>
        <p className="mt-6 max-w-3xl text-lg leading-relaxed">{service.description}</p>
        <dl className="mt-8 grid max-w-3xl gap-4 sm:grid-cols-3">
          <div><dt className="text-sm text-lumini-muted">Duração</dt><dd>cerca de {service.duration_minutes} minutos</dd></div>
          <div><dt className="text-sm text-lumini-muted">Valor</dt><dd>{priceText(service)}</dd></div>
          <div><dt className="text-sm text-lumini-muted">Agendamento</dt><dd>{service.booking_mode === "evaluation" ? "Começa com uma avaliação" : "Direto, com sinal"}</dd></div>
        </dl>
        <div className="max-w-3xl">
          <List title="Objetivos" items={service.content.objectives} />
          <section className="mt-10">
            <h2 className="font-display text-2xl">Para quem pode ser interessante</h2>
            <p className="mt-4 leading-relaxed">{service.content.audience}</p>
            <p className="mt-2 text-sm text-lumini-muted">A indicação para você é sempre definida pela profissional.</p>
          </section>
          <List title="Como se preparar" items={service.content.preparation} />
          <List title="Cuidados depois" items={service.content.aftercare} />
          <section className="mt-10 border-l-4 border-lumini-rose bg-lumini-white px-5 py-4">
            <h2 className="font-medium">Dúvidas de saúde</h2>
            <p className="mt-2 leading-relaxed">{service.content.human_guidance}</p>
          </section>
          <section className="mt-10">
            <h2 className="font-display text-2xl">Profissionais</h2>
            <ul className="mt-4 grid gap-3">
              {service.professionals.map((person) => (
                <li key={person.id}>{person.display_name} · {person.category} · Registro {person.council_registration}</li>
              ))}
            </ul>
          </section>
        </div>
        <section id="contato" aria-labelledby="contato-titulo" className="mt-16 max-w-3xl scroll-mt-8">
          <h2 id="contato-titulo" className="font-display text-3xl">Quero saber mais sobre {service.name}</h2>
          <div className="mt-6">
            <LeadForm apiOrigin={apiOrigin} services={(catalog ?? []).map(({ id, name }) => ({ id, name }))} preselected={service.id} />
          </div>
        </section>
      </main>
      <SiteFooter content={await getSiteContent()} />
    </>
  );
}
