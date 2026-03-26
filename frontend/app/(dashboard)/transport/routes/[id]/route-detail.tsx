"use client";

import { useCallback, useEffect, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { useForm , type Resolver} from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  ArrowLeft,
  ArrowDown,
  ArrowUp,
  Bus,
  Clock,
  Loader2,
  MapPin,
  MoreHorizontal,
  Pencil,
  Plus,
  Route,
  Trash2,
  Users,
} from "lucide-react";
import {
  addStop,
  updateStop,
  deleteStop,
  reorderStops,
  updateRoute,
  getRoute,
  getVehicles,
  getDrivers,
} from "@/actions/transport.action";
import { useToast } from "@/hooks/use-toast";
import type { TransportRouteDetail, RouteStop, RouteType, Vehicle, Driver } from "@/types";

// ─── Constants ────────────────────────────────────────────────────────────────

const ROUTE_TYPES: { value: RouteType; label: string }[] = [
  { value: "morning_pickup", label: "Morning Pickup" },
  { value: "afternoon_dropoff", label: "Afternoon Drop-off" },
  { value: "both", label: "Both" },
];

// ─── Schemas ──────────────────────────────────────────────────────────────────

const stopSchema = z.object({
  stop_name: z.string().min(1, "Stop name is required").max(100),
  stop_order: z.coerce.number().int().positive("Order must be a positive number"),
  pickup_time: z.string().optional(),
  dropoff_time: z.string().optional(),
  latitude: z.coerce.number().min(-90).max(90).optional().or(z.literal("")),
  longitude: z.coerce.number().min(-180).max(180).optional().or(z.literal("")),
  landmark: z.string().max(200).optional(),
});

type StopFormData = z.infer<typeof stopSchema>;

const routeEditSchema = z.object({
  name: z.string().min(1, "Route name is required").max(100),
  route_code: z.string().min(1, "Route code is required").max(20),
  description: z.string().optional(),
  route_type: z.enum(["morning_pickup", "afternoon_dropoff", "both"]),
  distance_km: z.coerce.number().positive("Distance must be positive").optional().or(z.literal("")),
  estimated_duration_minutes: z.coerce.number().int().positive("Duration must be positive").optional().or(z.literal("")),
  vehicle_id: z.string().optional(),
  driver_id: z.string().optional(),
  transport_fee_per_term: z.coerce.number().nonnegative("Fee cannot be negative").optional().or(z.literal("")),
});

type RouteEditFormData = z.infer<typeof routeEditSchema>;

// ─── Helpers ──────────────────────────────────────────────────────────────────

function getRouteTypeBadge(type: string) {
  switch (type) {
    case "morning_pickup":
      return <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200">Morning Pickup</Badge>;
    case "afternoon_dropoff":
      return <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">Afternoon Drop-off</Badge>;
    case "both":
      return <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">Both</Badge>;
    default:
      return <Badge variant="outline" className="capitalize">{type}</Badge>;
  }
}

// ─── Component ────────────────────────────────────────────────────────────────

interface Props {
  route: TransportRouteDetail;
}

