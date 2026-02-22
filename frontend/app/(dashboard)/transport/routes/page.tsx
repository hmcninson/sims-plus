"use client";

import { useEffect, useState, useTransition } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Plus, Pencil, Trash2, Loader2, Route, Search, Eye } from "lucide-react";
import { getRoutes, createRoute, updateRoute, deleteRoute, getVehicles, getDrivers } from "@/actions/transport.action";
import type { TransportRoute, RouteType, Vehicle, Driver } from "@/types";
import { useToast } from "@/hooks/use-toast";

const ROUTE_TYPES: { value: RouteType; label: string }[] = [
  { value: "morning_pickup", label: "Morning Pickup" },
  { value: "afternoon_dropoff", label: "Afternoon Drop-off" },
  { value: "both", label: "Both" },
];

function getRouteTypeBadge(type: string) {
  switch (type) {
    case "morning_pickup":
      return <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200">Morning</Badge>;
    case "afternoon_dropoff":
      return <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">Afternoon</Badge>;
    case "both":
      return <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">Both</Badge>;
    default:
      return <Badge variant="outline" className="capitalize">{type}</Badge>;
  }
}

const routeSchema = z.object({
  name: z.string().min(1, "Route name is required").max(100),
  route_code: z.string().min(1, "Route code is required").max(20),
  description: z.string().optional(),
  distance_km: z.coerce.number().positive("Distance must be positive").optional().or(z.literal("")),
  estimated_duration_minutes: z.coerce.number().int().positive("Duration must be positive").optional().or(z.literal("")),
  vehicle_id: z.string().optional(),
  driver_id: z.string().optional(),
  route_type: z.enum(["morning_pickup", "afternoon_dropoff", "both"]),
  transport_fee_per_term: z.coerce.number().nonnegative("Fee cannot be negative").optional().or(z.literal("")),
});

type RouteFormData = z.infer<typeof routeSchema>;

