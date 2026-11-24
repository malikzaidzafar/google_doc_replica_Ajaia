import Link from "next/link";
import type { ReactNode } from "react";
import type { DocSummary } from "@/lib/types";
import { IconButton } from "../ui/Button";
import { Icon } from "../ui/icons";
import { fullDate, timeAgo } from "../ui/time";

interface Props {
  doc: DocSummary;
  meta?: ReactNode; // extra line content, e.g. the owner
  badge?: ReactNode;
  onDelete?: () => void;
}

/**
 * One document row. The title link stretches over the whole row (after:inset-0), so the row is one
 * big click target, while the delete button sits above it instead of being nested inside the link.
 */
export default function DocRow({ doc, meta, badge, onDelete }: Props) {
  return (
    <li className="group relative flex items-center gap-4 px-5 py-3 transition-colors duration-150 hover:bg-zinc-50/80 focus-within:bg-zinc-50/80">
      <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-accent-50 text-accent-500 ring-1 ring-inset ring-accent-100 transition-colors duration-150 group-hover:bg-accent-100/70">
        <Icon name="file" size={17} />
      </span>
      <div className="min-w-0 flex-1">
        <Link
          href={`/docs/${doc.id}`}
          className="block truncate text-sm font-medium text-zinc-900 outline-none transition-colors after:absolute after:inset-0 after:rounded-[inherit] group-hover:text-accent-700 focus-visible:after:outline-2 focus-visible:after:-outline-offset-2 focus-visible:after:outline-accent-500"
        >
          {doc.title}
        </Link>
        <p className="mt-0.5 flex items-center gap-1.5 truncate text-xs text-zinc-500">
          {meta}
          <span title={fullDate(doc.updated_at)}>Edited {timeAgo(doc.updated_at)}</span>
        </p>
      </div>
      {badge}
      {onDelete && (
        <IconButton
          label={`Delete ${doc.title}`}
          icon="trash"
          variant="dangerGhost"
          onClick={onDelete}
          className="relative z-10 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100 focus-visible:opacity-100 max-sm:opacity-100"
        />
      )}
      <Icon
        name="chevronRight"
        size={16}
        className="shrink-0 text-zinc-300 max-sm:hidden transition-[transform,color] duration-150 group-hover:translate-x-0.5 group-hover:text-zinc-400"
      />
    </li>
  );
}
