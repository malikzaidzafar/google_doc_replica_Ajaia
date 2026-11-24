import { Skeleton, Spinner } from "../ui/Feedback";

/** Placeholder lines shaped like a document while it loads (or while the free-tier server wakes up). */
export default function PageSkeleton({ waking }: { waking: boolean }) {
  return (
    <div aria-live="polite" className="animate-fade-in">
      <p className="mb-8 flex items-center gap-2 text-sm text-zinc-500">
        <Spinner size={14} className="text-accent-500" />
        {waking ? "Waking up the server… this can take up to a minute." : "Loading document…"}
      </p>
      <div aria-hidden="true" className="space-y-3">
        <Skeleton className="h-7 w-2/5" />
        <Skeleton className="h-3.5 w-full" />
        <Skeleton className="h-3.5 w-11/12" />
        <Skeleton className="h-3.5 w-4/5" />
        <Skeleton className="mt-6 h-3.5 w-full" />
        <Skeleton className="h-3.5 w-3/4" />
      </div>
    </div>
  );
}
