import Link from "next/link";
import type { ReactNode } from "react";

import { site, sitePreview } from "@/content/site";
import { whatsappLink, type SiteContent } from "@/lib/public/site";

export const container = "mx-auto w-[min(100%-2rem,1120px)]";
const focus = "focus-visible:outline-3 focus-visible:outline-offset-4 focus-visible:outline-lumini-rose";
export const primaryLink = `inline-flex min-h-12 items-center justify-center bg-lumini-rose px-6 py-3 text-base font-medium text-lumini-white transition-colors hover:bg-lumini-ink ${focus}`;
export const secondaryLink = `inline-flex min-h-12 items-center justify-center border border-lumini-rose px-6 py-3 text-base font-medium text-lumini-rose transition-colors hover:bg-lumini-white ${focus}`;

export function SiteHeader() {
  return (
    <header className="border-b border-lumini-gold/40">
      <div className={`${container} flex flex-wrap items-center justify-between gap-4 py-5`}>
        <Link href="/" className={`flex flex-col items-start ${focus}`}>
          <span className="font-display text-4xl leading-none tracking-wide">lumini</span>
          <span className="mt-1 text-[0.62rem] uppercase tracking-[0.19em]">Estética e Saúde</span>
        </Link>
        <nav aria-label="Seções" className="flex flex-wrap gap-x-5 gap-y-2 text-sm">
          <Link className={`hover:text-lumini-rose ${focus}`} href="/#procedimentos">Procedimentos</Link>
          <Link className={`hover:text-lumini-rose ${focus}`} href="/#como-funciona">Como funciona</Link>
          <Link className={`hover:text-lumini-rose ${focus}`} href="/#politicas">Políticas</Link>
          <Link className={`hover:text-lumini-rose ${focus}`} href="/atendimento">Atendimento</Link>
          <Link className={`font-medium text-lumini-rose ${focus}`} href="/#contato">Fale com a clínica</Link>
        </nav>
      </div>
    </header>
  );
}

export function SiteFooter({ content }: { content: SiteContent }) {
  return (
    <footer className="mt-20 border-t border-lumini-gold/40 text-sm text-lumini-muted">
      <div className={`${container} flex flex-col gap-4 py-8 sm:flex-row sm:justify-between`}>
        <div className="flex flex-col gap-1">
          <span className="text-lumini-ink">{site.name}</span>
          <span>{site.region}</span>
          {content.address && <span>{content.address.street} · {content.address.city}</span>}
          {content.whatsapp && (
            <a className={`underline ${focus}`} href={whatsappLink(content.whatsapp)} target="_blank" rel="noopener noreferrer">
              WhatsApp da clínica
            </a>
          )}
          {content.instagram && (
            <a className={`underline ${focus}`} href={`https://www.instagram.com/${content.instagram}/`} target="_blank" rel="noopener noreferrer">
              Instagram @{content.instagram}
            </a>
          )}
        </div>
        <nav aria-label="Informações legais" className="flex flex-wrap gap-x-5 gap-y-2">
          <Link className={`underline ${focus}`} href="/privacidade">Privacidade</Link>
          <Link className={`underline ${focus}`} href="/termos">Termos e políticas</Link>
        </nav>
      </div>
      <p className={`${container} pb-8 text-xs leading-relaxed`}>
        As informações deste site não substituem a avaliação de uma profissional habilitada. Conteúdo clínico revisado e
        aprovado pelas profissionais responsáveis.
      </p>
    </footer>
  );
}

/** Missing clinic material: visible in the preview, absent in production. */
export function Pending({ what }: { what: string }) {
  if (!sitePreview()) return null;
  return (
    <p className="border border-dashed border-lumini-gold px-4 py-3 text-sm text-lumini-muted">
      Pendente da clínica: {what}. (Aviso visível só na prévia.)
    </p>
  );
}

export function Section({ id, title, eyebrow, children }: { id: string; title: string; eyebrow?: string; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-titulo`} className={`${container} scroll-mt-8 pt-20`}>
      {eyebrow && <p className="mb-3 text-xs uppercase tracking-[0.13em] text-lumini-muted">{eyebrow}</p>}
      <h2 id={`${id}-titulo`} className="font-display text-3xl leading-tight sm:text-4xl">
        {title}
      </h2>
      <div className="mt-8">{children}</div>
    </section>
  );
}
