"use client";

import { useCallback, useEffect, useState, useTransition } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Search,
  Loader2,
  MapPin,
  Plus,
  MoreHorizontal,
  Pencil,
  XCircle,
} from "lucide-react";
import {
  getTransportAssignments,
  getRoutes,
  getRoute,
  assignStudentTransport,
  updateTransportAssignment,
  cancelTransportAssignment,
} from "@/actions/transport.action";
import { getStudents } from "@/actions/students.action";
import { getAcademicYears } from "@/actions/academic.action";
import type {
  StudentTransportDetail,
  TransportRoute,
  RouteStop,
  StudentListItem,
  AcademicYear,
} from "@/types";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";

// =========================
// Schemas
// =========================

const assignSchema = z.object({
  student_id: z.string().min(1, "Student is required"),
  route_id: z.string().min(1, "Route is required"),
  stop_id: z.string().min(1, "Stop is required"),
  academic_year_id: z.string().min(1, "Academic year is required"),
  pickup_guardian_phone: z.string().optional(),
  special_instructions: z.string().optional(),
});

type AssignFormData = z.infer<typeof assignSchema>;

const editSchema = z.object({
  route_id: z.string().min(1, "Route is required"),
  stop_id: z.string().min(1, "Stop is required"),
  status: z.enum(["active", "suspended", "cancelled"]),
  pickup_guardian_phone: z.string().optional(),
  special_instructions: z.string().optional(),
});

type EditFormData = z.infer<typeof editSchema>;

// =========================
// Constants & Helpers
// =========================

const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: "active", label: "Active" },
  { value: "suspended", label: "Suspended" },
  { value: "cancelled", label: "Cancelled" },
];

function getStatusBadge(status: string) {
  switch (status) {
    case "active":
      return (
        <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
          Active
        </Badge>
      );
    case "suspended":
      return (
        <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200">
          Suspended
        </Badge>
      );
    case "cancelled":
      return <Badge variant="destructive">Cancelled</Badge>;
    default:
      return <Badge variant="secondary">{status}</Badge>;
  }
}

// =========================
// Page Component
// =========================

