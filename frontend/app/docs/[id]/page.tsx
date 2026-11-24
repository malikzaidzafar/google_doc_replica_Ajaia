import { Suspense } from "react";
import DocRoute from "@/components/doc/DocRoute";
import PageSkeleton from "@/components/doc/PageSkeleton";

// The doc id is only known at request time, so useParams needs a Suspense boundary (cacheComponents).
export default function Page() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-zinc-100/80 pt-24">
          <div className="mx-auto max-w-[816px] rounded-lg bg-white px-[72px] py-16 shadow-page max-sm:mx-3 max-sm:px-6">
            <PageSkeleton waking={false} />
          </div>
        </div>
      }
    >
      <DocRoute />
    </Suspense>
  );
}
