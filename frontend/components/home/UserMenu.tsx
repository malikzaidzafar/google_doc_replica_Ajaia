import type { User } from "@/lib/types";
import { Avatar } from "../ui/Avatar";
import { Button } from "../ui/Button";

export default function UserMenu({ me, onSignOut }: { me: User; onSignOut: () => void }) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex items-center gap-2.5">
        <Avatar name={me.name} />
        <div className="hidden leading-tight sm:block">
          <p className="text-sm font-medium text-zinc-900">{me.name}</p>
          <p className="text-xs text-zinc-500">{me.email}</p>
        </div>
      </div>
      <span className="h-6 w-px bg-zinc-200" aria-hidden="true" />
      <Button variant="ghost" size="sm" icon="logOut" onClick={onSignOut}>
        Switch user
      </Button>
    </div>
  );
}
