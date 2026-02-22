"use client";

import { useCallback, useEffect, useState, useTransition } from "react";
import { useForm } from "react-hook-form";
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
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import {
  CheckCircle2,
  Clock,
  Eye,
  Loader2,
  MoreHorizontal,
  Navigation,
  Pencil,
  Play,
  Plus,
  XCircle,
} from "lucide-react";
import {
  getTrips,
  getTrip,
  createTrip,
  updateTrip,
  startTrip,
  completeTrip,
  cancelTrip,
  getRoutes,
  getVehicles,
  getDrivers,
} from "@/actions/transport.action";
import { useToast } from "@/hooks/use-toast";
import type { TripLogDetail, TransportRoute, Vehicle, Driver, TripType } from "@/types";

// ─── Constants ────────────────────────────────────────────────────────────────

const TRIP_TYPES: { value: TripType; label: string }[] = [
  { value: "morning_pickup", label: "Morning Pickup" },
  { value: "afternoon_dropoff", label: "Afternoon Drop-off" },
  { value: "field_trip", label: "Field Trip" },
  { value: "other", label: "Other" },
];

// ─── Helpers ──────────────────────────────────────────────────────────────────

function getTripStatusBadge(status: string) {
  switch (status) {
    case "scheduled":
      return <Badge variant="secondary">Scheduled</Badge>;
    case "in_progress":
      return <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">In Progress</Badge>;
    case "completed":
      return <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">Completed</Badge>;
    case "cancelled":
      return <Badge variant="destructive">Cancelled</Badge>;
    default:
      return <Badge variant="secondary">{status}</Badge>;
  }
}

function getTripTypeBadge(type: string) {
  switch (type) {
    case "morning_pickup":
      return <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200">Morning</Badge>;
    case "afternoon_dropoff":
      return <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">Afternoon</Badge>;
    case "field_trip":
      return <Badge className="bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200">Field Trip</Badge>;
    case "other":
      return <Badge variant="outline">Other</Badge>;
    default:
      return <Badge variant="outline" className="capitalize">{type}</Badge>;
  }
}

function formatTripDate(dateStr: string) {
  return new Date(dateStr + "T00:00:00").toLocaleDateString("en-GB");
}

function formatTripTypeName(type: string) {
  return TRIP_TYPES.find((t) => t.value === type)?.label ?? type;
}

// ─── Schemas ──────────────────────────────────────────────────────────────────

const createTripSchema = z.object({
  route_id: z.string().min(1, "Route is required"),
  trip_date: z.string().min(1, "Date is required"),
  trip_type: z.enum(["morning_pickup", "afternoon_dropoff", "field_trip", "other"], {
    message: "Trip type is required",
  }),
  vehicle_id: z.string().min(1, "Vehicle is required"),
  driver_id: z.string().min(1, "Driver is required"),
  departure_time: z.string().optional(),
  student_count: z.coerce.number().int().nonnegative("Student count cannot be negative"),
  incidents: z.string().optional(),
});

type CreateTripFormData = z.infer<typeof createTripSchema>;

const editTripSchema = z.object({
  departure_time: z.string().optional(),
  arrival_time: z.string().optional(),
  odometer_start: z.coerce.number().nonnegative("Must be non-negative").optional().or(z.literal("")),
  odometer_end: z.coerce.number().nonnegative("Must be non-negative").optional().or(z.literal("")),
  student_count: z.coerce.number().int().nonnegative("Student count cannot be negative"),
  incidents: z.string().optional(),
});

type EditTripFormData = z.infer<typeof editTripSchema>;

// ─── Component ────────────────────────────────────────────────────────────────

