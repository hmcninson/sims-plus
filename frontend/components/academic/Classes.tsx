"use client";

import { useState, useEffect } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
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
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Users, Plus, Settings2, Trash2, Loader2, Search } from "lucide-react";
import {
  getClasses,
  createClass,
  updateClass,
  deleteClass,
  getSections,
  createSection,
  updateSection,
  deleteSection,
} from "@/actions/academic.action";
import type {
  Class,
  ClassCreate,
  ClassUpdate,
  ClassSection,
  ClassSectionCreate,
  ClassSectionUpdate,
  ClassLevel,
} from "@/types";

interface ClassesProps {
  initialData?: Class[];
}

export function Classes({ initialData }: ClassesProps) {
  const [classes, setClasses] = useState<Class[]>(initialData || []);
  const [loading, setLoading] = useState(!initialData);
  const [isClassDialogOpen, setIsClassDialogOpen] = useState(false);
  const [isSectionDialogOpen, setIsSectionDialogOpen] = useState(false);
  const [editingClass, setEditingClass] = useState<Class | null>(null);
  const [editingSection, setEditingSection] = useState<ClassSection | null>(null);
  const [selectedClassId, setSelectedClassId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleteSectionDialogOpen, setDeleteSectionDialogOpen] = useState(false);
  const [sectionToDelete, setSectionToDelete] = useState<{ classId: string; section: ClassSection } | null>(null);
  const [deleteClassDialogOpen, setDeleteClassDialogOpen] = useState(false);
  const [classToDelete, setClassToDelete] = useState<Class | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Filter and search state
  const [searchQuery, setSearchQuery] = useState("");
  const [levelFilter, setLevelFilter] = useState<string>("all");

  // Class form state
  const [classFormData, setClassFormData] = useState({
    name: "",
    short_name: "",
    level: "" as ClassLevel | "",
    sequence: 1,
    capacity: "",
  });

  // Section form state
  const [sectionFormData, setSectionFormData] = useState({
    class_id: "",
    name: "",
    capacity: "",
  });

  useEffect(() => {
    if (!initialData) {
      loadClasses();
    }
  }, [initialData]);

  const loadClasses = async () => {
    setLoading(true);
    // Fetch classes with sections included in a single request
    const result = await getClasses(true);
    if (result.success && result.data) {
      setClasses(result.data);
    }
    setLoading(false);
  };

  const resetClassForm = () => {
    setClassFormData({
      name: "",
      short_name: "",
      level: "",
      sequence: classes.length + 1,
      capacity: "",
    });
    setEditingClass(null);
    setError(null);
  };

  const resetSectionForm = () => {
    setSectionFormData({
      class_id: selectedClassId || "",
      name: "",
      capacity: "",
    });
    setEditingSection(null);
    setError(null);
  };

  const openCreateClassDialog = () => {
    resetClassForm();
    setIsClassDialogOpen(true);
  };

  const openEditClassDialog = (cls: Class) => {
    setEditingClass(cls);
    setClassFormData({
      name: cls.name,
      short_name: cls.short_name || "",
      level: cls.level || "",
      sequence: cls.sequence,
      capacity: cls.capacity?.toString() || "",
    });
    setIsClassDialogOpen(true);
  };

  const openCreateSectionDialog = (classId: string) => {
    setSelectedClassId(classId);
    setSectionFormData({
      class_id: classId,
      name: "",
      capacity: "",
    });
    setIsSectionDialogOpen(true);
  };

  const openEditSectionDialog = (section: ClassSection) => {
    setEditingSection(section);
    setSectionFormData({
      class_id: section.class_id,
      name: section.name,
      capacity: section.capacity?.toString() || "",
    });
    setIsSectionDialogOpen(true);
  };

  const handleClassSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      if (editingClass) {
        const updateData: ClassUpdate = {
          name: classFormData.name,
          short_name: classFormData.short_name || undefined,
          level: (classFormData.level as ClassLevel) || undefined,
          sequence: classFormData.sequence,
          capacity: classFormData.capacity ? parseInt(classFormData.capacity) : undefined,
        };
        const result = await updateClass(editingClass.id, updateData);
        if (result.success && result.data) {
          setClasses(
            classes.map((c) =>
              c.id === editingClass.id ? { ...result.data!, sections: c.sections } : c
            )
          );
          setIsClassDialogOpen(false);
          resetClassForm();
        } else {
          setError(result.error || "Failed to update class");
        }
      } else {
        const createData: ClassCreate = {
          name: classFormData.name,
          short_name: classFormData.short_name || undefined,
          level: (classFormData.level as ClassLevel) || undefined,
          sequence: classFormData.sequence,
          capacity: classFormData.capacity ? parseInt(classFormData.capacity) : undefined,
        };
        const result = await createClass(createData);
        if (result.success && result.data) {
          setClasses([...classes, { ...result.data, sections: [] }]);
          setIsClassDialogOpen(false);
          resetClassForm();
        } else {
          setError(result.error || "Failed to create class");
        }
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleSectionSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      if (editingSection) {
        const updateData: ClassSectionUpdate = {
          name: sectionFormData.name,
          capacity: sectionFormData.capacity ? parseInt(sectionFormData.capacity) : undefined,
        };
        const result = await updateSection(editingSection.id, updateData);
        if (result.success && result.data) {
          setClasses(
            classes.map((c) =>
              c.id === sectionFormData.class_id
                ? {
                    ...c,
                    sections: c.sections?.map((s) =>
                      s.id === editingSection.id ? result.data! : s
                    ),
                  }
                : c
            )
          );
          setIsSectionDialogOpen(false);
          resetSectionForm();
        } else {
          setError(result.error || "Failed to update section");
        }
      } else {
        const createData: ClassSectionCreate = {
          class_id: sectionFormData.class_id,
          name: sectionFormData.name,
          capacity: sectionFormData.capacity ? parseInt(sectionFormData.capacity) : undefined,
        };
        const result = await createSection(createData);
        if (result.success && result.data) {
          setClasses(
            classes.map((c) =>
              c.id === sectionFormData.class_id
                ? { ...c, sections: [...(c.sections || []), result.data!] }
                : c
            )
          );
          setIsSectionDialogOpen(false);
          resetSectionForm();
        } else {
          setError(result.error || "Failed to create section");
        }
      }
    } finally {
      setSubmitting(false);
    }
  };

  const openDeleteClassDialog = (cls: Class) => {
    setClassToDelete(cls);
    setDeleteClassDialogOpen(true);
  };

  const handleDeleteClass = async () => {
    if (!classToDelete) return;

    setIsDeleting(true);
    const result = await deleteClass(classToDelete.id);
    if (result.success) {
      setClasses(classes.filter((c) => c.id !== classToDelete.id));
      setDeleteClassDialogOpen(false);
      setClassToDelete(null);
    } else {
      setError(result.error || "Failed to delete class");
    }
    setIsDeleting(false);
  };

  const openDeleteSectionDialog = (classId: string, section: ClassSection) => {
    setSectionToDelete({ classId, section });
    setDeleteSectionDialogOpen(true);
  };

  const handleDeleteSection = async () => {
    if (!sectionToDelete) return;

    setIsDeleting(true);
    const result = await deleteSection(sectionToDelete.section.id);
    if (result.success) {
      setClasses(
        classes.map((c) =>
          c.id === sectionToDelete.classId
            ? { ...c, sections: c.sections?.filter((s) => s.id !== sectionToDelete.section.id) }
            : c
        )
      );
      setDeleteSectionDialogOpen(false);
      setSectionToDelete(null);
    } else {
      setError(result.error || "Failed to delete section");
    }
    setIsDeleting(false);
  };

  const getLevelCategory = (level?: string): string => {
    if (!level) return "other";
    if (level === "creche" || level.startsWith("nursery") || level.startsWith("kg")) return "preschool";
    if (level.startsWith("primary")) return "primary";
    if (level.startsWith("jhs")) return "jhs";
    if (level.startsWith("shs")) return "shs";
    return "other";
  };

  const getLevelLabel = (level?: string) => {
    if (!level) return "";
    const category = getLevelCategory(level);
    if (category === "preschool") return "Preschool";
    if (category === "primary") return "Primary";
    if (category === "jhs") return "JHS";
    if (category === "shs") return "SHS";
    return level;
  };

  // Filter classes based on search and level filter
  const filteredClasses = classes
    .filter((cls) => {
      // Apply level filter
      if (levelFilter !== "all") {
        const category = getLevelCategory(cls.level);
        if (category !== levelFilter) return false;
      }
      // Apply search filter
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        const matchesName = cls.name.toLowerCase().includes(query);
        const matchesShortName = cls.short_name?.toLowerCase().includes(query);
        const matchesSection = cls.sections?.some(s =>
          s.name.toLowerCase().includes(query) ||
          `${cls.name} ${s.name}`.toLowerCase().includes(query)
        );
        return matchesName || matchesShortName || matchesSection;
      }
      return true;
    })
    .sort((a, b) => a.sequence - b.sequence);

  // Level filter tabs configuration
  const levelTabs = [
    { value: "all", label: "All" },
    { value: "preschool", label: "Preschool" },
    { value: "primary", label: "Primary" },
    { value: "jhs", label: "JHS" },
    { value: "shs", label: "SHS" },
  ];

  // Count classes per level for badge display
  const levelCounts = {
    all: classes.length,
    preschool: classes.filter(c => getLevelCategory(c.level) === "preschool").length,
    primary: classes.filter(c => getLevelCategory(c.level) === "primary").length,
    jhs: classes.filter(c => getLevelCategory(c.level) === "jhs").length,
    shs: classes.filter(c => getLevelCategory(c.level) === "shs").length,
  };

  // Level options for the dropdown
  const levelOptions = [
    { group: "Preschool", options: [
      { value: "creche", label: "Creche" },
      { value: "nursery_1", label: "Nursery 1" },
      { value: "nursery_2", label: "Nursery 2" },
      { value: "kg_1", label: "KG 1" },
      { value: "kg_2", label: "KG 2" },
    ]},
    { group: "Primary", options: [
      { value: "primary_1", label: "Primary 1" },
      { value: "primary_2", label: "Primary 2" },
      { value: "primary_3", label: "Primary 3" },
      { value: "primary_4", label: "Primary 4" },
      { value: "primary_5", label: "Primary 5" },
      { value: "primary_6", label: "Primary 6" },
    ]},
    { group: "JHS", options: [
      { value: "jhs_1", label: "JHS 1" },
      { value: "jhs_2", label: "JHS 2" },
      { value: "jhs_3", label: "JHS 3" },
    ]},
    { group: "SHS", options: [
      { value: "shs_1", label: "SHS 1" },
      { value: "shs_2", label: "SHS 2" },
      { value: "shs_3", label: "SHS 3" },
    ]},
  ];

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Users className="h-5 w-5" />
              Classes & Sections
            </CardTitle>
            <CardDescription>
              Manage your school&apos;s classes and sections.
            </CardDescription>
          </div>
          <Dialog open={isClassDialogOpen} onOpenChange={setIsClassDialogOpen}>
            <DialogTrigger asChild>
              <Button size="sm" onClick={openCreateClassDialog}>
                <Plus className="mr-2 h-4 w-4" />
                New Class
              </Button>
            </DialogTrigger>
            <DialogContent>
              <form onSubmit={handleClassSubmit}>
                <DialogHeader>
                  <DialogTitle>
                    {editingClass ? "Edit Class" : "Create Class"}
                  </DialogTitle>
                  <DialogDescription>
                    {editingClass
                      ? "Update the class details."
                      : "Add a new class to your school."}
                  </DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                  {error && (
                    <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                      {error}
                    </div>
                  )}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="grid gap-2">
                      <Label htmlFor="name">Name</Label>
                      <Input
                        id="name"
                        placeholder="e.g., JHS 1"
                        value={classFormData.name}
                        onChange={(e) =>
                          setClassFormData({ ...classFormData, name: e.target.value })
                        }
                        required
                      />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="short_name">Short Name</Label>
                      <Input
                        id="short_name"
                        placeholder="e.g., J1"
                        value={classFormData.short_name}
                        onChange={(e) =>
                          setClassFormData({
                            ...classFormData,
                            short_name: e.target.value,
                          })
                        }
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="grid gap-2">
                      <Label htmlFor="level">Level</Label>
                      <Select
                        value={classFormData.level}
                        onValueChange={(value) =>
                          setClassFormData({
                            ...classFormData,
                            level: value as ClassLevel,
                          })
                        }
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Select level" />
                        </SelectTrigger>
                        <SelectContent>
                          {levelOptions.map((group) => (
                            <SelectGroup key={group.group}>
                              <SelectLabel>{group.group}</SelectLabel>
                              {group.options.map((option) => (
                                <SelectItem key={option.value} value={option.value}>
                                  {option.label}
                                </SelectItem>
                              ))}
                            </SelectGroup>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="sequence">Sequence</Label>
                      <Input
                        id="sequence"
                        type="number"
                        min={1}
                        value={classFormData.sequence}
                        onChange={(e) =>
                          setClassFormData({
                            ...classFormData,
                            sequence: parseInt(e.target.value) || 1,
                          })
                        }
                        required
                      />
                    </div>
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="capacity">Capacity (Optional)</Label>
                    <Input
                      id="capacity"
                      type="number"
                      min={1}
                      placeholder="Max students per section"
                      value={classFormData.capacity}
                      onChange={(e) =>
                        setClassFormData({ ...classFormData, capacity: e.target.value })
                      }
                    />
                  </div>
                </div>
                <DialogFooter>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setIsClassDialogOpen(false)}
                  >
                    Cancel
                  </Button>
                  <Button type="submit" disabled={submitting}>
                    {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    {editingClass ? "Update" : "Create"}
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Filter Tabs and Search */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          {/* Level Filter Tabs */}
          <div className="flex flex-wrap gap-1">
            {levelTabs.map((tab) => (
              <Button
                key={tab.value}
                variant={levelFilter === tab.value ? "default" : "outline"}
                size="sm"
                onClick={() => setLevelFilter(tab.value)}
                className="h-8"
              >
                {tab.label}
                {levelCounts[tab.value as keyof typeof levelCounts] > 0 && (
                  <Badge
                    variant={levelFilter === tab.value ? "secondary" : "outline"}
                    className="ml-1.5 h-5 px-1.5 text-xs"
                  >
                    {levelCounts[tab.value as keyof typeof levelCounts]}
                  </Badge>
                )}
              </Button>
            ))}
          </div>

          {/* Search Box */}
          <div className="relative w-full sm:w-64">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search classes..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8"
            />
          </div>
        </div>

        {/* Section Dialog */}
        <Dialog open={isSectionDialogOpen} onOpenChange={setIsSectionDialogOpen}>
          <DialogContent>
            <form onSubmit={handleSectionSubmit}>
              <DialogHeader>
                <DialogTitle>
                  {editingSection ? "Edit Section" : "Create Section"}
                </DialogTitle>
                <DialogDescription>
                  {editingSection
                    ? "Update the section details."
                    : "Add a new section to this class."}
                </DialogDescription>
              </DialogHeader>
              <div className="grid gap-4 py-4">
                {error && (
                  <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                    {error}
                  </div>
                )}
                <div className="grid gap-2">
                  <Label htmlFor="section_name">Section Name</Label>
                  <Input
                    id="section_name"
                    placeholder="e.g., A, B, Blue, Gold"
                    value={sectionFormData.name}
                    onChange={(e) =>
                      setSectionFormData({ ...sectionFormData, name: e.target.value })
                    }
                    required
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="section_capacity">Capacity (Optional)</Label>
                  <Input
                    id="section_capacity"
                    type="number"
                    min={1}
                    placeholder="Max students in this section"
                    value={sectionFormData.capacity}
                    onChange={(e) =>
                      setSectionFormData({
                        ...sectionFormData,
                        capacity: e.target.value,
                      })
                    }
                  />
                </div>
              </div>
              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsSectionDialogOpen(false)}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={submitting}>
                  {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  {editingSection ? "Update" : "Create"}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>

        {classes.length === 0 ? (
          <div className="py-8 text-center text-muted-foreground">
            No classes found. Create your first class to get started.
          </div>
        ) : filteredClasses.length === 0 ? (
          <div className="py-8 text-center text-muted-foreground">
            No classes match your search or filter criteria.
          </div>
        ) : (
          <Accordion type="single" collapsible className="w-full">
            {filteredClasses.map((cls) => (
                <AccordionItem key={cls.id} value={cls.id}>
                  <AccordionTrigger className="hover:no-underline">
                    <div className="flex items-center gap-3">
                      <span className="font-medium">{cls.name}</span>
                      {cls.level && (
                        <Badge variant="outline" className="text-xs">
                          {getLevelLabel(cls.level)}
                        </Badge>
                      )}
                      {cls.sections && cls.sections.length > 0 && (
                        <Badge variant="secondary" className="text-xs">
                          {cls.sections.length} section
                          {cls.sections.length !== 1 ? "s" : ""}
                        </Badge>
                      )}
                    </div>
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="space-y-3 pl-4">
                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => openCreateSectionDialog(cls.id)}
                        >
                          <Plus className="mr-2 h-3 w-3" />
                          Add Section
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openEditClassDialog(cls)}
                        >
                          <Settings2 className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openDeleteClassDialog(cls)}
                          className="text-destructive hover:text-destructive"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                      {cls.sections && cls.sections.length > 0 ? (
                        <div className="grid gap-2">
                          {cls.sections.map((section) => (
                            <div
                              key={section.id}
                              className="flex items-center justify-between rounded-lg border p-3"
                            >
                              <div>
                                <span className="font-medium">
                                  {cls.name} - {section.name}
                                </span>
                                {section.capacity && (
                                  <span className="ml-2 text-sm text-muted-foreground">
                                    (Capacity: {section.capacity})
                                  </span>
                                )}
                              </div>
                              <div className="flex items-center gap-2">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => openEditSectionDialog(section)}
                                >
                                  <Settings2 className="h-3 w-3" />
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => openDeleteSectionDialog(cls.id, section)}
                                  className="text-destructive hover:text-destructive"
                                >
                                  <Trash2 className="h-3 w-3" />
                                </Button>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="text-sm text-muted-foreground">
                          No sections yet. Add sections to organize students.
                        </p>
                      )}
                    </div>
                  </AccordionContent>
                </AccordionItem>
              ))}
          </Accordion>
        )}
      </CardContent>

      {/* Delete Section Confirmation Dialog */}
      <AlertDialog open={deleteSectionDialogOpen} onOpenChange={setDeleteSectionDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Section</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete section &quot;{sectionToDelete?.section.name}&quot;?
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteSection}
              disabled={isDeleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isDeleting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Deleting...
                </>
              ) : (
                "Delete"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Delete Class Confirmation Dialog */}
      <AlertDialog open={deleteClassDialogOpen} onOpenChange={setDeleteClassDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Class</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete &quot;{classToDelete?.name}&quot; and all its sections?
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteClass}
              disabled={isDeleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isDeleting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Deleting...
                </>
              ) : (
                "Delete"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Card>
  );
}
