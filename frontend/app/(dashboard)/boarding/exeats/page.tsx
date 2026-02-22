"use client";

import { useEffect, useState, useTransition, useCallback } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { format } from "date-fns";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
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
import { Calendar } from "@/components/ui/calendar";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Plus,
  Loader2,
  DoorOpen,
  MoreHorizontal,
  Eye,
  CheckCircle2,
  XCircle,
  RotateCcw,
  CalendarIcon,
  ChevronsUpDown,
  Check,
  Phone,
  User,
  Clock,
  FileText,
} from "lucide-react";

import {
  getExeats,
  getExeat,
  createExeat,
  approveExeat,
  activateExeat,
  recordReturn,
  getAssignments,
} from "@/actions/boarding.action";
import type {
  ExeatDetail,
  ExeatType,
  ExeatStatus,
  StudentBoardingDetail,
} from "@/types";
import { useToast } from "@/hooks/use-toast";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";

// -------------------------------------------------------------------
// Constants
// -------------------------------------------------------------------

const EXEAT_TYPES: { value: ExeatType; label: string }[] = [
  { value: "weekend", label: "Weekend" },
  { value: "medical", label: "Medical" },
  { value: "emergency", label: "Emergency" },
  { value: "funeral", label: "Funeral" },
  { value: "other", label: "Other" },
];

// -------------------------------------------------------------------
// Badge helpers
// -------------------------------------------------------------------

function getExeatStatusBadge(status: ExeatStatus | string) {
  switch (status) {
    case "pending":
      return <Badge variant="secondary">Pending</Badge>;
    case "approved":
      return (
        <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
          Approved
        </Badge>
      );
    case "active":
      return <Badge>Active</Badge>;
    case "overdue":
      return <Badge variant="destructive">Overdue</Badge>;
    case "returned":
      return (
        <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
          Returned
        </Badge>
      );
    case "denied":
      return <Badge variant="outline">Denied</Badge>;
    default:
      return <Badge variant="secondary">{status}</Badge>;
  }
}

function getExeatTypeBadge(type: ExeatType | string) {
  switch (type) {
    case "weekend":
      return <Badge variant="outline">Weekend</Badge>;
    case "medical":
      return (
        <Badge className="bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200">
          Medical
        </Badge>
      );
    case "emergency":
      return <Badge variant="destructive">Emergency</Badge>;
    case "funeral":
      return (
        <Badge className="bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200">
          Funeral
        </Badge>
      );
    default:
      return (
        <Badge variant="outline" className="capitalize">
          {type}
        </Badge>
      );
  }
}

// -------------------------------------------------------------------
// Zod schemas
// -------------------------------------------------------------------

const createExeatSchema = z
  .object({
    student_id: z.string().min(1, "Please select a student"),
    exeat_type: z.enum(["weekend", "medical", "emergency", "funeral", "other"], {
      message: "Please select an exeat type",
    }),
    reason: z.string().min(5, "Reason must be at least 5 characters"),
    start_date: z.date({ message: "Departure date is required" }),
    end_date: z.date({ message: "Expected return date is required" }),
    guardian_phone: z
      .string()
      .optional()
      .refine(
        (val) => !val || /^(\+233|0)\d{9}$/.test(val.replace(/\s/g, "")),
        "Use +233XXXXXXXXX or 0XXXXXXXXX format"
      ),
    notes: z.string().optional(),
  })
  .refine((data) => data.end_date >= data.start_date, {
    message: "Return date must be on or after departure date",
    path: ["end_date"],
  });

type CreateExeatFormData = z.infer<typeof createExeatSchema>;

// -------------------------------------------------------------------
// Main page component
// -------------------------------------------------------------------

