"use client";

import { useParams } from "next/navigation";
import MessageView from "../MessageView";
import DocWorkspace from "./DocWorkspace";

export default function DocRoute() {
  const { id } = useParams<{ id: string }>();
  if (!/^\d+$/.test(id)) {
    return <MessageView title="Document not found" message="That link doesn't point to a document." />;
  }
  // key: a fresh editor and sync state per document when navigating between docs
  return <DocWorkspace key={id} id={id} />;
}
