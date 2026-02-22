"use client";

import { useState, useTransition, useMemo } from "react";
import {
  GraduationCap,
  Plus,
  Search,
  MoreHorizontal,
  Loader2,
  Users,
  Pencil,
  Trash2,
  ChevronDown,
  ChevronRight,
  UserCheck,
  BookOpen,
} from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Progress } from "@/components/ui/progress";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

import {
  getClasses,
  createClass,
  updateClass,
  deleteClass,
  createSection,
  updateSection,
  deleteSection,
} from "@/actions/academic.action";
import type { Class, ClassSection, ClassLevel, ClassCreate, ClassSectionCreate } from "@/types";

// Category configuration for display
const CATEGORY_CONFIG = {
  preschool: { label: "Preschool", color: "bg-amber-500", textColor: "text-amber-600" },
  primary: { label: "Primary", color: "bg-blue-500", textColor: "text-blue-600" },
  jhs: { label: "JHS", color: "bg-green-500", textColor: "text-green-600" },
  shs: { label: "SHS", color: "bg-rose-500", textColor: "text-rose-600" },
};

// Map specific levels to their category
const getLevelCategory = (level: ClassLevel | string | undefined): keyof typeof CATEGORY_CONFIG | null => {
  if (!level) return null;
  const levelStr = String(level).toLowerCase();
  // Check for preschool levels (creche, nursery, kg, kindergarten)
  if (levelStr.includes("creche") || levelStr.includes("nursery") || levelStr.includes("kg") || levelStr.includes("kindergarten") || levelStr === "preschool") {
    return "preschool";
  }
  // Check for primary levels
  if (levelStr.includes("primary") || levelStr.startsWith("p") && /p[1-6]/.test(levelStr)) {
    return "primary";
  }
  // Check for JHS levels
  if (levelStr.includes("jhs") || levelStr.includes("junior")) {
    return "jhs";
  }
  // Check for SHS levels
  if (levelStr.includes("shs") || levelStr.includes("senior")) {
    return "shs";
  }
  return null;
};

// Get display config for a level
const getLevelConfig = (level: ClassLevel | undefined) => {
  const category = getLevelCategory(level);
  return category ? CATEGORY_CONFIG[category] : null;
};

interface ClassWithSections extends Class {
  sections?: ClassSection[];
}

interface ClassesManagementProps {
  initialClasses: ClassWithSections[];
}

