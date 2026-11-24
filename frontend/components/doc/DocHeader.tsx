"use client";

import type { SyncStatus } from "@/hooks/docSync";
import type { Doc } from "@/lib/types";
import { AvatarStack } from "../ui/Avatar";
import { RoleBadge } from "../ui/Badge";
import { Button, IconButton } from "../ui/Button";
import { Logo } from "../ui/icons";
import SaveStatus from "./SaveStatus";

interface Props {
  doc: Doc | null;
  title: string;
  status: SyncStatus;
  canEdit: boolean;
  onTitleChange: (value: string) => void;
  onBack: () => void;
  onShare: () => void;
}

export default function DocHeader({ doc, title, status, canEdit, onTitleChange, onBack, onShare }: Props) {
  return (
    <div className="flex items-center gap-3 px-4 py-2.5 sm:px-6">
      <IconButton label="Back to documents" icon="arrowLeft" onClick={onBack} />
      <span className="max-sm:hidden">
        <Logo size={32} />
      </span>
      <div className="min-w-0 flex-1">
        <input
          aria-label="Document title"
          value={title}
          maxLength={200}
          placeholder="Untitled document"
          disabled={!canEdit}
          onChange={(e) => onTitleChange(e.target.value)}
          className="-ml-1.5 w-full max-w-xl truncate rounded-md border border-transparent bg-transparent px-1.5 py-0.5 text-[17px] font-semibold text-zinc-900 transition-[border-color,box-shadow,background-color] duration-150 placeholder:text-zinc-400 enabled:hover:border-zinc-200 focus:border-accent-500 focus:bg-white focus:outline-none focus:ring-4 focus:ring-accent-500/15 focus-visible:outline-none disabled:cursor-default"
        />
        <div className="mt-0.5 flex items-center gap-2.5">
          <SaveStatus status={status} />
          {doc && doc.role !== "owner" && (
            <span className="flex items-center gap-1.5 truncate text-xs text-zinc-500">
              <span aria-hidden="true">·</span> Owned by {doc.owner.name}
              {doc.role === "editor" && <RoleBadge role="editor" />}
            </span>
          )}
        </div>
      </div>
      <AvatarStack names={doc?.active_users ?? []} />
      {doc && (
        <Button
          variant={doc.role === "owner" ? "primary" : "secondary"}
          icon={doc.role === "owner" ? "userPlus" : "users"}
          onClick={onShare}
        >
          {doc.role === "owner" ? "Share" : "People"}
        </Button>
      )}
    </div>
  );
}
