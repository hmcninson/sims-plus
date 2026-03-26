"use client";

import { useState, useEffect, useTransition, useMemo, useCallback } from "react";
import {
  Plus,
  Search,
  MoreHorizontal,
  Loader2,
  Pencil,
  Trash2,
  AlertCircle,
  BookOpen,
  Link2,
} from "lucide-react";
import { useForm , type Resolver} from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
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
  FormDescription,
} from "@/components/ui/form";
import {
  getSubjectMappings,
  createSubjectMapping,
  updateSubjectMapping,
  deleteSubjectMapping,
} from "@/actions/curriculum.action";
import { getSubjects } from "@/actions/academic.action";
import type { Subject } from "@/types";
import type {
  CurriculumProfile,
  SubjectCurriculumMapping,
} from "@/types/curriculum.type";

const mappingSchema = z.object({
  subject_id: z.string().min(1, "Subject is required"),
  curriculum_profile_id: z.string().min(1, "Curriculum profile is required"),
  external_code: z.string().optional(),
  external_name: z.string().optional(),
  level: z.string().optional(),
  credits: z.coerce.number().min(0).optional(),
  coefficient: z.coerce.number().min(0).optional(),
  is_hl: z.boolean().optional(),
});

type MappingFormValues = z.infer<typeof mappingSchema>;

interface SubjectMappingTableProps {
  profiles: CurriculumProfile[];
}

