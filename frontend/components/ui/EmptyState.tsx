import type { ReactNode } from "react";
import { cx } from "./cx";
import { Icon, type IconName } from "./icons";

interface Props {
  icon: IconName;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  tone?: "neutral" | "danger";
  className?: string;
}

/** Centered icon + message + optional action, for empty lists and full-page messages. */
export function EmptyState({ icon, title, description, action, tone = "neutral", className }: Props) {
  return (
    <div className={cx("flex flex-col items-center px-6 py-12 text-center animate-fade-in", className)}>
      <span
        className={cx(
          "grid size-12 place-items-center rounded-2xl ring-1 ring-inset",
          tone === "danger" ? "bg-red-50 text-red-500 ring-red-100" : "bg-zinc-50 text-zinc-400 ring-zinc-200/70",
        )}
      >
        <Icon name={icon} size={22} />
      </span>
      <h3 className="mt-4 text-[15px] font-semibold text-zinc-900">{title}</h3>
      {description && <p className="mt-1 max-w-sm text-sm leading-relaxed text-zinc-500">{description}</p>}
      {action && <div className="mt-5 flex flex-wrap justify-center gap-2">{action}</div>}
    </div>
  );
}
