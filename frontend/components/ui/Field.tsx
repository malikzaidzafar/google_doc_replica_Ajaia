import type { InputHTMLAttributes, SelectHTMLAttributes } from "react";
import { cx } from "./cx";
import { Icon } from "./icons";

const field = cx(
  "h-9 rounded-lg border border-zinc-200 bg-white text-sm text-zinc-900 shadow-xs",
  "transition-[border-color,box-shadow] duration-150 placeholder:text-zinc-400 hover:border-zinc-300",
  "focus:border-accent-500 focus:outline-none focus:ring-4 focus:ring-accent-500/15 focus-visible:outline-none",
  "disabled:bg-zinc-50 disabled:text-zinc-500",
);

export function Input({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cx(field, "px-3", className)} {...rest} />;
}

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  compact?: boolean;
  wrapperClassName?: string;
}

/** Native <select> (keyboard + screen reader support for free) with a custom chevron. */
export function Select({ className, wrapperClassName, compact, children, ...rest }: SelectProps) {
  return (
    <span className={cx("relative inline-flex", wrapperClassName)}>
      <select
        className={cx(field, "w-full appearance-none pl-3 pr-8", compact && "h-8 text-[13px]", className)}
        {...rest}
      >
        {children}
      </select>
      <Icon name="chevronDown" size={14} className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-400" />
    </span>
  );
}
