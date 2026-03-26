"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useForm , type Resolver} from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ArrowLeft, Bus, Calendar, Shield, Wrench, Pencil, Plus, Loader2 } from "lucide-react";
import { updateVehicle, createMaintenance } from "@/actions/transport.action";
import { useToast } from "@/hooks/use-toast";
import type { VehicleDetail, VehicleMaintenanceDetail, VehicleType, VehicleStatus, MaintenanceType } from "@/types";

interface Props {
  vehicle: VehicleDetail;
  maintenanceHistory: VehicleMaintenanceDetail[];
}

const VEHICLE_TYPES: { value: VehicleType; label: string }[] = [
  { value: "bus", label: "Bus" },
  { value: "minibus", label: "Minibus" },
  { value: "van", label: "Van" },
  { value: "car", label: "Car" },
];

const VEHICLE_STATUSES: { value: VehicleStatus; label: string }[] = [
  { value: "active", label: "Active" },
  { value: "maintenance", label: "Maintenance" },
  { value: "retired", label: "Retired" },
];

const MAINTENANCE_TYPES: { value: MaintenanceType; label: string }[] = [
  { value: "routine", label: "Routine" },
  { value: "repair", label: "Repair" },
  { value: "inspection", label: "Inspection" },
  { value: "emergency", label: "Emergency" },
];

function getStatusBadge(status: string) {
  switch (status) {
    case "active":
      return <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">Active</Badge>;
    case "maintenance":
      return <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200">Maintenance</Badge>;
    case "retired":
      return <Badge variant="secondary">Retired</Badge>;
    default:
      return <Badge variant="secondary">{status}</Badge>;
  }
}

function getMaintenanceTypeBadge(type: string) {
  switch (type) {
    case "routine":
      return <Badge variant="outline">Routine</Badge>;
    case "repair":
      return <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200">Repair</Badge>;
    case "inspection":
      return <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">Inspection</Badge>;
    case "emergency":
      return <Badge variant="destructive">Emergency</Badge>;
    default:
      return <Badge variant="outline" className="capitalize">{type}</Badge>;
  }
}

function formatDate(dateStr: string | undefined): string {
  if (!dateStr) return "--";
  return new Date(dateStr + "T00:00:00").toLocaleDateString("en-GB");
}

// ========================
// Edit Vehicle Schema
// ========================

const editVehicleSchema = z.object({
  registration_number: z.string().min(1, "Registration number is required").max(20),
  vehicle_type: z.enum(["bus", "minibus", "van", "car"]),
  make: z.string().optional(),
  model_name: z.string().optional(),
  year: z.coerce.number().int().min(1990).max(2030).optional().or(z.literal("")),
  capacity: z.coerce.number().int().positive("Capacity must be positive"),
  status: z.enum(["active", "maintenance", "retired"]).optional(),
  insurance_expiry: z.string().optional(),
  roadworthy_expiry: z.string().optional(),
  gps_tracker_id: z.string().optional(),
  notes: z.string().optional(),
});

type EditVehicleFormData = z.infer<typeof editVehicleSchema>;

// ========================
// Log Maintenance Schema
// ========================

const maintenanceSchema = z.object({
  maintenance_type: z.enum(["routine", "repair", "inspection", "emergency"], {
    message: "Select a maintenance type",
  }),
  description: z.string().min(1, "Description is required"),
  cost: z.coerce.number().min(0, "Cost cannot be negative").optional().or(z.literal("")),
  service_date: z.string().min(1, "Service date is required"),
  odometer_reading: z.coerce.number().min(0).optional().or(z.literal("")),
  service_provider: z.string().optional(),
  invoice_number: z.string().optional(),
  next_service_date: z.string().optional(),
});

type MaintenanceFormData = z.infer<typeof maintenanceSchema>;

