"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { EditorContent } from "@tiptap/react";
import { useDocEditor } from "@/hooks/useDocEditor";
import MessageView from "../MessageView";
import DocBanners from "./DocBanners";
import DocHeader from "./DocHeader";
import PageSkeleton from "./PageSkeleton";
import SharePanel from "./SharePanel";
import Toolbar from "./Toolbar";

export default function DocWorkspace({ id }: { id: string }) {
  const router = useRouter();
  const s = useDocEditor(id);
  const [sharing, setSharing] = useState(false);

  if (s.fatal) return <MessageView icon="lock" title="Can't open this document" message={s.fatal} />;

  async function goBack() {
    if (await s.flush()) router.push("/");
  }

  return (
    <div className="min-h-screen bg-zinc-100/80 pb-24">
      <header className="sticky top-0 z-20 border-b border-zinc-200/70 bg-white/85 backdrop-blur-md">
        <DocHeader
          doc={s.doc}
          title={s.title}
          status={s.status}
          canEdit={s.canEdit}
          onTitleChange={s.changeTitle}
          onBack={goBack}
          onShare={() => setSharing(true)}
        />
      </header>
      {s.editor && s.doc?.role !== "viewer" && (
        <div className="sticky top-[69px] z-10 px-4 pt-3">
          <Toolbar editor={s.editor} disabled={!s.canEdit} />
        </div>
      )}

      <DocBanners
        conflict={s.conflict}
        notice={s.notice}
        draft={s.draft}
        onLoadTheirs={s.loadTheirs}
        onKeepMine={s.keepMine}
        onRestore={s.restoreDraft}
        onDiscard={s.discardDraft}
      />

      <main className="mx-auto mt-5 max-w-[816px] rounded-lg bg-white px-[72px] py-16 shadow-page ring-1 ring-zinc-900/5 max-sm:mx-3 max-sm:px-6 max-sm:py-10">
        {!s.doc && <PageSkeleton waking={s.status === "waking"} />}
        <EditorContent editor={s.editor} />
      </main>

      {sharing && s.doc && <SharePanel doc={s.doc} onChange={s.setShares} onClose={() => setSharing(false)} />}
    </div>
  );
}
