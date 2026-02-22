"use client";

import { useEffect, useState, useTransition, useCallback } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Plus,
  Loader2,
  ShieldAlert,
  CheckCircle2,
  MoreHorizontal,
  Eye,
  Pencil,
  ChevronsUpDown,
  Check,
  User,
  Clock,
  FileText,
} from "lucide-react";

import {
  getIncidents,
  getIncident,
  reportIncident,
  updateIncident,
  resolveIncident,
  getAssignments,
  getHouses,
} from "@/actions/boarding.action";
import type {
  BoardingIncidentDetail,
  BoardingIncidentType,
  IncidentSeverity,
  StudentBoardingDetail,
  House,
} from "@/types";
import { useToast } from "@/hooks/use-toast";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";

// -------------------------------------------------------------------
// Constants
// -------------------------------------------------------------------

const INCIDENT_TYPES: { value: BoardingIncidentType; label: string }[] = [
  { value: "disciplinary", label: "Disciplinary" },
  { value: "health", label: "Health" },
  { value: "property_damage", label: "Property Damage" },
  { value: "missing_student", label: "Missing Student" },
  { value: "bullying", label: "Bullying" },
  { value: "theft", label: "Theft" },
  { value: "other", label: "Other" },
];

const SEVERITY_LEVELS: { value: IncidentSeverity; label: string }[] = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
  { value: "critical", label: "Critical" },
];

// -------------------------------------------------------------------
// Badge helpers
// -------------------------------------------------------------------

function getSeverityBadge(severity: IncidentSeverity | string) {
  switch (severity) {
    case "low":
      return (
        <Badge className="bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300">
          Low
        </Badge>
      );
    case "medium":
      return (
        <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200">
          Medium
        </Badge>
      );
    case "high":
      return (
        <Badge className="bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200">
          High
        </Badge>
      );
    case "critical":
      return <Badge variant="destructive">Critical</Badge>;
    default:
      return <Badge variant="secondary">{severity}</Badge>;
  }
}

function getIncidentTypeBadge(type: BoardingIncidentType | string) {
  switch (type) {
    case "bullying":
      return <Badge variant="destructive">Bullying</Badge>;
    case "theft":
      return (
        <Badge className="bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200">
          Theft
        </Badge>
      );
    case "property_damage":
      return (
        <Badge className="bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200">
          Property Damage
        </Badge>
      );
    case "health":
      return (
        <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
          Health
        </Badge>
      );
    case "disciplinary":
      return (
        <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200">
          Disciplinary
        </Badge>
      );
    case "missing_student":
      return (
        <Badge className="bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200">
          Missing Student
        </Badge>
      );
    default:
      return (
        <Badge variant="outline" className="capitalize">
          {type.replace(/_/g, " ")}
        </Badge>
      );
  }
}

// -------------------------------------------------------------------
// Zod schemas
// -------------------------------------------------------------------

const incidentTypeValues = [
  "disciplinary",
  "health",
  "property_damage",
  "missing_student",
  "bullying",
  "theft",
  "other",
] as const;

const severityValues = ["low", "medium", "high", "critical"] as const;

const reportSchema = z.object({
  student_id: z.string().min(1, "Please select a student"),
  incident_type: z.enum(incidentTypeValues, {
    message: "Please select an incident type",
  }),
  severity: z.enum(severityValues, {
    message: "Please select a severity level",
  }),
  description: z.string().min(10, "Description must be at least 10 characters"),
  action_taken: z.string().optional(),
});

const editSchema = z.object({
  incident_type: z.enum(incidentTypeValues, {
    message: "Please select an incident type",
  }),
  severity: z.enum(severityValues, {
    message: "Please select a severity level",
  }),
  description: z.string().min(10, "Description must be at least 10 characters"),
  action_taken: z.string().optional(),
});

const resolveSchema = z.object({
  action_taken: z.string().min(5, "Resolution details must be at least 5 characters"),
  parent_notified: z.boolean().optional(),
});

type ReportFormData = z.infer<typeof reportSchema>;
type EditFormData = z.infer<typeof editSchema>;
type ResolveFormData = z.infer<typeof resolveSchema>;

// -------------------------------------------------------------------
// Main page component
// -------------------------------------------------------------------