export default function ExeatsPage() {
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();

  // List state
  const [exeats, setExeats] = useState<ExeatDetail[]>([]);
  const [total, setTotal] = useState(0);
  const [activeTab, setActiveTab] = useState("all");

  // Dialog state
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [detailExeat, setDetailExeat] = useState<ExeatDetail | null>(null);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [confirmAction, setConfirmAction] = useState<{
    type: "approve" | "deny" | "activate" | "return";
    exeat: ExeatDetail;
  } | null>(null);

  // Student search state for create form
  const [boardingStudents, setBoardingStudents] = useState<StudentBoardingDetail[]>([]);
  const [studentSearchOpen, setStudentSearchOpen] = useState(false);
  const [isLoadingStudents, setIsLoadingStudents] = useState(false);

  // Submitting state
  const [isSubmitting, setIsSubmitting] = useState(false);

  // -------------------------------------------------------------------
  // Create form
  // -------------------------------------------------------------------

  const createForm = useForm<CreateExeatFormData>({
    resolver: zodResolver(createExeatSchema),
    defaultValues: {
      student_id: "",
      exeat_type: "weekend",
      reason: "",
      guardian_phone: "",
      notes: "",
    },
  });

  // -------------------------------------------------------------------
  // Data loading
  // -------------------------------------------------------------------

  const loadExeats = useCallback(() => {
    startTransition(async () => {
      const statusFilter = activeTab !== "all" ? activeTab : undefined;
      const result = await getExeats({ status: statusFilter, pageSize: 50 });
      if (result.success && result.data) {
        const data = result.data;
        const items = Array.isArray(data) ? data : (data.items ?? []);
        const count = Array.isArray(data) ? data.length : (data.total ?? 0);
        setExeats(items);
        setTotal(count);
      }
    });
  }, [activeTab]);

  useEffect(() => {
    loadExeats();
  }, [loadExeats]);

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

  // -------------------------------------------------------------------
  // Actions
  // -------------------------------------------------------------------

  const handleCreateExeat = async (data: CreateExeatFormData) => {
    setIsSubmitting(true);
    try {
      const result = await createExeat({
        student_id: data.student_id,
        exeat_type: data.exeat_type,
        reason: data.reason,
        start_date: format(data.start_date, "yyyy-MM-dd"),
        end_date: format(data.end_date, "yyyy-MM-dd"),
        guardian_phone: data.guardian_phone || undefined,
        notes: data.notes || undefined,
      });
      if (result.success) {
        toast({ title: "Exeat request created" });
        setIsCreateOpen(false);
        createForm.reset();
        loadExeats();
      } else {
        toast({ title: "Error", description: result.error, variant: "destructive" });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleViewDetail = async (exeatId: string) => {
    setIsDetailLoading(true);
    const result = await getExeat(exeatId);
    if (result.success && result.data) {
      setDetailExeat(result.data);
    } else {
      toast({
        title: "Error",
        description: result.error || "Failed to load exeat details",
        variant: "destructive",
      });
    }
    setIsDetailLoading(false);
  };

  const handleConfirmAction = async () => {
    if (!confirmAction) return;
    setIsSubmitting(true);
    try {
      const { type, exeat } = confirmAction;
      let result;

      switch (type) {
        case "approve":
          result = await approveExeat(exeat.id, { status: "approved" });
          break;
        case "deny":
          result = await approveExeat(exeat.id, { status: "denied" });
          break;
        case "activate":
          result = await activateExeat(exeat.id);
          break;
        case "return": {
          const today = format(new Date(), "yyyy-MM-dd");
          result = await recordReturn(exeat.id, { actual_return_date: today });
          break;
        }
      }

      if (result.success) {
        const messages: Record<typeof type, string> = {
          approve: "Exeat approved",
          deny: "Exeat denied",
          activate: "Exeat activated",
          return: "Return recorded",
        };
        toast({ title: messages[type] });
        loadExeats();
      } else {
        toast({ title: "Error", description: result.error, variant: "destructive" });
      }
    } finally {
      setIsSubmitting(false);
      setConfirmAction(null);
    }
  };

  // -------------------------------------------------------------------
  // Helpers
  // -------------------------------------------------------------------

  const getSelectedStudentName = (studentId: string): string => {
    const student = boardingStudents.find((s) => s.student_id === studentId);
    return student?.student_name || "";
  };

  const getActionLabel = (type: string): string => {
    switch (type) {
      case "approve":
        return "Approve Exeat";
      case "deny":
        return "Deny Exeat";
      case "activate":
        return "Activate Exeat";
      case "return":
        return "Record Return";
      default:
        return "Confirm";
    }
  };

  const getActionDescription = (type: string): string => {
    switch (type) {
      case "approve":
        return "This will approve the exeat request, allowing the student to leave on the scheduled date.";
      case "deny":
        return "This will deny the exeat request. The student will not be permitted to leave.";
      case "activate":
        return "This will mark the exeat as active, indicating the student has departed.";
      case "return":
        return "This will record the student as returned. Today's date will be used as the return date.";
      default:
        return "Are you sure you want to proceed?";
    }
  };

  // -------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Exeats</h1>
          <p className="text-muted-foreground">
            Manage student leave permissions and exeat requests
          </p>
        </div>
        <Button
          onClick={() => {
            loadBoardingStudents();
            setIsCreateOpen(true);
          }}
        >
          <Plus className="mr-2 h-4 w-4" />
          Request Exeat
        </Button>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="all">All</TabsTrigger>
          <TabsTrigger value="pending">Pending</TabsTrigger>
          <TabsTrigger value="approved">Approved</TabsTrigger>
          <TabsTrigger value="active">Active</TabsTrigger>
          <TabsTrigger value="overdue">Overdue</TabsTrigger>
          <TabsTrigger value="returned">Returned</TabsTrigger>
        </TabsList>

        <TabsContent value={activeTab} className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle>Exeats</CardTitle>
              <CardDescription>
                {total} exeat{total !== 1 ? "s" : ""} found
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isPending ? (
                <div className="flex h-[200px] items-center justify-center">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
              ) : exeats.length > 0 ? (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Student</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead className="hidden sm:table-cell">Reason</TableHead>
                        <TableHead>Departure</TableHead>
                        <TableHead>Return</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {exeats.map((exeat) => (
                        <TableRow key={exeat.id}>
                          <TableCell className="font-medium">
                            {exeat.student_name || "--"}
                          </TableCell>
                          <TableCell>{getExeatTypeBadge(exeat.exeat_type)}</TableCell>
                          <TableCell className="hidden max-w-[200px] truncate sm:table-cell">
                            {exeat.reason}
                          </TableCell>
                          <TableCell className="whitespace-nowrap">
                            {formatDate(exeat.start_date)}
                          </TableCell>
                          <TableCell className="whitespace-nowrap">
                            {formatDate(exeat.end_date)}
                          </TableCell>
                          <TableCell>{getExeatStatusBadge(exeat.status)}</TableCell>
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
                                  onClick={() => handleViewDetail(exeat.id)}
                                >
                                  <Eye className="mr-2 h-4 w-4" />
                                  View Details
                                </DropdownMenuItem>

                                {/* Pending actions */}
                                {exeat.status === "pending" && (
                                  <>
                                    <DropdownMenuSeparator />
                                    <DropdownMenuItem
                                      onClick={() =>
                                        setConfirmAction({ type: "approve", exeat })
                                      }
                                    >
                                      <CheckCircle2 className="mr-2 h-4 w-4 text-green-600" />
                                      Approve
                                    </DropdownMenuItem>
                                    <DropdownMenuItem
                                      onClick={() =>
                                        setConfirmAction({ type: "deny", exeat })
                                      }
                                    >
                                      <XCircle className="mr-2 h-4 w-4 text-red-600" />
                                      Deny
                                    </DropdownMenuItem>
                                  </>
                                )}

                                {/* Approved actions */}
                                {exeat.status === "approved" && (
                                  <>
                                    <DropdownMenuSeparator />
                                    <DropdownMenuItem
                                      onClick={() =>
                                        setConfirmAction({ type: "activate", exeat })
                                      }
                                    >
                                      <DoorOpen className="mr-2 h-4 w-4 text-blue-600" />
                                      Activate (Student Departed)
                                    </DropdownMenuItem>
                                  </>
                                )}

                                {/* Active / Overdue actions */}
                                {(exeat.status === "active" ||
                                  exeat.status === "overdue") && (
                                  <>
                                    <DropdownMenuSeparator />
                                    <DropdownMenuItem
                                      onClick={() =>
                                        setConfirmAction({ type: "return", exeat })
                                      }
                                    >
                                      <RotateCcw className="mr-2 h-4 w-4 text-green-600" />
                                      Record Return
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
                  <DoorOpen className="h-12 w-12" />
                  <p className="font-medium">No exeats found</p>
                  <p className="text-sm">
                    {activeTab === "all"
                      ? "Create an exeat request to get started."
                      : `No ${activeTab} exeats at this time.`}
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* ============================================================= */}
      {/* Create Exeat Dialog                                            */}
      {/* ============================================================= */}
      <Dialog
        open={isCreateOpen}
        onOpenChange={(open) => {
          if (!open) {
            createForm.reset();
          }
          setIsCreateOpen(open);
        }}
      >
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-[560px]">
          <DialogHeader>
            <DialogTitle>Request Exeat</DialogTitle>
            <DialogDescription>
              Submit a leave request for a boarding student.
            </DialogDescription>
          </DialogHeader>
          <Form {...createForm}>
            <form
              onSubmit={createForm.handleSubmit(handleCreateExeat)}
              className="space-y-4"
            >
              {/* Student select */}
              <FormField
                control={createForm.control}
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
                              ? getSelectedStudentName(field.value) ||
                                "Student selected"
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

              {/* Exeat type */}
              <FormField
                control={createForm.control}
                name="exeat_type"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Exeat Type *</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Select type" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {EXEAT_TYPES.map((t) => (
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

              {/* Reason */}
              <FormField
                control={createForm.control}
                name="reason"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Reason *</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Describe the reason for the exeat request..."
                        rows={3}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Date pickers */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <FormField
                  control={createForm.control}
                  name="start_date"
                  render={({ field }) => (
                    <FormItem className="flex flex-col">
                      <FormLabel>Departure Date *</FormLabel>
                      <Popover>
                        <PopoverTrigger asChild>
                          <FormControl>
                            <Button
                              variant="outline"
                              className={cn(
                                "w-full pl-3 text-left font-normal",
                                !field.value && "text-muted-foreground"
                              )}
                            >
                              {field.value
                                ? format(field.value, "dd/MM/yyyy")
                                : "DD/MM/YYYY"}
                              <CalendarIcon className="ml-auto h-4 w-4 opacity-50" />
                            </Button>
                          </FormControl>
                        </PopoverTrigger>
                        <PopoverContent className="w-auto p-0" align="start">
                          <Calendar
                            mode="single"
                            selected={field.value}
                            onSelect={field.onChange}
                            disabled={(date) => date < new Date(new Date().setHours(0, 0, 0, 0))}
                          />
                        </PopoverContent>
                      </Popover>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={createForm.control}
                  name="end_date"
                  render={({ field }) => (
                    <FormItem className="flex flex-col">
                      <FormLabel>Expected Return *</FormLabel>
                      <Popover>
                        <PopoverTrigger asChild>
                          <FormControl>
                            <Button
                              variant="outline"
                              className={cn(
                                "w-full pl-3 text-left font-normal",
                                !field.value && "text-muted-foreground"
                              )}
                            >
                              {field.value
                                ? format(field.value, "dd/MM/yyyy")
                                : "DD/MM/YYYY"}
                              <CalendarIcon className="ml-auto h-4 w-4 opacity-50" />
                            </Button>
                          </FormControl>
                        </PopoverTrigger>
                        <PopoverContent className="w-auto p-0" align="start">
                          <Calendar
                            mode="single"
                            selected={field.value}
                            onSelect={field.onChange}
                            disabled={(date) => {
                              const startDate = createForm.getValues("start_date");
                              if (startDate) {
                                return date < startDate;
                              }
                              return date < new Date(new Date().setHours(0, 0, 0, 0));
                            }}
                          />
                        </PopoverContent>
                      </Popover>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              {/* Guardian phone */}
              <FormField
                control={createForm.control}
                name="guardian_phone"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Guardian Contact Phone</FormLabel>
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

              {/* Notes */}
              <FormField
                control={createForm.control}
                name="notes"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Additional Notes</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Any additional information (destination, pickup details, etc.)"
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
                  onClick={() => setIsCreateOpen(false)}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting && (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  )}
                  Submit Request
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* ============================================================= */}
      {/* Exeat Detail Dialog                                            */}
      {/* ============================================================= */}
      <Dialog
        open={!!detailExeat || isDetailLoading}
        onOpenChange={(open) => {
          if (!open) {
            setDetailExeat(null);
            setIsDetailLoading(false);
          }
        }}
      >
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-[560px]">
          {isDetailLoading ? (
            <div className="flex h-[200px] items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : detailExeat ? (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-3">
                  Exeat Details
                  {getExeatStatusBadge(detailExeat.status)}
                </DialogTitle>
                <DialogDescription>
                  {detailExeat.student_name || "Unknown Student"} &mdash;{" "}
                  {getExeatTypeBadge(detailExeat.exeat_type)}
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-4">
                {/* Student & Requester */}
                <div className="rounded-lg border p-4 space-y-3">
                  <div className="flex items-start gap-3">
                    <User className="mt-0.5 h-4 w-4 text-muted-foreground shrink-0" />
                    <div>
                      <p className="text-sm font-medium">Student</p>
                      <p className="text-sm text-muted-foreground">
                        {detailExeat.student_name || "Unknown"}
                      </p>
                    </div>
                  </div>
                  {detailExeat.requested_by_name && (
                    <div className="flex items-start gap-3">
                      <FileText className="mt-0.5 h-4 w-4 text-muted-foreground shrink-0" />
                      <div>
                        <p className="text-sm font-medium">Requested By</p>
                        <p className="text-sm text-muted-foreground">
                          {detailExeat.requested_by_name}
                        </p>
                      </div>
                    </div>
                  )}
                  {detailExeat.approved_by_name && (
                    <div className="flex items-start gap-3">
                      <CheckCircle2 className="mt-0.5 h-4 w-4 text-muted-foreground shrink-0" />
                      <div>
                        <p className="text-sm font-medium">
                          {detailExeat.status === "denied"
                            ? "Denied By"
                            : "Approved By"}
                        </p>
                        <p className="text-sm text-muted-foreground">
                          {detailExeat.approved_by_name}
                        </p>
                      </div>
                    </div>
                  )}
                </div>

                {/* Dates */}
                <div className="rounded-lg border p-4 space-y-3">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="flex items-start gap-3">
                      <CalendarIcon className="mt-0.5 h-4 w-4 text-muted-foreground shrink-0" />
                      <div>
                        <p className="text-sm font-medium">Departure</p>
                        <p className="text-sm text-muted-foreground">
                          {formatDate(detailExeat.start_date)}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <CalendarIcon className="mt-0.5 h-4 w-4 text-muted-foreground shrink-0" />
                      <div>
                        <p className="text-sm font-medium">Expected Return</p>
                        <p className="text-sm text-muted-foreground">
                          {formatDate(detailExeat.end_date)}
                        </p>
                      </div>
                    </div>
                  </div>
                  {detailExeat.actual_return_date && (
                    <div className="flex items-start gap-3">
                      <RotateCcw className="mt-0.5 h-4 w-4 text-green-600 shrink-0" />
                      <div>
                        <p className="text-sm font-medium">Actual Return</p>
                        <p className="text-sm text-muted-foreground">
                          {formatDate(detailExeat.actual_return_date)}
                        </p>
                      </div>
                    </div>
                  )}
                </div>

                {/* Reason */}
                <div className="rounded-lg border p-4 space-y-2">
                  <p className="text-sm font-medium">Reason</p>
                  <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                    {detailExeat.reason}
                  </p>
                </div>

                {/* Guardian Phone */}
                {detailExeat.guardian_phone && (
                  <div className="rounded-lg border p-4">
                    <div className="flex items-start gap-3">
                      <Phone className="mt-0.5 h-4 w-4 text-muted-foreground shrink-0" />
                      <div>
                        <p className="text-sm font-medium">Guardian Contact</p>
                        <p className="text-sm text-muted-foreground">
                          {detailExeat.guardian_phone}
                        </p>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {detailExeat.guardian_notified
                            ? "Guardian has been notified"
                            : "Guardian not yet notified"}
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                {/* Notes */}
                {detailExeat.notes && (
                  <div className="rounded-lg border p-4 space-y-2">
                    <p className="text-sm font-medium">Notes</p>
                    <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                      {detailExeat.notes}
                    </p>
                  </div>
                )}

                {/* Timeline */}
                <div className="rounded-lg border p-4 space-y-2">
                  <p className="text-sm font-medium">Timeline</p>
                  <div className="space-y-2">
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Clock className="h-3 w-3 shrink-0" />
                      <span>
                        Created {formatDate(detailExeat.created_at)}
                      </span>
                    </div>
                    {detailExeat.updated_at !== detailExeat.created_at && (
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <Clock className="h-3 w-3 shrink-0" />
                        <span>
                          Updated {formatDate(detailExeat.updated_at)}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Detail dialog actions */}
              <DialogFooter className="flex-col gap-2 sm:flex-row">
                {detailExeat.status === "pending" && (
                  <>
                    <Button
                      variant="outline"
                      onClick={() => {
                        setDetailExeat(null);
                        setConfirmAction({ type: "deny", exeat: detailExeat });
                      }}
                    >
                      <XCircle className="mr-2 h-4 w-4" />
                      Deny
                    </Button>
                    <Button
                      onClick={() => {
                        setDetailExeat(null);
                        setConfirmAction({
                          type: "approve",
                          exeat: detailExeat,
                        });
                      }}
                    >
                      <CheckCircle2 className="mr-2 h-4 w-4" />
                      Approve
                    </Button>
                  </>
                )}
                {detailExeat.status === "approved" && (
                  <Button
                    onClick={() => {
                      setDetailExeat(null);
                      setConfirmAction({
                        type: "activate",
                        exeat: detailExeat,
                      });
                    }}
                  >
                    <DoorOpen className="mr-2 h-4 w-4" />
                    Activate
                  </Button>
                )}
                {(detailExeat.status === "active" ||
                  detailExeat.status === "overdue") && (
                  <Button
                    onClick={() => {
                      setDetailExeat(null);
                      setConfirmAction({
                        type: "return",
                        exeat: detailExeat,
                      });
                    }}
                  >
                    <RotateCcw className="mr-2 h-4 w-4" />
                    Record Return
                  </Button>
                )}
              </DialogFooter>
            </>
          ) : null}
        </DialogContent>
      </Dialog>

      {/* ============================================================= */}
      {/* Confirmation AlertDialog                                       */}
      {/* ============================================================= */}
      <AlertDialog
        open={!!confirmAction}
        onOpenChange={(open) => {
          if (!open) setConfirmAction(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {confirmAction ? getActionLabel(confirmAction.type) : "Confirm"}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {confirmAction && (
                <>
                  <span className="font-medium">
                    {confirmAction.exeat.student_name || "Unknown Student"}
                  </span>
                  {" "}
                  &mdash;{" "}
                  {getActionDescription(confirmAction.type)}
                </>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isSubmitting}>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmAction} disabled={isSubmitting}>
              {isSubmitting && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              {confirmAction ? getActionLabel(confirmAction.type) : "Confirm"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
