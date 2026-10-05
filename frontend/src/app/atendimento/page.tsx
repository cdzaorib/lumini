import type { Metadata } from "next";
import { headers } from "next/headers";

import { site } from "@/content/site";
import { readApiOrigin } from "@/lib/api-origin";
import { getSiteContent } from "@/lib/public/site";
import { getCatalog } from "@/lib/public/catalog";

import { Chat } from "../_site/chat";
import { LeadForm } from "../_site/lead-form";
import { SiteFooter, SiteHeader, container } from "../_site/chrome";

export const metadata: Metadata = {
  title: `Atendimento — ${site.name}`,
  description: "Tire dúvidas sobre os procedimentos e reserve um horário com a Lumini.",
};

export default async function AttendancePage() {
  await headers();
  const apiOrigin = readApiOrigin(process.env.NEXT_PUBLIC_API_BASE_URL, process.env.NODE_ENV);
  const services = ((await getCatalog()) ?? []).map(({ id, name }) => ({ id, name }));
  return (
    <>
      <SiteHeader />
      <main id="conteudo" tabIndex={-1} className={`${container} py-12 focus:outline-none`}>
        <h1 className="font-display text-4xl sm:text-5xl">Atendimento</h1>
        <p className="mt-4 max-w-2xl leading-relaxed text-lumini-muted">
          Conheça os procedimentos e reserve um horário. Para assuntos de saúde ou para falar com a equipe, use “Fale
          com a clínica” e a equipe chama você no WhatsApp.
        </p>
        <div className="mt-8 h-[min(680px,80svh)] max-w-2xl">
          <Chat apiOrigin={apiOrigin} />
        </div>
        <section id="contato" aria-labelledby="contato-titulo" className="mt-16 max-w-3xl scroll-mt-8">
          <h2 id="contato-titulo" className="font-display text-3xl">Fale com a clínica</h2>
          <p className="mt-3 leading-relaxed text-lumini-muted">
            Deixe seu nome e WhatsApp e a equipe chama você. Não precisa contar detalhes de saúde por aqui.
          </p>
          <div className="mt-6">
            <LeadForm apiOrigin={apiOrigin} services={services} />
          </div>
        </section>
      </main>
      <SiteFooter content={await getSiteContent()} />
    </>
  );
}
