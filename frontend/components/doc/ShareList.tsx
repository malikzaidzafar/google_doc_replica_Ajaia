import type { Doc, ShareRole } from "@/lib/types";
import { Avatar } from "../ui/Avatar";
import { RoleBadge } from "../ui/Badge";
import { IconButton } from "../ui/Button";
import { Select } from "../ui/Field";

interface Props {
  doc: Doc;
  busy: boolean;
  onRoleChange: (email: string, role: ShareRole) => void;
  onRemove: (userId: number) => void;
}

function Person({ name, detail }: { name: string; detail?: string }) {
  return (
    <span className="flex min-w-0 flex-1 items-center gap-3">
      <Avatar name={name} />
      <span className="min-w-0">
        <span className="block truncate text-sm font-medium text-zinc-900">{name}</span>
        {detail && <span className="block truncate text-xs text-zinc-500">{detail}</span>}
      </span>
    </span>
  );
}

export default function ShareList({ doc, busy, onRoleChange, onRemove }: Props) {
  const isOwner = doc.role === "owner";
  return (
    <ul aria-label="People with access" className="-mx-2 mt-2 space-y-0.5">
      <li className="flex items-center gap-3 rounded-lg px-2 py-2">
        <Person name={doc.owner.name} detail="Owner" />
        <RoleBadge role="owner" />
      </li>
      {doc.shares.map((s) => (
        <li key={s.user_id} className="group flex items-center gap-2 rounded-lg px-2 py-2 transition-colors duration-150 hover:bg-zinc-50">
          <Person name={s.name} detail={s.email} />
          {isOwner ? (
            <>
              <Select
                aria-label={`Access for ${s.name}`}
                compact
                value={s.role}
                disabled={busy}
                onChange={(e) => onRoleChange(s.email, e.target.value as ShareRole)}
              >
                <option value="editor">Can edit</option>
                <option value="viewer">View only</option>
              </Select>
              <IconButton
                label={`Remove access for ${s.name}`}
                icon="x"
                variant="dangerGhost"
                disabled={busy}
                onClick={() => onRemove(s.user_id)}
              />
            </>
          ) : (
            <RoleBadge role={s.role} />
          )}
        </li>
      ))}
      {doc.shares.length === 0 && (
        <li className="px-2 py-3 text-sm text-zinc-500">Only the owner has access so far.</li>
      )}
    </ul>
  );
}
