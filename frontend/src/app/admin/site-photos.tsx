"use client";

import { useId, useState } from "react";

import type { SiteSettings } from "@/lib/admin/types";

import { ui } from "./ui";

export type PhotoDraft = SiteSettings["content"]["photos"][number] & { key: number };

export function SitePhotos({ photos, onChange, origins, nextKey, onAdded }: {
  photos: PhotoDraft[]; onChange: (photos: PhotoDraft[]) => void; origins: string[];
  nextKey: number; onAdded: () => void;
}) {
  const id = useId();
  const [confirmed, setConfirmed] = useState(false);
  const change = (key: number, fields: Partial<PhotoDraft>) => onChange(photos.map((item) => item.key === key ? { ...item, ...fields } : item));
  return (
    <fieldset className={`${ui.card} flex flex-col gap-4`}>
      <legend className="px-1 font-semibold">Fotos autorizadas</legend>
      <p className={ui.hint}>Use imagens hospedadas pela clínica. A autorização por escrito deve incluir a publicação da foto e ser mantida pela clínica. Não use antes e depois.</p>
      <p className={ui.hint}>Origens permitidas: {origins.length ? origins.join(", ") : "nenhuma configurada; a equipe precisa configurar a hospedagem antes de publicar fotos"}.</p>
      {photos.map((photo, index) => (
        <div key={photo.key} className="grid gap-3 border-b border-lumini-gold/30 pb-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label htmlFor={`${id}-url-${photo.key}`} className={ui.label}>Link da foto {index + 1} (HTTPS, sem parâmetros)</label>
            <input id={`${id}-url-${photo.key}`} type="url" required value={photo.url} maxLength={500} className={ui.input} onChange={(event) => change(photo.key, { url: event.target.value })} />
          </div>
          <div className="sm:col-span-2">
            <label htmlFor={`${id}-alt-${photo.key}`} className={ui.label}>Descrição da foto para acessibilidade</label>
            <input id={`${id}-alt-${photo.key}`} required value={photo.alt} maxLength={200} className={ui.input} onChange={(event) => change(photo.key, { alt: event.target.value })} />
          </div>
          <div>
            <label htmlFor={`${id}-width-${photo.key}`} className={ui.label}>Largura original (pixels)</label>
            <input id={`${id}-width-${photo.key}`} type="number" min={100} max={6000} required value={photo.width || ""} className={ui.input} onChange={(event) => change(photo.key, { width: Number(event.target.value) })} />
          </div>
          <div>
            <label htmlFor={`${id}-height-${photo.key}`} className={ui.label}>Altura original (pixels)</label>
            <input id={`${id}-height-${photo.key}`} type="number" min={100} max={6000} required value={photo.height || ""} className={ui.input} onChange={(event) => change(photo.key, { height: Number(event.target.value) })} />
          </div>
          <div>
            <label htmlFor={`${id}-date-${photo.key}`} className={ui.label}>Data da autorização da foto</label>
            <input id={`${id}-date-${photo.key}`} type="date" required value={photo.authorized_on} className={ui.input} onChange={(event) => change(photo.key, { authorized_on: event.target.value })} />
          </div>
          <div className="self-end">
            <button type="button" className={ui.secondary} onClick={() => onChange(photos.filter((item) => item.key !== photo.key))}>Remover foto {index + 1}</button>
          </div>
        </div>
      ))}
      <label className="flex items-start gap-3 text-sm" htmlFor={`${id}-consent`}>
        <input id={`${id}-consent`} type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} className="mt-1 size-5" />
        Tenho autorização por escrito para publicar esta foto.
      </label>
      <div>
        <button type="button" className={ui.secondary} disabled={photos.length >= 12 || !confirmed} onClick={() => {
          onChange([...photos, { key: nextKey, url: "", alt: "", width: 0, height: 0, authorized_on: "", authorization_confirmed: true }]);
          onAdded(); setConfirmed(false);
        }}>Adicionar foto autorizada</button>
      </div>
    </fieldset>
  );
}
