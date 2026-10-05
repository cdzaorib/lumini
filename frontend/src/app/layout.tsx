import type { Metadata, Viewport } from "next";
import "./globals.css";

import { siteIndexable } from "@/content/site";

export const metadata: Metadata = {
  title: "Lumini Estética e Saúde",
  description: "Estética facial e corporal, emagrecimento saudável e saúde integrativa.",
  // Search engines stay out until the launch gate (LUMINI_SITE_PUBLIC=true).
  robots: siteIndexable() ? undefined : { index: false, follow: false, nocache: true },
};

export const viewport: Viewport = {
  themeColor: "#f5edef",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-BR">
      <body>
        <a className="skip-link" href="#conteudo">
          Pular para o conteúdo
        </a>
        {children}
      </body>
    </html>
  );
}
