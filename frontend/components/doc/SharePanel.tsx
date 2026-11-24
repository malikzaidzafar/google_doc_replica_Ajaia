"use client";

import { useState, type FormEvent } from "react";
import { useShares } from "@/hooks/useShares";
import type { Doc, Share, ShareRole } from "@/lib/types";
import { Banner } from "../ui/Banner";
import { Button } from "../ui/Button";
import { Dialog } from "../ui/Dialog";
import { Input, Select } from "../ui/Field";
import ShareList from "./ShareList";

interface Props {
  doc: Doc;
  onChange: (shares: Share[]) => void;
  onClose: () => void;
}

export default function SharePanel({ doc, onChange, onClose }: Props) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<ShareRole>("editor");
  const { busy, error, share, remove } = useShares(doc.id, onChange);
  const isOwner = doc.role === "owner";

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (await share(email, role)) setEmail("");
  }

  return (
    <Dialog
      title={isOwner ? `Share “${doc.title}”` : "People with access"}
      description={isOwner ? "Invite people by email and choose what they can do." : `Owned by ${doc.owner.name}.`}
      onClose={onClose}
      footer={
        <form method="dialog">
          <Button type="submit" variant="secondary">Done</Button>
        </form>
      }
    >
      {isOwner && (
        <form onSubmit={onSubmit} className="flex flex-wrap gap-2">
          <label htmlFor="share-email" className="sr-only">Email address</label>
          <Input
            id="share-email"
            type="email"
            required
            autoComplete="off"
            placeholder="name@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="min-w-0 flex-1 basis-48"
          />
          <label htmlFor="share-role" className="sr-only">Access</label>
          <Select id="share-role" value={role} onChange={(e) => setRole(e.target.value as ShareRole)}>
            <option value="editor">Can edit</option>
            <option value="viewer">View only</option>
          </Select>
          <Button type="submit" variant="primary" loading={busy}>Invite</Button>
        </form>
      )}
      {isOwner && (
        <p className="mt-2 text-xs text-zinc-500">Demo accounts: alice@, bob@ and carol@example.com</p>
      )}
      {error && <Banner tone="danger" className="mt-3">{error}</Banner>}
      <h3 className="mt-5 text-xs font-semibold uppercase tracking-wide text-zinc-400">People with access</h3>
      <ShareList doc={doc} busy={busy} onRoleChange={share} onRemove={remove} />
    </Dialog>
  );
}