export function RouteDetailView({ route: initialRoute }: Props) {
  const { toast } = useToast();
  const router = useRouter();
  const [, startTransition] = useTransition();
  const [route, setRoute] = useState<TransportRouteDetail>(initialRoute);
  const [sortedStops, setSortedStops] = useState<RouteStop[]>(
    [...initialRoute.stops].sort((a, b) => a.stop_order - b.stop_order)
  );

  // Dialog state
  const [isStopDialogOpen, setIsStopDialogOpen] = useState(false);
  const [editingStop, setEditingStop] = useState<RouteStop | null>(null);
  const [deleteStopId, setDeleteStopId] = useState<string | null>(null);
  const [isRouteDialogOpen, setIsRouteDialogOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isReordering, setIsReordering] = useState(false);

  // Vehicles and drivers for route edit
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [drivers, setDrivers] = useState<Driver[]>([]);

  // Keep sorted stops in sync with route
  useEffect(() => {
    setSortedStops([...route.stops].sort((a, b) => a.stop_order - b.stop_order));
  }, [route.stops]);

  // Reload route data from server
  const reloadRoute = useCallback(() => {
    startTransition(async () => {
      const result = await getRoute(route.id);
      if (result.success && result.data) {
        setRoute(result.data);
      }
    });
  }, [route.id]);

  // Load vehicles and drivers when route edit dialog opens
  const loadVehiclesAndDrivers = useCallback(async () => {
    const [vehiclesRes, driversRes] = await Promise.all([
      getVehicles({ status: "active", pageSize: 100 }),
      getDrivers({ status: "active", pageSize: 100 }),
    ]);
    if (vehiclesRes.success && vehiclesRes.data) {
      setVehicles(Array.isArray(vehiclesRes.data) ? vehiclesRes.data : (vehiclesRes.data.items ?? []));
    }
    if (driversRes.success && driversRes.data) {
      setDrivers(Array.isArray(driversRes.data) ? driversRes.data : (driversRes.data.items ?? []));
    }
  }, []);

  // ─── Stop Form ─────────────────────────────────────────────────────────────

  const stopForm = useForm<StopFormData>({
    resolver: zodResolver(stopSchema) as Resolver<StopFormData>,
    defaultValues: {
      stop_name: "",
      stop_order: sortedStops.length + 1,
      pickup_time: "",
      dropoff_time: "",
      latitude: "",
      longitude: "",
      landmark: "",
    },
  });

  const handleOpenStopDialog = (stop?: RouteStop) => {
    if (stop) {
      setEditingStop(stop);
      stopForm.reset({
        stop_name: stop.stop_name,
        stop_order: stop.stop_order,
        pickup_time: stop.pickup_time || "",
        dropoff_time: stop.dropoff_time || "",
        latitude: stop.latitude ?? "",
        longitude: stop.longitude ?? "",
        landmark: stop.landmark || "",
      });
    } else {
      setEditingStop(null);
      stopForm.reset({
        stop_name: "",
        stop_order: sortedStops.length + 1,
        pickup_time: "",
        dropoff_time: "",
        latitude: "",
        longitude: "",
        landmark: "",
      });
    }
    setIsStopDialogOpen(true);
  };

  const onSubmitStop = async (data: StopFormData) => {
    setIsSubmitting(true);
    try {
      const payload = {
        stop_name: data.stop_name.trim(),
        stop_order: data.stop_order,
        pickup_time: data.pickup_time?.trim() || undefined,
        dropoff_time: data.dropoff_time?.trim() || undefined,
        latitude: typeof data.latitude === "number" ? data.latitude : undefined,
        longitude: typeof data.longitude === "number" ? data.longitude : undefined,
        landmark: data.landmark?.trim() || undefined,
      };

      if (editingStop) {
        const result = await updateStop(route.id, editingStop.id, payload);
        if (result.success) {
          toast({ title: "Stop updated" });
          setIsStopDialogOpen(false);
          reloadRoute();
        } else {
          toast({ title: "Error", description: result.error, variant: "destructive" });
        }
      } else {
        const result = await addStop(route.id, payload);
        if (result.success) {
          toast({ title: "Stop added" });
          setIsStopDialogOpen(false);
          reloadRoute();
        } else {
          toast({ title: "Error", description: result.error, variant: "destructive" });
        }
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteStop = async () => {
    if (!deleteStopId) return;
    setIsSubmitting(true);
    try {
      const result = await deleteStop(route.id, deleteStopId);
      if (result.success) {
        toast({ title: "Stop deleted" });
        reloadRoute();
      } else {
        toast({ title: "Error", description: result.error, variant: "destructive" });
      }
    } finally {
      setIsSubmitting(false);
      setDeleteStopId(null);
    }
  };

  // ─── Reorder ───────────────────────────────────────────────────────────────

  const handleMoveStop = async (stopId: string, direction: "up" | "down") => {
    const currentIndex = sortedStops.findIndex((s) => s.id === stopId);
    if (currentIndex < 0) return;

    const swapIndex = direction === "up" ? currentIndex - 1 : currentIndex + 1;
    if (swapIndex < 0 || swapIndex >= sortedStops.length) return;

    // Optimistic UI update
    const newStops = [...sortedStops];
    [newStops[currentIndex], newStops[swapIndex]] = [newStops[swapIndex], newStops[currentIndex]];
    setSortedStops(newStops);

    setIsReordering(true);
    try {
      const orderedIds = newStops.map((s) => s.id);
      const result = await reorderStops(route.id, orderedIds);
      if (result.success) {
        reloadRoute();
      } else {
        // Revert on failure
        setSortedStops([...route.stops].sort((a, b) => a.stop_order - b.stop_order));
        toast({ title: "Error", description: result.error, variant: "destructive" });
      }
    } finally {
      setIsReordering(false);
    }
  };

  // ─── Route Edit Form ──────────────────────────────────────────────────────

  const routeEditForm = useForm<RouteEditFormData>({
    resolver: zodResolver(routeEditSchema) as Resolver<RouteEditFormData>,
    defaultValues: {
      name: route.name,
      route_code: route.route_code,
      description: route.description || "",
      route_type: route.route_type,
      distance_km: route.distance_km ?? "",
      estimated_duration_minutes: route.estimated_duration_minutes ?? "",
      vehicle_id: route.vehicle_id || "",
      driver_id: route.driver_id || "",
      transport_fee_per_term: route.transport_fee_per_term ?? "",
    },
  });

  const handleOpenRouteDialog = () => {
    routeEditForm.reset({
      name: route.name,
      route_code: route.route_code,
      description: route.description || "",
      route_type: route.route_type,
      distance_km: route.distance_km ?? "",
      estimated_duration_minutes: route.estimated_duration_minutes ?? "",
      vehicle_id: route.vehicle_id || "",
      driver_id: route.driver_id || "",
      transport_fee_per_term: route.transport_fee_per_term ?? "",
    });
    loadVehiclesAndDrivers();
    setIsRouteDialogOpen(true);
  };

  const onSubmitRoute = async (data: RouteEditFormData) => {
    setIsSubmitting(true);
    try {
      const payload = {
        name: data.name.trim(),
        route_code: data.route_code.trim(),
        description: data.description?.trim() || undefined,
        route_type: data.route_type,
        distance_km: typeof data.distance_km === "number" ? data.distance_km : undefined,
        estimated_duration_minutes:
          typeof data.estimated_duration_minutes === "number" ? data.estimated_duration_minutes : undefined,
        vehicle_id: data.vehicle_id && data.vehicle_id !== "none" ? data.vehicle_id : undefined,
        driver_id: data.driver_id && data.driver_id !== "none" ? data.driver_id : undefined,
        transport_fee_per_term:
          typeof data.transport_fee_per_term === "number" ? data.transport_fee_per_term : undefined,
      };

      const result = await updateRoute(route.id, payload);
      if (result.success) {
        toast({ title: "Route updated" });
        setIsRouteDialogOpen(false);
        reloadRoute();
        router.refresh();
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
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/transport/routes">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold tracking-tight">{route.name}</h1>
          <p className="text-muted-foreground">Route Code: {route.route_code}</p>
        </div>
        <Button variant="outline" onClick={handleOpenRouteDialog}>
          <Pencil className="mr-2 h-4 w-4" />
          Edit Route
        </Button>
        <Badge variant={route.is_active ? "default" : "secondary"}>
          {route.is_active ? "Active" : "Inactive"}
        </Badge>
      </div>

      {/* Route Info Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Route Type</CardTitle>
            <Route className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {getRouteTypeBadge(route.route_type)}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Distance</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {route.distance_km != null ? `${route.distance_km} km` : "--"}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Duration</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {route.estimated_duration_minutes != null
                ? `${route.estimated_duration_minutes} min`
                : "--"}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Students</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{route.student_count}</div>
            <p className="text-xs text-muted-foreground">assigned to this route</p>
          </CardContent>
        </Card>
      </div>

      {/* Assigned Vehicle & Driver */}
      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-base">Assigned Vehicle</CardTitle>
            <Bus className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {route.vehicle_registration ? (
              <p className="text-sm font-medium">{route.vehicle_registration}</p>
            ) : (
              <p className="text-sm text-muted-foreground">No vehicle assigned</p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-base">Assigned Driver</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {route.driver_name ? (
              <p className="text-sm font-medium">{route.driver_name}</p>
            ) : (
              <p className="text-sm text-muted-foreground">No driver assigned</p>
            )}
          </CardContent>
        </Card>
      </div>

      {route.description && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Description</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">{route.description}</p>
          </CardContent>
        </Card>
      )}

      {route.transport_fee_per_term != null && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Transport Fee</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              GHS {route.transport_fee_per_term.toLocaleString()}
            </div>
            <p className="text-xs text-muted-foreground">per term</p>
          </CardContent>
        </Card>
      )}

      {/* Route Stops */}
      <Card>
        <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <CardTitle>Route Stops</CardTitle>
            <CardDescription>
              {sortedStops.length} stop{sortedStops.length !== 1 ? "s" : ""} on this route
            </CardDescription>
          </div>
          <Button onClick={() => handleOpenStopDialog()} size="sm">
            <Plus className="mr-2 h-4 w-4" />
            Add Stop
          </Button>
        </CardHeader>
        <CardContent>
          {sortedStops.length > 0 ? (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[80px]">Order</TableHead>
                    <TableHead>Stop Name</TableHead>
                    <TableHead>Landmark</TableHead>
                    <TableHead>Pickup Time</TableHead>
                    <TableHead>Drop-off Time</TableHead>
                    <TableHead className="w-[100px]">Reorder</TableHead>
                    <TableHead className="w-[50px] text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sortedStops.map((stop, index) => (
                    <TableRow key={stop.id}>
                      <TableCell>
                        <Badge variant="outline">{index + 1}</Badge>
                      </TableCell>
                      <TableCell className="font-medium">{stop.stop_name}</TableCell>
                      <TableCell>{stop.landmark || "--"}</TableCell>
                      <TableCell>{stop.pickup_time || "--"}</TableCell>
                      <TableCell>{stop.dropoff_time || "--"}</TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7"
                            disabled={index === 0 || isReordering}
                            onClick={() => handleMoveStop(stop.id, "up")}
                            aria-label="Move stop up"
                          >
                            <ArrowUp className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7"
                            disabled={index === sortedStops.length - 1 || isReordering}
                            onClick={() => handleMoveStop(stop.id, "down")}
                            aria-label="Move stop down"
                          >
                            <ArrowDown className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-8 w-8">
                              <MoreHorizontal className="h-4 w-4" />
                              <span className="sr-only">Open menu</span>
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => handleOpenStopDialog(stop)}>
                              <Pencil className="mr-2 h-4 w-4" />
                              Edit Stop
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() => setDeleteStopId(stop.id)}
                              className="text-destructive focus:text-destructive"
                            >
                              <Trash2 className="mr-2 h-4 w-4" />
                              Delete Stop
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <div className="flex h-[150px] flex-col items-center justify-center gap-2 text-muted-foreground">
              <MapPin className="h-8 w-8" />
              <p className="text-sm">No stops defined for this route</p>
              <p className="text-xs">Click "Add Stop" to define pickup/drop-off points</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ─── Add/Edit Stop Dialog ──────────────────────────────────────────── */}
      <Dialog open={isStopDialogOpen} onOpenChange={setIsStopDialogOpen}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>{editingStop ? "Edit Stop" : "Add Stop"}</DialogTitle>
            <DialogDescription>
              {editingStop
                ? "Update the stop details."
                : "Add a new stop to this route."}
            </DialogDescription>
          </DialogHeader>
          <Form {...stopForm}>
            <form onSubmit={stopForm.handleSubmit(onSubmitStop)} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
                <div className="col-span-2">
                  <FormField
                    control={stopForm.control}
                    name="stop_name"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Stop Name *</FormLabel>
                        <FormControl>
                          <Input placeholder="e.g., Tema Station" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
                <FormField
                  control={stopForm.control}
                  name="stop_order"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Order *</FormLabel>
                      <FormControl>
                        <Input type="number" min={1} {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <FormField
                control={stopForm.control}
                name="landmark"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Landmark</FormLabel>
                    <FormControl>
                      <Input placeholder="e.g., Near the Total filling station" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={stopForm.control}
                  name="pickup_time"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Pickup Time</FormLabel>
                      <FormControl>
                        <Input type="time" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={stopForm.control}
                  name="dropoff_time"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Drop-off Time</FormLabel>
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
                  control={stopForm.control}
                  name="latitude"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Latitude</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          step="any"
                          placeholder="e.g., 5.6037"
                          {...field}
                          value={field.value ?? ""}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={stopForm.control}
                  name="longitude"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Longitude</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          step="any"
                          placeholder="e.g., -0.1870"
                          {...field}
                          value={field.value ?? ""}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsStopDialogOpen(false)}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  {editingStop ? "Save Changes" : "Add Stop"}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* ─── Delete Stop Confirmation ──────────────────────────────────────── */}
      <AlertDialog open={!!deleteStopId} onOpenChange={() => setDeleteStopId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Stop?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently remove this stop from the route. Students assigned to this stop will need to be reassigned.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isSubmitting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteStop}
              disabled={isSubmitting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* ─── Edit Route Dialog ─────────────────────────────────────────────── */}
      <Dialog open={isRouteDialogOpen} onOpenChange={setIsRouteDialogOpen}>
        <DialogContent className="sm:max-w-[550px]">
          <DialogHeader>
            <DialogTitle>Edit Route</DialogTitle>
            <DialogDescription>Update route details and assignments.</DialogDescription>
          </DialogHeader>
          <Form {...routeEditForm}>
            <form onSubmit={routeEditForm.handleSubmit(onSubmitRoute)} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={routeEditForm.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Route Name *</FormLabel>
                      <FormControl>
                        <Input placeholder="e.g., Tema Route" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={routeEditForm.control}
                  name="route_code"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Route Code *</FormLabel>
                      <FormControl>
                        <Input placeholder="e.g., RT-001" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <FormField
                control={routeEditForm.control}
                name="description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Description</FormLabel>
                    <FormControl>
                      <Textarea placeholder="Route description..." rows={2} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
                <FormField
                  control={routeEditForm.control}
                  name="route_type"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Route Type *</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {ROUTE_TYPES.map((t) => (
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
                <FormField
                  control={routeEditForm.control}
                  name="distance_km"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Distance (km)</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          step="0.1"
                          placeholder="km"
                          {...field}
                          value={field.value ?? ""}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={routeEditForm.control}
                  name="estimated_duration_minutes"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Duration (min)</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          placeholder="min"
                          {...field}
                          value={field.value ?? ""}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={routeEditForm.control}
                  name="vehicle_id"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Assigned Vehicle</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder="Select vehicle" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value="none">None</SelectItem>
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
                  control={routeEditForm.control}
                  name="driver_id"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Assigned Driver</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder="Select driver" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value="none">None</SelectItem>
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
              <FormField
                control={routeEditForm.control}
                name="transport_fee_per_term"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Transport Fee per Term (GHS)</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        step="0.01"
                        placeholder="0.00"
                        {...field}
                        value={field.value ?? ""}
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
                  onClick={() => setIsRouteDialogOpen(false)}
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
