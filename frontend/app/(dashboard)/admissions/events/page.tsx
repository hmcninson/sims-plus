import { Suspense } from "react";
import { Metadata } from "next";
import { EventsManagement } from "./events-management";

export const metadata: Metadata = {
  title: "School Events",
  description: "Manage school tours, open days, and orientations",
};

export default function EventsPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-[400px] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      }
    >
      <EventsManagement />
    </Suspense>
  );
}