export function VehicleDetailView({ vehicle, maintenanceHistory }: Props) {
  const router = useRouter();
  const { toast } = useToast();
  const [, startTransition] = useTransition();
  const makeModel = [vehicle.make, vehicle.model_name].filter(Boolean).join(" ");

  // Edit Vehicle Dialog
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isEditSubmitting, setIsEditSubmitting] = useState(false);

  const editForm = useForm<EditVehicleFormData>({
    resolver: zodResolver(editVehicleSchema) as Resolver<EditVehicleFormData>,
    defaultValues: {
      registration_number: vehicle.registration_number,
      vehicle_type: vehicle.vehicle_type,
      make: vehicle.make || "",
      model_name: vehicle.model_name || "",
      year: vehicle.year ?? "",
      capacity: vehicle.capacity,
      status: vehicle.status,
      insurance_expiry: vehicle.insurance_expiry || "",
      roadworthy_expiry: vehicle.roadworthy_expiry || "",
      gps_tracker_id: vehicle.gps_tracker_id || "",
      notes: vehicle.notes || "",
    },
  });

  // Log Maintenance Dialog
  const [isMaintenanceOpen, setIsMaintenanceOpen] = useState(false);
  const [isMaintenanceSubmitting, setIsMaintenanceSubmitting] = useState(false);

  const maintenanceForm = useForm<MaintenanceFormData>({
    resolver: zodResolver(maintenanceSchema) as Resolver<MaintenanceFormData>,
    defaultValues: {
      maintenance_type: "routine",
      description: "",
      cost: "",
      service_date: new Date().toISOString().split("T")[0],
      odometer_reading: "",
      service_provider: "",
      invoice_number: "",
      next_service_date: "",
    },
  });

  const handleEditSubmit = async (data: EditVehicleFormData) => {
    setIsEditSubmitting(true);
    try {
      const payload = {
        registration_number: data.registration_number.trim(),
        vehicle_type: data.vehicle_type,
        make: data.make?.trim() || undefined,
        model_name: data.model_name?.trim() || undefined,
        year: typeof data.year === "number" ? data.year : undefined,
        capacity: data.capacity,
        status: data.status,
        insurance_expiry: data.insurance_expiry || undefined,
        roadworthy_expiry: data.roadworthy_expiry || undefined,
        gps_tracker_id: data.gps_tracker_id?.trim() || undefined,
        notes: data.notes?.trim() || undefined,
      };

      const result = await updateVehicle(vehicle.id, payload);
      if (result.success) {
        toast({ title: "Vehicle updated" });
        setIsEditOpen(false);
        startTransition(() => {
          router.refresh();
        });
      } else {
        toast({ title: "Error", description: result.error, variant: "destructive" });
      }
    } finally {
      setIsEditSubmitting(false);
    }
  };

  const handleMaintenanceSubmit = async (data: MaintenanceFormData) => {
    setIsMaintenanceSubmitting(true);
    try {
      const payload = {
        vehicle_id: vehicle.id,
        maintenance_type: data.maintenance_type,
        description: data.description.trim(),
        cost: typeof data.cost === "number" ? data.cost : undefined,
        service_date: data.service_date,
        odometer_reading: typeof data.odometer_reading === "number" ? data.odometer_reading : undefined,
        service_provider: data.service_provider?.trim() || undefined,
        invoice_number: data.invoice_number?.trim() || undefined,
        next_service_date: data.next_service_date || undefined,
      };

      const result = await createMaintenance(payload);
      if (result.success) {
        toast({ title: "Maintenance record logged" });
        setIsMaintenanceOpen(false);
        maintenanceForm.reset({
          maintenance_type: "routine",
          description: "",
          cost: "",
          service_date: new Date().toISOString().split("T")[0],
          odometer_reading: "",
          service_provider: "",
          invoice_number: "",
          next_service_date: "",
        });
        startTransition(() => {
          router.refresh();
        });
      } else {
        toast({ title: "Error", description: result.error, variant: "destructive" });
      }
    } finally {
      setIsMaintenanceSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/transport/vehicles">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold tracking-tight">{vehicle.registration_number}</h1>
          <p className="text-muted-foreground">
            {makeModel || "Vehicle"} {vehicle.year ? `(${vehicle.year})` : ""}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {getStatusBadge(vehicle.status)}
          <Button variant="outline" size="sm" onClick={() => setIsEditOpen(true)}>
            <Pencil className="mr-2 h-4 w-4" />
            Edit Vehicle
          </Button>
          <Button size="sm" onClick={() => setIsMaintenanceOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Log Maintenance
          </Button>
        </div>
      </div>

      {/* Vehicle Info Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Type</CardTitle>
            <Bus className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <Badge variant="outline" className="capitalize">{vehicle.vehicle_type}</Badge>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Capacity</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{vehicle.capacity}</div>
            <p className="text-xs text-muted-foreground">passengers</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Insurance Expiry</CardTitle>
            <Shield className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-sm font-medium">{formatDate(vehicle.insurance_expiry)}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Roadworthy Expiry</CardTitle>
            <Calendar className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-sm font-medium">{formatDate(vehicle.roadworthy_expiry)}</div>
          </CardContent>
        </Card>
      </div>

      {/* Additional Info */}
      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Route Assignments</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{vehicle.active_route_count}</div>
            <p className="text-xs text-muted-foreground">active routes</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Maintenance</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1 text-sm">
              <p>
                <span className="text-muted-foreground">Last:</span>{" "}
                {formatDate(vehicle.last_maintenance_date)}
              </p>
              <p>
                <span className="text-muted-foreground">Next:</span>{" "}
                {formatDate(vehicle.next_maintenance_date)}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {vehicle.notes && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Notes</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">{vehicle.notes}</p>
          </CardContent>
        </Card>
      )}

      {/* Maintenance History */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Maintenance History</CardTitle>
            <CardDescription>
              {maintenanceHistory.length} record{maintenanceHistory.length !== 1 ? "s" : ""}
            </CardDescription>
          </div>
          <Button variant="outline" size="sm" onClick={() => setIsMaintenanceOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Log Maintenance
          </Button>
        </CardHeader>
        <CardContent>
          {maintenanceHistory.length > 0 ? (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead className="text-right">Cost (GHS)</TableHead>
                    <TableHead>Provider</TableHead>
                    <TableHead>Next Service</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {maintenanceHistory.map((record) => (
                    <TableRow key={record.id}>
                      <TableCell className="whitespace-nowrap">
                        {formatDate(record.service_date)}
                      </TableCell>
                      <TableCell>{getMaintenanceTypeBadge(record.maintenance_type)}</TableCell>
                      <TableCell className="max-w-[200px] truncate">{record.description}</TableCell>
                      <TableCell className="text-right">
                        {record.cost != null ? record.cost.toLocaleString() : "--"}
                      </TableCell>
                      <TableCell>{record.service_provider || "--"}</TableCell>
                      <TableCell>{formatDate(record.next_service_date)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <div className="flex h-[150px] flex-col items-center justify-center gap-2 text-muted-foreground">
              <Wrench className="h-8 w-8" />
              <p className="text-sm">No maintenance records yet</p>
              <Button variant="link" size="sm" onClick={() => setIsMaintenanceOpen(true)}>
                Log the first maintenance record
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Edit Vehicle Dialog */}
      <Dialog open={isEditOpen} onOpenChange={setIsEditOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-[550px]">
          <DialogHeader>
            <DialogTitle>Edit Vehicle</DialogTitle>
            <DialogDescription>
              Update details for {vehicle.registration_number}.
            </DialogDescription>
          </DialogHeader>
          <Form {...editForm}>
            <form onSubmit={editForm.handleSubmit(handleEditSubmit)} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={editForm.control}
                  name="registration_number"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Registration Number *</FormLabel>
                      <FormControl>
                        <Input placeholder="e.g., GR-1234-24" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={editForm.control}
                  name="vehicle_type"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Vehicle Type *</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {VEHICLE_TYPES.map((t) => (
                            <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
                <FormField
                  control={editForm.control}
                  name="make"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Make</FormLabel>
                      <FormControl>
                        <Input placeholder="e.g., Toyota" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={editForm.control}
                  name="model_name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Model</FormLabel>
                      <FormControl>
                        <Input placeholder="e.g., HiAce" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={editForm.control}
                  name="year"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Year</FormLabel>
                      <FormControl>
                        <Input type="number" placeholder="2024" {...field} value={field.value ?? ""} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={editForm.control}
                  name="capacity"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Capacity *</FormLabel>
                      <FormControl>
                        <Input type="number" min={1} {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={editForm.control}
                  name="status"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Status</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {VEHICLE_STATUSES.map((s) => (
                            <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={editForm.control}
                  name="insurance_expiry"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Insurance Expiry</FormLabel>
                      <FormControl>
                        <Input type="date" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={editForm.control}
                  name="roadworthy_expiry"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Roadworthy Expiry</FormLabel>
                      <FormControl>
                        <Input type="date" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <FormField
                control={editForm.control}
                name="gps_tracker_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>GPS Tracker ID</FormLabel>
                    <FormControl>
                      <Input placeholder="Tracker ID (optional)" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={editForm.control}
                name="notes"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Notes</FormLabel>
                    <FormControl>
                      <Textarea placeholder="Any additional notes..." rows={2} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setIsEditOpen(false)} disabled={isEditSubmitting}>
                  Cancel
                </Button>
                <Button type="submit" disabled={isEditSubmitting}>
                  {isEditSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Save Changes
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* Log Maintenance Dialog */}
      <Dialog open={isMaintenanceOpen} onOpenChange={setIsMaintenanceOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-[550px]">
          <DialogHeader>
            <DialogTitle>Log Maintenance</DialogTitle>
            <DialogDescription>
              Record a maintenance activity for {vehicle.registration_number}.
            </DialogDescription>
          </DialogHeader>
          <Form {...maintenanceForm}>
            <form onSubmit={maintenanceForm.handleSubmit(handleMaintenanceSubmit)} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={maintenanceForm.control}
                  name="maintenance_type"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Maintenance Type *</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder="Select type" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {MAINTENANCE_TYPES.map((t) => (
                            <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={maintenanceForm.control}
                  name="service_date"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Service Date *</FormLabel>
                      <FormControl>
                        <Input type="date" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <FormField
                control={maintenanceForm.control}
                name="description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Description *</FormLabel>
                    <FormControl>
                      <Textarea placeholder="Describe the maintenance work performed..." rows={3} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={maintenanceForm.control}
                  name="cost"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Cost (GHS)</FormLabel>
                      <FormControl>
                        <Input type="number" min={0} step="0.01" placeholder="0.00" {...field} value={field.value ?? ""} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={maintenanceForm.control}
                  name="odometer_reading"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Odometer Reading (km)</FormLabel>
                      <FormControl>
                        <Input type="number" min={0} placeholder="e.g., 45000" {...field} value={field.value ?? ""} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={maintenanceForm.control}
                  name="service_provider"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Service Provider</FormLabel>
                      <FormControl>
                        <Input placeholder="Garage / mechanic name" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={maintenanceForm.control}
                  name="invoice_number"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Invoice Number</FormLabel>
                      <FormControl>
                        <Input placeholder="Invoice / receipt no." {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <FormField
                control={maintenanceForm.control}
                name="next_service_date"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Next Service Date</FormLabel>
                    <FormControl>
                      <Input type="date" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setIsMaintenanceOpen(false)} disabled={isMaintenanceSubmitting}>
                  Cancel
                </Button>
                <Button type="submit" disabled={isMaintenanceSubmitting}>
                  {isMaintenanceSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Log Maintenance
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
