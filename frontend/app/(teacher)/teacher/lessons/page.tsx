"use client";

/**
 * SIMS Plus - Teacher Lesson Plans Page
 *
 * Full CRUD interface for lesson plans with:
 * - Table/card list with date, class, subject, topic, status
 * - Filters by class and date range
 * - Create dialog with class/subject cascading selects
 * - Edit dialog for updating plan details
 * - Status workflow: planned -> taught -> cancelled
 * - Delete with confirmation
 * - Mobile responsive (cards on mobile, table on desktop)
 */

import { useEffect, useState, useCallback, useTransition } from "react";
import {
  AlertCircle,
  BookOpen,
  Calendar,
  Edit,
  Loader2,
  MoreHorizontal,
  Plus,
  Trash2,
  CheckCircle2,
  XCircle,
  Clock,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
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
  DialogTrigger,
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  getTeacherLessonPlans,
  createTeacherLessonPlan,
  updateTeacherLessonPlan,
  deleteTeacherLessonPlan,
  getTeacherClasses,
  getTeacherClassDetail,
} from "@/actions/teacher.action";
import type {
  TeacherLessonPlan,
  TeacherLessonPlanCreate,
  TeacherLessonPlanUpdate,
  TeacherClassSummary,
  TeacherSubjectSummary,
} from "@/types/teacher.type";
import { toast } from "sonner";

