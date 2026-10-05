"use client";

import { useRef, useState } from "react";

import { Chat } from "./chat";

const focus = "focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-lumini-rose";

// Floating entry point on public pages; the conversation starts only when someone opens it.
export function ChatWidget({ apiOrigin }: { apiOrigin: string | null }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [opened, setOpened] = useState(false);
  if (!apiOrigin) return null;
  return (
    <>
      <button
        type="button"
        onClick={() => {
          setOpened(true);
          dialog.current?.showModal();
        }}
        className={`fixed right-4 bottom-4 z-20 min-h-12 bg-lumini-rose px-5 text-lumini-white shadow-lg hover:bg-lumini-ink ${focus}`}
      >
        Atendimento
      </button>
      <dialog
        ref={dialog}
        aria-labelledby="chat-titulo"
        className="m-auto h-[min(640px,92svh)] w-[min(100%-1rem,440px)] overscroll-contain bg-lumini-paper p-4 text-lumini-ink backdrop:bg-lumini-ink/40"
      >
        <div className="flex h-full flex-col gap-3">
          <div className="flex items-center justify-between">
            <h2 id="chat-titulo" className="font-display text-2xl">Atendimento Lumini</h2>
            <button type="button" onClick={() => dialog.current?.close()} className={`min-h-11 px-3 text-sm underline ${focus}`}>
              Fechar
            </button>
          </div>
          <div className="min-h-0 flex-1">{opened && <Chat apiOrigin={apiOrigin} />}</div>
        </div>
      </dialog>
    </>
  );
}
