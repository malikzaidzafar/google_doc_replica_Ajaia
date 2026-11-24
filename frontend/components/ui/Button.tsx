import type { ButtonHTMLAttributes } from "react";
import { cx } from "./cx";
import { Icon, type IconName } from "./icons";
import { Spinner } from "./Feedback";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "dangerGhost";
type Size = "sm" | "md";

const VARIANTS: Record<ButtonVariant, string> = {
  primary: "bg-accent-600 text-white shadow-sm ring-1 ring-accent-700/20 hover:bg-accent-500 enabled:active:bg-accent-700",
  secondary:
    "border border-zinc-200 bg-white text-zinc-800 shadow-xs hover:border-zinc-300 hover:bg-zinc-50 enabled:active:bg-zinc-100",
  ghost: "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 enabled:active:bg-zinc-200/70",
  danger: "bg-red-600 text-white shadow-sm hover:bg-red-500 enabled:active:bg-red-700",
  dangerGhost: "text-zinc-500 hover:bg-red-50 hover:text-red-600 enabled:active:bg-red-100",
};

const SIZES: Record<Size, string> = {
  sm: "h-8 gap-1.5 px-2.5 text-[13px]",
  md: "h-9 gap-2 px-3.5 text-sm",
};

/** Class string for anything that should look like a button (e.g. a Next.js <Link>). */
export const buttonClass = (variant: ButtonVariant = "secondary", size: Size = "md") =>
  cx(
    "inline-flex shrink-0 select-none items-center justify-center whitespace-nowrap rounded-lg font-medium",
    "transition-[background-color,border-color,color,box-shadow,transform] duration-150 ease-out",
    "enabled:active:scale-[0.98] disabled:opacity-50",
    VARIANTS[variant],
    SIZES[size],
  );

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: Size;
  icon?: IconName;
  loading?: boolean;
}

export function Button({ variant, size = "md", icon, loading, className, children, disabled, type, ...rest }: ButtonProps) {
  return (
    <button
      type={type ?? "button"}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cx(buttonClass(variant, size), className)}
      {...rest}
    >
      {loading ? <Spinner size={size === "sm" ? 14 : 16} /> : icon && <Icon name={icon} size={size === "sm" ? 15 : 16} />}
      {children}
    </button>
  );
}

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  label: string; // accessible name + native tooltip
  icon: IconName;
  variant?: "ghost" | "dangerGhost";
  pressed?: boolean;
}

/** Square icon-only button. `pressed` makes it a toggle (aria-pressed). */
export function IconButton({ label, icon, variant = "ghost", pressed, className, type, ...rest }: IconButtonProps) {
  return (
    <button
      type={type ?? "button"}
      aria-label={label}
      title={label}
      aria-pressed={pressed}
      className={cx(
        "inline-grid size-8 shrink-0 place-items-center rounded-md transition-[background-color,color,transform] duration-150",
        "enabled:active:scale-95 disabled:opacity-40",
        VARIANTS[variant],
        "aria-pressed:bg-accent-50 aria-pressed:text-accent-700 aria-pressed:hover:bg-accent-100",
        className,
      )}
      {...rest}
    >
      <Icon name={icon} size={16} />
    </button>
  );
}