// ---- Status display helpers ----

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: React.ComponentType<{ className?: string }> }> = {
  planned: {
    label: "Planned",
    color: "bg-blue-100 text-blue-800 border-blue-300",
    icon: Clock,
  },
  taught: {
    label: "Taught",
    color: "bg-green-100 text-green-800 border-green-300",
    icon: CheckCircle2,
  },
  cancelled: {
    label: "Cancelled",
    color: "bg-red-100 text-red-800 border-red-300",
    icon: XCircle,
  },
};

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export default function TeacherLessonPlansPage() {
  // ---- List state ----
  const [plans, setPlans] = useState<TeacherLessonPlan[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // ---- Filter state ----
  const [filterClassId, setFilterClassId] = useState<string>("all");
  const [filterDateFrom, setFilterDateFrom] = useState("");
  const [filterDateTo, setFilterDateTo] = useState("");

  // ---- Shared data ----
  const [classes, setClasses] = useState<TeacherClassSummary[]>([]);

  // ---- Create dialog state ----
  const [createOpen, setCreateOpen] = useState(false);
  const [createClassId, setCreateClassId] = useState("");
  const [createSubjects, setCreateSubjects] = useState<TeacherSubjectSummary[]>([]);
  const [loadingSubjects, setLoadingSubjects] = useState(false);
  const [createSubjectId, setCreateSubjectId] = useState("");
  const [createDate, setCreateDate] = useState("");
  const [createPeriod, setCreatePeriod] = useState("");
  const [createTopic, setCreateTopic] = useState("");
  const [createObjectives, setCreateObjectives] = useState("");
  const [createResources, setCreateResources] = useState("");
  const [createActivities, setCreateActivities] = useState("");
  const [createNotes, setCreateNotes] = useState("");
  const [isPending, startTransition] = useTransition();

  // ---- Edit dialog state ----
  const [editOpen, setEditOpen] = useState(false);
  const [editingPlan, setEditingPlan] = useState<TeacherLessonPlan | null>(null);
  const [editTopic, setEditTopic] = useState("");
  const [editObjectives, setEditObjectives] = useState("");
  const [editResources, setEditResources] = useState("");
  const [editActivities, setEditActivities] = useState("");
  const [editNotes, setEditNotes] = useState("");
  const [isEditPending, startEditTransition] = useTransition();

  // ---- Delete confirmation state ----
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingPlanId, setDeletingPlanId] = useState<string | null>(null);
  const [isDeletePending, startDeleteTransition] = useTransition();

  // ---- Load classes on mount ----
  useEffect(() => {
    async function loadClasses() {
      const result = await getTeacherClasses();
      if (result.success) {
        setClasses(result.data);
      }
    }
    loadClasses();
  }, []);

  // ---- Load lesson plans (re-fetch on filter change) ----
  const loadPlans = useCallback(async () => {
    setLoading(true);
    setError(null);
    const result = await getTeacherLessonPlans({
      classId: filterClassId !== "all" ? filterClassId : undefined,
      dateFrom: filterDateFrom || undefined,
      dateTo: filterDateTo || undefined,
      limit: 100,
      offset: 0,
    });
    if (result.success) {
      setPlans(result.data.plans);
      setTotalCount(result.data.total);
    } else {
      setError(result.error);
    }
    setLoading(false);
  }, [filterClassId, filterDateFrom, filterDateTo]);

  useEffect(() => {
    loadPlans();
  }, [loadPlans]);

  // ---- Load subjects when class changes in create dialog ----
  useEffect(() => {
    if (!createClassId) {
      setCreateSubjects([]);
      setCreateSubjectId("");
      return;
    }
    let cancelled = false;
    async function loadSubjects() {
      setLoadingSubjects(true);
      setCreateSubjectId("");
      const result = await getTeacherClassDetail(createClassId);
      if (!cancelled && result.success) {
        setCreateSubjects(result.data.subjects);
      }
      if (!cancelled) setLoadingSubjects(false);
    }
    loadSubjects();
    return () => {
      cancelled = true;
    };
  }, [createClassId]);

  // ---- Create handler ----
  const handleCreate = () => {
    if (!createClassId || !createSubjectId || !createDate || !createTopic.trim()) {
      toast.error("Please fill in class, subject, date, and topic");
      return;
    }

    const data: TeacherLessonPlanCreate = {
      class_id: createClassId,
      subject_id: createSubjectId,
      date: createDate,
      period: createPeriod ? Number(createPeriod) : undefined,
      topic: createTopic.trim(),
      objectives: createObjectives.trim() || undefined,
      resources: createResources.trim() || undefined,
      activities: createActivities.trim() || undefined,
      notes: createNotes.trim() || undefined,
    };

    startTransition(async () => {
      const result = await createTeacherLessonPlan(data);
      if (result.success) {
        toast.success("Lesson plan created");
        setPlans((prev) => [result.data, ...prev]);
        setTotalCount((prev) => prev + 1);
        resetCreateForm();
        setCreateOpen(false);
      } else {
        toast.error(result.error);
      }
    });
  };

  const resetCreateForm = () => {
    setCreateClassId("");
    setCreateSubjects([]);
    setCreateSubjectId("");
    setCreateDate("");
    setCreatePeriod("");
    setCreateTopic("");
    setCreateObjectives("");
    setCreateResources("");
    setCreateActivities("");
    setCreateNotes("");
  };

  // ---- Edit handler ----
  const openEditDialog = (plan: TeacherLessonPlan) => {
    setEditingPlan(plan);
    setEditTopic(plan.topic);
    setEditObjectives(plan.objectives || "");
    setEditResources(plan.resources || "");
    setEditActivities(plan.activities || "");
    setEditNotes(plan.notes || "");
    setEditOpen(true);
  };

  const handleEdit = () => {
    if (!editingPlan || !editTopic.trim()) {
      toast.error("Topic is required");
      return;
    }

    const data: TeacherLessonPlanUpdate = {
      topic: editTopic.trim(),
      objectives: editObjectives.trim() || undefined,
      resources: editResources.trim() || undefined,
      activities: editActivities.trim() || undefined,
      notes: editNotes.trim() || undefined,
    };

    startEditTransition(async () => {
      const result = await updateTeacherLessonPlan(editingPlan.id, data);
      if (result.success) {
        toast.success("Lesson plan updated");
        setPlans((prev) =>
          prev.map((p) => (p.id === editingPlan.id ? result.data : p))
        );
        setEditOpen(false);
        setEditingPlan(null);
      } else {
        toast.error(result.error);
      }
    });
  };

  // ---- Status change handler ----
  const handleStatusChange = (planId: string, newStatus: string) => {
    startTransition(async () => {
      const result = await updateTeacherLessonPlan(planId, { status: newStatus });
      if (result.success) {
        toast.success(`Marked as ${STATUS_CONFIG[newStatus]?.label || newStatus}`);
        setPlans((prev) =>
          prev.map((p) => (p.id === planId ? result.data : p))
        );
      } else {
        toast.error(result.error);
      }
    });
  };

  // ---- Delete handler ----
  const handleDelete = () => {
    if (!deletingPlanId) return;

    startDeleteTransition(async () => {
      const result = await deleteTeacherLessonPlan(deletingPlanId);
      if (result.success) {
        toast.success("Lesson plan deleted");
        setPlans((prev) => prev.filter((p) => p.id !== deletingPlanId));
        setTotalCount((prev) => prev - 1);
      } else {
        toast.error(result.error);
      }
      setDeleteDialogOpen(false);
      setDeletingPlanId(null);
    });
  };

  // ---- Loading state ----
  if (loading && plans.length === 0) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error && plans.length === 0) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Lesson Plans</h1>
          <p className="text-muted-foreground">
            Plan and track your lessons across classes
          </p>
        </div>
        <Dialog open={createOpen} onOpenChange={(open) => { setCreateOpen(open); if (!open) resetCreateForm(); }}>
          <DialogTrigger asChild>
            <Button size="sm">
              <Plus className="h-4 w-4 mr-1" />
              New Plan
            </Button>
          </DialogTrigger>
          <DialogContent className="max-sm:max-w-[calc(100vw-2rem)] max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Create Lesson Plan</DialogTitle>
              <DialogDescription>
                Plan a lesson for one of your classes.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Class *</Label>
                  <Select value={createClassId} onValueChange={setCreateClassId}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select a class" />
                    </SelectTrigger>
                    <SelectContent>
                      {classes.map((cls) => (
                        <SelectItem
                          key={`${cls.class_id}-${cls.section_id || "main"}`}
                          value={cls.class_id}
                        >
                          {cls.class_name}
                          {cls.section_name ? ` - ${cls.section_name}` : ""}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Subject *</Label>
                  <Select
                    value={createSubjectId}
                    onValueChange={setCreateSubjectId}
                    disabled={!createClassId || loadingSubjects}
                  >
                    <SelectTrigger>
                      {loadingSubjects ? (
                        <span className="flex items-center gap-2 text-muted-foreground">
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          Loading...
                        </span>
                      ) : (
                        <SelectValue
                          placeholder={createClassId ? "Select a subject" : "Select a class first"}
                        />
                      )}
                    </SelectTrigger>
                    <SelectContent>
                      {createSubjects.map((subj) => (
                        <SelectItem key={subj.subject_id} value={subj.subject_id}>
                          {subj.subject_name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Date *</Label>
                  <Input
                    type="date"
                    value={createDate}
                    onChange={(e) => setCreateDate(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Period (optional)</Label>
                  <Input
                    type="number"
                    min={1}
                    max={12}
                    placeholder="e.g. 3"
                    value={createPeriod}
                    onChange={(e) => setCreatePeriod(e.target.value)}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label>Topic *</Label>
                <Input
                  placeholder="Lesson topic"
                  value={createTopic}
                  onChange={(e) => setCreateTopic(e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <Label>Objectives</Label>
                <Textarea
                  placeholder="What students should learn..."
                  value={createObjectives}
                  onChange={(e) => setCreateObjectives(e.target.value)}
                  rows={3}
                />
              </div>

              <div className="space-y-2">
                <Label>Resources</Label>
                <Textarea
                  placeholder="Materials and resources needed..."
                  value={createResources}
                  onChange={(e) => setCreateResources(e.target.value)}
                  rows={2}
                />
              </div>

              <div className="space-y-2">
                <Label>Activities</Label>
                <Textarea
                  placeholder="Planned lesson activities..."
                  value={createActivities}
                  onChange={(e) => setCreateActivities(e.target.value)}
                  rows={3}
                />
              </div>

              <div className="space-y-2">
                <Label>Notes</Label>
                <Textarea
                  placeholder="Additional notes or reminders..."
                  value={createNotes}
                  onChange={(e) => setCreateNotes(e.target.value)}
                  rows={2}
                />
              </div>
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => { setCreateOpen(false); resetCreateForm(); }}
                disabled={isPending}
              >
                Cancel
              </Button>
              <Button onClick={handleCreate} disabled={isPending}>
                {isPending ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                    Creating...
                  </>
                ) : (
                  "Create Plan"
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-end">
        <div className="space-y-1">
          <Label className="text-xs text-muted-foreground">Class</Label>
          <Select value={filterClassId} onValueChange={setFilterClassId}>
            <SelectTrigger className="w-full sm:w-[200px]">
              <SelectValue placeholder="All classes" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All classes</SelectItem>
              {classes.map((cls) => (
                <SelectItem
                  key={`filter-${cls.class_id}-${cls.section_id || "main"}`}
                  value={cls.class_id}
                >
                  {cls.class_name}
                  {cls.section_name ? ` - ${cls.section_name}` : ""}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <Label className="text-xs text-muted-foreground">From</Label>
          <Input
            type="date"
            value={filterDateFrom}
            onChange={(e) => setFilterDateFrom(e.target.value)}
            className="w-full sm:w-[160px]"
          />
        </div>
        <div className="space-y-1">
          <Label className="text-xs text-muted-foreground">To</Label>
          <Input
            type="date"
            value={filterDateTo}
            onChange={(e) => setFilterDateTo(e.target.value)}
            className="w-full sm:w-[160px]"
          />
        </div>
        {(filterClassId !== "all" || filterDateFrom || filterDateTo) && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setFilterClassId("all");
              setFilterDateFrom("");
              setFilterDateTo("");
            }}
          >
            Clear filters
          </Button>
        )}
      </div>

      {/* Empty state */}
      {plans.length === 0 && !loading ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <BookOpen className="h-12 w-12 text-muted-foreground/50 mb-3" />
            <p className="text-muted-foreground">No lesson plans found</p>
            <p className="text-xs text-muted-foreground mt-1">
              Click &quot;New Plan&quot; to create your first lesson plan
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Desktop table view */}
          <Card className="hidden md:block">
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b bg-muted/50">
                      <th className="p-3 text-left text-xs font-medium text-muted-foreground">Date</th>
                      <th className="p-3 text-left text-xs font-medium text-muted-foreground">Class</th>
                      <th className="p-3 text-left text-xs font-medium text-muted-foreground">Subject</th>
                      <th className="p-3 text-left text-xs font-medium text-muted-foreground">Topic</th>
                      <th className="p-3 text-left text-xs font-medium text-muted-foreground">Period</th>
                      <th className="p-3 text-left text-xs font-medium text-muted-foreground">Status</th>
                      <th className="p-3 text-right text-xs font-medium text-muted-foreground w-12"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {plans.map((plan) => {
                      const statusCfg = STATUS_CONFIG[plan.status] || STATUS_CONFIG.planned;
                      const StatusIcon = statusCfg.icon;
                      return (
                        <tr key={plan.id} className="border-b last:border-0 hover:bg-muted/30">
                          <td className="p-3 text-sm whitespace-nowrap">
                            {formatDate(plan.date)}
                          </td>
                          <td className="p-3 text-sm">{plan.class_name || "--"}</td>
                          <td className="p-3 text-sm">{plan.subject_name || "--"}</td>
                          <td className="p-3 text-sm font-medium max-w-[250px] truncate">
                            {plan.topic}
                          </td>
                          <td className="p-3 text-sm text-muted-foreground">
                            {plan.period || "--"}
                          </td>
                          <td className="p-3">
                            <Badge className={`text-[10px] ${statusCfg.color}`}>
                              <StatusIcon className="h-3 w-3 mr-1" />
                              {statusCfg.label}
                            </Badge>
                          </td>
                          <td className="p-3 text-right">
                            <PlanActions
                              plan={plan}
                              onEdit={() => openEditDialog(plan)}
                              onStatusChange={handleStatusChange}
                              onDelete={(id) => {
                                setDeletingPlanId(id);
                                setDeleteDialogOpen(true);
                              }}
                            />
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {/* Mobile card view */}
          <div className="md:hidden space-y-3">
            {plans.map((plan) => {
              const statusCfg = STATUS_CONFIG[plan.status] || STATUS_CONFIG.planned;
              const StatusIcon = statusCfg.icon;
              return (
                <Card key={plan.id}>
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{plan.topic}</p>
                        <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
                          <Calendar className="h-3 w-3 shrink-0" />
                          <span>{formatDate(plan.date)}</span>
                          {plan.period && <span>Period {plan.period}</span>}
                        </div>
                        <div className="flex items-center gap-2 mt-1 flex-wrap">
                          <span className="text-xs text-muted-foreground">
                            {plan.class_name || "--"}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            {plan.subject_name || "--"}
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center gap-1 shrink-0">
                        <Badge className={`text-[10px] ${statusCfg.color}`}>
                          <StatusIcon className="h-3 w-3 mr-0.5" />
                          {statusCfg.label}
                        </Badge>
                        <PlanActions
                          plan={plan}
                          onEdit={() => openEditDialog(plan)}
                          onStatusChange={handleStatusChange}
                          onDelete={(id) => {
                            setDeletingPlanId(id);
                            setDeleteDialogOpen(true);
                          }}
                        />
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </>
      )}

      {/* Summary */}
      {plans.length > 0 && (
        <p className="text-xs text-muted-foreground text-center">
          Showing {plans.length} of {totalCount} lesson plan{totalCount !== 1 ? "s" : ""}
        </p>
      )}

      {/* Edit dialog */}
      <Dialog open={editOpen} onOpenChange={(open) => { setEditOpen(open); if (!open) setEditingPlan(null); }}>
        <DialogContent className="max-sm:max-w-[calc(100vw-2rem)] max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit Lesson Plan</DialogTitle>
            <DialogDescription>
              {editingPlan
                ? `${editingPlan.class_name || ""} - ${editingPlan.subject_name || ""} | ${formatDate(editingPlan.date)}`
                : ""}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Topic *</Label>
              <Input
                value={editTopic}
                onChange={(e) => setEditTopic(e.target.value)}
                placeholder="Lesson topic"
              />
            </div>
            <div className="space-y-2">
              <Label>Objectives</Label>
              <Textarea
                value={editObjectives}
                onChange={(e) => setEditObjectives(e.target.value)}
                placeholder="What students should learn..."
                rows={3}
              />
            </div>
            <div className="space-y-2">
              <Label>Resources</Label>
              <Textarea
                value={editResources}
                onChange={(e) => setEditResources(e.target.value)}
                placeholder="Materials and resources needed..."
                rows={2}
              />
            </div>
            <div className="space-y-2">
              <Label>Activities</Label>
              <Textarea
                value={editActivities}
                onChange={(e) => setEditActivities(e.target.value)}
                placeholder="Planned lesson activities..."
                rows={3}
              />
            </div>
            <div className="space-y-2">
              <Label>Notes</Label>
              <Textarea
                value={editNotes}
                onChange={(e) => setEditNotes(e.target.value)}
                placeholder="Additional notes..."
                rows={2}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => { setEditOpen(false); setEditingPlan(null); }}
              disabled={isEditPending}
            >
              Cancel
            </Button>
            <Button onClick={handleEdit} disabled={isEditPending}>
              {isEditPending ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                  Saving...
                </>
              ) : (
                "Save Changes"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete confirmation */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete lesson plan?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently remove this lesson plan. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeletePending}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={isDeletePending}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isDeletePending ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                  Deleting...
                </>
              ) : (
                "Delete"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

// ---- Plan actions dropdown ----

interface PlanActionsProps {
  plan: TeacherLessonPlan;
  onEdit: () => void;
  onStatusChange: (planId: string, status: string) => void;
  onDelete: (planId: string) => void;
}

function PlanActions({ plan, onEdit, onStatusChange, onDelete }: PlanActionsProps) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="h-8 w-8">
          <MoreHorizontal className="h-4 w-4" />
          <span className="sr-only">Actions</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={onEdit}>
          <Edit className="h-4 w-4 mr-2" />
          Edit
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        {plan.status !== "taught" && (
          <DropdownMenuItem onClick={() => onStatusChange(plan.id, "taught")}>
            <CheckCircle2 className="h-4 w-4 mr-2 text-green-600" />
            Mark as Taught
          </DropdownMenuItem>
        )}
        {plan.status !== "planned" && (
          <DropdownMenuItem onClick={() => onStatusChange(plan.id, "planned")}>
            <Clock className="h-4 w-4 mr-2 text-blue-600" />
            Mark as Planned
          </DropdownMenuItem>
        )}
        {plan.status !== "cancelled" && (
          <DropdownMenuItem onClick={() => onStatusChange(plan.id, "cancelled")}>
            <XCircle className="h-4 w-4 mr-2 text-red-600" />
            Mark as Cancelled
          </DropdownMenuItem>
        )}
        <DropdownMenuSeparator />
        <DropdownMenuItem
          className="text-destructive focus:text-destructive"
          onClick={() => onDelete(plan.id)}
        >
          <Trash2 className="h-4 w-4 mr-2" />
          Delete
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
