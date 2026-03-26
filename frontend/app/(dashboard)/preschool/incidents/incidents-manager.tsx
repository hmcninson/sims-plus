"use client";

import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { format } from "date-fns";
import {
  Plus,
  Loader2,
  AlertTriangle,
  Clock,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Bell,
  Pencil,
  Shield,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { Label } from "@/components/ui/label";
import { CollapsibleFilters } from "@/components/filters/collapsible-filters";
import { IncidentForm } from "@/components/preschool/IncidentForm";
import { IncidentTimeline } from "@/components/preschool/IncidentTimeline";
import { getStudents } from "@/actions/students.action";
import {
  listIncidents,
  createIncident,
  updateIncident,
  notifyParentIncident,
  resolveIncident,
} from "@/actions/preschool.action";
import type {
  Class,
  Student,
  PreschoolIncident,
  PreschoolIncidentCreate,
  PreschoolIncidentUpdate,
  PreschoolIncidentStatus,
  PreschoolIncidentSeverity,
} from "@/types";

interface IncidentsManagerProps {
  classes: Class[];
}

const SEVERITY_BADGE: Record<PreschoolIncidentSeverity, { color: string; label: string }> = {
  minor: { color: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200", label: "Minor" },
  moderate: { color: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200", label: "Moderate" },
  serious: { color: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200", label: "Serious" },
};

const STATUS_BADGE: Record<PreschoolIncidentStatus, { color: string; label: string }> = {
  reported: { color: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200", label: "Reported" },
  reviewed: { color: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200", label: "Reviewed" },
  parent_notified: { color: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200", label: "Parent Notified" },
  resolved: { color: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200", label: "Resolved" },
};

const INCIDENT_TYPE_LABELS: Record<string, string> = {
  accident: "Accident",
  illness: "Illness",
  behavioral: "Behavioral",
  allergic_reaction: "Allergic Reaction",
  other: "Other",
};

export function IncidentsManager({ classes }: IncidentsManagerProps) {
  // Filter state
  const [selectedClassId, setSelectedClassId] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [severityFilter, setSeverityFilter] = useState<string>("all");

  // Data state
  const [incidents, setIncidents] = useState<PreschoolIncident[]>([]);
  const [students, setStudents] = useState<Student[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingStudents, setLoadingStudents] = useState(false);

  // UI state
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingIncident, setEditingIncident] = useState<PreschoolIncident | null>(null);
  const [saving, setSaving] = useState(false);

  // Notify / Resolve dialogs
  const [notifyingId, setNotifyingId] = useState<string | null>(null);
  const [resolvingId, setResolvingId] = useState<string | null>(null);
  const [resolveNotes, setResolveNotes] = useState("");
  const [actionLoading, setActionLoading] = useState(false);

  // Fetch incidents
  const fetchIncidents = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (selectedClassId) params.class_id = selectedClassId;
      if (statusFilter !== "all") params.status = statusFilter;
      if (severityFilter !== "all") params.severity = severityFilter;

      const result = await listIncidents(params);
      if (result.success) {
        setIncidents(result.data);
      } else {
        toast.error(result.error);
      }
    } catch {
      toast.error("Failed to load incidents");
    } finally {
      setLoading(false);
    }
  }, [selectedClassId, statusFilter, severityFilter]);

  useEffect(() => {
    fetchIncidents();
  }, [fetchIncidents]);

  // Fetch students when class changes (for the form)
  useEffect(() => {
    async function fetchStudents() {
      if (!selectedClassId) {
        // If no class selected, load all preschool students
        setLoadingStudents(true);
        try {
          const result = await getStudents({ page_size: 200 });
          if (result.success && result.data) {
            setStudents(
              result.data.items.map((s) => ({
                id: s.id,
                student_id: s.student_id,
                first_name: s.first_name,
                middle_name: s.middle_name,
                last_name: s.last_name,
                gender: s.gender,
                date_of_birth: s.date_of_birth,
                status: s.status,
                class_id: s.class_id,
                section_id: s.section_id,
                photo_url: s.photo_url,
                is_boarder: false,
                created_at: "",
                updated_at: "",
              })) as Student[]
            );
          }
        } catch {
          // Silent
        } finally {
          setLoadingStudents(false);
        }
        return;
      }

      setLoadingStudents(true);
      try {
        const result = await getStudents({
          class_id: selectedClassId,
          page_size: 200,
        });
        if (result.success && result.data) {
          setStudents(
            result.data.items.map((s) => ({
              id: s.id,
              student_id: s.student_id,
              first_name: s.first_name,
              middle_name: s.middle_name,
              last_name: s.last_name,
              gender: s.gender,
              date_of_birth: s.date_of_birth,
              status: s.status,
              class_id: s.class_id,
              section_id: s.section_id,
              photo_url: s.photo_url,
              is_boarder: false,
              created_at: "",
              updated_at: "",
            })) as Student[]
          );
        }
      } catch {
        // Silent
      } finally {
        setLoadingStudents(false);
      }
    }

    fetchStudents();
  }, [selectedClassId]);

  // Stats
  const totalIncidents = incidents.length;
  const openIncidents = incidents.filter((i) => i.status !== "resolved").length;
  const seriousIncidents = incidents.filter((i) => i.severity === "serious").length;
  const resolvedIncidents = incidents.filter((i) => i.status === "resolved").length;

  // Handlers
  function handleOpenCreate() {
    setEditingIncident(null);
    setDialogOpen(true);
  }

  function handleOpenEdit(incident: PreschoolIncident) {
    setEditingIncident(incident);
    setDialogOpen(true);
  }

  async function handleFormSubmit(data: PreschoolIncidentCreate | PreschoolIncidentUpdate) {
    setSaving(true);
    try {
      if (editingIncident) {
        const result = await updateIncident(editingIncident.id, data as PreschoolIncidentUpdate);
        if (result.success) {
          toast.success("Incident updated");
          setDialogOpen(false);
          fetchIncidents();
        } else {
          toast.error(result.error);
        }
      } else {
        const result = await createIncident(data as PreschoolIncidentCreate);
        if (result.success) {
          toast.success("Incident reported");
          setDialogOpen(false);
          fetchIncidents();
        } else {
          toast.error(result.error);
        }
      }
    } catch {
      toast.error("Failed to save incident");
    } finally {
      setSaving(false);
    }
  }

  async function handleNotifyParent() {
    if (!notifyingId) return;
    setActionLoading(true);
    try {
      const result = await notifyParentIncident(notifyingId);
      if (result.success) {
        toast.success("Parent notified");
        setNotifyingId(null);
        fetchIncidents();
      } else {
        toast.error(result.error);
      }
    } catch {
      toast.error("Failed to notify parent");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleResolve() {
    if (!resolvingId) return;
    setActionLoading(true);
    try {
      const result = await resolveIncident(resolvingId, resolveNotes || undefined);
      if (result.success) {
        toast.success("Incident resolved");
        setResolvingId(null);
        setResolveNotes("");
        fetchIncidents();
      } else {
        toast.error(result.error);
      }
    } catch {
      toast.error("Failed to resolve incident");
    } finally {
      setActionLoading(false);
    }
  }

  // Get student name from incident
  function getStudentName(studentId: string): string {
    const student = students.find((s) => s.id === studentId);
    return student
      ? `${student.first_name} ${student.last_name}`
      : "Unknown Student";
  }

  const activeFilterCount =
    (statusFilter !== "all" ? 1 : 0) + (severityFilter !== "all" ? 1 : 0);

  return (
    <div className="space-y-6">
      {/* Actions & Filters */}
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div className="flex flex-wrap items-end gap-3">
          <div className="w-full sm:w-auto">
            <Label className="mb-1.5 block text-sm font-medium">Class</Label>
            <Select value={selectedClassId} onValueChange={setSelectedClassId}>
              <SelectTrigger className="w-full md:w-[200px]">
                <SelectValue placeholder="All classes" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All classes</SelectItem>
                {classes.map((cls) => (
                  <SelectItem key={cls.id} value={cls.id}>
                    {cls.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <CollapsibleFilters activeFilterCount={activeFilterCount}>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-full md:w-[180px]">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                <SelectItem value="reported">Reported</SelectItem>
                <SelectItem value="reviewed">Reviewed</SelectItem>
                <SelectItem value="parent_notified">Parent Notified</SelectItem>
                <SelectItem value="resolved">Resolved</SelectItem>
              </SelectContent>
            </Select>

            <Select value={severityFilter} onValueChange={setSeverityFilter}>
              <SelectTrigger className="w-full md:w-[160px]">
                <SelectValue placeholder="Severity" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Severities</SelectItem>
                <SelectItem value="minor">Minor</SelectItem>
                <SelectItem value="moderate">Moderate</SelectItem>
                <SelectItem value="serious">Serious</SelectItem>
              </SelectContent>
            </Select>
          </CollapsibleFilters>
        </div>

        <Button onClick={handleOpenCreate} disabled={loadingStudents}>
          <Plus className="mr-1 h-4 w-4" />
          Report Incident
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total</CardTitle>
            <Shield className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalIncidents}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Open</CardTitle>
            <Clock className="h-4 w-4 text-amber-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{openIncidents}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Serious</CardTitle>
            <AlertTriangle className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{seriousIncidents}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Resolved</CardTitle>
            <CheckCircle2 className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{resolvedIncidents}</div>
          </CardContent>
        </Card>
      </div>

      {/* Incidents Table */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-16 rounded-lg" />
          ))}
        </div>
      ) : incidents.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-12 text-center">
            <Shield className="h-12 w-12 text-muted-foreground/50" />
            <h3 className="mt-4 text-lg font-medium">No Incidents</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              No incidents have been reported with the current filters.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-8" />
                <TableHead>Date</TableHead>
                <TableHead>Student</TableHead>
                <TableHead className="hidden sm:table-cell">Type</TableHead>
                <TableHead>Severity</TableHead>
                <TableHead className="hidden md:table-cell">Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {incidents.map((incident) => {
                const isExpanded = expandedRow === incident.id;
                const sev = SEVERITY_BADGE[incident.severity];
                const stat = STATUS_BADGE[incident.status];

                return (
                  <>
                    <TableRow
                      key={incident.id}
                      className="cursor-pointer"
                      onClick={() =>
                        setExpandedRow(isExpanded ? null : incident.id)
                      }
                    >
                      <TableCell>
                        {isExpanded ? (
                          <ChevronDown className="h-4 w-4" />
                        ) : (
                          <ChevronRight className="h-4 w-4" />
                        )}
                      </TableCell>
                      <TableCell className="text-sm">
                        {format(new Date(incident.incident_date), "dd/MM/yyyy")}
                        {incident.incident_time && (
                          <span className="text-muted-foreground ml-1">
                            {incident.incident_time}
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="text-sm font-medium">
                        {getStudentName(incident.student_id)}
                      </TableCell>
                      <TableCell className="hidden sm:table-cell text-sm">
                        {INCIDENT_TYPE_LABELS[incident.incident_type] ??
                          incident.incident_type}
                      </TableCell>
                      <TableCell>
                        <Badge className={`${sev.color} text-xs`}>
                          {sev.label}
                        </Badge>
                      </TableCell>
                      <TableCell className="hidden md:table-cell">
                        <Badge variant="outline" className={`${stat.color} text-xs`}>
                          {stat.label}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <div
                          className="flex justify-end gap-1"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7"
                            title="Edit"
                            onClick={() => handleOpenEdit(incident)}
                          >
                            <Pencil className="h-3.5 w-3.5" />
                          </Button>
                          {incident.status !== "parent_notified" &&
                            incident.status !== "resolved" && (
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7"
                                title="Notify Parent"
                                onClick={() => setNotifyingId(incident.id)}
                              >
                                <Bell className="h-3.5 w-3.5" />
                              </Button>
                            )}
                          {incident.status !== "resolved" && (
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7"
                              title="Resolve"
                              onClick={() => {
                                setResolvingId(incident.id);
                                setResolveNotes(incident.follow_up_notes ?? "");
                              }}
                            >
                              <CheckCircle2 className="h-3.5 w-3.5" />
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>

                    {/* Expanded Detail Row */}
                    {isExpanded && (
                      <TableRow key={`${incident.id}-detail`}>
                        <TableCell colSpan={7} className="bg-muted/30 p-4">
                          <div className="space-y-4">
                            {/* Mobile-only info */}
                            <div className="sm:hidden flex flex-wrap gap-2">
                              <Badge variant="outline" className="text-xs">
                                {INCIDENT_TYPE_LABELS[incident.incident_type] ??
                                  incident.incident_type}
                              </Badge>
                              <Badge
                                variant="outline"
                                className={`${stat.color} text-xs`}
                              >
                                {stat.label}
                              </Badge>
                            </div>

                            <IncidentTimeline incident={incident} />

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                              <div>
                                <p className="font-medium text-muted-foreground">
                                  Description
                                </p>
                                <p>{incident.description}</p>
                              </div>

                              {incident.action_taken && (
                                <div>
                                  <p className="font-medium text-muted-foreground">
                                    Action Taken
                                  </p>
                                  <p>{incident.action_taken}</p>
                                </div>
                              )}

                              {incident.location && (
                                <div>
                                  <p className="font-medium text-muted-foreground">
                                    Location
                                  </p>
                                  <p>{incident.location}</p>
                                </div>
                              )}

                              <div className="flex gap-4">
                                {incident.first_aid_given && (
                                  <Badge variant="secondary" className="text-xs">
                                    First Aid Given
                                  </Badge>
                                )}
                                {incident.medical_attention_required && (
                                  <Badge variant="destructive" className="text-xs">
                                    Medical Attention Required
                                  </Badge>
                                )}
                              </div>

                              {incident.witnesses &&
                                incident.witnesses.length > 0 && (
                                  <div>
                                    <p className="font-medium text-muted-foreground">
                                      Witnesses
                                    </p>
                                    <p>{incident.witnesses.join(", ")}</p>
                                  </div>
                                )}

                              {incident.follow_up_notes && (
                                <div className="md:col-span-2">
                                  <p className="font-medium text-muted-foreground">
                                    Follow-up Notes
                                  </p>
                                  <p>{incident.follow_up_notes}</p>
                                </div>
                              )}
                            </div>
                          </div>
                        </TableCell>
                      </TableRow>
                    )}
                  </>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {editingIncident ? "Edit Incident" : "Report Incident"}
            </DialogTitle>
          </DialogHeader>
          <IncidentForm
            incident={editingIncident ?? undefined}
            students={students}
            onSubmit={handleFormSubmit}
            onCancel={() => setDialogOpen(false)}
            isSaving={saving}
          />
        </DialogContent>
      </Dialog>

      {/* Notify Parent Confirmation */}
      <AlertDialog
        open={!!notifyingId}
        onOpenChange={(open) => !open && setNotifyingId(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Notify Parent</AlertDialogTitle>
            <AlertDialogDescription>
              This will send a notification to the parent/guardian about this
              incident. Are you sure you want to proceed?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={actionLoading}>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleNotifyParent} disabled={actionLoading}>
              {actionLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Notify Parent
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Resolve Dialog */}
      <AlertDialog
        open={!!resolvingId}
        onOpenChange={(open) => {
          if (!open) {
            setResolvingId(null);
            setResolveNotes("");
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Resolve Incident</AlertDialogTitle>
            <AlertDialogDescription>
              Mark this incident as resolved. You can add follow-up notes below.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="py-2">
            <Label htmlFor="resolve-notes" className="text-sm font-medium">
              Follow-up Notes (optional)
            </Label>
            <Textarea
              id="resolve-notes"
              placeholder="Any final notes or follow-up actions..."
              value={resolveNotes}
              onChange={(e) => setResolveNotes(e.target.value)}
              rows={3}
              className="mt-1.5"
            />
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={actionLoading}>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleResolve} disabled={actionLoading}>
              {actionLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Resolve
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
