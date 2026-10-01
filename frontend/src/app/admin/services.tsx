"use client";

import { useId, useRef, useState, type FormEvent, type ReactNode } from "react";

import { serviceFields } from "@/lib/admin/forms";
import { contentGaps, unverifiedProfessionals } from "@/lib/admin/requirements";
import type {
  AdminIdentity,
  Catalog,
  Mutation,
  Professional,
  Service,
  ServiceDraft,
} from "@/lib/admin/types";

import { cardHeading, formatDate, formatMoney, rescueFocus, ui } from "./ui";

type Props = { catalog: Catalog; identity: AdminIdentity; mutate: Mutation; busy: boolean };

const STATUS = {
  draft: { label: "Rascunho", tone: "border-lumini-muted text-lumini-muted" },
  approved: { label: "Aprovado, não publicado", tone: "border-lumini-gold text-lumini-ink" },
  published: { label: "Publicado", tone: "border-lumini-rose text-lumini-rose" },
} as const;

export function ServicesSection({ catalog, identity, mutate, busy }: Props) {
  return (
    <section aria-labelledby="procedimentos" className="flex flex-col gap-4">
      <h2 id="procedimentos" className="font-display text-2xl">
        Procedimentos
      </h2>
      <p className="max-w-prose text-sm leading-relaxed text-lumini-muted">
        Fluxo: rascunho → aprovação de cada profissional vinculada → publicação. Qualquer alteração
        salva cria nova revisão, despublica e exige novas aprovações. Só procedimentos publicados
        aparecem para o público.
      </p>
      <details className={ui.card}>
        <summary className={ui.summary}>Cadastrar procedimento</summary>
        <ServiceForm
          professionals={catalog.professionals}
          submitLabel="Salvar rascunho"
          busy={busy}
          resetOnSuccess
          onSubmit={(draft) =>
            mutate("/api/admin/services", "POST", draft, "Procedimento salvo como rascunho.")
          }
        />
      </details>
      {catalog.services.length === 0 ? (
        <p className={ui.hint}>Nenhum procedimento cadastrado.</p>
      ) : (
        <ul className="flex flex-col gap-4">
          {catalog.services.map((service) => (
            <ServiceCard
              key={service.id}
              service={service}
              professionals={catalog.professionals}
              identity={identity}
              mutate={mutate}
              busy={busy}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

function priceLabel(service: Service): string {
  const { price_kind } = service.content;
  if (price_kind === "on_evaluation" || service.price_brl === null) return "Valor após avaliação";
  const value = formatMoney(service.price_brl);
  return price_kind === "from" ? `A partir de ${value}` : value;
}

function ServiceCard({
  service,
  professionals,
  identity,
  mutate,
  busy,
}: {
  service: Service;
  professionals: Professional[];
  identity: AdminIdentity;
  mutate: Mutation;
  busy: boolean;
}) {
  const path = `/api/admin/services/${service.id}`;
  const version = { expected_revision: service.revision };
  const heading = useRef<HTMLHeadingElement>(null);
  const act = async (suffix: string, body: object, success: string) => {
    const done = await mutate(`${path}/${suffix}`, "POST", body, success);
    if (done) rescueFocus(heading.current);
    return done;
  };
  const gaps = contentGaps(service);
  const unverified = unverifiedProfessionals(service, professionals);
  const approvedIds = new Set(service.approvals.map((approval) => approval.professional_id));
  const status = STATUS[service.status];

  return (
    <li className={ui.card}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 ref={heading} tabIndex={-1} className={cardHeading}>
            {service.name}
          </h3>
          <p className="text-sm text-lumini-muted">
            {service.category} · revisão {service.revision} · {priceLabel(service)}
            {service.deposit_brl !== null && ` · sinal ${formatMoney(service.deposit_brl)}`}
          </p>
        </div>
        <span className={`${ui.badge} ${status.tone}`}>{status.label}</span>
      </div>

      <h4 className="mt-4 text-sm font-semibold">Aprovações da revisão atual</h4>
      {service.professional_ids.length === 0 ? (
        <p className={ui.hint}>Nenhuma profissional vinculada.</p>
      ) : (
        <ul className="mt-1 flex flex-col gap-1 text-sm">
          {service.professional_ids.map((id) => {
            const person = professionals.find((item) => item.id === id);
            const approval = service.approvals.find((item) => item.professional_id === id);
            return (
              <li key={id}>
                {person?.display_name ?? "Profissional removida"}:{" "}
                {approval ? `aprovado em ${formatDate(approval.approved_at)}` : "pendente"}
                {person && !person.credentials_verified_at && " (credencial não verificada)"}
              </li>
            );
          })}
        </ul>
      )}

      {gaps.length > 0 && (
        <div className="mt-4 text-sm">
          <h4 className="font-semibold">Falta para aprovar</h4>
          <ul className="mt-1 list-disc pl-5 text-lumini-muted">
            {gaps.map((gap) => (
              <li key={gap}>{gap}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-4 flex flex-col gap-3">
        {service.professional_ids
          .filter((id) => identity.reviewer_professional_ids.includes(id) && !approvedIds.has(id))
          .map((id) => {
            const person = professionals.find((item) => item.id === id);
            if (!person) return null;
            return (
              <ApprovalForm
                key={id}
                service={service}
                person={person}
                disabledReason={
                  gaps.length > 0
                    ? "Complete o conteúdo antes de aprovar."
                    : !person.credentials_verified_at
                      ? "A credencial desta profissional precisa estar verificada."
                      : null
                }
                busy={busy}
                onApprove={() =>
                  act(
                    "approve",
                    { ...version, professional_id: id },
                    `Aprovação de ${person.display_name} registrada.`,
                  )
                }
              />
            );
          })}

        <div className="flex flex-wrap gap-3">
          {service.status === "approved" && (
            <button
              type="button"
              className={ui.button}
              disabled={busy || unverified.length > 0}
              onClick={() => void act("publish", version, "Procedimento publicado.")}
            >
              Publicar
            </button>
          )}
          {service.status !== "draft" && (
            <button
              type="button"
              className={ui.secondary}
              disabled={busy}
              onClick={() =>
                void act(
                  "unpublish",
                  version,
                  "Procedimento voltou a rascunho; novas aprovações serão necessárias.",
                )
              }
            >
              {service.status === "published" ? "Despublicar" : "Voltar a rascunho"}
            </button>
          )}
        </div>
        {service.status === "approved" && unverified.length > 0 && (
          <p className={ui.hint}>Publicação exige credencial verificada de: {unverified.join(", ")}.</p>
        )}

        <details>
          <summary className={ui.summary}>Editar conteúdo</summary>
          <p className={ui.hint}>
            Salvar uma alteração cria a revisão {service.revision + 1}, despublica e apaga as
            aprovações atuais.
          </p>
          <ServiceForm
            initial={service}
            professionals={professionals}
            submitLabel="Salvar nova revisão"
            busy={busy}
            onSubmit={(draft) =>
              mutate(path, "PATCH", { ...version, ...draft }, "Nova revisão salva como rascunho.")
            }
          />
        </details>
      </div>
    </li>
  );
}

function ApprovalForm({
  service,
  person,
  disabledReason,
  busy,
  onApprove,
}: {
  service: Service;
  person: Professional;
  disabledReason: string | null;
  busy: boolean;
  onApprove: () => Promise<boolean>;
}) {
  const id = useId();
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void onApprove();
  }
  return (
    <form onSubmit={submit} className="flex flex-col gap-3 border-t border-lumini-gold/30 pt-3">
      <label htmlFor={id} className="flex items-start gap-3 text-sm">
        <input id={id} type="checkbox" required disabled={Boolean(disabledReason)} className="mt-1 size-5" />
        Revisei a revisão {service.revision} deste procedimento e aprovo o conteúdo como{" "}
        {person.display_name}.
      </label>
      {disabledReason && <p className={ui.hint}>{disabledReason}</p>}
      <div>
        <button type="submit" className={ui.button} disabled={busy || Boolean(disabledReason)}>
          Aprovar como {person.display_name}
        </button>
      </div>
    </form>
  );
}

function Field({
  id,
  label,
  hint,
  wide = false,
  children,
}: {
  id: string;
  label: string;
  hint?: string;
  wide?: boolean;
  children: ReactNode;
}) {
  return (
    <div className={wide ? "sm:col-span-2" : undefined}>
      <label htmlFor={id} className={ui.label}>
        {label}
      </label>
      {children}
      {hint && (
        <p id={`${id}-hint`} className={ui.hint}>
          {hint}
        </p>
      )}
    </div>
  );
}

function ServiceForm({
  initial,
  professionals,
  submitLabel,
  busy,
  resetOnSuccess = false,
  onSubmit,
}: {
  initial?: Service;
  professionals: Professional[];
  submitLabel: string;
  busy: boolean;
  resetOnSuccess?: boolean;
  onSubmit: (draft: ServiceDraft) => Promise<boolean>;
}) {
  const id = useId();
  const [error, setError] = useState<string | null>(null);
  const content = initial?.content;
  const lines = (values: string[] | undefined) => values?.join("\n") ?? "";
  const textarea = `${ui.input} min-h-24`;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    setError(null);
    let draft: ServiceDraft;
    try {
      draft = serviceFields(new FormData(form));
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : "Revise os campos.");
      return;
    }
    if ((await onSubmit(draft)) && resetOnSuccess) form.reset();
  }

  return (
    <form onSubmit={submit} className="mt-3 grid gap-4 sm:grid-cols-2">
      <Field id={`${id}-name`} label="Nome">
        <input id={`${id}-name`} name="name" required maxLength={160} defaultValue={initial?.name} className={ui.input} />
      </Field>
      <Field id={`${id}-slug`} label="Identificador do endereço" hint="Minúsculas, números e hífens. Ex.: limpeza-de-pele">
        <input
          id={`${id}-slug`}
          name="slug"
          required
          maxLength={160}
          pattern="[a-z0-9]+(-[a-z0-9]+)*"
          aria-describedby={`${id}-slug-hint`}
          defaultValue={initial?.slug}
          className={ui.input}
        />
      </Field>
      <Field id={`${id}-category`} label="Categoria">
        <input id={`${id}-category`} name="category" required maxLength={120} defaultValue={initial?.category} className={ui.input} />
      </Field>
      <Field id={`${id}-mode`} label="Modo de agendamento">
        <select id={`${id}-mode`} name="booking_mode" defaultValue={initial?.booking_mode ?? ""} className={ui.input}>
          <option value="">Ainda não definido</option>
          <option value="evaluation">Avaliação primeiro</option>
          <option value="direct">Agendamento direto</option>
        </select>
      </Field>
      <Field id={`${id}-description`} label="Descrição aprovada" wide>
        <textarea id={`${id}-description`} name="description" maxLength={6000} defaultValue={initial?.description ?? ""} className={textarea} />
      </Field>
      <Field id={`${id}-objectives`} label="Objetivos" hint="Um por linha." wide>
        <textarea id={`${id}-objectives`} name="objectives" aria-describedby={`${id}-objectives-hint`} defaultValue={lines(content?.objectives)} className={textarea} />
      </Field>
      <Field id={`${id}-audience`} label="Para quem pode ser interessante" hint="Linguagem cautelosa, sem indicar adequação individual." wide>
        <textarea id={`${id}-audience`} name="audience" maxLength={2000} aria-describedby={`${id}-audience-hint`} defaultValue={content?.audience ?? ""} className={textarea} />
      </Field>
      <Field id={`${id}-preparation`} label="Preparação" hint="Uma orientação por linha." >
        <textarea id={`${id}-preparation`} name="preparation" aria-describedby={`${id}-preparation-hint`} defaultValue={lines(content?.preparation)} className={textarea} />
      </Field>
      <Field id={`${id}-aftercare`} label="Recomendações posteriores" hint="Uma orientação por linha.">
        <textarea id={`${id}-aftercare`} name="aftercare" aria-describedby={`${id}-aftercare-hint`} defaultValue={lines(content?.aftercare)} className={textarea} />
      </Field>
      <Field id={`${id}-guidance`} label="Quando falar com a profissional" hint="Texto mostrado para encaminhar dúvidas e condições de saúde." wide>
        <textarea id={`${id}-guidance`} name="human_guidance" maxLength={2000} aria-describedby={`${id}-guidance-hint`} defaultValue={content?.human_guidance ?? ""} className={textarea} />
      </Field>
      <Field id={`${id}-restrictions`} label="Restrições de comunicação (uso interno)" hint="O que bot e divulgação não podem dizer. Uma por linha. Não é publicado." wide>
        <textarea id={`${id}-restrictions`} name="communication_restrictions" aria-describedby={`${id}-restrictions-hint`} defaultValue={lines(content?.communication_restrictions)} className={textarea} />
      </Field>
      <Field id={`${id}-price-kind`} label="Forma de preço">
        <select id={`${id}-price-kind`} name="price_kind" defaultValue={content?.price_kind ?? "on_evaluation"} className={ui.input}>
          <option value="on_evaluation">Valor após avaliação</option>
          <option value="fixed">Preço fixo</option>
          <option value="from">A partir de</option>
        </select>
      </Field>
      <Field id={`${id}-price`} label="Preço (R$)" hint="Deixe vazio em “valor após avaliação”.">
        <input id={`${id}-price`} name="price_brl" inputMode="decimal" aria-describedby={`${id}-price-hint`} defaultValue={initial?.price_brl ?? ""} className={ui.input} />
      </Field>
      <Field id={`${id}-deposit`} label="Sinal (R$)" hint="Zero é permitido; vazio impede a aprovação.">
        <input id={`${id}-deposit`} name="deposit_brl" inputMode="decimal" aria-describedby={`${id}-deposit-hint`} defaultValue={initial?.deposit_brl ?? ""} className={ui.input} />
      </Field>
      <Field id={`${id}-duration`} label="Duração (minutos)">
        <input id={`${id}-duration`} name="duration_minutes" type="number" min={1} max={1440} defaultValue={initial?.duration_minutes ?? ""} className={ui.input} />
      </Field>
      <Field id={`${id}-buffer`} label="Intervalo após o atendimento (minutos)" hint="Mínimo de 15.">
        <input id={`${id}-buffer`} name="buffer_minutes" type="number" min={15} max={1440} required aria-describedby={`${id}-buffer-hint`} defaultValue={initial?.buffer_minutes ?? 15} className={ui.input} />
      </Field>
      <fieldset className="sm:col-span-2">
        <legend className={ui.label}>Profissionais responsáveis</legend>
        {professionals.length === 0 ? (
          <p className={ui.hint}>Cadastre uma profissional primeiro.</p>
        ) : (
          <div className="mt-2 flex flex-wrap gap-x-6 gap-y-2">
            {professionals.map((person) => (
              <label key={person.id} className="flex min-h-11 items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  name="professional_ids"
                  value={person.id}
                  defaultChecked={initial?.professional_ids.includes(person.id)}
                  className="size-5"
                />
                {person.display_name}
              </label>
            ))}
          </div>
        )}
      </fieldset>
      {error && (
        <p role="alert" className="text-sm text-lumini-rose sm:col-span-2">
          {error}
        </p>
      )}
      <div className="sm:col-span-2">
        <button type="submit" className={ui.button} disabled={busy}>
          {submitLabel}
        </button>
      </div>
    </form>
  );
}
