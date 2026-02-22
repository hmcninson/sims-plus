"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  ArrowLeft,
  Pencil,
  Loader2,
  User,
  Phone,
  CreditCard,
  Calendar,
  MapPin,
  Bus,
  AlertTriangle,
} from "lucide-react";
import { updateDriver } from "@/actions/transport.action";
import { useToast } from "@/hooks/use-toast";
import type { Driver, DriverStatus, TransportRoute, TripLogDetail } from "@/types";

interface Props {
  driver: Driver;
  assignedRoutes: TransportRoute[];
  recentTrips: TripLogDetail[];
}

const DRIVER_STATUSES: { value: DriverStatus; label: string }[] = [
  { value: "active", label: "Active" },
  { value: "on_leave", label: "On Leave" },
  { value: "terminated", label: "Terminated" },
];

function getStatusBadge(status: string) {
  switch (status) {
    case "active":
      return <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">Active</Badge>;
    case "on_leave":
      return <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200">On Leave</Badge>;
    case "terminated":
      return <Badge variant="destructive">Terminated</Badge>;
    default:
      return <Badge variant="secondary">{status}</Badge>;
  }
}

function getTripStatusBadge(status: string) {
  switch (status) {
    case "completed":
      return <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">Completed</Badge>;
    case "in_progress":
      return <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">In Progress</Badge>;
    case "scheduled":
      return <Badge variant="outline">Scheduled</Badge>;
    case "cancelled":
      return <Badge variant="destructive">Cancelled</Badge>;
    default:
      return <Badge variant="secondary">{status}</Badge>;
  }
}

function getTripTypeBadge(type: string) {
  switch (type) {
    case "morning_pickup":
      return <Badge variant="outline">Morning Pickup</Badge>;
    case "afternoon_dropoff":
      return <Badge variant="outline">Afternoon Dropoff</Badge>;
    case "field_trip":
      return <Badge className="bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200">Field Trip</Badge>;
    default:
      return <Badge variant="outline" className="capitalize">{type.replace("_", " ")}</Badge>;
  }
}

function getRouteTypeBadge(type: string) {
  switch (type) {
    case "morning_pickup":
      return <Badge variant="outline">Morning</Badge>;
    case "afternoon_dropoff":
      return <Badge variant="outline">Afternoon</Badge>;
    case "both":
      return <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">Both</Badge>;
    default:
      return <Badge variant="outline" className="capitalize">{type.replace("_", " ")}</Badge>;
  }
}

function formatDate(dateStr: string | undefined): string {
  if (!dateStr) return "--";
  return new Date(dateStr + "T00:00:00").toLocaleDateString("en-GB");
}

function isLicenseExpiringSoon(expiryDate: string): boolean {
  const expiry = new Date(expiryDate + "T00:00:00");
  const thirtyDaysFromNow = new Date();
  thirtyDaysFromNow.setDate(thirtyDaysFromNow.getDate() + 30);
  return expiry <= thirtyDaysFromNow;
}

function isLicenseExpired(expiryDate: string): boolean {
  const expiry = new Date(expiryDate + "T00:00:00");
  return expiry < new Date();
}

// ========================
// Edit Driver Schema
// ========================

const editDriverSchema = z.object({
  first_name: z.string().min(1, "First name is required"),
  last_name: z.string().min(1, "Last name is required"),
  phone: z.string().min(10, "Phone number is required"),
  license_number: z.string().min(1, "License number is required"),
  license_expiry: z.string().min(1, "License expiry date is required"),
  license_class: z.string().min(1, "License class is required"),
  status: z.enum(["active", "on_leave", "terminated"]).optional(),
  emergency_contact_name: z.string().optional(),
  emergency_contact_phone: z.string().optional(),
});

type EditDriverFormData = z.infer<typeof editDriverSchema>;

