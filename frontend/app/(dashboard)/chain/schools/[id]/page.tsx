import { getChainSchool } from "@/actions/chain.action";
import { SchoolDetailView } from "./school-detail-view";

export const metadata = {
  title: "School Details",
};

interface SchoolDetailPageProps {
  params: Promise<{ id: string }>;
}

export default async function SchoolDetailPage({ params }: SchoolDetailPageProps) {
  const { id } = await params;
  const result = await getChainSchool(id);

  if (!result.success || !result.data) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold tracking-tight">School Not Found</h1>
        <p className="text-muted-foreground">
          {result.error || "The requested school could not be found."}
        </p>
      </div>
    );
  }

  return <SchoolDetailView school={result.data} />;
}
