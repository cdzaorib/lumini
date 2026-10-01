"use client";

import { useId, useRef, useState, type FormEvent } from "react";

import { professionalFields } from "@/lib/admin/forms";
import type { Mutation, Professional } from "@/lib/admin/types";

import { cardHeading, formatDate, rescueFocus, ui } from "./ui";

type Props = { professionals: Professional[]; mutate: Mutation; busy: boolean };

export function ProfessionalsSection({ professionals, mutate, busy }: Props) {
  return (
    <section aria-labelledby="profissionais" className="flex flex-col gap-4">
      <h2 id="profissionais" className="font-display text-2xl">
        Profissionais
      </h2>
      <p className="max-w-prose text-sm leading-relaxed text-lumini-muted">
        A verificação registra que alguém da clínica conferiu o documento do conselho. Alterar nome,
        categoria ou registro desfaz a verificação e volta a rascunho todos os procedimentos
        vinculados.
      </p>
      <details className={ui.card}>
        <summary className={ui.summary}>Cadastrar profissional</summary>
        <ProfessionalForm
          submitLabel="Cadastrar"
          busy={busy}
          resetOnSuccess
          onSubmit={(fields) =>
            mutate("/api/admin/professionals", "POST", fields, "Profissional cadastrada.")
          }
        />
      </details>
      {professionals.length === 0 ? (
        <p className={ui.hint}>Nenhuma profissional cadastrada.</p>
      ) : (
        <ul className="flex flex-col gap-4">
          {professionals.map((person) => (
            <ProfessionalCard key={person.id} person={person} mutate={mutate} busy={busy} />
          ))}
        </ul>
      )}
    </section>
  );
}

function ProfessionalCard({
  person,
  mutate,
  busy,
}: {
  person: Professional;
  mutate: Mutation;
  busy: boolean;
}) {
  const confirmId = useId();
  const heading = useRef<HTMLHeadingElement>(null);
  const path = `/api/admin/professionals/${person.id}`;
  const version = { expected_revision: person.revision };
  const complete = Boolean(person.category && person.council_registration);

  async function act(action: "verify" | "revoke", success: string) {
    if (await mutate(`${path}/${action}`, "POST", version, success)) rescueFocus(heading.current);
  }

  function verify(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void act("verify", "Verificação registrada.");
  }

  return (
    <li className={ui.card}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 ref={heading} tabIndex={-1} className={cardHeading}>
            {person.display_name}
          </h3>
          <p className="text-sm text-lumini-muted">
            {person.category ?? "Categoria não informada"} ·{" "}
            {person.council_registration ?? "Registro não informado"}
          </p>
        </div>
        <span
          className={`${ui.badge} ${
            person.credentials_verified_at
              ? "border-lumini-rose text-lumini-rose"
              : "border-lumini-muted text-lumini-muted"
          }`}
        >
          {person.credentials_verified_at
            ? `Verificada em ${formatDate(person.credentials_verified_at)}`
            : "Credencial não verificada"}
        </span>
      </div>

      <div className="mt-4 flex flex-col gap-3">
        {person.credentials_verified_at ? (
          <details>
            <summary className={ui.summary}>Revogar verificação</summary>
            <p className={ui.hint}>
              Todos os procedimentos vinculados voltam a rascunho e perdem as aprovações.
            </p>
            <button
              type="button"
              className={`${ui.secondary} mt-3`}
              disabled={busy}
              onClick={() => void act("revoke", "Verificação revogada.")}
            >
              Confirmar revogação
            </button>
          </details>
        ) : complete ? (
          <form onSubmit={verify} className="flex flex-col gap-3">
            <label htmlFor={confirmId} className="flex items-start gap-3 text-sm">
              <input id={confirmId} type="checkbox" required className="mt-1 size-5" />
              Conferi o documento do conselho correspondente a este nome, categoria e registro.
            </label>
            <div>
              <button type="submit" className={ui.button} disabled={busy}>
                Registrar verificação
              </button>
            </div>
          </form>
        ) : (
          <p className={ui.hint}>Informe categoria e registro para poder verificar.</p>
        )}

        <details>
          <summary className={ui.summary}>Editar dados</summary>
          <ProfessionalForm
            initial={person}
            submitLabel="Salvar alterações"
            busy={busy}
            onSubmit={(fields) =>
              mutate(path, "PATCH", { ...version, ...fields }, "Profissional atualizada.")
            }
          />
        </details>
      </div>
    </li>
  );
}

function ProfessionalForm({
  initial,
  submitLabel,
  busy,
  resetOnSuccess = false,
  onSubmit,
}: {
  initial?: Professional;
  submitLabel: string;
  busy: boolean;
  resetOnSuccess?: boolean;
  onSubmit: (fields: ReturnType<typeof professionalFields>) => Promise<boolean>;
}) {
  const id = useId();
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    setError(null);
    const fields = professionalFields(new FormData(form));
    if (!fields.display_name) {
      setError("Informe o nome.");
      return;
    }
    if ((await onSubmit(fields)) && resetOnSuccess) form.reset();
  }

  return (
    <form onSubmit={submit} className="mt-3 grid gap-4 sm:grid-cols-3">
      <div>
        <label htmlFor={`${id}-name`} className={ui.label}>
          Nome profissional
        </label>
        <input
          id={`${id}-name`}
          name="display_name"
          required
          maxLength={160}
          defaultValue={initial?.display_name}
          className={ui.input}
        />
      </div>
      <div>
        <label htmlFor={`${id}-category`} className={ui.label}>
          Categoria (ex.: enfermagem)
        </label>
        <input
          id={`${id}-category`}
          name="category"
          maxLength={120}
          defaultValue={initial?.category ?? ""}
          className={ui.input}
        />
      </div>
      <div>
        <label htmlFor={`${id}-registration`} className={ui.label}>
          Registro no conselho
        </label>
        <input
          id={`${id}-registration`}
          name="council_registration"
          maxLength={100}
          defaultValue={initial?.council_registration ?? ""}
          className={ui.input}
        />
      </div>
      {error && (
        <p role="alert" className="text-sm text-lumini-rose sm:col-span-3">
          {error}
        </p>
      )}
      <div className="sm:col-span-3">
        <button type="submit" className={ui.button} disabled={busy}>
          {submitLabel}
        </button>
      </div>
    </form>
  );
}
