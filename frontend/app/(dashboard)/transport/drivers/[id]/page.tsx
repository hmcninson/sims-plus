import { getDriver, getTrips, getRoutes } from "@/actions/transport.action";
import { DriverDetailView } from "./driver-detail";
import { AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import Link from "next/link";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function DriverDetailPage({ params }: Props) {
  const { id } = await params;

  const [driverResult, tripsResult, routesResult] = await Promise.all([
    getDriver(id),
    getTrips({ driverId: id, pageSize: 10 }),
    getRoutes({ pageSize: 100 }),
  ]);

  if (!driverResult.success || !driverResult.data) {
    return (
      <div className="flex h-[400px] flex-col items-center justify-center gap-4">
        <AlertCircle className="h-10 w-10 text-destructive" />
        <h2 className="text-lg font-semibold">Driver not found</h2>
        <p className="text-sm text-muted-foreground">
          {driverResult.error || "The driver you are looking for does not exist."}
        </p>
        <Button variant="outline" asChild>
          <Link href="/transport/drivers">Back to Drivers</Link>
        </Button>
      </div>
    );
  }

  // Filter routes assigned to this driver
  const assignedRoutes =
    routesResult.success && routesResult.data
      ? (Array.isArray(routesResult.data) ? routesResult.data : (routesResult.data.items ?? [])).filter(
          (r) => r.driver_id === id
        )
      : [];

  const trips =
    tripsResult.success && tripsResult.data
      ? Array.isArray(tripsResult.data)
        ? tripsResult.data
        : (tripsResult.data.items ?? [])
      : [];

  return (
    <DriverDetailView
      driver={driverResult.data}
      assignedRoutes={assignedRoutes}
      recentTrips={trips}
    />
  );
}
