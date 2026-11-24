import type { Notice } from "@/hooks/docSync";
import type { Draft } from "@/lib/draft";
import type { Doc } from "@/lib/types";
import { Banner } from "../ui/Banner";
import { Button } from "../ui/Button";
import { fullDate } from "../ui/time";

interface Props {
  conflict: Doc | null;
  notice: Notice | null;
  draft: Draft | null;
  onLoadTheirs: () => void;
  onKeepMine: () => void;
  onRestore: () => void;
  onDiscard: () => void;
}

export default function DocBanners({ conflict, notice, draft, onLoadTheirs, onKeepMine, onRestore, onDiscard }: Props) {
  if (!conflict && !notice && !draft) return null;
  return (
    <div className="mx-auto mt-4 max-w-[816px] space-y-3 px-4 sm:px-0">
      {conflict && (
        <Banner
          tone="danger"
          title={`${conflict.updated_by ?? "Someone"} saved a newer version while you were editing.`}
          actions={
            <>
              <Button size="sm" variant="secondary" onClick={onLoadTheirs}>Load their version</Button>
              <Button size="sm" variant="danger" onClick={onKeepMine}>Keep mine</Button>
            </>
          }
        >
          Your changes are still on screen but not saved. Keeping yours overwrites their version.
        </Banner>
      )}
      {notice && !conflict && <Banner tone={notice.tone === "error" ? "danger" : "warning"}>{notice.message}</Banner>}
      {draft && (
        <Banner
          tone="info"
          role="status"
          title="Restore unsaved changes?"
          actions={
            <>
              <Button size="sm" variant="ghost" onClick={onDiscard}>Discard</Button>
              <Button size="sm" variant="primary" onClick={onRestore}>Restore</Button>
            </>
          }
        >
          This browser kept changes from {fullDate(draft.savedAt)} that never reached the server.
        </Banner>
      )}
    </div>
  );
}
