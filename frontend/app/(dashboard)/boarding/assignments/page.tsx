"use client";

import { useCallback, useEffect, useState, useTransition } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { format } from "date-fns";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Calendar } from "@/components/ui/calendar";
import {
  Search,
  Loader2,
  Users,
  Plus,
  MoreHorizontal,
  Pencil,
  UserMinus,
  CalendarIcon,
} from "lucide-react";
import {
  getAssignments,
  getHouses,
  getDormitories,
  getBeds,
  assignStudent,
  updateAssignment,
  unassignStudent,
} from "@/actions/boarding.action";
import { getStudents } from "@/actions/students.action";
import { getAcademicYears } from "@/actions/academic.action";
import type {
  StudentBoardingDetail,
  House,
  Dormitory,
  Bed,
  StudentListItem,
  AcademicYear,
  BoardingStatus,
} from "@/types";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";

// =========================
// Schemas
// =========================

const assignSchema = z.object({
  student_id: z.string().min(1, "Student is required"),
  house_id: z.string().min(1, "House is required"),
  dormitory_id: z.string().optional(),
  bed_id: z.string().optional(),
  academic_year_id: z.string().min(1, "Academic year is required"),
  check_in_date: z.date({ error: "Check-in date is required" }),
});

type AssignFormData = z.infer<typeof assignSchema>;

const editSchema = z.object({
  house_id: z.string().min(1, "House is required"),
  dormitory_id: z.string().optional(),
  bed_id: z.string().optional(),
  boarding_status: z.enum(["active", "withdrawn", "suspended", "graduated"]),
  check_out_date: z.date().optional().nullable(),
});

type EditFormData = z.infer<typeof editSchema>;

// =========================
// Constants & Helpers
// =========================

const STATUS_OPTIONS: { value: BoardingStatus; label: string }[] = [
  { value: "active", label: "Active" },
  { value: "withdrawn", label: "Withdrawn" },
  { value: "suspended", label: "Suspended" },
  { value: "graduated", label: "Graduated" },
];

function getStatusBadge(status: string) {
  switch (status) {
    case "active":
      return (
        <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
          Active
        </Badge>
      );
    case "withdrawn":
      return <Badge variant="secondary">Withdrawn</Badge>;
    case "suspended":
      return <Badge variant="destructive">Suspended</Badge>;
    case "graduated":
      return (
        <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
          Graduated
        </Badge>
      );
    default:
      return <Badge variant="secondary">{status}</Badge>;
  }
}

// =========================
// Page Component
// =========================

