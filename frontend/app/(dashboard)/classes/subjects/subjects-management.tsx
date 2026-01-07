"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import {
  Plus,
  Search,
  Pencil,
  Trash2,
  Loader2,
  BookOpen,
  MoreHorizontal,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
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
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

import {
  getSubjects,
  createSubject,
  updateSubject,
  deleteSubject,
} from "@/actions/academic.action";
import type { Subject, SubjectCategory } from "@/types";

const CATEGORY_CONFIG: Record<SubjectCategory, { label: string; color: string }> = {
  core: { label: "Core", color: "bg-blue-500" },
  elective: { label: "Elective", color: "bg-green-500" },
  vocational: { label: "Vocational", color: "bg-amber-500" },
  extra: { label: "Extra", color: "bg-purple-500" },
};

interface SubjectsManagementProps {
  initialSubjects: Subject[];
}

export function SubjectsManagement({ initialSubjects }: SubjectsManagementProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  const [subjects, setSubjects] = useState<Subject[]>(initialSubjects);
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<SubjectCategory | "all">("all");

  // Dialog states
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  const [selectedSubject, setSelectedSubject] = useState<Subject | null>(null);
  const [formData, setFormData] = useState({
    name: "",
    code: "",
    description: "",
    category: "core" as SubjectCategory,
  });

  // Filter subjects
  const filteredSubjects = subjects.filter((subject) => {
    const matchesSearch =
      subject.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      subject.code.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCategory =
      categoryFilter === "all" || subject.category === categoryFilter;
    return matchesSearch && matchesCategory;
  });

  const refreshSubjects = () => {
    startTransition(async () => {
      const result = await getSubjects();
      if (result.success && result.data) {
        setSubjects(result.data);
      }
    });
  };

  const handleAddSubject = async () => {
    if (!formData.name || !formData.code) {
      toast.error("Please fill in required fields");
      return;
    }

    startTransition(async () => {
      const result = await createSubject({
        name: formData.name,
        code: formData.code.toUpperCase(),
        description: formData.description || undefined,
        category: formData.category,
      });

      if (result.success) {
        toast.success("Subject created", {
          description: `${formData.name} has been added.`,
        });
        setAddDialogOpen(false);
        setFormData({ name: "", code: "", description: "", category: "core" });
        refreshSubjects();
      } else {
        toast.error("Failed to create subject", {
          description: result.error,
        });
      }
    });
  };

  const handleEditSubject = async () => {
    if (!selectedSubject || !formData.name || !formData.code) {
      toast.error("Please fill in required fields");
      return;
    }

    startTransition(async () => {
      const result = await updateSubject(selectedSubject.id, {
        name: formData.name,
        code: formData.code.toUpperCase(),
        description: formData.description || undefined,
        category: formData.category,
      });

      if (result.success) {
        toast.success("Subject updated", {
          description: `${formData.name} has been updated.`,
        });
        setEditDialogOpen(false);
        setSelectedSubject(null);
        refreshSubjects();
      } else {
        toast.error("Failed to update subject", {
          description: result.error,
        });
      }
    });
  };

  const handleDeleteSubject = async () => {
    if (!selectedSubject) return;

    startTransition(async () => {
      const result = await deleteSubject(selectedSubject.id);

      if (result.success) {
        toast.success("Subject deleted", {
          description: `${selectedSubject.name} has been removed.`,
        });
        setDeleteDialogOpen(false);
        setSelectedSubject(null);
        refreshSubjects();
      } else {
        toast.error("Failed to delete subject", {
          description: result.error,
        });
      }
    });
  };

  const openAddDialog = () => {
    setFormData({ name: "", code: "", description: "", category: "core" });
    setAddDialogOpen(true);
  };

  const openEditDialog = (subject: Subject) => {
    setSelectedSubject(subject);
    setFormData({
      name: subject.name,
      code: subject.code,
      description: subject.description || "",
      category: subject.category,
    });
    setEditDialogOpen(true);
  };

  const openDeleteDialog = (subject: Subject) => {
    setSelectedSubject(subject);
    setDeleteDialogOpen(true);
  };

  // Stats
  const stats = {
    total: subjects.length,
    core: subjects.filter((s) => s.category === "core").length,
    elective: subjects.filter((s) => s.category === "elective").length,
    vocational: subjects.filter((s) => s.category === "vocational").length,
    extra: subjects.filter((s) => s.category === "extra").length,
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Subjects</h1>
          <p className="text-muted-foreground">
            Manage subjects and curriculum for your school.
          </p>
        </div>
        <Button onClick={openAddDialog}>
          <Plus className="mr-2 h-4 w-4" />
          Add Subject
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-5">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total Subjects</CardDescription>
            <CardTitle className="text-3xl">{stats.total}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Core</CardDescription>
            <CardTitle className="text-3xl text-blue-600">{stats.core}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Elective</CardDescription>
            <CardTitle className="text-3xl text-green-600">{stats.elective}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Vocational</CardDescription>
            <CardTitle className="text-3xl text-amber-600">{stats.vocational}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Extra</CardDescription>
            <CardTitle className="text-3xl text-purple-600">{stats.extra}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle>Subject List</CardTitle>
          <CardDescription>
            View and manage all subjects in your curriculum.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col sm:flex-row gap-4 mb-6">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search subjects..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select
              value={categoryFilter}
              onValueChange={(value) => setCategoryFilter(value as SubjectCategory | "all")}
            >
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Filter by category" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Categories</SelectItem>
                <SelectItem value="core">Core</SelectItem>
                <SelectItem value="elective">Elective</SelectItem>
                <SelectItem value="vocational">Vocational</SelectItem>
                <SelectItem value="extra">Extra-curricular</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Subject Table */}
          {filteredSubjects.length === 0 ? (
            <div className="text-center py-12">
              <BookOpen className="mx-auto h-12 w-12 text-muted-foreground/50" />
              <h3 className="mt-4 text-lg font-semibold">No subjects found</h3>
              <p className="text-muted-foreground">
                {searchQuery || categoryFilter !== "all"
                  ? "Try adjusting your search or filter."
                  : "Get started by adding your first subject."}
              </p>
              {!searchQuery && categoryFilter === "all" && (
                <Button onClick={openAddDialog} className="mt-4">
                  <Plus className="mr-2 h-4 w-4" />
                  Add Subject
                </Button>
              )}
            </div>
          ) : (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Code</TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead>Category</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="w-[70px]"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredSubjects.map((subject) => (
                    <TableRow key={subject.id}>
                      <TableCell className="font-mono font-medium">
                        {subject.code}
                      </TableCell>
                      <TableCell className="font-medium">{subject.name}</TableCell>
                      <TableCell>
                        <Badge
                          className={`${CATEGORY_CONFIG[subject.category].color} text-white`}
                        >
                          {CATEGORY_CONFIG[subject.category].label}
                        </Badge>
                      </TableCell>
                      <TableCell className="max-w-[200px] truncate text-muted-foreground">
                        {subject.description || "-"}
                      </TableCell>
                      <TableCell>
                        <Badge variant={subject.is_active ? "default" : "secondary"}>
                          {subject.is_active ? "Active" : "Inactive"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-8 w-8">
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => openEditDialog(subject)}>
                              <Pencil className="mr-2 h-4 w-4" />
                              Edit
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() => openDeleteDialog(subject)}
                              className="text-destructive"
                            >
                              <Trash2 className="mr-2 h-4 w-4" />
                              Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Add Subject Dialog */}
      <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Subject</DialogTitle>
            <DialogDescription>
              Create a new subject for your curriculum.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="name">Subject Name *</Label>
              <Input
                id="name"
                placeholder="e.g., Mathematics"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="code">Subject Code *</Label>
              <Input
                id="code"
                placeholder="e.g., MATH"
                value={formData.code}
                onChange={(e) => setFormData({ ...formData, code: e.target.value.toUpperCase() })}
                className="font-mono"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="category">Category</Label>
              <Select
                value={formData.category}
                onValueChange={(value) =>
                  setFormData({ ...formData, category: value as SubjectCategory })
                }
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="core">Core (Compulsory)</SelectItem>
                  <SelectItem value="elective">Elective (Optional)</SelectItem>
                  <SelectItem value="vocational">Vocational</SelectItem>
                  <SelectItem value="extra">Extra-curricular</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                placeholder="Brief description of the subject..."
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleAddSubject} disabled={isPending}>
              {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Create Subject
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Subject Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Subject</DialogTitle>
            <DialogDescription>Update the subject details.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="edit-name">Subject Name *</Label>
              <Input
                id="edit-name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit-code">Subject Code *</Label>
              <Input
                id="edit-code"
                value={formData.code}
                onChange={(e) => setFormData({ ...formData, code: e.target.value.toUpperCase() })}
                className="font-mono"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit-category">Category</Label>
              <Select
                value={formData.category}
                onValueChange={(value) =>
                  setFormData({ ...formData, category: value as SubjectCategory })
                }
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="core">Core (Compulsory)</SelectItem>
                  <SelectItem value="elective">Elective (Optional)</SelectItem>
                  <SelectItem value="vocational">Vocational</SelectItem>
                  <SelectItem value="extra">Extra-curricular</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit-description">Description</Label>
              <Textarea
                id="edit-description"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleEditSubject} disabled={isPending}>
              {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Subject</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete {selectedSubject?.name}? This action cannot
              be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteSubject}
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
