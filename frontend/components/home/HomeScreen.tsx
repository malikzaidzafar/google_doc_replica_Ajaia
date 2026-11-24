"use client";

import { useDocuments } from "@/hooks/useDocuments";
import { useSession } from "@/hooks/useSession";
import type { DocSummary, SharedDocSummary } from "@/lib/types";
import AppBar from "../AppBar";
import { Avatar } from "../ui/Avatar";
import { RoleBadge } from "../ui/Badge";
import { Banner } from "../ui/Banner";
import DocRow from "./DocRow";
import DocSection from "./DocSection";
import HomeActions from "./HomeActions";
import SignIn from "./SignIn";
import UserMenu from "./UserMenu";

export default function HomeScreen() {
  const session = useSession();
  const { me } = session;
  const docs = useDocuments(me, session.signOut);

  if (!me) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-gradient-to-b from-white to-zinc-100 px-4 py-16">
        <SignIn users={session.users} error={session.error} waking={session.waking} onSignIn={session.signIn} />
      </main>
    );
  }

  return (
    <>
      <AppBar>
        <UserMenu me={me} onSignOut={session.signOut} />
      </AppBar>
      <main className="mx-auto max-w-5xl space-y-6 px-6 py-10">
        <HomeActions busy={docs.busy} onCreate={docs.create} onImport={docs.importFile} />
        {docs.error && <Banner tone="danger">{docs.error}</Banner>}
        <DocSection<DocSummary>
          title="My documents"
          docs={docs.docs?.owned}
          empty={{ icon: "file", title: "No documents yet", description: "Create a blank document or import a file to get started." }}
          renderItem={(doc) => (
            <DocRow key={doc.id} doc={doc} onDelete={() => docs.remove(doc)} />
          )}
        />
        <DocSection<SharedDocSummary>
          title="Shared with me"
          docs={docs.docs?.shared}
          empty={{ icon: "inbox", title: "Nothing shared yet", description: "Documents other people share with you will show up here." }}
          renderItem={(doc) => (
            <DocRow
              key={doc.id}
              doc={doc}
              badge={<RoleBadge role={doc.role} />}
              meta={
                <>
                  <Avatar name={doc.owner_name} size="xs" />
                  <span>{doc.owner_name}</span>
                  <span aria-hidden="true">·</span>
                </>
              }
            />
          )}
        />
      </main>
    </>
  );
}