export default function AssignmentsPage() {
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();

  // List state
  const [assignments, setAssignments] = useState<StudentBoardingDetail[]>([]);
  const [total, setTotal] = useState(0);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterHouse, setFilterHouse] = useState("all");
  const [filterStatus, setFilterStatus] = useState("all");

  // Reference data
  const [houses, setHouses] = useState<House[]>([]);
  const [academicYears, setAcademicYears] = useState<AcademicYear[]>([]);
  const [students, setStudents] = useState<StudentListItem[]>([]);

  // Cascading selects state (shared between assign & edit)
  const [dormitories, setDormitories] = useState<Dormitory[]>([]);
  const [beds, setBeds] = useState<Bed[]>([]);
  const [dormitoriesLoading, setDormitoriesLoading] = useState(false);
  const [bedsLoading, setBedsLoading] = useState(false);

  // Dialog state
  const [isAssignOpen, setIsAssignOpen] = useState(false);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [editingAssignment, setEditingAssignment] =
    useState<StudentBoardingDetail | null>(null);
  const [unassignId, setUnassignId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Student search
  const [studentSearch, setStudentSearch] = useState("");
  const [studentsLoading, setStudentsLoading] = useState(false);

  // Forms
  const assignForm = useForm<AssignFormData>({
    resolver: zodResolver(assignSchema),
    defaultValues: {
      student_id: "",
      house_id: "",
      dormitory_id: "",
      bed_id: "",
      academic_year_id: "",
      check_in_date: undefined,
    },
  });

  const editForm = useForm<EditFormData>({
    resolver: zodResolver(editSchema),
    defaultValues: {
      house_id: "",
      dormitory_id: "",
      bed_id: "",
      boarding_status: "active",
      check_out_date: null,
    },
  });

  // Watch house & dormitory for cascading
  const assignHouseId = assignForm.watch("house_id");
  const assignDormitoryId = assignForm.watch("dormitory_id");
  const editHouseId = editForm.watch("house_id");
  const editDormitoryId = editForm.watch("dormitory_id");

  // =========================
  // Load Reference Data
  // =========================

  useEffect(() => {
    startTransition(async () => {
      const [housesRes, yearsRes] = await Promise.all([
        getHouses({ pageSize: 100 }),
        getAcademicYears(false),
      ]);

      if (housesRes.success && housesRes.data) {
        const items = Array.isArray(housesRes.data)
          ? housesRes.data
          : (housesRes.data.items ?? []);
        setHouses(items);
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
      const result = await getAssignments({
        search: searchQuery || undefined,
        houseId: filterHouse !== "all" ? filterHouse : undefined,
        status: filterStatus !== "all" ? filterStatus : undefined,
      });
      if (result.success && result.data) {
        const items = Array.isArray(result.data)
          ? result.data
          : (result.data.items ?? []);
        const count = Array.isArray(result.data)
          ? result.data.length
          : (result.data.total ?? 0);
        setAssignments(items);
        setTotal(count);
      }
    });
  }, [searchQuery, filterHouse, filterStatus]);

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
  // Cascading: House -> Dormitories
  // =========================

  const loadDormitories = useCallback(async (houseId: string) => {
    if (!houseId) {
      setDormitories([]);
      setBeds([]);
      return;
    }
    setDormitoriesLoading(true);
    try {
      const result = await getDormitories({
        houseId,
        isActive: true,
        pageSize: 100,
      });
      if (result.success && result.data) {
        const items = Array.isArray(result.data)
          ? result.data
          : (result.data.items ?? []);
        setDormitories(items);
      } else {
        setDormitories([]);
      }
    } finally {
      setDormitoriesLoading(false);
    }
    setBeds([]);
  }, []);

  const loadBeds = useCallback(async (dormitoryId: string) => {
    if (!dormitoryId) {
      setBeds([]);
      return;
    }
    setBedsLoading(true);
    try {
      const result = await getBeds({
        dormitoryId,
        status: "available",
        pageSize: 100,
      });
      if (result.success && result.data) {
        const items = Array.isArray(result.data)
          ? result.data
          : (result.data.items ?? []);
        setBeds(items);
      } else {
        setBeds([]);
      }
    } finally {
      setBedsLoading(false);
    }
  }, []);

  // Cascade for assign dialog
  useEffect(() => {
    if (isAssignOpen && assignHouseId) {
      assignForm.setValue("dormitory_id", "");
      assignForm.setValue("bed_id", "");
      loadDormitories(assignHouseId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [assignHouseId, isAssignOpen]);

  useEffect(() => {
    if (isAssignOpen && assignDormitoryId) {
      assignForm.setValue("bed_id", "");
      loadBeds(assignDormitoryId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [assignDormitoryId, isAssignOpen]);

  // Cascade for edit dialog
  useEffect(() => {
    if (isEditOpen && editHouseId && editingAssignment) {
      // Only clear downstream if user changed the house
      if (editHouseId !== editingAssignment.house_id) {
        editForm.setValue("dormitory_id", "");
        editForm.setValue("bed_id", "");
      }
      loadDormitories(editHouseId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editHouseId, isEditOpen]);

  useEffect(() => {
    if (isEditOpen && editDormitoryId && editingAssignment) {
      if (editDormitoryId !== editingAssignment.dormitory_id) {
        editForm.setValue("bed_id", "");
      }
      loadBeds(editDormitoryId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editDormitoryId, isEditOpen]);

  // =========================
  // Dialog Handlers
  // =========================

  const handleOpenAssign = () => {
    assignForm.reset({
      student_id: "",
      house_id: "",
      dormitory_id: "",
      bed_id: "",
      academic_year_id:
        academicYears.find((y) => y.is_current || y.status === "active")?.id ??
        "",
      check_in_date: undefined,
    });
    setStudentSearch("");
    setStudents([]);
    setDormitories([]);
    setBeds([]);
    setIsAssignOpen(true);
  };

  const handleOpenEdit = (assignment: StudentBoardingDetail) => {
    setEditingAssignment(assignment);
    editForm.reset({
      house_id: assignment.house_id,
      dormitory_id: assignment.dormitory_id ?? "",
      bed_id: assignment.bed_id ?? "",
      boarding_status: assignment.boarding_status,
      check_out_date: assignment.check_out_date
        ? new Date(assignment.check_out_date)
        : null,
    });
    // Pre-load dormitories and beds for current values
    if (assignment.house_id) {
      loadDormitories(assignment.house_id).then(() => {
        if (assignment.dormitory_id) {
          loadBeds(assignment.dormitory_id);
        }
      });
    }
    setIsEditOpen(true);
  };

  // =========================
  // Submit Handlers
  // =========================

  const onAssignSubmit = async (data: AssignFormData) => {
    setIsSubmitting(true);
    try {
      const result = await assignStudent({
        student_id: data.student_id,
        house_id: data.house_id,
        dormitory_id: data.dormitory_id || undefined,
        bed_id: data.bed_id || undefined,
        academic_year_id: data.academic_year_id,
        check_in_date: format(data.check_in_date, "yyyy-MM-dd"),
      });
      if (result.success) {
        toast({
          title: "Student assigned",
          description: "Student has been assigned to boarding.",
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
      const result = await updateAssignment(editingAssignment.id, {
        house_id: data.house_id,
        dormitory_id: data.dormitory_id || undefined,
        bed_id: data.bed_id || undefined,
        boarding_status: data.boarding_status,
        check_out_date: data.check_out_date
          ? format(data.check_out_date, "yyyy-MM-dd")
          : undefined,
      });
      if (result.success) {
        toast({
          title: "Assignment updated",
          description: "Boarding assignment has been updated.",
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

  const handleUnassign = async () => {
    if (!unassignId) return;
    setIsSubmitting(true);
    try {
      const result = await unassignStudent(unassignId);
      if (result.success) {
        toast({ title: "Student unassigned from boarding" });
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
      setUnassignId(null);
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
            Boarding Assignments
          </h1>
          <p className="text-muted-foreground">
            View and manage student boarding assignments
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
            <Select value={filterHouse} onValueChange={setFilterHouse}>
              <SelectTrigger className="w-full sm:w-[200px]">
                <SelectValue placeholder="House" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Houses</SelectItem>
                {houses.map((h) => (
                  <SelectItem key={h.id} value={h.id}>
                    {h.name}
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
                {STATUS_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
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
                    <TableHead>House</TableHead>
                    <TableHead className="hidden md:table-cell">
                      Dormitory
                    </TableHead>
                    <TableHead className="hidden md:table-cell">Bed</TableHead>
                    <TableHead className="hidden lg:table-cell">
                      Academic Year
                    </TableHead>
                    <TableHead className="hidden lg:table-cell">
                      Check-in
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
                      <TableCell>{a.house_name || "--"}</TableCell>
                      <TableCell className="hidden md:table-cell">
                        {a.dormitory_name || "--"}
                      </TableCell>
                      <TableCell className="hidden md:table-cell">
                        {a.bed_number || "--"}
                      </TableCell>
                      <TableCell className="hidden lg:table-cell">
                        {a.academic_year_name || "--"}
                      </TableCell>
                      <TableCell className="hidden lg:table-cell">
                        {a.check_in_date || "--"}
                      </TableCell>
                      <TableCell>
                        {getStatusBadge(a.boarding_status)}
                      </TableCell>
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
                            <DropdownMenuItem
                              onClick={() => setUnassignId(a.id)}
                              className="text-destructive focus:text-destructive"
                            >
                              <UserMinus className="mr-2 h-4 w-4" />
                              Unassign
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
            <div className="flex h-[200px] flex-col items-center justify-center gap-2 text-muted-foreground">
              <Users className="h-12 w-12" />
              <p>No boarding assignments found</p>
              <p className="text-center text-sm max-w-md">
                Assign students to boarding houses to track their
                accommodation.
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
            <DialogTitle>Assign Student to Boarding</DialogTitle>
            <DialogDescription>
              Select a student and assign them to a house, dormitory, and bed.
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

              {/* House */}
              <FormField
                control={assignForm.control}
                name="house_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>House *</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      value={field.value}
                    >
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Select house" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {houses
                          .filter((h) => h.is_active)
                          .map((house) => (
                            <SelectItem key={house.id} value={house.id}>
                              {house.name}
                            </SelectItem>
                          ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Dormitory (cascaded from house) */}
              <FormField
                control={assignForm.control}
                name="dormitory_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Dormitory</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      value={field.value ?? ""}
                      disabled={!assignHouseId || dormitoriesLoading}
                    >
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue
                            placeholder={
                              dormitoriesLoading
                                ? "Loading dormitories..."
                                : !assignHouseId
                                  ? "Select a house first"
                                  : "Select dormitory"
                            }
                          />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {dormitories.map((dorm) => (
                          <SelectItem key={dorm.id} value={dorm.id}>
                            {dorm.name}
                            {dorm.floor ? ` (${dorm.floor})` : ""}
                          </SelectItem>
                        ))}
                        {!dormitoriesLoading && dormitories.length === 0 && assignHouseId && (
                          <div className="px-3 py-2 text-sm text-muted-foreground">
                            No dormitories found for this house
                          </div>
                        )}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Bed (cascaded from dormitory) */}
              <FormField
                control={assignForm.control}
                name="bed_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Bed</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      value={field.value ?? ""}
                      disabled={!assignDormitoryId || bedsLoading}
                    >
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue
                            placeholder={
                              bedsLoading
                                ? "Loading beds..."
                                : !assignDormitoryId
                                  ? "Select a dormitory first"
                                  : "Select bed"
                            }
                          />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {beds.map((bed) => (
                          <SelectItem key={bed.id} value={bed.id}>
                            Bed {bed.bed_number} ({bed.bed_type.replace("_", " ")})
                          </SelectItem>
                        ))}
                        {!bedsLoading && beds.length === 0 && assignDormitoryId && (
                          <div className="px-3 py-2 text-sm text-muted-foreground">
                            No available beds in this dormitory
                          </div>
                        )}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Check-in Date */}
              <FormField
                control={assignForm.control}
                name="check_in_date"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Check-in Date *</FormLabel>
                    <Popover>
                      <PopoverTrigger asChild>
                        <FormControl>
                          <Button
                            variant="outline"
                            className={cn(
                              "w-full justify-start text-left font-normal",
                              !field.value && "text-muted-foreground"
                            )}
                          >
                            <CalendarIcon className="mr-2 h-4 w-4" />
                            {field.value
                              ? format(field.value, "dd/MM/yyyy")
                              : "Select date"}
                          </Button>
                        </FormControl>
                      </PopoverTrigger>
                      <PopoverContent className="w-auto p-0" align="start">
                        <Calendar
                          mode="single"
                          selected={field.value}
                          onSelect={field.onChange}
                        />
                      </PopoverContent>
                    </Popover>
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
              Update boarding assignment for{" "}
              {editingAssignment?.student_name ?? "student"}.
            </DialogDescription>
          </DialogHeader>
          <Form {...editForm}>
            <form
              onSubmit={editForm.handleSubmit(onEditSubmit)}
              className="space-y-4"
            >
              {/* House */}
              <FormField
                control={editForm.control}
                name="house_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>House *</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      value={field.value}
                    >
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Select house" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {houses
                          .filter((h) => h.is_active)
                          .map((house) => (
                            <SelectItem key={house.id} value={house.id}>
                              {house.name}
                            </SelectItem>
                          ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Dormitory */}
              <FormField
                control={editForm.control}
                name="dormitory_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Dormitory</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      value={field.value ?? ""}
                      disabled={!editHouseId || dormitoriesLoading}
                    >
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue
                            placeholder={
                              dormitoriesLoading
                                ? "Loading dormitories..."
                                : !editHouseId
                                  ? "Select a house first"
                                  : "Select dormitory"
                            }
                          />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {dormitories.map((dorm) => (
                          <SelectItem key={dorm.id} value={dorm.id}>
                            {dorm.name}
                            {dorm.floor ? ` (${dorm.floor})` : ""}
                          </SelectItem>
                        ))}
                        {!dormitoriesLoading && dormitories.length === 0 && editHouseId && (
                          <div className="px-3 py-2 text-sm text-muted-foreground">
                            No dormitories found for this house
                          </div>
                        )}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Bed */}
              <FormField
                control={editForm.control}
                name="bed_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Bed</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      value={field.value ?? ""}
                      disabled={!editDormitoryId || bedsLoading}
                    >
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue
                            placeholder={
                              bedsLoading
                                ? "Loading beds..."
                                : !editDormitoryId
                                  ? "Select a dormitory first"
                                  : "Select bed"
                            }
                          />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {beds.map((bed) => (
                          <SelectItem key={bed.id} value={bed.id}>
                            Bed {bed.bed_number} ({bed.bed_type.replace("_", " ")})
                          </SelectItem>
                        ))}
                        {!bedsLoading && beds.length === 0 && editDormitoryId && (
                          <div className="px-3 py-2 text-sm text-muted-foreground">
                            No available beds in this dormitory
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
                name="boarding_status"
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

              {/* Check-out Date (optional) */}
              <FormField
                control={editForm.control}
                name="check_out_date"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Check-out Date</FormLabel>
                    <div className="flex gap-2">
                      <Popover>
                        <PopoverTrigger asChild>
                          <FormControl>
                            <Button
                              variant="outline"
                              className={cn(
                                "flex-1 justify-start text-left font-normal",
                                !field.value && "text-muted-foreground"
                              )}
                            >
                              <CalendarIcon className="mr-2 h-4 w-4" />
                              {field.value
                                ? format(field.value, "dd/MM/yyyy")
                                : "No check-out date"}
                            </Button>
                          </FormControl>
                        </PopoverTrigger>
                        <PopoverContent
                          className="w-auto p-0"
                          align="start"
                        >
                          <Calendar
                            mode="single"
                            selected={field.value ?? undefined}
                            onSelect={field.onChange}
                          />
                        </PopoverContent>
                      </Popover>
                      {field.value && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => field.onChange(null)}
                        >
                          Clear
                        </Button>
                      )}
                    </div>
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
      {/* Unassign Confirmation     */}
      {/* ========================= */}
      <AlertDialog
        open={!!unassignId}
        onOpenChange={() => setUnassignId(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Unassign Student?</AlertDialogTitle>
            <AlertDialogDescription>
              This will remove the student from their boarding assignment. The
              bed will become available for other students.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isSubmitting}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleUnassign}
              disabled={isSubmitting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isSubmitting && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Unassign
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