export function ClassesManagement({ initialClasses }: ClassesManagementProps) {
  const [classes, setClasses] = useState<ClassWithSections[]>(initialClasses);
  const [searchQuery, setSearchQuery] = useState("");
  const [levelFilter, setLevelFilter] = useState<keyof typeof CATEGORY_CONFIG | "all">("all");
  const [expandedClasses, setExpandedClasses] = useState<Set<string>>(new Set());
  const [isPending, startTransition] = useTransition();

  // Calculate stats
  const stats = useMemo(() => {
    const totalClasses = classes.length;
    const totalSections = classes.reduce((acc, c) => acc + (c.sections?.length || 0), 0);
    const totalCapacity = classes.reduce((acc, c) => {
      // Sum section capacities if available, otherwise use class capacity
      const sectionCapacity = c.sections?.reduce((s, sec) => s + (sec.capacity || 0), 0) || 0;
      return acc + (sectionCapacity || c.capacity || 0);
    }, 0);
    const totalEnrolled = classes.reduce((acc, c) => acc + (c.student_count || 0), 0);
    const totalMale = classes.reduce((acc, c) => acc + (c.male_count || 0), 0);
    const totalFemale = classes.reduce((acc, c) => acc + (c.female_count || 0), 0);
    const byLevel = {
      preschool: classes.filter((c) => getLevelCategory(c.level) === "preschool").length,
      primary: classes.filter((c) => getLevelCategory(c.level) === "primary").length,
      jhs: classes.filter((c) => getLevelCategory(c.level) === "jhs").length,
      shs: classes.filter((c) => getLevelCategory(c.level) === "shs").length,
    };
    return { totalClasses, totalSections, totalCapacity, totalEnrolled, totalMale, totalFemale, byLevel };
  }, [classes]);

  // Dialog states
  const [addClassDialogOpen, setAddClassDialogOpen] = useState(false);
  const [editClassDialogOpen, setEditClassDialogOpen] = useState(false);
  const [deleteClassDialogOpen, setDeleteClassDialogOpen] = useState(false);
  const [addSectionDialogOpen, setAddSectionDialogOpen] = useState(false);
  const [editSectionDialogOpen, setEditSectionDialogOpen] = useState(false);
  const [deleteSectionDialogOpen, setDeleteSectionDialogOpen] = useState(false);

  const [selectedClass, setSelectedClass] = useState<ClassWithSections | null>(null);
  const [selectedSection, setSelectedSection] = useState<ClassSection | null>(null);

  // Form states
  const [classFormData, setClassFormData] = useState({
    name: "",
    short_name: "",
    level: "" as ClassLevel | "",
    capacity: "",
    sequence: "",
  });

  const [sectionFormData, setSectionFormData] = useState({
    name: "",
    capacity: "",
  });

  const refreshClasses = async () => {
    startTransition(async () => {
      const result = await getClasses(true);
      if (result.success && result.data) {
        setClasses(result.data);
      }
    });
  };

  const toggleClassExpanded = (classId: string) => {
    setExpandedClasses((prev) => {
      const next = new Set(prev);
      if (next.has(classId)) {
        next.delete(classId);
      } else {
        next.add(classId);
      }
      return next;
    });
  };

  const filteredClasses = classes.filter((c) => {
    const matchesSearch =
      c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.short_name?.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesLevel = levelFilter === "all" || getLevelCategory(c.level) === levelFilter;
    return matchesSearch && matchesLevel;
  });

  // Class handlers
  const handleCreateClass = async (e: React.FormEvent) => {
    e.preventDefault();
    startTransition(async () => {
      const data: ClassCreate = {
        name: classFormData.name,
        short_name: classFormData.short_name || undefined,
        level: classFormData.level || undefined,
        capacity: classFormData.capacity ? parseInt(classFormData.capacity) : undefined,
        sequence: classFormData.sequence ? parseInt(classFormData.sequence) : undefined,
      };

      const result = await createClass(data);

      if (result.success) {
        toast.success("Class created", {
          description: `${classFormData.name} has been added.`,
        });
        setAddClassDialogOpen(false);
        setClassFormData({ name: "", short_name: "", level: "", capacity: "", sequence: "" });
        refreshClasses();
      } else {
        toast.error("Failed to create class", {
          description: result.error,
        });
      }
    });
  };

  const handleUpdateClass = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedClass) return;

    startTransition(async () => {
      const result = await updateClass(selectedClass.id, {
        name: classFormData.name,
        short_name: classFormData.short_name || undefined,
        level: classFormData.level || undefined,
        capacity: classFormData.capacity ? parseInt(classFormData.capacity) : undefined,
        sequence: classFormData.sequence ? parseInt(classFormData.sequence) : undefined,
      });

      if (result.success) {
        toast.success("Class updated", {
          description: `${classFormData.name} has been updated.`,
        });
        setEditClassDialogOpen(false);
        setSelectedClass(null);
        refreshClasses();
      } else {
        toast.error("Failed to update class", {
          description: result.error,
        });
      }
    });
  };

  const handleDeleteClass = async () => {
    if (!selectedClass) return;

    startTransition(async () => {
      const result = await deleteClass(selectedClass.id);

      if (result.success) {
        toast.success("Class deleted", {
          description: `${selectedClass.name} has been removed.`,
        });
        setDeleteClassDialogOpen(false);
        setSelectedClass(null);
        refreshClasses();
      } else {
        toast.error("Failed to delete class", {
          description: result.error,
        });
      }
    });
  };

  const openEditClassDialog = (classItem: ClassWithSections) => {
    setSelectedClass(classItem);
    setClassFormData({
      name: classItem.name,
      short_name: classItem.short_name || "",
      level: classItem.level || "",
      capacity: classItem.capacity?.toString() || "",
      sequence: classItem.sequence?.toString() || "",
    });
    setEditClassDialogOpen(true);
  };

  const openDeleteClassDialog = (classItem: ClassWithSections) => {
    setSelectedClass(classItem);
    setDeleteClassDialogOpen(true);
  };

  // Section handlers
  const handleCreateSection = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedClass) return;

    startTransition(async () => {
      const data: ClassSectionCreate = {
        class_id: selectedClass.id,
        name: sectionFormData.name,
        capacity: sectionFormData.capacity ? parseInt(sectionFormData.capacity) : undefined,
      };

      const result = await createSection(data);

      if (result.success) {
        toast.success("Section created", {
          description: `${sectionFormData.name} has been added to ${selectedClass.name}.`,
        });
        setAddSectionDialogOpen(false);
        setSectionFormData({ name: "", capacity: "" });
        setSelectedClass(null);
        refreshClasses();
      } else {
        toast.error("Failed to create section", {
          description: result.error,
        });
      }
    });
  };

  const handleUpdateSection = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedSection) return;

    startTransition(async () => {
      const result = await updateSection(selectedSection.id, {
        name: sectionFormData.name,
        capacity: sectionFormData.capacity ? parseInt(sectionFormData.capacity) : undefined,
      });

      if (result.success) {
        toast.success("Section updated", {
          description: `${sectionFormData.name} has been updated.`,
        });
        setEditSectionDialogOpen(false);
        setSelectedSection(null);
        refreshClasses();
      } else {
        toast.error("Failed to update section", {
          description: result.error,
        });
      }
    });
  };

  const handleDeleteSection = async () => {
    if (!selectedSection) return;

    startTransition(async () => {
      const result = await deleteSection(selectedSection.id);

      if (result.success) {
        toast.success("Section deleted", {
          description: `${selectedSection.name} has been removed.`,
        });
        setDeleteSectionDialogOpen(false);
        setSelectedSection(null);
        refreshClasses();
      } else {
        toast.error("Failed to delete section", {
          description: result.error,
        });
      }
    });
  };

  const openAddSectionDialog = (classItem: ClassWithSections) => {
    setSelectedClass(classItem);
    setSectionFormData({ name: "", capacity: "" });
    setAddSectionDialogOpen(true);
  };

  const openEditSectionDialog = (section: ClassSection) => {
    setSelectedSection(section);
    setSectionFormData({
      name: section.name,
      capacity: section.capacity?.toString() || "",
    });
    setEditSectionDialogOpen(true);
  };

  const openDeleteSectionDialog = (section: ClassSection) => {
    setSelectedSection(section);
    setDeleteSectionDialogOpen(true);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Classes & Sections</h1>
          <p className="text-muted-foreground">
            Manage classes, sections, and student capacity.
          </p>
        </div>
        <Dialog open={addClassDialogOpen} onOpenChange={setAddClassDialogOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              Add Class
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-[425px]">
            <form onSubmit={handleCreateClass}>
              <DialogHeader>
                <DialogTitle>Add New Class</DialogTitle>
                <DialogDescription>
                  Create a new class for your school.
                </DialogDescription>
              </DialogHeader>
              <div className="grid gap-4 py-4">
                <div className="space-y-2">
                  <Label htmlFor="class_name">Class Name</Label>
                  <Input
                    id="class_name"
                    placeholder="e.g., Class 1, Form 1, JHS 1"
                    required
                    value={classFormData.name}
                    onChange={(e) =>
                      setClassFormData((prev) => ({ ...prev, name: e.target.value }))
                    }
                  />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="short_name">Short Name</Label>
                    <Input
                      id="short_name"
                      placeholder="e.g., P1, F1"
                      value={classFormData.short_name}
                      onChange={(e) =>
                        setClassFormData((prev) => ({ ...prev, short_name: e.target.value }))
                      }
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="level">Level</Label>
                    <Select
                      value={classFormData.level}
                      onValueChange={(value) =>
                        setClassFormData((prev) => ({ ...prev, level: value as ClassLevel }))
                      }
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Select" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="preschool">Preschool</SelectItem>
                        <SelectItem value="primary">Primary</SelectItem>
                        <SelectItem value="jhs">JHS</SelectItem>
                        <SelectItem value="shs">SHS</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="capacity">Capacity</Label>
                    <Input
                      id="capacity"
                      type="number"
                      placeholder="e.g., 40"
                      value={classFormData.capacity}
                      onChange={(e) =>
                        setClassFormData((prev) => ({ ...prev, capacity: e.target.value }))
                      }
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="sequence">Order</Label>
                    <Input
                      id="sequence"
                      type="number"
                      placeholder="e.g., 1"
                      value={classFormData.sequence}
                      onChange={(e) =>
                        setClassFormData((prev) => ({ ...prev, sequence: e.target.value }))
                      }
                    />
                  </div>
                </div>
              </div>
              <DialogFooter>
                <Button type="submit" disabled={isPending}>
                  {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Create Class
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-6">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total Classes</CardDescription>
            <CardTitle className="text-3xl">{stats.totalClasses}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total Sections</CardDescription>
            <CardTitle className="text-3xl">{stats.totalSections}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total Enrolled</CardDescription>
            <CardTitle className="text-3xl">{stats.totalEnrolled}</CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <p className="text-xs text-muted-foreground">
              {stats.totalMale} male, {stats.totalFemale} female
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Primary</CardDescription>
            <CardTitle className={`text-3xl ${CATEGORY_CONFIG.primary.textColor}`}>
              {stats.byLevel.primary}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>JHS</CardDescription>
            <CardTitle className={`text-3xl ${CATEGORY_CONFIG.jhs.textColor}`}>
              {stats.byLevel.jhs}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>SHS</CardDescription>
            <CardTitle className={`text-3xl ${CATEGORY_CONFIG.shs.textColor}`}>
              {stats.byLevel.shs}
            </CardTitle>
          </CardHeader>
        </Card>
      </div>

      {/* Class List Card */}
      <Card>
        <CardHeader>
          <CardTitle>Class List</CardTitle>
          <CardDescription>
            View and manage all classes and their sections.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* Search and Filter */}
          <div className="flex flex-col sm:flex-row gap-4 mb-6">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search classes..."
                className="pl-9"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
            <Select
              value={levelFilter}
              onValueChange={(value) => setLevelFilter(value as keyof typeof CATEGORY_CONFIG | "all")}
            >
              <SelectTrigger className="w-full sm:w-[180px]">
                <SelectValue placeholder="Filter by level" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Levels</SelectItem>
                <SelectItem value="preschool">Preschool</SelectItem>
                <SelectItem value="primary">Primary</SelectItem>
                <SelectItem value="jhs">JHS</SelectItem>
                <SelectItem value="shs">SHS</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Classes List */}
          <div className="space-y-3">
            {filteredClasses.length === 0 ? (
              <div className="text-center py-12">
                <GraduationCap className="mx-auto h-12 w-12 text-muted-foreground/50" />
                <h3 className="mt-4 text-lg font-semibold">No classes found</h3>
                <p className="text-muted-foreground">
                  {searchQuery || levelFilter !== "all"
                    ? "Try adjusting your search or filter."
                    : "Get started by adding your first class."}
                </p>
                {!searchQuery && levelFilter === "all" && (
                  <Button onClick={() => setAddClassDialogOpen(true)} className="mt-4">
                    <Plus className="mr-2 h-4 w-4" />
                    Add Class
                  </Button>
                )}
              </div>
            ) : (
              filteredClasses.map((classItem) => (
                <Collapsible
                  key={classItem.id}
                  open={expandedClasses.has(classItem.id)}
                  onOpenChange={() => toggleClassExpanded(classItem.id)}
                >
                  <div className="rounded-lg border">
                    <div className="flex items-center justify-between p-4">
                      <div className="flex items-center gap-3 flex-1 min-w-0">
                        <CollapsibleTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-6 w-6 shrink-0">
                            {expandedClasses.has(classItem.id) ? (
                              <ChevronDown className="h-4 w-4" />
                            ) : (
                              <ChevronRight className="h-4 w-4" />
                            )}
                          </Button>
                        </CollapsibleTrigger>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <Link
                              href={`/classes/${classItem.id}`}
                              className="font-medium hover:text-primary hover:underline transition-colors"
                            >
                              {classItem.name}
                            </Link>
                            {classItem.short_name && (
                              <Badge variant="outline">{classItem.short_name}</Badge>
                            )}
                            {classItem.level && getLevelConfig(classItem.level) && (
                              <Badge
                                className={`${getLevelConfig(classItem.level)!.color} text-white`}
                              >
                                {getLevelConfig(classItem.level)!.label}
                              </Badge>
                            )}
                          </div>
                          <div className="flex items-center gap-4 text-sm text-muted-foreground mt-1">
                            <span>
                              {classItem.sections?.length || 0} section(s)
                            </span>
                          </div>
                        </div>

                        {/* Student Enrollment Stats */}
                        <div className="hidden md:flex items-center gap-6 ml-auto mr-4">
                          <TooltipProvider>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Link
                                  href={`/students?class_id=${classItem.id}`}
                                  className="flex items-center gap-2 text-sm hover:text-primary transition-colors"
                                >
                                  <UserCheck className="h-4 w-4 text-muted-foreground" />
                                  <span className="font-medium">{classItem.student_count || 0}</span>
                                  <span className="text-muted-foreground">students</span>
                                </Link>
                              </TooltipTrigger>
                              <TooltipContent>
                                <p>{classItem.male_count || 0} male, {classItem.female_count || 0} female</p>
                                <p className="text-xs text-muted-foreground">Click to view students</p>
                              </TooltipContent>
                            </Tooltip>
                          </TooltipProvider>

                          {/* Enrollment Progress */}
                          {classItem.capacity && classItem.capacity > 0 && (
                            <div className="w-32">
                              <TooltipProvider>
                                <Tooltip>
                                  <TooltipTrigger asChild>
                                    <div>
                                      <Progress
                                        value={Math.min(((classItem.student_count || 0) / classItem.capacity) * 100, 100)}
                                        className="h-2"
                                      />
                                      <p className="text-xs text-muted-foreground mt-1 text-center">
                                        {classItem.student_count || 0} / {classItem.capacity}
                                      </p>
                                    </div>
                                  </TooltipTrigger>
                                  <TooltipContent>
                                    <p>
                                      {Math.round(((classItem.student_count || 0) / classItem.capacity) * 100)}% capacity
                                    </p>
                                    {(classItem.student_count || 0) > classItem.capacity && (
                                      <p className="text-xs text-red-400">Over capacity!</p>
                                    )}
                                  </TooltipContent>
                                </Tooltip>
                              </TooltipProvider>
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => openAddSectionDialog(classItem)}
                        >
                          <Plus className="mr-1 h-3 w-3" />
                          Section
                        </Button>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon">
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuLabel>Actions</DropdownMenuLabel>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem asChild>
                              <Link href={`/classes/${classItem.id}`}>
                                <GraduationCap className="mr-2 h-4 w-4" />
                                View Details
                              </Link>
                            </DropdownMenuItem>
                            <DropdownMenuItem asChild>
                              <Link href={`/students?class_id=${classItem.id}`}>
                                <Users className="mr-2 h-4 w-4" />
                                View Students
                              </Link>
                            </DropdownMenuItem>
                            <DropdownMenuItem asChild>
                              <Link href={`/classes/${classItem.id}/subjects`}>
                                <BookOpen className="mr-2 h-4 w-4" />
                                Manage Subjects
                              </Link>
                            </DropdownMenuItem>
                            <DropdownMenuItem asChild>
                              <Link href={`/classes/${classItem.id}/teachers`}>
                                <UserCheck className="mr-2 h-4 w-4" />
                                Manage Teachers
                              </Link>
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => openEditClassDialog(classItem)}>
                              <Pencil className="mr-2 h-4 w-4" />
                              Edit
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              className="text-destructive"
                              onClick={() => openDeleteClassDialog(classItem)}
                            >
                              <Trash2 className="mr-2 h-4 w-4" />
                              Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    </div>

                    {/* Mobile Student Stats */}
                    <div className="md:hidden border-t px-4 py-2 flex items-center justify-between text-sm">
                      <Link
                        href={`/students?class_id=${classItem.id}`}
                        className="flex items-center gap-2 hover:text-primary transition-colors"
                      >
                        <UserCheck className="h-4 w-4 text-muted-foreground" />
                        <span className="font-medium">{classItem.student_count || 0}</span>
                        <span className="text-muted-foreground">
                          ({classItem.male_count || 0}M, {classItem.female_count || 0}F)
                        </span>
                      </Link>
                      {classItem.capacity && classItem.capacity > 0 && (
                        <div className="flex items-center gap-2">
                          <Progress
                            value={Math.min(((classItem.student_count || 0) / classItem.capacity) * 100, 100)}
                            className="h-2 w-16"
                          />
                          <span className="text-xs text-muted-foreground">
                            {classItem.student_count || 0}/{classItem.capacity}
                          </span>
                        </div>
                      )}
                    </div>

                    {/* Sections */}
                    <CollapsibleContent>
                      {classItem.sections && classItem.sections.length > 0 ? (
                        <div className="border-t px-4 py-3 bg-muted/30">
                          <p className="text-xs font-medium text-muted-foreground mb-2">
                            SECTIONS
                          </p>
                          <div className="space-y-2">
                            {classItem.sections.map((section) => (
                              <div
                                key={section.id}
                                className="flex items-center justify-between rounded-md border bg-background p-3"
                              >
                                <div className="flex-1">
                                  <p className="text-sm font-medium">{section.name}</p>
                                  <div className="flex items-center gap-3 mt-1">
                                    <span className="text-xs text-muted-foreground">
                                      {section.student_count || 0} students
                                      {(section.male_count !== undefined || section.female_count !== undefined) && (
                                        <span className="ml-1">
                                          ({section.male_count || 0}M, {section.female_count || 0}F)
                                        </span>
                                      )}
                                    </span>
                                    {section.capacity && section.capacity > 0 && (
                                      <div className="flex items-center gap-2">
                                        <Progress
                                          value={Math.min(((section.student_count || 0) / section.capacity) * 100, 100)}
                                          className="h-1.5 w-16"
                                        />
                                        <span className="text-xs text-muted-foreground">
                                          {section.student_count || 0}/{section.capacity}
                                        </span>
                                      </div>
                                    )}
                                  </div>
                                </div>
                                <div className="flex items-center gap-1">
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-7 w-7"
                                    onClick={() => openEditSectionDialog(section)}
                                  >
                                    <Pencil className="h-3 w-3" />
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-7 w-7 text-destructive"
                                    onClick={() => openDeleteSectionDialog(section)}
                                  >
                                    <Trash2 className="h-3 w-3" />
                                  </Button>
                                </div>
                              </div>
                            ))}

                            {/* Show unassigned students warning */}
                            {(() => {
                              const assignedToSections = classItem.sections.reduce(
                                (sum, s) => sum + (s.student_count || 0),
                                0
                              );
                              const unassigned = (classItem.student_count || 0) - assignedToSections;
                              if (unassigned > 0) {
                                return (
                                  <div className="flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950 p-3 text-xs text-amber-700 dark:text-amber-400">
                                    <Users className="h-4 w-4 shrink-0" />
                                    <span>
                                      <strong>{unassigned}</strong> student{unassigned !== 1 ? "s" : ""} not assigned to any section
                                    </span>
                                  </div>
                                );
                              }
                              return null;
                            })()}
                          </div>
                        </div>
                      ) : (
                        <div className="border-t px-4 py-6 bg-muted/30 text-center text-sm text-muted-foreground">
                          No sections. Click &quot;+ Section&quot; to add one.
                        </div>
                      )}
                    </CollapsibleContent>
                  </div>
                </Collapsible>
              ))
            )}
          </div>
        </CardContent>
      </Card>

      {/* Edit Class Dialog */}
      <Dialog open={editClassDialogOpen} onOpenChange={setEditClassDialogOpen}>
        <DialogContent className="sm:max-w-[425px]">
          <form onSubmit={handleUpdateClass}>
            <DialogHeader>
              <DialogTitle>Edit Class</DialogTitle>
              <DialogDescription>Update class information.</DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="edit_class_name">Class Name</Label>
                <Input
                  id="edit_class_name"
                  required
                  value={classFormData.name}
                  onChange={(e) =>
                    setClassFormData((prev) => ({ ...prev, name: e.target.value }))
                  }
                />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="edit_short_name">Short Name</Label>
                  <Input
                    id="edit_short_name"
                    value={classFormData.short_name}
                    onChange={(e) =>
                      setClassFormData((prev) => ({ ...prev, short_name: e.target.value }))
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="edit_level">Level</Label>
                  <Select
                    value={classFormData.level}
                    onValueChange={(value) =>
                      setClassFormData((prev) => ({ ...prev, level: value as ClassLevel }))
                    }
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Select" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="preschool">Preschool</SelectItem>
                      <SelectItem value="primary">Primary</SelectItem>
                      <SelectItem value="jhs">JHS</SelectItem>
                      <SelectItem value="shs">SHS</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="edit_capacity">Capacity</Label>
                  <Input
                    id="edit_capacity"
                    type="number"
                    value={classFormData.capacity}
                    onChange={(e) =>
                      setClassFormData((prev) => ({ ...prev, capacity: e.target.value }))
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="edit_sequence">Order</Label>
                  <Input
                    id="edit_sequence"
                    type="number"
                    value={classFormData.sequence}
                    onChange={(e) =>
                      setClassFormData((prev) => ({ ...prev, sequence: e.target.value }))
                    }
                  />
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setEditClassDialogOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={isPending}>
                {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Save Changes
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete Class Dialog */}
      <AlertDialog open={deleteClassDialogOpen} onOpenChange={setDeleteClassDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Class</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete {selectedClass?.name}? This will also remove all
              associated sections. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteClass}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Add Section Dialog */}
      <Dialog open={addSectionDialogOpen} onOpenChange={setAddSectionDialogOpen}>
        <DialogContent className="sm:max-w-[350px]">
          <form onSubmit={handleCreateSection}>
            <DialogHeader>
              <DialogTitle>Add Section</DialogTitle>
              <DialogDescription>
                Add a new section to {selectedClass?.name}.
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="section_name">Section Name</Label>
                <Input
                  id="section_name"
                  placeholder="e.g., A, B, Red, Blue"
                  required
                  value={sectionFormData.name}
                  onChange={(e) =>
                    setSectionFormData((prev) => ({ ...prev, name: e.target.value }))
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="section_capacity">Capacity (Optional)</Label>
                <Input
                  id="section_capacity"
                  type="number"
                  placeholder="e.g., 35"
                  value={sectionFormData.capacity}
                  onChange={(e) =>
                    setSectionFormData((prev) => ({ ...prev, capacity: e.target.value }))
                  }
                />
              </div>
            </div>
            <DialogFooter>
              <Button type="submit" disabled={isPending}>
                {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Add Section
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Edit Section Dialog */}
      <Dialog open={editSectionDialogOpen} onOpenChange={setEditSectionDialogOpen}>
        <DialogContent className="sm:max-w-[350px]">
          <form onSubmit={handleUpdateSection}>
            <DialogHeader>
              <DialogTitle>Edit Section</DialogTitle>
              <DialogDescription>Update section information.</DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="edit_section_name">Section Name</Label>
                <Input
                  id="edit_section_name"
                  required
                  value={sectionFormData.name}
                  onChange={(e) =>
                    setSectionFormData((prev) => ({ ...prev, name: e.target.value }))
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit_section_capacity">Capacity</Label>
                <Input
                  id="edit_section_capacity"
                  type="number"
                  value={sectionFormData.capacity}
                  onChange={(e) =>
                    setSectionFormData((prev) => ({ ...prev, capacity: e.target.value }))
                  }
                />
              </div>
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setEditSectionDialogOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={isPending}>
                {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Save Changes
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete Section Dialog */}
      <AlertDialog open={deleteSectionDialogOpen} onOpenChange={setDeleteSectionDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Section</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete {selectedSection?.name}? This action cannot be
              undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteSection}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
