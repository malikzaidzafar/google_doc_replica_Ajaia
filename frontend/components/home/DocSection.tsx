import type { ReactNode } from "react";
import type { DocSummary } from "@/lib/types";
import { EmptyState } from "../ui/EmptyState";
import { SkeletonRows } from "../ui/Feedback";
import type { IconName } from "../ui/icons";

interface Props<T extends DocSummary> {
  title: string;
  docs: T[] | undefined;
  empty: { icon: IconName; title: string; description: string };
  renderItem: (doc: T) => ReactNode;
}

/** A titled card listing documents, with loading skeletons and an empty state. */
export default function DocSection<T extends DocSummary>({ title, docs, empty, renderItem }: Props<T>) {
  return (
    <section aria-label={title} className="overflow-hidden rounded-2xl border border-zinc-200/80 bg-white shadow-card">
      <header className="flex items-center gap-2 border-b border-zinc-100 px-5 py-3">
        <h2 className="text-sm font-semibold text-zinc-900">{title}</h2>
        {docs && (
          <span className="rounded-full bg-zinc-100 px-1.5 text-xs font-medium tabular-nums text-zinc-500">{docs.length}</span>
        )}
      </header>
      {!docs ? (
        <SkeletonRows rows={2} />
      ) : docs.length === 0 ? (
        <EmptyState icon={empty.icon} title={empty.title} description={empty.description} className="py-10" />
      ) : (
        <ul className="divide-y divide-zinc-100">{docs.map(renderItem)}</ul>
      )}
    </section>
  );
}
