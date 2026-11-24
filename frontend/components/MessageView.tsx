import Link from "next/link";
import type { ReactNode } from "react";
import AppBar from "./AppBar";
import { buttonClass } from "./ui/Button";
import { EmptyState } from "./ui/EmptyState";
import type { IconName } from "./ui/icons";

interface Props {
  title: string;
  message: string;
  action?: ReactNode;
  icon?: IconName;
}

/** Full-page friendly message: not found, access lost, unexpected errors. */
export default function MessageView({ title, message, action, icon = "alert" }: Props) {
  return (
    <>
      <AppBar />
      <main className="mx-auto max-w-lg px-4 py-20">
        <section role="alert" className="rounded-2xl border border-zinc-200/80 bg-white shadow-card animate-pop-in">
          <EmptyState
            icon={icon}
            title={title}
            description={message}
            action={
              <>
                {action}
                <Link href="/" className={buttonClass(action ? "secondary" : "primary")}>
                  Back to documents
                </Link>
              </>
            }
          />
        </section>
      </main>
    </>
  );
}
