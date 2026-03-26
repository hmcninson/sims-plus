import { Suspense } from "react";
import { Metadata } from "next";
import { InquiryDetail } from "./inquiry-detail";

export const metadata: Metadata = {
  title: "Inquiry Detail",
  description: "View and manage inquiry details",
};

export default async function InquiryDetailPage({
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
      <InquiryDetail inquiryId={id} />
    </Suspense>
  );
}