export function SubjectMappingTable({ profiles }: SubjectMappingTableProps) {
  const [mappings, setMappings] = useState<SubjectCurriculumMapping[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [profileFilter, setProfileFilter] = useState<string>("all");
  const [isPending, startTransition] = useTransition();

  // Dialog states
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingMapping, setEditingMapping] = useState<SubjectCurriculumMapping | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<SubjectCurriculumMapping | null>(null);

  const form = useForm<MappingFormValues>({
    resolver: zodResolver(mappingSchema) as Resolver<MappingFormValues>,
    defaultValues: {
      subject_id: "",
      curriculum_profile_id: "",
      external_code: "",
      external_name: "",
      level: "",
      credits: undefined,
      coefficient: undefined,
      is_hl: false,
    },
  });

  // Load subjects
  useEffect(() => {
    let mounted = true;
    async function loadSubjects() {
      const result = await getSubjects();
      if (mounted && result.success) {
        setSubjects(result.data);
      }
    }
    loadSubjects();
    return () => { mounted = false; };
  }, []);

  // Load mappings
  const loadMappings = useCallback(() => {
    startTransition(async () => {
      const params: { curriculum_profile_id?: string; page_size?: number } = { page_size: 500 };
      if (profileFilter !== "all") {
        params.curriculum_profile_id = profileFilter;
      }
      const result = await getSubjectMappings(params);
      if (result.success) {
        setMappings(result.data.items);
      }
      setIsLoading(false);
    });
  }, [profileFilter]);

  useEffect(() => {
    loadMappings();
  }, [loadMappings]);

  const filteredMappings = useMemo(() => {
    if (!searchQuery) return mappings;
    const q = searchQuery.toLowerCase();
    return mappings.filter((m) => {
      const subject = subjects.find((s) => s.id === m.subject_id);
      return (
        subject?.name.toLowerCase().includes(q) ||
        subject?.code.toLowerCase().includes(q) ||
        m.external_code?.toLowerCase().includes(q) ||
        m.external_name?.toLowerCase().includes(q)
      );
    });
  }, [mappings, searchQuery, subjects]);

  const getSubjectName = (subjectId: string): string => {
    return subjects.find((s) => s.id === subjectId)?.name || "Unknown";
  };

  const getSubjectCode = (subjectId: string): string => {
    return subjects.find((s) => s.id === subjectId)?.code || "";
  };

  const getProfileName = (profileId: string): string => {
    return profiles.find((p) => p.id === profileId)?.name || "Unknown";
  };

  const openCreateDialog = () => {
    setEditingMapping(null);
    form.reset({
      subject_id: "",
      curriculum_profile_id: profiles.length === 1 ? profiles[0].id : "",
      external_code: "",
      external_name: "",
      level: "",
      credits: undefined,
      coefficient: undefined,
      is_hl: false,
    });
    setIsFormOpen(true);
  };

  const openEditDialog = (mapping: SubjectCurriculumMapping) => {
    setEditingMapping(mapping);
    form.reset({
      subject_id: mapping.subject_id,
      curriculum_profile_id: mapping.curriculum_profile_id,
      external_code: mapping.external_code || "",
      external_name: mapping.external_name || "",
      level: mapping.level || "",
      credits: mapping.credits ?? undefined,
      coefficient: mapping.coefficient ?? undefined,
      is_hl: mapping.is_hl || false,
    });
    setIsFormOpen(true);
  };

  const onSubmit = async (values: MappingFormValues) => {
    if (editingMapping) {
      const updateData = {
        external_code: values.external_code || undefined,
        external_name: values.external_name || undefined,
        level: values.level || undefined,
        credits: values.credits ?? undefined,
        coefficient: values.coefficient ?? undefined,
        is_hl: values.is_hl,
      };
      const result = await updateSubjectMapping(editingMapping.id, updateData);
      if (result.success) {
        toast.success("Subject mapping updated");
        setIsFormOpen(false);
        loadMappings();
      } else {
        toast.error("Failed to update mapping", { description: result.error });
      }
    } else {
      const createData = {
        subject_id: values.subject_id,
        curriculum_profile_id: values.curriculum_profile_id,
        external_code: values.external_code || undefined,
        external_name: values.external_name || undefined,
        level: values.level || undefined,
        credits: values.credits ?? undefined,
        coefficient: values.coefficient ?? undefined,
        is_hl: values.is_hl,
      };
      const result = await createSubjectMapping(createData);
      if (result.success) {
        toast.success("Subject mapping created");
        setIsFormOpen(false);
        loadMappings();
      } else {
        toast.error("Failed to create mapping", { description: result.error });
      }
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    const result = await deleteSubjectMapping(deleteTarget.id);
    if (result.success) {
      toast.success("Subject mapping deleted");
      setDeleteTarget(null);
      loadMappings();
    } else {
      toast.error("Failed to delete mapping", { description: result.error });
    }
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <div className="h-5 w-40 bg-muted rounded animate-pulse" />
              <div className="h-4 w-64 bg-muted rounded animate-pulse" />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-12 w-full bg-muted rounded animate-pulse" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold">Subject Mappings</h3>
          <p className="text-sm text-muted-foreground">
            {mappings.length} mapping{mappings.length !== 1 && "s"} configured
          </p>
        </div>
        <Button size="sm" onClick={openCreateDialog}>
          <Plus className="mr-2 h-4 w-4" />
          Add Mapping
        </Button>
      </div>

      <Card>
        <CardHeader className="pb-4">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search subjects..."
                className="pl-9"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
            <Select value={profileFilter} onValueChange={setProfileFilter}>
              <SelectTrigger className="w-full sm:w-[200px]">
                <SelectValue placeholder="All profiles" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Profiles</SelectItem>
                {profiles.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent>
          {filteredMappings.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 gap-3">
              <Link2 className="h-10 w-10 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                {mappings.length === 0
                  ? "No subject mappings configured yet."
                  : "No mappings match your search."}
              </p>
              {mappings.length === 0 && (
                <Button size="sm" onClick={openCreateDialog}>
                  <Plus className="mr-2 h-4 w-4" />
                  Add Mapping
                </Button>
              )}
            </div>
          ) : (
            <>
              {/* Desktop table */}
              <div className="hidden md:block">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Subject</TableHead>
                      <TableHead>Profile</TableHead>
                      <TableHead>External Code</TableHead>
                      <TableHead>External Name</TableHead>
                      <TableHead>Level</TableHead>
                      <TableHead className="text-right">Credits</TableHead>
                      <TableHead className="w-[60px]">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredMappings.map((mapping) => (
                      <TableRow key={mapping.id}>
                        <TableCell>
                          <div>
                            <p className="font-medium text-sm">{getSubjectName(mapping.subject_id)}</p>
                            <p className="text-xs text-muted-foreground">{getSubjectCode(mapping.subject_id)}</p>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant="secondary" className="text-xs">
                            {getProfileName(mapping.curriculum_profile_id)}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-sm">
                          {mapping.external_code || (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </TableCell>
                        <TableCell className="text-sm">
                          {mapping.external_name || (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </TableCell>
                        <TableCell className="text-sm">
                          <div className="flex items-center gap-1">
                            {mapping.level || (
                              <span className="text-muted-foreground">-</span>
                            )}
                            {mapping.is_hl && (
                              <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200 text-[10px]">
                                HL
                              </Badge>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="text-right text-sm">
                          {mapping.credits != null ? mapping.credits : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </TableCell>
                        <TableCell>
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="icon" className="h-8 w-8">
                                <MoreHorizontal className="h-4 w-4" />
                                <span className="sr-only">Actions</span>
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem onClick={() => openEditDialog(mapping)}>
                                <Pencil className="mr-2 h-4 w-4" />
                                Edit
                              </DropdownMenuItem>
                              <DropdownMenuSeparator />
                              <DropdownMenuItem
                                onClick={() => setDeleteTarget(mapping)}
                                className="text-destructive focus:text-destructive"
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

              {/* Mobile cards */}
              <div className="md:hidden space-y-3">
                {filteredMappings.map((mapping) => (
                  <div key={mapping.id} className="rounded-lg border p-4 space-y-2">
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="font-medium text-sm">{getSubjectName(mapping.subject_id)}</p>
                        <p className="text-xs text-muted-foreground">{getSubjectCode(mapping.subject_id)}</p>
                      </div>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-8 w-8">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => openEditDialog(mapping)}>
                            <Pencil className="mr-2 h-4 w-4" />
                            Edit
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            onClick={() => setDeleteTarget(mapping)}
                            className="text-destructive"
                          >
                            <Trash2 className="mr-2 h-4 w-4" />
                            Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="secondary" className="text-[10px]">
                        {getProfileName(mapping.curriculum_profile_id)}
                      </Badge>
                      {mapping.is_hl && (
                        <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200 text-[10px]">
                          HL
                        </Badge>
                      )}
                      {mapping.credits != null && (
                        <span className="text-xs text-muted-foreground">
                          {mapping.credits} credits
                        </span>
                      )}
                    </div>
                    {(mapping.external_code || mapping.external_name) && (
                      <p className="text-xs text-muted-foreground">
                        External: {mapping.external_code}
                        {mapping.external_code && mapping.external_name && " - "}
                        {mapping.external_name}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}

          {isPending && (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create/Edit Dialog */}
      <Dialog open={isFormOpen} onOpenChange={setIsFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editingMapping ? "Edit Subject Mapping" : "Add Subject Mapping"}
            </DialogTitle>
            <DialogDescription>
              Map a school subject to a curriculum profile with optional external references.
            </DialogDescription>
          </DialogHeader>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <FormField
                control={form.control}
                name="subject_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Subject</FormLabel>
                    <Select
                      value={field.value}
                      onValueChange={field.onChange}
                      disabled={!!editingMapping}
                    >
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Select subject" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {subjects
                          .filter((s) => s.is_active)
                          .map((s) => (
                            <SelectItem key={s.id} value={s.id}>
                              {s.name} ({s.code})
                            </SelectItem>
                          ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="curriculum_profile_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Curriculum Profile</FormLabel>
                    <Select
                      value={field.value}
                      onValueChange={field.onChange}
                      disabled={!!editingMapping}
                    >
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Select profile" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {profiles
                          .filter((p) => p.is_active)
                          .map((p) => (
                            <SelectItem key={p.id} value={p.id}>
                              {p.name}
                            </SelectItem>
                          ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="external_code"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>External Code</FormLabel>
                      <FormControl>
                        <Input placeholder="e.g., IGCSE-0580" {...field} />
                      </FormControl>
                      <FormDescription className="text-xs">
                        Code used by the external curriculum body
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="external_name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>External Name</FormLabel>
                      <FormControl>
                        <Input placeholder="e.g., Mathematics (Extended)" {...field} />
                      </FormControl>
                      <FormDescription className="text-xs">
                        Name used by the external curriculum body
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <FormField
                  control={form.control}
                  name="level"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Level</FormLabel>
                      <FormControl>
                        <Input placeholder="e.g., SL, HL" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="credits"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Credits</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          step="0.5"
                          min="0"
                          placeholder="e.g., 3"
                          {...field}
                          value={field.value ?? ""}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="coefficient"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Coefficient</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          step="0.5"
                          min="0"
                          placeholder="e.g., 2"
                          {...field}
                          value={field.value ?? ""}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <FormField
                control={form.control}
                name="is_hl"
                render={({ field }) => (
                  <FormItem className="flex items-center gap-3 space-y-0">
                    <FormControl>
                      <Checkbox
                        checked={field.value}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                    <FormLabel className="font-normal">Higher Level (HL)</FormLabel>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsFormOpen(false)}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={form.formState.isSubmitting}>
                  {form.formState.isSubmitting && (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  )}
                  {editingMapping ? "Update" : "Create"}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* Delete confirmation */}
      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => { if (!open) setDeleteTarget(null); }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Subject Mapping</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to remove the mapping for &ldquo;
              {deleteTarget ? getSubjectName(deleteTarget.subject_id) : ""}
              &rdquo;? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-destructive text-white hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
