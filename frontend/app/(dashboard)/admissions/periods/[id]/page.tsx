import { Suspense } from "react";
import { Metadata } from "next";
import { PeriodDetail } from "./period-detail";

export const metadata: Metadata = {
  title: "Period Detail",
  description: "View and configure an admission period",
};

interface PeriodDetailPageProps {
  params: Promise<{ id: string }>;
}

export default async function PeriodDetailPage({
  params,
}: PeriodDetailPageProps) {
  const { id } = await params;

  return (
    <Suspense
      fallback={
        <div className="flex h-[400px] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      }
    >
      <PeriodDetail periodId={id} />
    </Suspense>
  );
}
