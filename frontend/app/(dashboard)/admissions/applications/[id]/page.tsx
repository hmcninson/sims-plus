import { Suspense } from "react";
import { Metadata } from "next";
import { ApplicationDetailView } from "./application-detail-view";

export const metadata: Metadata = {
  title: "Application Detail",
  description: "View and manage an admission application",
};

interface ApplicationDetailPageProps {
  params: Promise<{ id: string }>;
}

export default async function ApplicationDetailPage({
  params,
}: ApplicationDetailPageProps) {
  const { id } = await params;

  return (
    <Suspense
      fallback={
        <div className="flex h-[400px] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      }
    >
      <ApplicationDetailView applicationId={id} />
    </Suspense>
  );
}