export function DriverDetailView({ driver, assignedRoutes, recentTrips }: Props) {
  const router = useRouter();
  const { toast } = useToast();
  const [, startTransition] = useTransition();

  // Edit Driver Dialog
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isEditSubmitting, setIsEditSubmitting] = useState(false);

  const editForm = useForm<EditDriverFormData>({
    resolver: zodResolver(editDriverSchema),
    defaultValues: {
      first_name: driver.first_name,
      last_name: driver.last_name,
      phone: driver.phone,
      license_number: driver.license_number,
      license_expiry: driver.license_expiry,
      license_class: driver.license_class,
      status: driver.status,
      emergency_contact_name: driver.emergency_contact_name || "",
      emergency_contact_phone: driver.emergency_contact_phone || "",
    },
  });

  const handleEditSubmit = async (data: EditDriverFormData) => {
    setIsEditSubmitting(true);
    try {
      const payload = {
        first_name: data.first_name.trim(),
        last_name: data.last_name.trim(),
        phone: data.phone.trim(),
        license_number: data.license_number.trim(),
        license_expiry: data.license_expiry,
        license_class: data.license_class.trim(),
        status: data.status,
        emergency_contact_name: data.emergency_contact_name?.trim() || undefined,
        emergency_contact_phone: data.emergency_contact_phone?.trim() || undefined,
      };

      const result = await updateDriver(driver.id, payload);
      if (result.success) {
        toast({ title: "Driver updated" });
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

  const licenseExpired = isLicenseExpired(driver.license_expiry);
  const licenseExpiringSoon = !licenseExpired && isLicenseExpiringSoon(driver.license_expiry);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/transport/drivers">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold tracking-tight">
            {driver.first_name} {driver.last_name}
          </h1>
          <p className="text-muted-foreground">Driver Profile</p>
        </div>
        <div className="flex items-center gap-2">
          {getStatusBadge(driver.status)}
          <Button variant="outline" size="sm" onClick={() => setIsEditOpen(true)}>
            <Pencil className="mr-2 h-4 w-4" />
            Edit Driver
          </Button>
        </div>
      </div>

      {/* License Warning */}
      {(licenseExpired || licenseExpiringSoon) && (
        <div
          className={`flex items-center gap-3 rounded-lg border p-4 ${
            licenseExpired
              ? "border-destructive/50 bg-destructive/10 text-destructive"
              : "border-amber-500/50 bg-amber-50 text-amber-800 dark:bg-amber-950 dark:text-amber-200"
          }`}
        >
          <AlertTriangle className="h-5 w-5 shrink-0" />
          <p className="text-sm font-medium">
            {licenseExpired
              ? `License expired on ${formatDate(driver.license_expiry)}. This driver should not be assigned to active routes.`
              : `License expiring on ${formatDate(driver.license_expiry)}. Please arrange for renewal.`}
          </p>
        </div>
      )}

      {/* Driver Profile Card */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Contact</CardTitle>
            <User className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex items-center gap-2 text-sm">
              <Phone className="h-4 w-4 text-muted-foreground" />
              <span>{driver.phone}</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">License Information</CardTitle>
            <CreditCard className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Number</span>
              <span className="font-medium">{driver.license_number}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Class</span>
              <span className="font-medium">{driver.license_class}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Expiry</span>
              <span
                className={`font-medium ${
                  licenseExpired
                    ? "text-destructive"
                    : licenseExpiringSoon
                      ? "text-amber-600 dark:text-amber-400"
                      : ""
                }`}
              >
                {formatDate(driver.license_expiry)}
              </span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Emergency Contact</CardTitle>
            <Phone className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {driver.emergency_contact_name ? (
              <>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Name</span>
                  <span className="font-medium">{driver.emergency_contact_name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Phone</span>
                  <span className="font-medium">{driver.emergency_contact_phone || "--"}</span>
                </div>
              </>
            ) : (
              <p className="text-muted-foreground">No emergency contact on file</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Assigned Routes */}
      <Card>
        <CardHeader>
          <CardTitle>Assigned Routes</CardTitle>
          <CardDescription>
            {assignedRoutes.length} route{assignedRoutes.length !== 1 ? "s" : ""} assigned
          </CardDescription>
        </CardHeader>
        <CardContent>
          {assignedRoutes.length > 0 ? (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Route Code</TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Distance</TableHead>
                    <TableHead>Duration</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {assignedRoutes.map((route) => (
                    <TableRow key={route.id}>
                      <TableCell className="font-medium">
                        <Link
                          href={`/transport/routes/${route.id}`}
                          className="text-primary underline-offset-4 hover:underline"
                        >
                          {route.route_code}
                        </Link>
                      </TableCell>
                      <TableCell>{route.name}</TableCell>
                      <TableCell>{getRouteTypeBadge(route.route_type)}</TableCell>
                      <TableCell>
                        {route.distance_km != null ? `${route.distance_km} km` : "--"}
                      </TableCell>
                      <TableCell>
                        {route.estimated_duration_minutes != null
                          ? `${route.estimated_duration_minutes} min`
                          : "--"}
                      </TableCell>
                      <TableCell>
                        {route.is_active ? (
                          <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">Active</Badge>
                        ) : (
                          <Badge variant="secondary">Inactive</Badge>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <div className="flex h-[150px] flex-col items-center justify-center gap-2 text-muted-foreground">
              <MapPin className="h-8 w-8" />
              <p className="text-sm">No routes assigned to this driver</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Recent Trips */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Trips</CardTitle>
          <CardDescription>
            {recentTrips.length} trip{recentTrips.length !== 1 ? "s" : ""}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {recentTrips.length > 0 ? (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Route</TableHead>
                    <TableHead>Vehicle</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Students</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {recentTrips.map((trip) => (
                    <TableRow key={trip.id}>
                      <TableCell className="whitespace-nowrap">
                        {formatDate(trip.trip_date)}
                      </TableCell>
                      <TableCell>{trip.route_name || "--"}</TableCell>
                      <TableCell>{trip.vehicle_registration || "--"}</TableCell>
                      <TableCell>{getTripTypeBadge(trip.trip_type)}</TableCell>
                      <TableCell>{trip.student_count}</TableCell>
                      <TableCell>{getTripStatusBadge(trip.status)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <div className="flex h-[150px] flex-col items-center justify-center gap-2 text-muted-foreground">
              <Bus className="h-8 w-8" />
              <p className="text-sm">No trip records found for this driver</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Edit Driver Dialog */}
      <Dialog open={isEditOpen} onOpenChange={setIsEditOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-[550px]">
          <DialogHeader>
            <DialogTitle>Edit Driver</DialogTitle>
            <DialogDescription>
              Update details for {driver.first_name} {driver.last_name}.
            </DialogDescription>
          </DialogHeader>
          <Form {...editForm}>
            <form onSubmit={editForm.handleSubmit(handleEditSubmit)} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={editForm.control}
                  name="first_name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>First Name *</FormLabel>
                      <FormControl>
                        <Input placeholder="First name" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={editForm.control}
                  name="last_name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Last Name *</FormLabel>
                      <FormControl>
                        <Input placeholder="Last name" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={editForm.control}
                  name="phone"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Phone *</FormLabel>
                      <FormControl>
                        <Input placeholder="+233 XX XXX XXXX" {...field} />
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
                          {DRIVER_STATUSES.map((s) => (
                            <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
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
                  name="license_number"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>License No. *</FormLabel>
                      <FormControl>
                        <Input placeholder="License number" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={editForm.control}
                  name="license_class"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>License Class *</FormLabel>
                      <FormControl>
                        <Input placeholder="e.g., B, C, D" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={editForm.control}
                  name="license_expiry"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>License Expiry *</FormLabel>
                      <FormControl>
                        <Input type="date" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={editForm.control}
                  name="emergency_contact_name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Emergency Contact</FormLabel>
                      <FormControl>
                        <Input placeholder="Contact name" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={editForm.control}
                  name="emergency_contact_phone"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Emergency Phone</FormLabel>
                      <FormControl>
                        <Input placeholder="+233 XX XXX XXXX" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
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
    </div>
  );
}
