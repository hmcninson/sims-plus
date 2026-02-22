import { getRoute } from "@/actions/transport.action";
import { RouteDetailView } from "./route-detail";
import { AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import Link from "next/link";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function RouteDetailPage({ params }: Props) {
  const { id } = await params;
  const result = await getRoute(id);

  if (!result.success || !result.data) {
    return (
      <div className="flex h-[400px] flex-col items-center justify-center gap-4">
        <AlertCircle className="h-10 w-10 text-destructive" />
        <h2 className="text-lg font-semibold">Route not found</h2>
        <p className="text-sm text-muted-foreground">
          {result.error || "The route you are looking for does not exist."}
        </p>
        <Button variant="outline" asChild>
          <Link href="/transport/routes">Back to Routes</Link>
        </Button>
      </div>
    );
  }

  return <RouteDetailView route={result.data} />;
}
