import { Suspense } from "react";
import type { Metadata } from "next";
import { AnnouncementsPage } from "./announcements-page";

export const metadata: Metadata = {
  title: "Announcements",
  description: "Manage school announcements for parents",
};

export default function Page() {
  return (
    <Suspense
      fallback={
        <div className="flex h-[400px] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      }
    >
      <AnnouncementsPage />
    </Suspense>
  );
}
