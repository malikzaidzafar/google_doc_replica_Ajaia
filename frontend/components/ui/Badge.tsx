import type { ReactNode } from "react";
import type { Role } from "@/lib/types";
import { cx } from "./cx";

type Tone = "accent" | "green" | "zinc" | "amber";

const TONES: Record<Tone, string> = {
  accent: "bg-accent-50 text-accent-700 ring-accent-600/15",
  green: "bg-emerald-50 text-emerald-700 ring-emerald-600/15",
  zinc: "bg-zinc-100 text-zinc-600 ring-zinc-500/15",
  amber: "bg-amber-50 text-amber-800 ring-amber-600/20",
};

export function Badge({ tone = "zinc", children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return (
    <span
      className={cx(
        "inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

const ROLE: Record<Role, { tone: Tone; label: string }> = {
  owner: { tone: "accent", label: "Owner" },
  editor: { tone: "green", label: "Can edit" },
  viewer: { tone: "zinc", label: "View only" },
};

export function RoleBadge({ role }: { role: Role }) {
  return <Badge tone={ROLE[role].tone}>{ROLE[role].label}</Badge>;
}
