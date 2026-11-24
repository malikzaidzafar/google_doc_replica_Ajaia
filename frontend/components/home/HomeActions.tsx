"use client";

import { useRef } from "react";
import { UPLOAD_ACCEPT } from "@/lib/upload";
import { Button } from "../ui/Button";

interface Props {
  busy: boolean;
  onCreate: () => void;
  onImport: (file: File) => void;
}

/** Page heading plus the two primary actions: create a blank doc or import a file. */
export default function HomeActions({ busy, onCreate, onImport }: Props) {
  const fileInput = useRef<HTMLInputElement>(null);

  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold text-zinc-900">Documents</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Import .txt, .md or .docx up to 2 MB. Images and tables aren&apos;t imported.
        </p>
      </div>
      <div className="flex items-center gap-2">
        <Button variant="secondary" icon="upload" loading={busy} onClick={() => fileInput.current?.click()}>
          Import file
        </Button>
        <Button variant="primary" icon="plus" disabled={busy} onClick={onCreate}>
          New document
        </Button>
      </div>
      <input
        ref={fileInput}
        type="file"
        accept={UPLOAD_ACCEPT}
        hidden
        aria-label="Import a .txt, .md or .docx file"
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = ""; // allow picking the same file again
          if (file) onImport(file);
        }}
      />
    </div>
  );
}
