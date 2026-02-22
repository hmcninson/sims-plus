import { getVehicle, getMaintenanceHistory } from "@/actions/transport.action";
import { VehicleDetailView } from "./vehicle-detail";
import { AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import Link from "next/link";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function VehicleDetailPage({ params }: Props) {
  const { id } = await params;

  const [vehicleResult, maintenanceResult] = await Promise.all([
    getVehicle(id),
    getMaintenanceHistory({ vehicleId: id, pageSize: 20 }),
  ]);

  if (!vehicleResult.success || !vehicleResult.data) {
    return (
      <div className="flex h-[400px] flex-col items-center justify-center gap-4">
        <AlertCircle className="h-10 w-10 text-destructive" />
        <h2 className="text-lg font-semibold">Vehicle not found</h2>
        <p className="text-sm text-muted-foreground">
          {vehicleResult.error || "The vehicle you are looking for does not exist."}
        </p>
        <Button variant="outline" asChild>
          <Link href="/transport/vehicles">Back to Vehicles</Link>
        </Button>
      </div>
    );
  }

  return (
    <VehicleDetailView
      vehicle={vehicleResult.data}
      maintenanceHistory={maintenanceResult.success && maintenanceResult.data ? (Array.isArray(maintenanceResult.data) ? maintenanceResult.data : (maintenanceResult.data.items ?? [])) : []}
    />
  );
}