export default function IncidentsPage() {
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();

  // List state
  const [incidents, setIncidents] = useState<BoardingIncidentDetail[]>([]);
  const [total, setTotal] = useState(0);
  const [activeTab, setActiveTab] = useState("all");
  const [filterSeverity, setFilterSeverity] = useState("all");

  // Dialog state
  const [isReportOpen, setIsReportOpen] = useState(false);
  const [detailIncident, setDetailIncident] = useState<BoardingIncidentDetail | null>(null);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [editingIncident, setEditingIncident] = useState<BoardingIncidentDetail | null>(null);
  const [resolveTarget, setResolveTarget] = useState<BoardingIncidentDetail | null>(null);

  // Submitting state
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Student search state for report form
  const [boardingStudents, setBoardingStudents] = useState<StudentBoardingDetail[]>([]);
  const [studentSearchOpen, setStudentSearchOpen] = useState(false);
  const [isLoadingStudents, setIsLoadingStudents] = useState(false);

  // House list for filtering
  const [houses, setHouses] = useState<House[]>([]);

  // -------------------------------------------------------------------
  // Forms
  // -------------------------------------------------------------------

  const reportForm = useForm<ReportFormData>({
    resolver: zodResolver(reportSchema),
    defaultValues: {
      student_id: "",
      incident_type: "disciplinary",
      severity: "medium",
      description: "",
      action_taken: "",
    },
  });

  const editForm = useForm<EditFormData>({
    resolver: zodResolver(editSchema),
    defaultValues: {
      incident_type: "disciplinary",
      severity: "medium",
      description: "",
      action_taken: "",
    },
  });

  const resolveForm = useForm<ResolveFormData>({
    resolver: zodResolver(resolveSchema),
    defaultValues: {
      action_taken: "",
      parent_notified: false,
    },
  });

  // -------------------------------------------------------------------
  // Data loading
  // -------------------------------------------------------------------

  const loadIncidents = useCallback(() => {
    startTransition(async () => {
      const resolved =
        activeTab === "unresolved" ? false : activeTab === "resolved" ? true : undefined;
      const result = await getIncidents({
        resolved,
        severity: filterSeverity !== "all" ? filterSeverity : undefined,
        pageSize: 50,
      });
      if (result.success && result.data) {
        const data = result.data;
        const items = Array.isArray(data) ? data : (data.items ?? []);
        const count = Array.isArray(data) ? data.length : (data.total ?? 0);
        setIncidents(items);
        setTotal(count);
      }
    });
  }, [activeTab, filterSeverity]);

  useEffect(() => {
    loadIncidents();
  }, [loadIncidents]);

  const loadBoardingStudents = useCallback(async () => {
    if (boardingStudents.length > 0) return;
    setIsLoadingStudents(true);
    try {
      const result = await getAssignments({ status: "active", pageSize: 200 });
      if (result.success && result.data) {
        const data = result.data;
        const items = Array.isArray(data) ? data : (data.items ?? []);
        setBoardingStudents(items);
      }
    } finally {
      setIsLoadingStudents(false);
    }
  }, [boardingStudents.length]);

  const loadHouses = useCallback(async () => {
    if (houses.length > 0) return;
    try {
      const result = await getHouses({ isActive: true, pageSize: 100 });
      if (result.success && result.data) {
        const data = result.data;
        const items = Array.isArray(data) ? data : (data.items ?? []);
        setHouses(items);
      }
    } catch {
      // Silent fail for house loading
    }
  }, [houses.length]);

  // -------------------------------------------------------------------
  // Actions
  // -------------------------------------------------------------------

  const handleReport = async (data: ReportFormData) => {
    setIsSubmitting(true);
    try {
      const result = await reportIncident({
        student_id: data.student_id,
        incident_type: data.incident_type,
        severity: data.severity,
        description: data.description,
        action_taken: data.action_taken || undefined,
      });
      if (result.success) {
        toast({ title: "Incident reported successfully" });
        setIsReportOpen(false);
        reportForm.reset();
        loadIncidents();
      } else {
        toast({ title: "Error", description: result.error, variant: "destructive" });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleEdit = async (data: EditFormData) => {
    if (!editingIncident) return;
    setIsSubmitting(true);
    try {
      const result = await updateIncident(editingIncident.id, {
        incident_type: data.incident_type,
        severity: data.severity,
        description: data.description,
        action_taken: data.action_taken || undefined,
      });
      if (result.success) {
        toast({ title: "Incident updated successfully" });
        setEditingIncident(null);
        editForm.reset();
        loadIncidents();
      } else {
        toast({ title: "Error", description: result.error, variant: "destructive" });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResolve = async (data: ResolveFormData) => {
    if (!resolveTarget) return;
    setIsSubmitting(true);
    try {
      const result = await resolveIncident(resolveTarget.id, {
        action_taken: data.action_taken,
        parent_notified: data.parent_notified,
      });
      if (result.success) {
        toast({ title: "Incident resolved successfully" });
        setResolveTarget(null);
        resolveForm.reset();
        loadIncidents();
      } else {
        toast({ title: "Error", description: result.error, variant: "destructive" });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleViewDetail = async (incidentId: string) => {
    setIsDetailLoading(true);
    const result = await getIncident(incidentId);
    if (result.success && result.data) {
      setDetailIncident(result.data);
    } else {
      toast({
        title: "Error",
        description: result.error || "Failed to load incident details",
        variant: "destructive",
      });
    }
    setIsDetailLoading(false);
  };

  const openEditDialog = (incident: BoardingIncidentDetail) => {
    editForm.reset({
      incident_type: incident.incident_type,
      severity: incident.severity,
      description: incident.description,
      action_taken: incident.action_taken || "",
    });
    setEditingIncident(incident);
  };

  const openResolveDialog = (incident: BoardingIncidentDetail) => {
    resolveForm.reset({
      action_taken: incident.action_taken || "",
      parent_notified: incident.parent_notified,
    });
    setResolveTarget(incident);
  };

  // -------------------------------------------------------------------
  // Helpers
  // -------------------------------------------------------------------

  const getSelectedStudentName = (studentId: string): string => {
    const student = boardingStudents.find((s) => s.student_id === studentId);
    return student?.student_name || "";
  };

  // -------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Boarding Incidents</h1>
          <p className="text-muted-foreground">
            Report, track, and resolve boarding incidents
          </p>
        </div>
        <Button
          onClick={() => {
            loadBoardingStudents();
            loadHouses();
            setIsReportOpen(true);
          }}
        >
          <Plus className="mr-2 h-4 w-4" />
          Report Incident
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
        <Select value={filterSeverity} onValueChange={setFilterSeverity}>
          <SelectTrigger className="w-full sm:w-[180px]">
            <SelectValue placeholder="Severity" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Severities</SelectItem>
            {SEVERITY_LEVELS.map((s) => (
              <SelectItem key={s.value} value={s.value}>
                {s.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="all">All</TabsTrigger>
          <TabsTrigger value="unresolved">Unresolved</TabsTrigger>
          <TabsTrigger value="resolved">Resolved</TabsTrigger>
        </TabsList>

        <TabsContent value={activeTab} className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle>Incidents</CardTitle>
              <CardDescription>
                {total} incident{total !== 1 ? "s" : ""} found
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isPending ? (
                <div className="flex h-[200px] items-center justify-center">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
              ) : incidents.length > 0 ? (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Date</TableHead>
                        <TableHead>Student</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Severity</TableHead>
                        <TableHead className="hidden md:table-cell">Description</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {incidents.map((incident) => (
                        <TableRow key={incident.id}>
                          <TableCell className="whitespace-nowrap">
                            {formatDate(incident.created_at)}
                          </TableCell>
                          <TableCell className="font-medium">
                            {incident.student_name || "--"}
                          </TableCell>
                          <TableCell>{getIncidentTypeBadge(incident.incident_type)}</TableCell>
                          <TableCell>{getSeverityBadge(incident.severity)}</TableCell>
                          <TableCell className="hidden max-w-[200px] truncate md:table-cell">
                            {incident.description}
                          </TableCell>
                          <TableCell>
                            {incident.resolved ? (
                              <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                                Resolved
                              </Badge>
                            ) : (
                              <Badge variant="destructive">Open</Badge>
                            )}
                          </TableCell>
                          <TableCell className="text-right">
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="h-8 w-8"
                                  aria-label="Row actions"
                                >
                                  <MoreHorizontal className="h-4 w-4" />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end">
                                <DropdownMenuItem
                                  onClick={() => handleViewDetail(incident.id)}
                                >
                                  <Eye className="mr-2 h-4 w-4" />
                                  View Details
                                </DropdownMenuItem>

                                {!incident.resolved && (
                                  <>
                                    <DropdownMenuItem
                                      onClick={() => openEditDialog(incident)}
                                    >
                                      <Pencil className="mr-2 h-4 w-4" />
                                      Edit
                                    </DropdownMenuItem>
                                    <DropdownMenuSeparator />
                                    <DropdownMenuItem
                                      onClick={() => openResolveDialog(incident)}
                                    >
                                      <CheckCircle2 className="mr-2 h-4 w-4 text-green-600" />
                                      Resolve
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
                  <ShieldAlert className="h-12 w-12" />
                  <p className="font-medium">No incidents found</p>
                  <p className="text-sm text-center max-w-md">
                    {activeTab === "all"
                      ? "When incidents are reported, they will appear here."
                      : `No ${activeTab} incidents at this time.`}
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* ============================================================= */}
      {/* Report Incident Dialog                                         */}
      {/* ============================================================= */}
      <Dialog
        open={isReportOpen}
        onOpenChange={(open) => {
          if (!open) {
            reportForm.reset();
          }
          setIsReportOpen(open);
        }}
      >
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-[560px]">
          <DialogHeader>
            <DialogTitle>Report Incident</DialogTitle>
            <DialogDescription>
              Record a boarding incident. Provide as much detail as possible.
            </DialogDescription>
          </DialogHeader>
          <Form {...reportForm}>
            <form onSubmit={reportForm.handleSubmit(handleReport)} className="space-y-4">
              {/* Student select (searchable) */}
              <FormField
                control={reportForm.control}
                name="student_id"
                render={({ field }) => (
                  <FormItem className="flex flex-col">
                    <FormLabel>Student *</FormLabel>
                    <Popover
                      open={studentSearchOpen}
                      onOpenChange={setStudentSearchOpen}
                    >
                      <PopoverTrigger asChild>
                        <FormControl>
                          <Button
                            variant="outline"
                            role="combobox"
                            aria-expanded={studentSearchOpen}
                            className={cn(
                              "w-full justify-between",
                              !field.value && "text-muted-foreground"
                            )}
                          >
                            {field.value
                              ? getSelectedStudentName(field.value) || "Student selected"
                              : "Search boarding students..."}
                            <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                          </Button>
                        </FormControl>
                      </PopoverTrigger>
                      <PopoverContent className="w-full p-0" align="start">
                        <Command>
                          <CommandInput placeholder="Type a name to search..." />
                          <CommandList>
                            <CommandEmpty>
                              {isLoadingStudents
                                ? "Loading students..."
                                : "No boarding students found."}
                            </CommandEmpty>
                            <CommandGroup>
                              {boardingStudents.map((student) => (
                                <CommandItem
                                  key={student.id}
                                  value={student.student_name || student.student_id}
                                  onSelect={() => {
                                    field.onChange(student.student_id);
                                    setStudentSearchOpen(false);
                                  }}
                                >
                                  <Check
                                    className={cn(
                                      "mr-2 h-4 w-4",
                                      field.value === student.student_id
                                        ? "opacity-100"
                                        : "opacity-0"
                                    )}
                                  />
                                  <div className="flex flex-col">
                                    <span>{student.student_name || "Unknown"}</span>
                                    <span className="text-xs text-muted-foreground">
                                      {student.house_name || "No house"}
                                      {student.dormitory_name
                                        ? ` / ${student.dormitory_name}`
                                        : ""}
                                    </span>
                                  </div>
                                </CommandItem>
                              ))}
                            </CommandGroup>
                          </CommandList>
                        </Command>
                      </PopoverContent>
                    </Popover>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Incident type + severity */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <FormField
                  control={reportForm.control}
                  name="incident_type"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Incident Type *</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {INCIDENT_TYPES.map((t) => (
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
                  control={reportForm.control}
                  name="severity"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Severity *</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {SEVERITY_LEVELS.map((s) => (
                            <SelectItem key={s.value} value={s.value}>
                              {s.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              {/* Description */}
              <FormField
                control={reportForm.control}
                name="description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Description *</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Describe the incident in detail..."
                        rows={4}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Immediate action taken */}
              <FormField
                control={reportForm.control}
                name="action_taken"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Immediate Action Taken</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Describe any immediate actions taken..."
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
                  onClick={() => setIsReportOpen(false)}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Report Incident
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* ============================================================= */}
      {/* Edit Incident Dialog                                           */}
      {/* ============================================================= */}
      <Dialog
        open={!!editingIncident}
        onOpenChange={(open) => {
          if (!open) {
            setEditingIncident(null);
            editForm.reset();
          }
        }}
      >
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-[560px]">
          <DialogHeader>
            <DialogTitle>Edit Incident</DialogTitle>
            <DialogDescription>
              Update the details of this incident.
              {editingIncident && (
                <span className="block mt-1">
                  Student: <span className="font-medium">{editingIncident.student_name || "Unknown"}</span>
                </span>
              )}
            </DialogDescription>
          </DialogHeader>
          <Form {...editForm}>
            <form onSubmit={editForm.handleSubmit(handleEdit)} className="space-y-4">
              {/* Incident type + severity */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <FormField
                  control={editForm.control}
                  name="incident_type"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Incident Type *</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {INCIDENT_TYPES.map((t) => (
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
                  control={editForm.control}
                  name="severity"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Severity *</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {SEVERITY_LEVELS.map((s) => (
                            <SelectItem key={s.value} value={s.value}>
                              {s.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              {/* Description */}
              <FormField
                control={editForm.control}
                name="description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Description *</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Describe the incident in detail..."
                        rows={4}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Action taken */}
              <FormField
                control={editForm.control}
                name="action_taken"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Action Taken</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Describe any actions taken..."
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
                  onClick={() => setEditingIncident(null)}
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

      {/* ============================================================= */}
      {/* Incident Detail Dialog                                         */}
      {/* ============================================================= */}
      <Dialog
        open={!!detailIncident || isDetailLoading}
        onOpenChange={(open) => {
          if (!open) {
            setDetailIncident(null);
            setIsDetailLoading(false);
          }
        }}
      >
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-[560px]">
          {isDetailLoading ? (
            <div className="flex h-[200px] items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : detailIncident ? (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-3">
                  Incident Details
                  {detailIncident.resolved ? (
                    <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                      Resolved
                    </Badge>
                  ) : (
                    <Badge variant="destructive">Open</Badge>
                  )}
                </DialogTitle>
                <DialogDescription>
                  Reported on {formatDate(detailIncident.created_at)}
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-4">
                {/* Severity + Type banner */}
                <div className="flex flex-wrap items-center gap-2">
                  {getSeverityBadge(detailIncident.severity)}
                  {getIncidentTypeBadge(detailIncident.incident_type)}
                </div>

                {/* Student + Reporter */}
                <div className="rounded-lg border p-4 space-y-3">
                  <div className="flex items-start gap-3">
                    <User className="mt-0.5 h-4 w-4 text-muted-foreground shrink-0" />
                    <div>
                      <p className="text-sm font-medium">Student</p>
                      <p className="text-sm text-muted-foreground">
                        {detailIncident.student_name || "Unknown"}
                      </p>
                    </div>
                  </div>
                  {detailIncident.reported_by_name && (
                    <div className="flex items-start gap-3">
                      <FileText className="mt-0.5 h-4 w-4 text-muted-foreground shrink-0" />
                      <div>
                        <p className="text-sm font-medium">Reported By</p>
                        <p className="text-sm text-muted-foreground">
                          {detailIncident.reported_by_name}
                        </p>
                      </div>
                    </div>
                  )}
                </div>

                {/* Description */}
                <div className="rounded-lg border p-4 space-y-2">
                  <p className="text-sm font-medium">Description</p>
                  <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                    {detailIncident.description}
                  </p>
                </div>

                {/* Action taken */}
                {detailIncident.action_taken && (
                  <div className="rounded-lg border p-4 space-y-2">
                    <p className="text-sm font-medium">Action Taken</p>
                    <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                      {detailIncident.action_taken}
                    </p>
                  </div>
                )}

                {/* Resolution info (if resolved) */}
                {detailIncident.resolved && (
                  <div className="rounded-lg border border-green-200 bg-green-50 p-4 space-y-3 dark:border-green-800 dark:bg-green-950">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />
                      <p className="text-sm font-medium text-green-800 dark:text-green-200">
                        Resolved
                      </p>
                    </div>
                    {detailIncident.resolved_by_name && (
                      <p className="text-sm text-green-700 dark:text-green-300">
                        Resolved by: {detailIncident.resolved_by_name}
                      </p>
                    )}
                    {detailIncident.resolved_at && (
                      <p className="text-sm text-green-700 dark:text-green-300">
                        Resolved on: {formatDate(detailIncident.resolved_at)}
                      </p>
                    )}
                    <p className="text-sm text-green-700 dark:text-green-300">
                      Parent notified: {detailIncident.parent_notified ? "Yes" : "No"}
                    </p>
                  </div>
                )}

                {/* Timeline */}
                <div className="rounded-lg border p-4 space-y-2">
                  <p className="text-sm font-medium">Timeline</p>
                  <div className="space-y-2">
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Clock className="h-3 w-3 shrink-0" />
                      <span>Created {formatDate(detailIncident.created_at)}</span>
                    </div>
                    {detailIncident.updated_at !== detailIncident.created_at && (
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <Clock className="h-3 w-3 shrink-0" />
                        <span>Updated {formatDate(detailIncident.updated_at)}</span>
                      </div>
                    )}
                    {detailIncident.resolved_at && (
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <CheckCircle2 className="h-3 w-3 shrink-0 text-green-600" />
                        <span>Resolved {formatDate(detailIncident.resolved_at)}</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Detail dialog footer actions */}
              {!detailIncident.resolved && (
                <DialogFooter className="flex-col gap-2 sm:flex-row">
                  <Button
                    variant="outline"
                    onClick={() => {
                      const incident = detailIncident;
                      setDetailIncident(null);
                      openEditDialog(incident);
                    }}
                  >
                    <Pencil className="mr-2 h-4 w-4" />
                    Edit
                  </Button>
                  <Button
                    onClick={() => {
                      const incident = detailIncident;
                      setDetailIncident(null);
                      openResolveDialog(incident);
                    }}
                  >
                    <CheckCircle2 className="mr-2 h-4 w-4" />
                    Resolve
                  </Button>
                </DialogFooter>
              )}
            </>
          ) : null}
        </DialogContent>
      </Dialog>

      {/* ============================================================= */}
      {/* Resolve Incident AlertDialog                                   */}
      {/* ============================================================= */}
      <Dialog
        open={!!resolveTarget}
        onOpenChange={(open) => {
          if (!open) {
            setResolveTarget(null);
            resolveForm.reset();
          }
        }}
      >
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Resolve Incident</DialogTitle>
            <DialogDescription>
              Provide resolution details for this incident.
            </DialogDescription>
          </DialogHeader>

          {resolveTarget && (
            <div className="rounded-lg border p-3 space-y-2">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium">
                  {resolveTarget.student_name || "Unknown Student"}
                </p>
                <div className="flex items-center gap-2">
                  {getIncidentTypeBadge(resolveTarget.incident_type)}
                  {getSeverityBadge(resolveTarget.severity)}
                </div>
              </div>
              <p className="text-sm text-muted-foreground line-clamp-2">
                {resolveTarget.description}
              </p>
            </div>
          )}

          <Form {...resolveForm}>
            <form onSubmit={resolveForm.handleSubmit(handleResolve)} className="space-y-4">
              <FormField
                control={resolveForm.control}
                name="action_taken"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Resolution / Action Taken *</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Describe how the incident was resolved..."
                        rows={4}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={resolveForm.control}
                name="parent_notified"
                render={({ field }) => (
                  <FormItem className="flex flex-row items-start space-x-3 space-y-0">
                    <FormControl>
                      <Checkbox
                        checked={field.value}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                    <div className="space-y-1 leading-none">
                      <FormLabel className="text-sm font-normal">
                        Parent/Guardian has been notified
                      </FormLabel>
                    </div>
                  </FormItem>
                )}
              />
              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setResolveTarget(null)}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Resolve Incident
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
