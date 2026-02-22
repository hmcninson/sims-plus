import { Suspense } from "react";
import { getChildOverview } from "@/actions/parent.action";
import { ChildDetailView } from "./child-detail";
import ChildDetailLoading from "./loading";

export const metadata = {
  title: "Child Details",
};

interface ChildDetailPageProps {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ tab?: string }>;
}

export default async function ChildDetailPage({
  params,
  searchParams,
}: ChildDetailPageProps) {
  const { id } = await params;
  const { tab } = await searchParams;

  const result = await getChildOverview(id);
  const overview = result.success ? result.data : null;

  return (
    <Suspense fallback={<ChildDetailLoading />}>
      <ChildDetailView
        studentId={id}
        overview={overview}
        initialTab={tab || "overview"}
      />
    </Suspense>
  );
}
