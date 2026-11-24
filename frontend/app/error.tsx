"use client"; // Error boundaries must be Client Components

import { useEffect } from "react";
import MessageView from "@/components/MessageView";
import { Button } from "@/components/ui/Button";

export default function Error({ error, retry }: { error: unknown; retry: () => void }) {
  useEffect(() => {
    console.error(error); // details stay in the console, never on screen
  }, [error]);

  return (
    <MessageView
      title="Something went wrong"
      message="This page hit an unexpected problem. Saved work is safe on the server; please try again."
      action={<Button variant="primary" icon="refresh" onClick={() => retry()}>Try again</Button>}
    />
  );
}
