"use client";

import { useState, useTransition, useEffect } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  UserCheck,
  Plus,
  Trash2,
  Loader2,
  Search,
  GraduationCap,
  BookOpen,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
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
import { Label } from "@/components/ui/label";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";

import {
  getSectionStaff,
  assignStaffToSection,
  updateStaffAssignment,
  removeStaffFromSection,
} from "@/actions/staff.action";
import type { Class, ClassSection, ClassSubject, StaffListItem, StaffAssignment, Subject } from "@/types";

interface TeacherAssignmentsManagementProps {
  classData: Class;
  sections: ClassSection[];
  allTeachers: StaffListItem[];
  classSubjects: ClassSubject[];
}

interface AssignmentWithDetails extends StaffAssignment {
  teacher_name: string;
  teacher_photo?: string;
  teacher_email?: string;
  subject_name?: string;
  subject_code?: string;
}

export function TeacherAssignmentsManagement({
  classData,
  sections,
  allTeachers,
  classSubjects,
}: TeacherAssignmentsManagementProps) {
  const [isPending, startTransition] = useTransition();
  const [selectedSection, setSelectedSection] = useState<string | null>(
    sections.length > 0 ? sections[0].id : null
  );
  const [assignments, setAssignments] = useState<AssignmentWithDetails[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [removeDialogOpen, setRemoveDialogOpen] = useState(false);
  const [selectedAssignment, setSelectedAssignment] = useState<AssignmentWithDetails | null>(null);

  // Form state for adding assignment
  const [formData, setFormData] = useState({
    staff_id: "",
    subject_id: "",
    is_class_teacher: false,
  });

  // Load assignments when section changes
  useEffect(() => {
    if (selectedSection) {
      loadAssignments(selectedSection);
    }
  }, [selectedSection]);

  const loadAssignments = async (sectionId: string) => {
    startTransition(async () => {
      const result = await getSectionStaff(sectionId);
      if (result.success && result.data) {
        // Enrich with teacher details
        const enriched = result.data.map((assignment) => {
          const teacher = allTeachers.find((t) => t.id === assignment.staff_id);
          const classSubject = classSubjects.find((cs) => cs.subject_id === assignment.subject_id);
          return {
            ...assignment,
            teacher_name: teacher
              ? `${teacher.first_name} ${teacher.last_name}`
              : "Unknown",
            teacher_photo: teacher?.photo_url,
            teacher_email: teacher?.email,
            subject_name: classSubject?.subject?.name,
            subject_code: classSubject?.subject?.code,
          };
        });
        setAssignments(enriched);
      }
    });
  };

  const getCurrentSection = () => sections.find((s) => s.id === selectedSection);

  // Get teachers not assigned to this section
  const assignedTeacherIds = new Set(assignments.map((a) => a.staff_id));
  const availableTeachers = allTeachers.filter((t) => !assignedTeacherIds.has(t.id));

  const filteredTeachers = availableTeachers.filter(
    (t) =>
      t.first_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.last_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.email.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleAddAssignment = async () => {
    if (!formData.staff_id || !selectedSection) {
      toast.error("Please select a teacher");
      return;
    }

    startTransition(async () => {
      const result = await assignStaffToSection(formData.staff_id, {
        section_id: selectedSection,
        subject_id: formData.subject_id || undefined,
        is_class_teacher: formData.is_class_teacher,
      });

      if (result.success) {
        const teacher = allTeachers.find((t) => t.id === formData.staff_id);
        toast.success("Teacher assigned", {
          description: `${teacher?.first_name} ${teacher?.last_name} has been assigned to ${getCurrentSection()?.name}.`,
        });
        setAddDialogOpen(false);
        setFormData({ staff_id: "", subject_id: "", is_class_teacher: false });
        setSearchQuery("");
        loadAssignments(selectedSection);
      } else {
        toast.error("Failed to assign teacher", {
          description: result.error,
        });
      }
    });
  };

  const handleToggleClassTeacher = async (assignment: AssignmentWithDetails) => {
    if (!selectedSection) return;

    startTransition(async () => {
      const result = await updateStaffAssignment(assignment.staff_id, assignment.id, {
        is_class_teacher: !assignment.is_class_teacher,
      });

      if (result.success) {
        toast.success(
          assignment.is_class_teacher
            ? `${assignment.teacher_name} is no longer the class teacher`
            : `${assignment.teacher_name} is now the class teacher`
        );
        loadAssignments(selectedSection);
      } else {
        toast.error("Failed to update assignment", {
          description: result.error,
        });
      }
    });
  };

  const openRemoveDialog = (assignment: AssignmentWithDetails) => {
    setSelectedAssignment(assignment);
    setRemoveDialogOpen(true);
  };

  const handleRemoveAssignment = async () => {
    if (!selectedAssignment || !selectedSection) return;

    startTransition(async () => {
      const result = await removeStaffFromSection(
        selectedAssignment.staff_id,
        selectedAssignment.section_id
      );

      if (result.success) {
        toast.success(`${selectedAssignment.teacher_name} removed from ${getCurrentSection()?.name}`);
        setRemoveDialogOpen(false);
        setSelectedAssignment(null);
        loadAssignments(selectedSection);
      } else {
        toast.error("Failed to remove assignment", {
          description: result.error,
        });
      }
    });
  };

  // Stats
  const classTeacher = assignments.find((a) => a.is_class_teacher);
  const subjectTeachersCount = assignments.filter((a) => a.subject_id).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href="/classes">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold tracking-tight">
            {classData.name} - Teacher Assignments
          </h1>
          <p className="text-muted-foreground">
            Assign teachers to class sections and subjects.
          </p>
        </div>
      </div>

      {sections.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <GraduationCap className="mx-auto h-12 w-12 text-muted-foreground/50" />
            <h3 className="mt-4 text-lg font-semibold">No sections found</h3>
            <p className="text-muted-foreground">
              Create sections for this class first, then you can assign teachers.
            </p>
            <Link href="/classes">
              <Button className="mt-4">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Classes
              </Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Section Tabs */}
          <Tabs
            value={selectedSection || undefined}
            onValueChange={setSelectedSection}
            className="space-y-4"
          >
            <TabsList>
              {sections.map((section) => (
                <TabsTrigger key={section.id} value={section.id}>
                  {section.name}
                </TabsTrigger>
              ))}
            </TabsList>

            {sections.map((section) => (
              <TabsContent key={section.id} value={section.id} className="space-y-4">
                {/* Stats Cards */}
                <div className="grid gap-4 md:grid-cols-3">
                  <Card>
                    <CardHeader className="pb-2">
                      <CardDescription>Total Assigned</CardDescription>
                      <CardTitle className="text-3xl">{assignments.length}</CardTitle>
                    </CardHeader>
                  </Card>
                  <Card>
                    <CardHeader className="pb-2">
                      <CardDescription>Class Teacher</CardDescription>
                      <CardTitle className="text-lg">
                        {classTeacher?.teacher_name || "Not assigned"}
                      </CardTitle>
                    </CardHeader>
                  </Card>
                  <Card>
                    <CardHeader className="pb-2">
                      <CardDescription>Subject Teachers</CardDescription>
                      <CardTitle className="text-3xl text-blue-600">
                        {subjectTeachersCount}
                      </CardTitle>
                    </CardHeader>
                  </Card>
                </div>

                {/* Assignment List */}
                <Card>
                  <CardHeader className="flex flex-row items-center justify-between">
                    <div>
                      <CardTitle>Assigned Teachers</CardTitle>
                      <CardDescription>
                        Teachers currently assigned to {section.name}.
                      </CardDescription>
                    </div>
                    <Button onClick={() => setAddDialogOpen(true)}>
                      <Plus className="mr-2 h-4 w-4" />
                      Assign Teacher
                    </Button>
                  </CardHeader>
                  <CardContent>
                    {assignments.length === 0 ? (
                      <div className="text-center py-12">
                        <UserCheck className="mx-auto h-12 w-12 text-muted-foreground/50" />
                        <h3 className="mt-4 text-lg font-semibold">
                          No teachers assigned
                        </h3>
                        <p className="text-muted-foreground">
                          Assign teachers to this section to enable score entry.
                        </p>
                        <Button onClick={() => setAddDialogOpen(true)} className="mt-4">
                          <Plus className="mr-2 h-4 w-4" />
                          Assign Teacher
                        </Button>
                      </div>
                    ) : (
                      <div className="rounded-md border">
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>Teacher</TableHead>
                              <TableHead className="hidden sm:table-cell">Subject</TableHead>
                              <TableHead>Class Teacher</TableHead>
                              <TableHead className="w-[70px]"></TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {assignments.map((assignment) => (
                              <TableRow key={assignment.id}>
                                <TableCell>
                                  <div className="flex items-center gap-3">
                                    <Avatar className="h-9 w-9">
                                      <AvatarImage
                                        src={assignment.teacher_photo}
                                        alt={assignment.teacher_name}
                                      />
                                      <AvatarFallback>
                                        {assignment.teacher_name
                                          .split(" ")
                                          .map((n) => n[0])
                                          .join("")
                                          .toUpperCase()}
                                      </AvatarFallback>
                                    </Avatar>
                                    <div>
                                      <p className="font-medium">
                                        {assignment.teacher_name}
                                      </p>
                                      <p className="text-sm text-muted-foreground">
                                        {assignment.teacher_email}
                                      </p>
                                    </div>
                                  </div>
                                </TableCell>
                                <TableCell className="hidden sm:table-cell">
                                  {assignment.subject_name ? (
                                    <Badge variant="outline">
                                      <BookOpen className="mr-1 h-3 w-3" />
                                      {assignment.subject_code} - {assignment.subject_name}
                                    </Badge>
                                  ) : (
                                    <span className="text-muted-foreground">
                                      All subjects
                                    </span>
                                  )}
                                </TableCell>
                                <TableCell>
                                  <Switch
                                    checked={assignment.is_class_teacher}
                                    onCheckedChange={() =>
                                      handleToggleClassTeacher(assignment)
                                    }
                                    disabled={isPending}
                                  />
                                </TableCell>
                                <TableCell>
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-8 w-8 text-destructive hover:text-destructive"
                                    onClick={() => openRemoveDialog(assignment)}
                                  >
                                    <Trash2 className="h-4 w-4" />
                                  </Button>
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>
            ))}
          </Tabs>
        </>
      )}

      {/* Add Assignment Dialog */}
      <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Assign Teacher to {getCurrentSection()?.name}</DialogTitle>
            <DialogDescription>
              Select a teacher and optionally assign them to a specific subject.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {/* Teacher Search & Select */}
            <div className="space-y-2">
              <Label>Teacher *</Label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search teachers..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9"
                />
              </div>
              <div className="max-h-48 overflow-y-auto border rounded-md">
                {filteredTeachers.length === 0 ? (
                  <div className="p-4 text-center text-muted-foreground">
                    {availableTeachers.length === 0
                      ? "All teachers are already assigned."
                      : "No teachers match your search."}
                  </div>
                ) : (
                  <div className="divide-y">
                    {filteredTeachers.map((teacher) => (
                      <div
                        key={teacher.id}
                        className={`p-3 cursor-pointer flex items-center gap-3 transition-colors ${
                          formData.staff_id === teacher.id
                            ? "bg-muted"
                            : "hover:bg-muted/50"
                        }`}
                        onClick={() =>
                          setFormData({ ...formData, staff_id: teacher.id })
                        }
                      >
                        <Avatar className="h-8 w-8">
                          <AvatarImage src={teacher.photo_url} />
                          <AvatarFallback>
                            {teacher.first_name[0]}
                            {teacher.last_name[0]}
                          </AvatarFallback>
                        </Avatar>
                        <div className="flex-1 min-w-0">
                          <p className="font-medium truncate">
                            {teacher.first_name} {teacher.last_name}
                          </p>
                          <p className="text-sm text-muted-foreground truncate">
                            {teacher.email}
                          </p>
                        </div>
                        {formData.staff_id === teacher.id && (
                          <Badge variant="default">Selected</Badge>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Subject Select (Optional) */}
            <div className="space-y-2">
              <Label>Subject (Optional)</Label>
              <Select
                value={formData.subject_id || "__all__"}
                onValueChange={(value) =>
                  setFormData({ ...formData, subject_id: value === "__all__" ? "" : value })
                }
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="All subjects (general assignment)" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">All subjects</SelectItem>
                  {classSubjects.map((cs) => (
                    <SelectItem key={cs.subject_id} value={cs.subject_id}>
                      {cs.subject?.code} - {cs.subject?.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-sm text-muted-foreground">
                Assign to a specific subject for score entry permissions, or leave
                empty for general class assignment.
              </p>
            </div>

            {/* Class Teacher Toggle */}
            <div className="flex items-center justify-between rounded-lg border p-4">
              <div>
                <Label>Class Teacher (Form Tutor)</Label>
                <p className="text-sm text-muted-foreground">
                  Can enter all scores and add remarks for report cards.
                </p>
              </div>
              <Switch
                checked={formData.is_class_teacher}
                onCheckedChange={(checked) =>
                  setFormData({ ...formData, is_class_teacher: checked })
                }
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setAddDialogOpen(false);
                setFormData({ staff_id: "", subject_id: "", is_class_teacher: false });
                setSearchQuery("");
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={handleAddAssignment}
              disabled={isPending || !formData.staff_id}
            >
              {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Assign Teacher
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Remove Confirmation Dialog */}
      <AlertDialog open={removeDialogOpen} onOpenChange={setRemoveDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove Assignment</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to remove {selectedAssignment?.teacher_name} from{" "}
              {getCurrentSection()?.name}? They will no longer be able to enter
              scores for this section.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleRemoveAssignment}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
