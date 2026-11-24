import { cx } from "./cx";

const COLORS = [
  "bg-accent-500", "bg-emerald-700", "bg-amber-700", "bg-rose-700", "bg-sky-700", "bg-violet-700", "bg-teal-700",
];

/** Same name → same colour, on every screen and every visit. */
function colorFor(name: string) {
  let hash = 7;
  for (const ch of name) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  return COLORS[hash % COLORS.length];
}

const initials = (name: string) =>
  name.trim().split(/\s+/).slice(0, 2).map((part) => part[0]?.toUpperCase() ?? "").join("") || "?";

const SIZES = { xs: "size-4 text-[8px]", sm: "size-6 text-[10px]", md: "size-8 text-xs", lg: "size-10 text-sm" } as const;

interface AvatarProps {
  name: string;
  size?: keyof typeof SIZES;
  className?: string;
}

/** Decorative initials avatar; always render the person's name as text next to it. */
export function Avatar({ name, size = "md", className }: AvatarProps) {
  return (
    <span
      aria-hidden="true"
      className={cx(
        "inline-grid shrink-0 select-none place-items-center rounded-full font-semibold text-white",
        colorFor(name),
        SIZES[size],
        className,
      )}
    >
      {initials(name)}
    </span>
  );
}

/** Overlapping avatars for "who else is here", with a pulsing live dot. */
export function AvatarStack({ names, max = 3 }: { names: string[]; max?: number }) {
  if (names.length === 0) return null;
  const shown = names.slice(0, max);
  const label = `${names.join(", ")} ${names.length === 1 ? "is" : "are"} also here`;
  return (
    <span className="flex items-center gap-2 animate-fade-in" title={label}>
      <span className="relative flex size-2" aria-hidden="true">
        <span className="absolute inset-0 rounded-full bg-emerald-500 animate-pulse-dot" />
      </span>
      <span className="flex -space-x-2">
        {shown.map((name) => (
          <Avatar key={name} name={name} size="sm" className="ring-2 ring-white" />
        ))}
        {names.length > max && (
          <span aria-hidden="true" className="inline-grid size-6 place-items-center rounded-full bg-zinc-200 text-[10px] font-semibold text-zinc-700 ring-2 ring-white">
            +{names.length - max}
          </span>
        )}
      </span>
      <span className="sr-only">{label}</span>
    </span>
  );
}