export default function RoutesPage() {
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();
  const [routes, setRoutes] = useState<TransportRoute[]>([]);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [total, setTotal] = useState(0);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterType, setFilterType] = useState("all");

  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingRoute, setEditingRoute] = useState<TransportRoute | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const form = useForm<RouteFormData>({
    resolver: zodResolver(routeSchema),
    defaultValues: {
      name: "",
      route_code: "",
      description: "",
      distance_km: "",
      estimated_duration_minutes: "",
      vehicle_id: "",
      driver_id: "",
      route_type: "both",
      transport_fee_per_term: "",
    },
  });

  // Load vehicles and drivers for the form dropdowns
  useEffect(() => {
    startTransition(async () => {
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
    });
  }, []);

  const loadRoutes = () => {
    startTransition(async () => {
      const result = await getRoutes({
        search: searchQuery || undefined,
        routeType: filterType !== "all" ? filterType : undefined,
      });
      if (result.success && result.data) {
        const data = result.data;
        const items = Array.isArray(data) ? data : (data.items ?? []);
        const count = Array.isArray(data) ? data.length : (data.total ?? 0);
        setRoutes(items);
        setTotal(count);
      }
    });
  };

  useEffect(() => {
    const timer = setTimeout(loadRoutes, 300);
    return () => clearTimeout(timer);
  }, [searchQuery, filterType]);

  const handleOpenDialog = (route?: TransportRoute) => {
    if (route) {
      setEditingRoute(route);
      form.reset({
        name: route.name,
        route_code: route.route_code,
        description: route.description || "",
        distance_km: route.distance_km ?? "",
        estimated_duration_minutes: route.estimated_duration_minutes ?? "",
        vehicle_id: route.vehicle_id || "",
        driver_id: route.driver_id || "",
        route_type: route.route_type,
        transport_fee_per_term: route.transport_fee_per_term ?? "",
      });
    } else {
      setEditingRoute(null);
      form.reset({
        name: "",
        route_code: "",
        description: "",
        distance_km: "",
        estimated_duration_minutes: "",
        vehicle_id: "",
        driver_id: "",
        route_type: "both",
        transport_fee_per_term: "",
      });
    }
    setIsDialogOpen(true);
  };

  const onSubmit = async (data: RouteFormData) => {
    setIsSubmitting(true);
    try {
      const payload = {
        name: data.name.trim(),
        route_code: data.route_code.trim(),
        description: data.description?.trim() || undefined,
        distance_km: typeof data.distance_km === "number" ? data.distance_km : undefined,
        estimated_duration_minutes:
          typeof data.estimated_duration_minutes === "number" ? data.estimated_duration_minutes : undefined,
        vehicle_id: data.vehicle_id && data.vehicle_id !== "none" ? data.vehicle_id : undefined,
        driver_id: data.driver_id && data.driver_id !== "none" ? data.driver_id : undefined,
        route_type: data.route_type,
        transport_fee_per_term:
          typeof data.transport_fee_per_term === "number" ? data.transport_fee_per_term : undefined,
      };

      if (editingRoute) {
        const result = await updateRoute(editingRoute.id, payload);
        if (result.success) {
          toast({ title: "Route updated" });
          setIsDialogOpen(false);
          loadRoutes();
        } else {
          toast({ title: "Error", description: result.error, variant: "destructive" });
        }
      } else {
        const result = await createRoute(payload);
        if (result.success) {
          toast({ title: "Route created" });
          setIsDialogOpen(false);
          loadRoutes();
        } else {
          toast({ title: "Error", description: result.error, variant: "destructive" });
        }
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    setIsSubmitting(true);
    try {
      const result = await deleteRoute(deleteId);
      if (result.success) {
        toast({ title: "Route deleted" });
        loadRoutes();
      } else {
        toast({ title: "Error", description: result.error, variant: "destructive" });
      }
    } finally {
      setIsSubmitting(false);
      setDeleteId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Routes</h1>
          <p className="text-muted-foreground">Manage transport routes and stops</p>
        </div>
        <Button onClick={() => handleOpenDialog()}>
          <Plus className="mr-2 h-4 w-4" />
          Add Route
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Filters</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-4 sm:flex-row">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search by route name or code..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select value={filterType} onValueChange={setFilterType}>
              <SelectTrigger className="w-full sm:w-[180px]">
                <SelectValue placeholder="Route Type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Types</SelectItem>
                {ROUTE_TYPES.map((t) => (
                  <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Routes</CardTitle>
          <CardDescription>{total} route{total !== 1 ? "s" : ""}</CardDescription>
        </CardHeader>
        <CardContent>
          {isPending ? (
            <div className="flex h-[200px] items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : routes.length > 0 ? (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Code</TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead className="hidden sm:table-cell">Type</TableHead>
                    <TableHead className="hidden md:table-cell">Distance</TableHead>
                    <TableHead className="hidden md:table-cell">Duration</TableHead>
                    <TableHead className="hidden md:table-cell">Fee/Term</TableHead>
                    <TableHead className="hidden sm:table-cell">Status</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {routes.map((route) => (
                    <TableRow key={route.id}>
                      <TableCell className="font-medium">{route.route_code}</TableCell>
                      <TableCell>{route.name}</TableCell>
                      <TableCell className="hidden sm:table-cell">{getRouteTypeBadge(route.route_type)}</TableCell>
                      <TableCell className="hidden md:table-cell">
                        {route.distance_km != null ? `${route.distance_km} km` : "--"}
                      </TableCell>
                      <TableCell className="hidden md:table-cell">
                        {route.estimated_duration_minutes != null
                          ? `${route.estimated_duration_minutes} min`
                          : "--"}
                      </TableCell>
                      <TableCell className="hidden md:table-cell">
                        {route.transport_fee_per_term != null
                          ? `GHS ${route.transport_fee_per_term.toLocaleString()}`
                          : "--"}
                      </TableCell>
                      <TableCell className="hidden sm:table-cell">
                        <Badge variant={route.is_active ? "default" : "secondary"}>
                          {route.is_active ? "Active" : "Inactive"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          <Button variant="ghost" size="icon" asChild>
                            <Link href={`/transport/routes/${route.id}`}>
                              <Eye className="h-4 w-4" />
                            </Link>
                          </Button>
                          <Button variant="ghost" size="icon" onClick={() => handleOpenDialog(route)}>
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="icon" onClick={() => setDeleteId(route.id)}>
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <div className="flex h-[200px] flex-col items-center justify-center gap-2 text-muted-foreground">
              <Route className="h-12 w-12" />
              <p>No routes found</p>
              <p className="text-sm text-center max-w-md">
                Create transport routes and add stops to organize student pickup and drop-off.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create/Edit Route Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="sm:max-w-[550px]">
          <DialogHeader>
            <DialogTitle>{editingRoute ? "Edit Route" : "Create Route"}</DialogTitle>
            <DialogDescription>
              {editingRoute ? "Update route details." : "Create a new transport route."}
            </DialogDescription>
          </DialogHeader>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={form.control}
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
                  control={form.control}
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
                control={form.control}
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
                  control={form.control}
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
                            <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="distance_km"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Distance (km)</FormLabel>
                      <FormControl>
                        <Input type="number" step="0.1" placeholder="km" {...field} value={field.value ?? ""} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="estimated_duration_minutes"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Duration (min)</FormLabel>
                      <FormControl>
                        <Input type="number" placeholder="min" {...field} value={field.value ?? ""} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={form.control}
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
                  control={form.control}
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
                control={form.control}
                name="transport_fee_per_term"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Transport Fee per Term (GHS)</FormLabel>
                    <FormControl>
                      <Input type="number" step="0.01" placeholder="0.00" {...field} value={field.value ?? ""} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setIsDialogOpen(false)} disabled={isSubmitting}>
                  Cancel
                </Button>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  {editingRoute ? "Save Changes" : "Create Route"}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog open={!!deleteId} onOpenChange={() => setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Route?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete this route and its stops. Student assignments on this route will be affected.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isSubmitting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={isSubmitting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
