import Link from "next/link";
import type { ReactNode } from "react";
import { Logo } from "./ui/icons";

/** Top bar shared by every non-editor screen: brand on the left, `children` (user menu) on the right. */
export default function AppBar({ children }: { children?: ReactNode }) {
  return (
    <header className="sticky top-0 z-20 border-b border-zinc-200/70 bg-white/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-5xl items-center justify-between gap-4 px-6">
        <Link
          href="/"
          className="flex items-center gap-2.5 rounded-lg text-[15px] font-semibold tracking-tight text-zinc-900 transition-opacity hover:opacity-80"
        >
          <Logo />
          DocShare
        </Link>
        {children}
      </div>
    </header>
  );
}
