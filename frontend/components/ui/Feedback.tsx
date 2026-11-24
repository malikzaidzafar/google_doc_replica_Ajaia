import { cx } from "./cx";

/** Indeterminate spinner; decorative (pair it with text or aria-busy). */
export function Spinner({ size = 16, className }: { size?: number; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cx("inline-block shrink-0 animate-spin rounded-full border-2 border-current border-r-transparent opacity-80", className)}
      style={{ width: size, height: size }}
    />
  );
}

/** Grey shimmer block for loading placeholders. */
export function Skeleton({ className }: { className?: string }) {
  return <span aria-hidden="true" className={cx("block animate-pulse rounded-md bg-zinc-200/70", className)} />;
}

/** Three skeleton rows shaped like document list items. */
export function SkeletonRows({ rows = 3 }: { rows?: number }) {
  return (
    <ul aria-hidden="true" className="divide-y divide-zinc-100">
      {Array.from({ length: rows }, (_, i) => (
        <li key={i} className="flex items-center gap-4 px-5 py-3.5">
          <Skeleton className="size-9 rounded-lg" />
          <span className="flex-1 space-y-2">
            <Skeleton className="h-3.5 w-1/3" />
            <Skeleton className="h-3 w-1/5" />
          </span>
        </li>
      ))}
    </ul>
  );
}
