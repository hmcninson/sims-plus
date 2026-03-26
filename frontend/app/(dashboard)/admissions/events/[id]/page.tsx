import { Suspense } from "react";
import { Metadata } from "next";
import { EventDetail } from "./event-detail";

export const metadata: Metadata = {
  title: "Event Detail",
  description: "View event details and manage registrations",
};

export default async function EventDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <Suspense
      fallback={
        <div className="flex h-[400px] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      }
    >
      <EventDetail eventId={id} />
    </Suspense>
  );
}
