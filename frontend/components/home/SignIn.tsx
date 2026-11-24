import type { User } from "@/lib/types";
import { Avatar } from "../ui/Avatar";
import { Banner } from "../ui/Banner";
import { SkeletonRows, Spinner } from "../ui/Feedback";
import { Icon, Logo } from "../ui/icons";

interface Props {
  users: User[] | null;
  error: string;
  waking: boolean;
  onSignIn: (user: User) => void;
}

export default function SignIn({ users, error, waking, onSignIn }: Props) {
  return (
    <section aria-labelledby="signin-title" className="mx-auto w-full max-w-md animate-pop-in">
      <div className="mb-8 flex flex-col items-center text-center">
        <Logo size={44} />
        <h1 id="signin-title" className="mt-5 text-2xl font-semibold text-zinc-900">Welcome to DocShare</h1>
        <p className="mt-2 max-w-sm text-sm leading-relaxed text-zinc-500">
          Pick a demo account to continue. Open a second browser as someone else to try sharing.
        </p>
      </div>

      <div className="overflow-hidden rounded-2xl border border-zinc-200/80 bg-white shadow-card">
        {error && <Banner tone="danger" className="m-4">{error}</Banner>}
        {!users && !error && (
          <>
            {waking && (
              <p aria-live="polite" className="flex items-center gap-2 border-b border-zinc-100 px-5 py-3 text-sm text-zinc-600">
                <Spinner size={14} className="text-accent-500" />
                Waking up the server… this can take up to a minute.
              </p>
            )}
            <SkeletonRows rows={3} />
          </>
        )}
        {users && (
          <ul className="divide-y divide-zinc-100">
            {users.map((u) => (
              <li key={u.id}>
                <button
                  type="button"
                  onClick={() => onSignIn(u)}
                  className="group flex w-full items-center gap-3.5 px-5 py-3.5 text-left transition-colors duration-150 hover:bg-zinc-50 focus-visible:bg-zinc-50 focus-visible:outline-offset-[-2px] active:bg-zinc-100"
                >
                  <Avatar name={u.name} size="lg" />
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-medium text-zinc-900">Continue as {u.name}</span>
                    <span className="block truncate text-[13px] text-zinc-500">{u.email}</span>
                  </span>
                  <Icon
                    name="chevronRight"
                    size={16}
                    className="text-zinc-300 transition-[transform,color] duration-150 group-hover:translate-x-0.5 group-hover:text-zinc-500"
                  />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <p className="mt-6 text-center text-xs text-zinc-400">Demo sign-in only: no passwords are used.</p>
    </section>
  );
}
