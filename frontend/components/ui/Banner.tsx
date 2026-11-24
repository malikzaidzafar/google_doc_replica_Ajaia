import type { ReactNode } from "react";
import { cx } from "./cx";
import { Icon, type IconName } from "./icons";

type Tone = "info" | "warning" | "danger";

const TONES: Record<Tone, { box: string; icon: string; name: IconName }> = {
  info: { box: "border-accent-200/80 bg-accent-50/80 text-accent-950", icon: "text-accent-500", name: "info" },
  warning: { box: "border-amber-200 bg-amber-50 text-amber-950", icon: "text-amber-500", name: "alert" },
  danger: { box: "border-red-200 bg-red-50 text-red-950", icon: "text-red-500", name: "alert" },
};

interface Props {
  tone?: Tone;
  title?: ReactNode;
  children?: ReactNode;
  actions?: ReactNode;
  role?: "alert" | "status";
  className?: string;
}

/** Inline message with an icon; slides in when it appears. */
export function Banner({ tone = "info", title, children, actions, role = "alert", className }: Props) {
  const t = TONES[tone];
  return (
    <div
      role={role}
      className={cx("flex flex-wrap items-start gap-x-3 gap-y-2 rounded-xl border px-4 py-3 text-sm shadow-xs animate-slide-down", t.box, className)}
    >
      <Icon name={t.name} size={18} className={cx("mt-px shrink-0", t.icon)} />
      <div className="min-w-0 flex-1 basis-60 leading-relaxed">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className={title ? "mt-0.5 opacity-80" : undefined}>{children}</div>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