export default function TransportAssignmentsPage() {
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();

  // List state
  const [assignments, setAssignments] = useState<StudentTransportDetail[]>([]);
  const [total, setTotal] = useState(0);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterRoute, setFilterRoute] = useState("all");
  const [filterStatus, setFilterStatus] = useState("all");

  // Reference data
  const [routes, setRoutes] = useState<TransportRoute[]>([]);
  const [academicYears, setAcademicYears] = useState<AcademicYear[]>([]);

  // Cascading selects state (shared between assign & edit)
  const [stops, setStops] = useState<RouteStop[]>([]);
  const [stopsLoading, setStopsLoading] = useState(false);

  // Dialog state
  const [isAssignOpen, setIsAssignOpen] = useState(false);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [editingAssignment, setEditingAssignment] =
    useState<StudentTransportDetail | null>(null);
  const [cancelId, setCancelId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Student search
  const [studentSearch, setStudentSearch] = useState("");
  const [students, setStudents] = useState<StudentListItem[]>([]);
  const [studentsLoading, setStudentsLoading] = useState(false);

  // Forms
  const assignForm = useForm<AssignFormData>({
    resolver: zodResolver(assignSchema),
    defaultValues: {
      student_id: "",
      route_id: "",
      stop_id: "",
      academic_year_id: "",
      pickup_guardian_phone: "",
      special_instructions: "",
    },
  });

  const editForm = useForm<EditFormData>({
    resolver: zodResolver(editSchema),
    defaultValues: {
      route_id: "",
      stop_id: "",
      status: "active",
      pickup_guardian_phone: "",
      special_instructions: "",
    },
  });

  // Watch route for cascading
  const assignRouteId = assignForm.watch("route_id");
  const editRouteId = editForm.watch("route_id");

  // =========================
  // Load Reference Data
  // =========================

  useEffect(() => {
    startTransition(async () => {
      const [routesRes, yearsRes] = await Promise.all([
        getRoutes({ isActive: true, pageSize: 100 }),
        getAcademicYears(false),
      ]);

      if (routesRes.success && routesRes.data) {
        const items = Array.isArray(routesRes.data)
          ? routesRes.data
          : (routesRes.data.items ?? []);
        setRoutes(items);
      }

      if (yearsRes.success && yearsRes.data) {
        setAcademicYears(
          Array.isArray(yearsRes.data) ? yearsRes.data : []
        );
      }
    });
  }, []);

  // =========================
  // Load Assignments
  // =========================

  const loadAssignments = useCallback(() => {
    startTransition(async () => {
      const result = await getTransportAssignments({
        search: searchQuery || undefined,
        routeId: filterRoute !== "all" ? filterRoute : undefined,
        status: filterStatus !== "all" ? filterStatus : undefined,
      });
      if (result.success && result.data) {
        const data = result.data;
        const items = Array.isArray(data) ? data : (data.items ?? []);
        const count = Array.isArray(data) ? data.length : (data.total ?? 0);
        setAssignments(items);
        setTotal(count);
      }
    });
  }, [searchQuery, filterRoute, filterStatus]);

  useEffect(() => {
    const timer = setTimeout(loadAssignments, 300);
    return () => clearTimeout(timer);
  }, [loadAssignments]);

  // =========================
  // Student Search (debounced)
  // =========================

  useEffect(() => {
    if (!studentSearch.trim()) {
      setStudents([]);
      return;
    }
    const timer = setTimeout(async () => {
      setStudentsLoading(true);
      try {
        const result = await getStudents({ search: studentSearch, page: 1 });
        if (result.success && result.data) {
          const items = Array.isArray(result.data)
            ? result.data
            : (result.data.items ?? []);
          setStudents(items);
        }
      } finally {
        setStudentsLoading(false);
      }
    }, 400);
    return () => clearTimeout(timer);
  }, [studentSearch]);

  // =========================
  // Cascading: Route -> Stops
  // =========================

  const loadStops = useCallback(async (routeId: string) => {
    if (!routeId) {
      setStops([]);
      return;
    }
    setStopsLoading(true);
    try {
      const result = await getRoute(routeId);
      if (result.success && result.data) {
        const routeStops = result.data.stops ?? [];
        // Sort by stop_order
        setStops([...routeStops].sort((a, b) => a.stop_order - b.stop_order));
      } else {
        setStops([]);
      }
    } finally {
      setStopsLoading(false);
    }
  }, []);

  // Cascade for assign dialog
  useEffect(() => {
    if (isAssignOpen && assignRouteId) {
      assignForm.setValue("stop_id", "");
      loadStops(assignRouteId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [assignRouteId, isAssignOpen]);

  // Cascade for edit dialog
  useEffect(() => {
    if (isEditOpen && editRouteId && editingAssignment) {
      // Only clear stop if user changed the route
      if (editRouteId !== editingAssignment.route_id) {
        editForm.setValue("stop_id", "");
      }
      loadStops(editRouteId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editRouteId, isEditOpen]);

  // =========================
  // Dialog Handlers
  // =========================

  const handleOpenAssign = () => {
    assignForm.reset({
      student_id: "",
      route_id: "",
      stop_id: "",
      academic_year_id:
        academicYears.find((y) => y.is_current || y.status === "active")?.id ??
        "",
      pickup_guardian_phone: "",
      special_instructions: "",
    });
    setStudentSearch("");
    setStudents([]);
    setStops([]);
    setIsAssignOpen(true);
  };

  const handleOpenEdit = (assignment: StudentTransportDetail) => {
    setEditingAssignment(assignment);
    editForm.reset({
      route_id: assignment.route_id,
      stop_id: assignment.stop_id,
      status: assignment.status,
      pickup_guardian_phone: assignment.pickup_guardian_phone ?? "",
      special_instructions: assignment.special_instructions ?? "",
    });
    // Pre-load stops for the current route
    if (assignment.route_id) {
      loadStops(assignment.route_id);
    }
    setIsEditOpen(true);
  };

  // =========================
  // Submit Handlers
  // =========================

  const onAssignSubmit = async (data: AssignFormData) => {
    setIsSubmitting(true);
    try {
      const result = await assignStudentTransport({
        student_id: data.student_id,
        route_id: data.route_id,
        stop_id: data.stop_id,
        academic_year_id: data.academic_year_id,
        pickup_guardian_phone: data.pickup_guardian_phone || undefined,
        special_instructions: data.special_instructions || undefined,
      });
      if (result.success) {
        toast({
          title: "Student assigned",
          description: "Student has been assigned to transport route.",
        });
        setIsAssignOpen(false);
        loadAssignments();
      } else {
        toast({
          title: "Error",
          description: result.error,
          variant: "destructive",
        });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const onEditSubmit = async (data: EditFormData) => {
    if (!editingAssignment) return;
    setIsSubmitting(true);
    try {
      const result = await updateTransportAssignment(editingAssignment.id, {
        route_id: data.route_id,
        stop_id: data.stop_id,
        status: data.status,
        pickup_guardian_phone: data.pickup_guardian_phone || undefined,
        special_instructions: data.special_instructions || undefined,
      });
      if (result.success) {
        toast({
          title: "Assignment updated",
          description: "Transport assignment has been updated.",
        });
        setIsEditOpen(false);
        setEditingAssignment(null);
        loadAssignments();
      } else {
        toast({
          title: "Error",
          description: result.error,
          variant: "destructive",
        });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancel = async () => {
    if (!cancelId) return;
    setIsSubmitting(true);
    try {
      const result = await cancelTransportAssignment(cancelId);
      if (result.success) {
        toast({ title: "Transport assignment cancelled" });
        loadAssignments();
      } else {
        toast({
          title: "Error",
          description: result.error,
          variant: "destructive",
        });
      }
    } finally {
      setIsSubmitting(false);
      setCancelId(null);
    }
  };

  // =========================
  // Render
  // =========================

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Transport Assignments
          </h1>
          <p className="text-muted-foreground">
            Manage student transport route assignments
          </p>
        </div>
        <Button onClick={handleOpenAssign}>
          <Plus className="mr-2 h-4 w-4" />
          Assign Student
        </Button>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Filters</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-4 sm:flex-row">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search by student name..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select value={filterRoute} onValueChange={setFilterRoute}>
              <SelectTrigger className="w-full sm:w-[200px]">
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
            <Select value={filterStatus} onValueChange={setFilterStatus}>
              <SelectTrigger className="w-full sm:w-[160px]">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="suspended">Suspended</SelectItem>
                <SelectItem value="cancelled">Cancelled</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Assignments Table */}
      <Card>
        <CardHeader>
          <CardTitle>Assignments</CardTitle>
          <CardDescription>
            {total} assignment{total !== 1 ? "s" : ""}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isPending ? (
            <div className="flex h-[200px] items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : assignments.length > 0 ? (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Student</TableHead>
                    <TableHead>Route</TableHead>
                    <TableHead className="hidden md:table-cell">Stop</TableHead>
                    <TableHead className="hidden md:table-cell">
                      Pickup Time
                    </TableHead>
                    <TableHead className="hidden lg:table-cell">
                      Drop-off Time
                    </TableHead>
                    <TableHead className="hidden lg:table-cell">
                      Academic Year
                    </TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {assignments.map((a) => (
                    <TableRow key={a.id}>
                      <TableCell className="font-medium">
                        {a.student_name || "--"}
                      </TableCell>
                      <TableCell>{a.route_name || "--"}</TableCell>
                      <TableCell className="hidden md:table-cell">
                        {a.stop_name || "--"}
                      </TableCell>
                      <TableCell className="hidden md:table-cell">
                        {a.pickup_time || "--"}
                      </TableCell>
                      <TableCell className="hidden lg:table-cell">
                        {a.dropoff_time || "--"}
                      </TableCell>
                      <TableCell className="hidden lg:table-cell">
                        {a.academic_year_name || "--"}
                      </TableCell>
                      <TableCell>{getStatusBadge(a.status)}</TableCell>
                      <TableCell className="text-right">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon">
                              <MoreHorizontal className="h-4 w-4" />
                              <span className="sr-only">Actions</span>
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem
                              onClick={() => handleOpenEdit(a)}
                            >
                              <Pencil className="mr-2 h-4 w-4" />
                              Edit
                            </DropdownMenuItem>
                            {a.status !== "cancelled" && (
                              <DropdownMenuItem
                                onClick={() => setCancelId(a.id)}
                                className="text-destructive focus:text-destructive"
                              >
                                <XCircle className="mr-2 h-4 w-4" />
                                Cancel
                              </DropdownMenuItem>
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
              <MapPin className="h-12 w-12" />
              <p>No transport assignments found</p>
              <p className="text-center text-sm max-w-md">
                Assign students to transport routes to track their pickup and
                drop-off.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ========================= */}
      {/* Assign Student Dialog     */}
      {/* ========================= */}
      <Dialog open={isAssignOpen} onOpenChange={setIsAssignOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Assign Student to Transport</DialogTitle>
            <DialogDescription>
              Select a student and assign them to a transport route and stop.
            </DialogDescription>
          </DialogHeader>
          <Form {...assignForm}>
            <form
              onSubmit={assignForm.handleSubmit(onAssignSubmit)}
              className="space-y-4"
            >
              {/* Student Search Select */}
              <FormField
                control={assignForm.control}
                name="student_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Student *</FormLabel>
                    <div className="space-y-2">
                      <Input
                        placeholder="Search students by name..."
                        value={studentSearch}
                        onChange={(e) => setStudentSearch(e.target.value)}
                      />
                      {studentsLoading && (
                        <div className="flex items-center gap-2 text-sm text-muted-foreground py-1">
                          <Loader2 className="h-3 w-3 animate-spin" />
                          Searching...
                        </div>
                      )}
                      {students.length > 0 && (
                        <div className="max-h-[160px] overflow-y-auto rounded-md border">
                          {students.map((student) => (
                            <button
                              key={student.id}
                              type="button"
                              className={cn(
                                "flex w-full items-center justify-between px-3 py-2 text-sm hover:bg-accent text-left",
                                field.value === student.id &&
                                  "bg-accent font-medium"
                              )}
                              onClick={() => {
                                field.onChange(student.id);
                                setStudentSearch(
                                  `${student.first_name} ${student.last_name}`
                                );
                                setStudents([]);
                              }}
                            >
                              <span>
                                {student.first_name} {student.last_name}
                              </span>
                              <span className="text-xs text-muted-foreground">
                                {student.class_name ?? ""}
                                {student.section_name
                                  ? ` - ${student.section_name}`
                                  : ""}
                              </span>
                            </button>
                          ))}
                        </div>
                      )}
                      {field.value && (
                        <p className="text-xs text-muted-foreground">
                          Student selected
                        </p>
                      )}
                    </div>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Academic Year */}
              <FormField
                control={assignForm.control}
                name="academic_year_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Academic Year *</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      value={field.value}
                    >
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Select academic year" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {academicYears.map((year) => (
                          <SelectItem key={year.id} value={year.id}>
                            {year.name}
                            {year.is_current ? " (Current)" : ""}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Route */}
              <FormField
                control={assignForm.control}
                name="route_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Route *</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      value={field.value}
                    >
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Select route" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {routes.map((route) => (
                          <SelectItem key={route.id} value={route.id}>
                            {route.route_code} - {route.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Stop (cascaded from route) */}
              <FormField
                control={assignForm.control}
                name="stop_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Stop *</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      value={field.value}
                      disabled={!assignRouteId || stopsLoading}
                    >
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue
                            placeholder={
                              stopsLoading
                                ? "Loading stops..."
                                : !assignRouteId
                                  ? "Select a route first"
                                  : "Select stop"
                            }
                          />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {stops.map((stop) => (
                          <SelectItem key={stop.id} value={stop.id}>
                            {stop.stop_name}
                            {stop.pickup_time
                              ? ` (Pickup: ${stop.pickup_time})`
                              : ""}
                            {stop.dropoff_time
                              ? ` (Drop-off: ${stop.dropoff_time})`
                              : ""}
                          </SelectItem>
                        ))}
                        {!stopsLoading &&
                          stops.length === 0 &&
                          assignRouteId && (
                            <div className="px-3 py-2 text-sm text-muted-foreground">
                              No stops found for this route
                            </div>
                          )}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Guardian Phone */}
              <FormField
                control={assignForm.control}
                name="pickup_guardian_phone"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Guardian Phone (for pickup)</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="+233 XX XXX XXXX"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Special Instructions */}
              <FormField
                control={assignForm.control}
                name="special_instructions"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Special Instructions</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Any special instructions for this student's transport..."
                        className="resize-none"
                        rows={3}
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
                  onClick={() => setIsAssignOpen(false)}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting && (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  )}
                  Assign Student
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* ========================= */}
      {/* Edit Assignment Dialog    */}
      {/* ========================= */}
      <Dialog
        open={isEditOpen}
        onOpenChange={(open) => {
          setIsEditOpen(open);
          if (!open) setEditingAssignment(null);
        }}
      >
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Edit Assignment</DialogTitle>
            <DialogDescription>
              Update transport assignment for{" "}
              {editingAssignment?.student_name ?? "student"}.
            </DialogDescription>
          </DialogHeader>
          <Form {...editForm}>
            <form
              onSubmit={editForm.handleSubmit(onEditSubmit)}
              className="space-y-4"
            >
              {/* Route */}
              <FormField
                control={editForm.control}
                name="route_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Route *</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      value={field.value}
                    >
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Select route" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {routes.map((route) => (
                          <SelectItem key={route.id} value={route.id}>
                            {route.route_code} - {route.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Stop (cascaded from route) */}
              <FormField
                control={editForm.control}
                name="stop_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Stop *</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      value={field.value}
                      disabled={!editRouteId || stopsLoading}
                    >
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue
                            placeholder={
                              stopsLoading
                                ? "Loading stops..."
                                : !editRouteId
                                  ? "Select a route first"
                                  : "Select stop"
                            }
                          />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {stops.map((stop) => (
                          <SelectItem key={stop.id} value={stop.id}>
                            {stop.stop_name}
                            {stop.pickup_time
                              ? ` (Pickup: ${stop.pickup_time})`
                              : ""}
                            {stop.dropoff_time
                              ? ` (Drop-off: ${stop.dropoff_time})`
                              : ""}
                          </SelectItem>
                        ))}
                        {!stopsLoading &&
                          stops.length === 0 &&
                          editRouteId && (
                            <div className="px-3 py-2 text-sm text-muted-foreground">
                              No stops found for this route
                            </div>
                          )}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Status */}
              <FormField
                control={editForm.control}
                name="status"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Status *</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      value={field.value}
                    >
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {STATUS_OPTIONS.map((opt) => (
                          <SelectItem key={opt.value} value={opt.value}>
                            {opt.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Guardian Phone */}
              <FormField
                control={editForm.control}
                name="pickup_guardian_phone"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Guardian Phone (for pickup)</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="+233 XX XXX XXXX"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Special Instructions */}
              <FormField
                control={editForm.control}
                name="special_instructions"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Special Instructions</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Any special instructions for this student's transport..."
                        className="resize-none"
                        rows={3}
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
                  onClick={() => {
                    setIsEditOpen(false);
                    setEditingAssignment(null);
                  }}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting && (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  )}
                  Save Changes
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* ========================= */}
      {/* Cancel Confirmation        */}
      {/* ========================= */}
      <AlertDialog
        open={!!cancelId}
        onOpenChange={() => setCancelId(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Cancel Assignment?</AlertDialogTitle>
            <AlertDialogDescription>
              This will cancel the student's transport assignment. They will no
              longer be assigned to this route.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isSubmitting}>
              Keep Assignment
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleCancel}
              disabled={isSubmitting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isSubmitting && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Cancel Assignment
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