export default function TripsPage() {
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();
  const [trips, setTrips] = useState<TripLogDetail[]>([]);
  const [routes, setRoutes] = useState<TransportRoute[]>([]);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [total, setTotal] = useState(0);
  const [activeTab, setActiveTab] = useState("all");
  const [filterRoute, setFilterRoute] = useState("all");
  const [isActioning, setIsActioning] = useState(false);

  // Dialog state
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [isDetailDialogOpen, setIsDetailDialogOpen] = useState(false);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [selectedTrip, setSelectedTrip] = useState<TripLogDetail | null>(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Load reference data (routes, vehicles, drivers)
  useEffect(() => {
    startTransition(async () => {
      const [routesResult, vehiclesResult, driversResult] = await Promise.all([
        getRoutes({ isActive: true, pageSize: 100 }),
        getVehicles({ status: "active", pageSize: 100 }),
        getDrivers({ status: "active", pageSize: 100 }),
      ]);
      if (routesResult.success && routesResult.data) {
        setRoutes(Array.isArray(routesResult.data) ? routesResult.data : (routesResult.data.items ?? []));
      }
      if (vehiclesResult.success && vehiclesResult.data) {
        setVehicles(Array.isArray(vehiclesResult.data) ? vehiclesResult.data : (vehiclesResult.data.items ?? []));
      }
      if (driversResult.success && driversResult.data) {
        setDrivers(Array.isArray(driversResult.data) ? driversResult.data : (driversResult.data.items ?? []));
      }
    });
  }, []);

  const loadTrips = useCallback(() => {
    startTransition(async () => {
      const statusFilter = activeTab !== "all" ? activeTab : undefined;
      const result = await getTrips({
        status: statusFilter,
        routeId: filterRoute !== "all" ? filterRoute : undefined,
        pageSize: 50,
      });
      if (result.success && result.data) {
        const data = result.data;
        const items = Array.isArray(data) ? data : (data.items ?? []);
        const count = Array.isArray(data) ? data.length : (data.total ?? 0);
        setTrips(items);
        setTotal(count);
      }
    });
  }, [activeTab, filterRoute]);

  useEffect(() => {
    loadTrips();
  }, [loadTrips]);

  // ─── Trip Actions ──────────────────────────────────────────────────────────

  const handleStartTrip = async (id: string) => {
    setIsActioning(true);
    try {
      const result = await startTrip(id);
      if (result.success) {
        toast({ title: "Trip started" });
        loadTrips();
      } else {
        toast({ title: "Error", description: result.error, variant: "destructive" });
      }
    } finally {
      setIsActioning(false);
    }
  };

  const handleCompleteTrip = async (id: string) => {
    setIsActioning(true);
    try {
      const result = await completeTrip(id);
      if (result.success) {
        toast({ title: "Trip completed" });
        loadTrips();
      } else {
        toast({ title: "Error", description: result.error, variant: "destructive" });
      }
    } finally {
      setIsActioning(false);
    }
  };

  const handleCancelTrip = async (id: string) => {
    setIsActioning(true);
    try {
      const result = await cancelTrip(id);
      if (result.success) {
        toast({ title: "Trip cancelled" });
        loadTrips();
      } else {
        toast({ title: "Error", description: result.error, variant: "destructive" });
      }
    } finally {
      setIsActioning(false);
    }
  };

  // ─── View Trip Detail ──────────────────────────────────────────────────────

  const handleViewDetail = async (tripId: string) => {
    setIsLoadingDetail(true);
    setIsDetailDialogOpen(true);
    try {
      const result = await getTrip(tripId);
      if (result.success && result.data) {
        setSelectedTrip(result.data);
      } else {
        toast({ title: "Error", description: result.error || "Failed to load trip details", variant: "destructive" });
        setIsDetailDialogOpen(false);
      }
    } finally {
      setIsLoadingDetail(false);
    }
  };

  // ─── Create Trip Form ─────────────────────────────────────────────────────

  const createForm = useForm<CreateTripFormData>({
    resolver: zodResolver(createTripSchema),
    defaultValues: {
      route_id: "",
      trip_date: new Date().toISOString().split("T")[0],
      trip_type: "morning_pickup",
      vehicle_id: "",
      driver_id: "",
      departure_time: "",
      student_count: 0,
      incidents: "",
    },
  });

  const handleOpenCreateDialog = () => {
    createForm.reset({
      route_id: "",
      trip_date: new Date().toISOString().split("T")[0],
      trip_type: "morning_pickup",
      vehicle_id: "",
      driver_id: "",
      departure_time: "",
      student_count: 0,
      incidents: "",
    });
    setIsCreateDialogOpen(true);
  };

  const onSubmitCreate = async (data: CreateTripFormData) => {
    setIsSubmitting(true);
    try {
      const payload = {
        route_id: data.route_id,
        vehicle_id: data.vehicle_id,
        driver_id: data.driver_id,
        trip_date: data.trip_date,
        trip_type: data.trip_type as TripType,
        departure_time: data.departure_time?.trim() || undefined,
        student_count: data.student_count,
        incidents: data.incidents?.trim() || undefined,
      };

      const result = await createTrip(payload);
      if (result.success) {
        toast({ title: "Trip created" });
        setIsCreateDialogOpen(false);
        loadTrips();
      } else {
        toast({ title: "Error", description: result.error, variant: "destructive" });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  // ─── Edit Trip Form ───────────────────────────────────────────────────────

  const editForm = useForm<EditTripFormData>({
    resolver: zodResolver(editTripSchema),
    defaultValues: {
      departure_time: "",
      arrival_time: "",
      odometer_start: "",
      odometer_end: "",
      student_count: 0,
      incidents: "",
    },
  });

  const handleOpenEditDialog = (trip: TripLogDetail) => {
    setSelectedTrip(trip);
    editForm.reset({
      departure_time: trip.departure_time || "",
      arrival_time: trip.arrival_time || "",
      odometer_start: trip.odometer_start ?? "",
      odometer_end: trip.odometer_end ?? "",
      student_count: trip.student_count,
      incidents: trip.incidents || "",
    });
    setIsEditDialogOpen(true);
  };

  const onSubmitEdit = async (data: EditTripFormData) => {
    if (!selectedTrip) return;
    setIsSubmitting(true);
    try {
      const payload = {
        departure_time: data.departure_time?.trim() || undefined,
        arrival_time: data.arrival_time?.trim() || undefined,
        odometer_start: typeof data.odometer_start === "number" ? data.odometer_start : undefined,
        odometer_end: typeof data.odometer_end === "number" ? data.odometer_end : undefined,
        student_count: data.student_count,
        incidents: data.incidents?.trim() || undefined,
      };

      const result = await updateTrip(selectedTrip.id, payload);
      if (result.success) {
        toast({ title: "Trip updated" });
        setIsEditDialogOpen(false);
        loadTrips();
      } else {
        toast({ title: "Error", description: result.error, variant: "destructive" });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  // ─── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Trip Logs</h1>
          <p className="text-muted-foreground">Track and manage daily transport trips</p>
        </div>
        <Button onClick={handleOpenCreateDialog}>
          <Plus className="mr-2 h-4 w-4" />
          Create Trip
        </Button>
      </div>

      <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
        <Select value={filterRoute} onValueChange={setFilterRoute}>
          <SelectTrigger className="w-full sm:w-[220px]">
            <SelectValue placeholder="Route" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Routes</SelectItem>
            {routes.map((r) => (
              <SelectItem key={r.id} value={r.id}>
                {r.route_code} - {r.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="all">All</TabsTrigger>
          <TabsTrigger value="scheduled">Scheduled</TabsTrigger>
          <TabsTrigger value="in_progress">In Progress</TabsTrigger>
          <TabsTrigger value="completed">Completed</TabsTrigger>
        </TabsList>

        <TabsContent value={activeTab} className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle>Trips</CardTitle>
              <CardDescription>{total} trip{total !== 1 ? "s" : ""}</CardDescription>
            </CardHeader>
            <CardContent>
              {isPending ? (
                <div className="flex h-[200px] items-center justify-center">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
              ) : trips.length > 0 ? (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Date</TableHead>
                        <TableHead>Route</TableHead>
                        <TableHead className="hidden sm:table-cell">Type</TableHead>
                        <TableHead className="hidden md:table-cell">Vehicle</TableHead>
                        <TableHead className="hidden md:table-cell">Driver</TableHead>
                        <TableHead className="hidden md:table-cell text-right">Students</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead className="w-[50px] text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {trips.map((trip) => (
                        <TableRow key={trip.id}>
                          <TableCell className="whitespace-nowrap">
                            {formatTripDate(trip.trip_date)}
                          </TableCell>
                          <TableCell className="font-medium">{trip.route_name || "--"}</TableCell>
                          <TableCell className="hidden sm:table-cell">{getTripTypeBadge(trip.trip_type)}</TableCell>
                          <TableCell className="hidden md:table-cell">{trip.vehicle_registration || "--"}</TableCell>
                          <TableCell className="hidden md:table-cell">{trip.driver_name || "--"}</TableCell>
                          <TableCell className="hidden md:table-cell text-right">{trip.student_count}</TableCell>
                          <TableCell>{getTripStatusBadge(trip.status)}</TableCell>
                          <TableCell className="text-right">
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button variant="ghost" size="icon" className="h-8 w-8">
                                  <MoreHorizontal className="h-4 w-4" />
                                  <span className="sr-only">Open menu</span>
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end">
                                <DropdownMenuItem onClick={() => handleViewDetail(trip.id)}>
                                  <Eye className="mr-2 h-4 w-4" />
                                  View Details
                                </DropdownMenuItem>
                                {trip.status === "scheduled" && (
                                  <>
                                    <DropdownMenuItem onClick={() => handleOpenEditDialog(trip)}>
                                      <Pencil className="mr-2 h-4 w-4" />
                                      Edit Trip
                                    </DropdownMenuItem>
                                    <DropdownMenuSeparator />
                                    <DropdownMenuItem
                                      onClick={() => handleStartTrip(trip.id)}
                                      disabled={isActioning}
                                    >
                                      <Play className="mr-2 h-4 w-4" />
                                      Start Trip
                                    </DropdownMenuItem>
                                    <DropdownMenuItem
                                      onClick={() => handleCancelTrip(trip.id)}
                                      disabled={isActioning}
                                      className="text-destructive focus:text-destructive"
                                    >
                                      <XCircle className="mr-2 h-4 w-4" />
                                      Cancel Trip
                                    </DropdownMenuItem>
                                  </>
                                )}
                                {trip.status === "in_progress" && (
                                  <>
                                    <DropdownMenuSeparator />
                                    <DropdownMenuItem
                                      onClick={() => handleCompleteTrip(trip.id)}
                                      disabled={isActioning}
                                    >
                                      <CheckCircle2 className="mr-2 h-4 w-4" />
                                      Complete Trip
                                    </DropdownMenuItem>
                                  </>
                                )}
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              ) : (
                <div className="flex h-[200px] flex-col items-center justify-center gap-2 text-muted-foreground">
                  <Navigation className="h-12 w-12" />
                  <p>No trips found</p>
                  <p className="max-w-md text-center text-sm">
                    Create a trip to start tracking transport journeys for your school.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* ─── Create Trip Dialog ────────────────────────────────────────────── */}
      <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
        <DialogContent className="sm:max-w-[550px]">
          <DialogHeader>
            <DialogTitle>Create Trip</DialogTitle>
            <DialogDescription>
              Schedule a new transport trip. Assign a route, vehicle, and driver.
            </DialogDescription>
          </DialogHeader>
          <Form {...createForm}>
            <form onSubmit={createForm.handleSubmit(onSubmitCreate)} className="space-y-4">
              <FormField
                control={createForm.control}
                name="route_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Route *</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Select a route" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {routes.map((r) => (
                          <SelectItem key={r.id} value={r.id}>
                            {r.route_code} - {r.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={createForm.control}
                  name="trip_date"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Date *</FormLabel>
                      <FormControl>
                        <Input type="date" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={createForm.control}
                  name="trip_type"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Trip Type *</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {TRIP_TYPES.map((t) => (
                            <SelectItem key={t.value} value={t.value}>
                              {t.label}
                            </SelectItem>
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
                  control={createForm.control}
                  name="vehicle_id"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Vehicle *</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder="Select vehicle" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {vehicles.map((v) => (
                            <SelectItem key={v.id} value={v.id}>
                              {v.registration_number} ({v.vehicle_type})
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={createForm.control}
                  name="driver_id"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Driver *</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder="Select driver" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {drivers.map((d) => (
                            <SelectItem key={d.id} value={d.id}>
                              {d.first_name} {d.last_name}
                            </SelectItem>
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
                  control={createForm.control}
                  name="departure_time"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Departure Time</FormLabel>
                      <FormControl>
                        <Input type="time" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={createForm.control}
                  name="student_count"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Student Count *</FormLabel>
                      <FormControl>
                        <Input type="number" min={0} {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <FormField
                control={createForm.control}
                name="incidents"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Notes / Incidents</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Any notes or incidents for this trip..."
                        rows={2}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsCreateDialogOpen(false)}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Create Trip
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* ─── Trip Detail Dialog ────────────────────────────────────────────── */}
      <Dialog open={isDetailDialogOpen} onOpenChange={setIsDetailDialogOpen}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Trip Details</DialogTitle>
            <DialogDescription>
              Full details for this transport trip.
            </DialogDescription>
          </DialogHeader>
          {isLoadingDetail ? (
            <div className="flex h-[200px] items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : selectedTrip ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {getTripStatusBadge(selectedTrip.status)}
                  {getTripTypeBadge(selectedTrip.trip_type)}
                </div>
                <span className="text-sm text-muted-foreground">
                  {formatTripDate(selectedTrip.trip_date)}
                </span>
              </div>

              <Separator />

              <div className="grid grid-cols-1 md:grid-cols-2 gap-y-3 text-sm">
                <div>
                  <p className="text-muted-foreground">Route</p>
                  <p className="font-medium">{selectedTrip.route_name || "--"}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Vehicle</p>
                  <p className="font-medium">{selectedTrip.vehicle_registration || "--"}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Driver</p>
                  <p className="font-medium">{selectedTrip.driver_name || "--"}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Students</p>
                  <p className="font-medium">{selectedTrip.student_count}</p>
                </div>
              </div>

              <Separator />

              <div className="grid grid-cols-1 md:grid-cols-2 gap-y-3 text-sm">
                <div>
                  <p className="text-muted-foreground">Departure Time</p>
                  <p className="font-medium">{selectedTrip.departure_time || "--"}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Arrival Time</p>
                  <p className="font-medium">{selectedTrip.arrival_time || "--"}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Odometer Start</p>
                  <p className="font-medium">
                    {selectedTrip.odometer_start != null ? `${selectedTrip.odometer_start.toLocaleString()} km` : "--"}
                  </p>
                </div>
                <div>
                  <p className="text-muted-foreground">Odometer End</p>
                  <p className="font-medium">
                    {selectedTrip.odometer_end != null ? `${selectedTrip.odometer_end.toLocaleString()} km` : "--"}
                  </p>
                </div>
              </div>

              {selectedTrip.incidents && (
                <>
                  <Separator />
                  <div className="text-sm">
                    <p className="text-muted-foreground">Notes / Incidents</p>
                    <p className="mt-1 whitespace-pre-wrap">{selectedTrip.incidents}</p>
                  </div>
                </>
              )}

              <Separator />

              <div className="text-sm">
                <p className="text-muted-foreground">Logged By</p>
                <p className="font-medium">{selectedTrip.logged_by_name || "--"}</p>
              </div>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>

      {/* ─── Edit Trip Dialog ──────────────────────────────────────────────── */}
      <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Edit Trip</DialogTitle>
            <DialogDescription>
              Update trip details. Only scheduled trips can be edited.
            </DialogDescription>
          </DialogHeader>
          {selectedTrip && (
            <div className="mb-2 flex items-center gap-2 text-sm text-muted-foreground">
              <Clock className="h-4 w-4" />
              <span>
                {selectedTrip.route_name} - {formatTripDate(selectedTrip.trip_date)} ({formatTripTypeName(selectedTrip.trip_type)})
              </span>
            </div>
          )}
          <Form {...editForm}>
            <form onSubmit={editForm.handleSubmit(onSubmitEdit)} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={editForm.control}
                  name="departure_time"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Departure Time</FormLabel>
                      <FormControl>
                        <Input type="time" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={editForm.control}
                  name="arrival_time"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Arrival Time</FormLabel>
                      <FormControl>
                        <Input type="time" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={editForm.control}
                  name="odometer_start"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Odometer Start (km)</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          step="0.1"
                          placeholder="0"
                          {...field}
                          value={field.value ?? ""}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={editForm.control}
                  name="odometer_end"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Odometer End (km)</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          step="0.1"
                          placeholder="0"
                          {...field}
                          value={field.value ?? ""}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <FormField
                control={editForm.control}
                name="student_count"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Student Count *</FormLabel>
                    <FormControl>
                      <Input type="number" min={0} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={editForm.control}
                name="incidents"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Notes / Incidents</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Any notes or incidents..."
                        rows={2}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsEditDialogOpen(false)}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Save Changes
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
