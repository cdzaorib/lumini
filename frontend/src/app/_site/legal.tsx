import type { ReactNode } from "react";

import { SiteFooter, SiteHeader, container } from "./chrome";

// Legal pages are drafts until a lawyer reviews them and the clinic approves (launch gate).
export const LEGAL_APPROVED = false;

export function LegalPage({ title, children }: { title: string; children: ReactNode }) {
  return (
    <>
      <SiteHeader />
      <main id="conteudo" tabIndex={-1} className={`${container} py-14 focus:outline-none`}>
        {!LEGAL_APPROVED && (
          <p role="note" className="mb-8 border-l-4 border-lumini-rose bg-lumini-white px-5 py-4 text-sm">
            Rascunho em revisão jurídica e pendente de aprovação da clínica. Pode mudar antes da publicação.
          </p>
        )}
        <h1 className="font-display text-4xl leading-tight sm:text-5xl">{title}</h1>
        <div className="mt-8 flex max-w-3xl flex-col gap-6 leading-relaxed [&_h2]:mt-4 [&_h2]:font-display [&_h2]:text-2xl [&_li]:ml-5 [&_li]:list-disc">
          {children}
        </div>
      </main>
      <SiteFooter />
    </>
  );
}
