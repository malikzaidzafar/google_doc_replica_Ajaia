"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { IconButton } from "./Button";

interface Props {
  title: ReactNode;
  description?: ReactNode;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
}

/**
 * Native <dialog> opened as a modal: focus trap, Escape to close and inert background for free.
 * Clicking the blurred backdrop also closes it.
 */
export function Dialog({ title, description, onClose, children, footer }: Props) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    ref.current?.showModal();
  }, []);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => e.target === ref.current && ref.current?.close()}
      aria-labelledby="dialog-title"
      className="m-auto w-[calc(100%-2rem)] max-w-lg rounded-2xl border border-zinc-200/80 bg-white p-0 text-zinc-900 shadow-pop"
    >
      <div className="flex items-start gap-3 border-b border-zinc-100 px-6 pb-4 pt-5">
        <div className="min-w-0 flex-1">
          <h2 id="dialog-title" className="truncate text-base font-semibold">{title}</h2>
          {description && <p className="mt-1 text-sm text-zinc-500">{description}</p>}
        </div>
        <IconButton label="Close" icon="x" onClick={() => ref.current?.close()} className="-mr-2 -mt-1" />
      </div>
      <div className="px-6 py-5">{children}</div>
      {footer && <div className="flex justify-end gap-2 rounded-b-2xl border-t border-zinc-100 bg-zinc-50/70 px-6 py-3">{footer}</div>}
    </dialog>
  );
}
