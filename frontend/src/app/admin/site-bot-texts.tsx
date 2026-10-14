import type { SiteSettings } from "@/lib/admin/types";

import { ui } from "./ui";

export function SiteBotTexts({ settings, id }: { settings: SiteSettings; id: string }) {
  return (
    <fieldset className={`${ui.card} flex flex-col gap-4`}>
      <legend className="px-1 font-semibold">Mensagens operacionais do atendimento</legend>
      <p className={ui.hint}>Deixe vazio para usar o texto padrão. As mudanças ficam em rascunho até a revisão e publicação. Regras de reserva, sinal, saúde e privacidade são mantidas pelo sistema.</p>
      {settings.bot_text_options.map((option) => (
        <details key={option.key} className="border-b border-lumini-gold/30 pb-3">
          <summary className="cursor-pointer py-2 font-medium">{option.label}</summary>
          <label htmlFor={`${id}-bot-${option.key}`} className={ui.label}>Texto personalizado: {option.label}</label>
          <textarea id={`${id}-bot-${option.key}`} name={`bot-${option.key}`} rows={4} maxLength={1000} className={ui.input} defaultValue={settings.content.bot_texts[option.key] ?? ""} placeholder={option.default} />
          <p className={ui.hint}>{option.placeholders.length ? `Mantenha estes campos exatamente: ${option.placeholders.map((field) => `{${field}}`).join(", ")}.` : "Este texto não aceita campos entre chaves."}</p>
          <p className={`${ui.hint} whitespace-pre-line`}>Texto padrão: {option.default}</p>
        </details>
      ))}
    </fieldset>
  );
}
