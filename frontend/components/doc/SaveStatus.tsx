import type { SyncStatus } from "@/hooks/docSync";
import { cx } from "../ui/cx";
import { Spinner } from "../ui/Feedback";
import { Icon, type IconName } from "../ui/icons";

type Look = { text: string; tone: string; icon?: IconName; spin?: boolean; dot?: boolean };

const LOOK: Record<SyncStatus, Look> = {
  loading: { text: "Loading…", tone: "text-zinc-500", spin: true },
  waking: { text: "Waking up the server…", tone: "text-zinc-500", spin: true },
  saved: { text: "All changes saved", tone: "text-zinc-500", icon: "check" },
  unsaved: { text: "Unsaved changes", tone: "text-zinc-500", dot: true },
  saving: { text: "Saving…", tone: "text-zinc-500", spin: true },
  offline: { text: "Offline, retrying…", tone: "text-amber-700", icon: "cloudOff" },
  conflict: { text: "Not saved: conflict", tone: "text-red-600", icon: "alert" },
  readonly: { text: "View only", tone: "text-zinc-500", icon: "eye" },
  stopped: { text: "Editing stopped", tone: "text-red-600", icon: "lock" },
};

/** Save state with an icon: spinner while saving, check when saved, warnings when not. */
export default function SaveStatus({ status }: { status: SyncStatus }) {
  const look = LOOK[status];
  return (
    <span aria-live="polite" className={cx("inline-flex items-center gap-1.5 text-xs font-medium", look.tone)}>
      <span key={status} className="inline-flex animate-fade-in items-center">
        {look.spin && <Spinner size={12} />}
        {look.icon && <Icon name={look.icon} size={13} strokeWidth={2.25} />}
        {look.dot && <span className="size-1.5 rounded-full bg-amber-400" aria-hidden="true" />}
      </span>
      {look.text}
    </span>
  );
}
