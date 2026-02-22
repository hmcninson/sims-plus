"use client";

import { useEffect, useState, useTransition } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
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
  FormDescription,
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
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
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
  Plus,
  Pencil,
  Trash2,
  Search,
  Loader2,
  Tag,
} from "lucide-react";
import {
  getFeeTypes,
  createFeeType,
  updateFeeType,
  deleteFeeType,
} from "@/actions/finance.action";
import type { FeeType, FeeTypeCategory } from "@/types/finance.type";
import { useToast } from "@/hooks/use-toast";

const CATEGORY_OPTIONS: { value: FeeTypeCategory; label: string }[] = [
  { value: "tuition", label: "Tuition" },
  { value: "examination", label: "Examination" },
  { value: "facilities", label: "Facilities" },
  { value: "activities", label: "Activities" },
  { value: "other", label: "Other" },
];

const feeTypeSchema = z.object({
  name: z.string().min(1, "Name is required").max(100, "Name must be 100 characters or less"),
  description: z.string().optional(),
  category: z.string().optional(),
  is_active: z.boolean(),
});

type FeeTypeFormData = z.infer<typeof feeTypeSchema>;

const getCategoryColor = (category?: FeeTypeCategory) => {
  switch (category) {
    case "tuition":
      return "bg-blue-100 text-blue-800";
    case "examination":
      return "bg-purple-100 text-purple-800";
    case "facilities":
      return "bg-green-100 text-green-800";
    case "activities":
      return "bg-orange-100 text-orange-800";
    default:
      return "bg-gray-100 text-gray-800";
  }
};

export default function FeeTypesPage() {
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();
  const [feeTypes, setFeeTypes] = useState<FeeType[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [filterCategory, setFilterCategory] = useState<string>("all");
  const [filterActive, setFilterActive] = useState<string>("all");

  // Debounce search query
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Dialog states
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingFeeType, setEditingFeeType] = useState<FeeType | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Form with react-hook-form
  const form = useForm<FeeTypeFormData>({
    resolver: zodResolver(feeTypeSchema),
    defaultValues: {
      name: "",
      description: "",
      category: "",
      is_active: true,
    },
  });

  const loadFeeTypes = () => {
    startTransition(async () => {
      const result = await getFeeTypes({
        search: debouncedSearch || undefined,
        category: filterCategory !== "all" ? filterCategory : undefined,
        isActive: filterActive === "all" ? undefined : filterActive === "true",
      });
      if (result.success && result.data) {
        setFeeTypes(result.data.items);
      }
    });
  };

  useEffect(() => {
    loadFeeTypes();
  }, [debouncedSearch, filterCategory, filterActive]);

  const handleOpenDialog = (feeType?: FeeType) => {
    if (feeType) {
      setEditingFeeType(feeType);
      form.reset({
        name: feeType.name,
        description: feeType.description || "",
        category: feeType.category || "",
        is_active: feeType.is_active,
      });
    } else {
      setEditingFeeType(null);
      form.reset({
        name: "",
        description: "",
        category: "",
        is_active: true,
      });
    }
    setIsDialogOpen(true);
  };

  const onSubmit = async (formData: FeeTypeFormData) => {
    setIsSubmitting(true);

    try {
      const data = {
        name: formData.name.trim(),
        description: formData.description?.trim() || undefined,
        category: (formData.category || undefined) as FeeTypeCategory | undefined,
        is_active: formData.is_active,
      };

      if (editingFeeType) {
        const result = await updateFeeType(editingFeeType.id, data);
        if (result.success && result.data) {
          // Update local state directly
          setFeeTypes((prev) =>
            prev.map((ft) => (ft.id === editingFeeType.id ? result.data! : ft))
          );
          toast({
            title: "Fee type updated",
            description: `${formData.name} has been updated successfully.`,
          });
          setIsDialogOpen(false);
        } else {
          toast({
            title: "Error",
            description: result.error || "Failed to update fee type",
            variant: "destructive",
          });
        }
      } else {
        const result = await createFeeType(data);
        if (result.success && result.data) {
          // Add to local state directly
          setFeeTypes((prev) => [result.data!, ...prev]);
          toast({
            title: "Fee type created",
            description: `${formData.name} has been created successfully.`,
          });
          setIsDialogOpen(false);
        } else {
          toast({
            title: "Error",
            description: result.error || "Failed to create fee type",
            variant: "destructive",
          });
        }
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteId) return;

    setIsSubmitting(true);
    try {
      const result = await deleteFeeType(deleteId);
      if (result.success) {
        // Remove from local state directly
        setFeeTypes((prev) => prev.filter((ft) => ft.id !== deleteId));
        toast({
          title: "Fee type deleted",
          description: "The fee type has been deleted successfully.",
        });
      } else {
        toast({
          title: "Error",
          description: result.error || "Failed to delete fee type",
          variant: "destructive",
        });
      }
    } finally {
      setIsSubmitting(false);
      setDeleteId(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Fee Types</h1>
          <p className="text-muted-foreground">
            Manage reusable fee type definitions for your school
          </p>
        </div>
        <Button onClick={() => handleOpenDialog()}>
          <Plus className="mr-2 h-4 w-4" />
          Add Fee Type
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
                placeholder="Search fee types..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select value={filterCategory} onValueChange={setFilterCategory}>
              <SelectTrigger className="w-full sm:w-[180px]">
                <SelectValue placeholder="Category" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Categories</SelectItem>
                {CATEGORY_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={filterActive} onValueChange={setFilterActive}>
              <SelectTrigger className="w-full sm:w-[140px]">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="true">Active</SelectItem>
                <SelectItem value="false">Inactive</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Fee Types List */}
      <Card>
        <CardHeader>
          <CardTitle>Fee Types</CardTitle>
          <CardDescription>
            {feeTypes.length} fee type{feeTypes.length !== 1 ? "s" : ""} found
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isPending ? (
            <div className="flex h-[200px] items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : feeTypes.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {feeTypes.map((feeType) => (
                  <TableRow key={feeType.id}>
                    <TableCell className="font-medium">
                      <div className="flex items-center gap-2">
                        <Tag className="h-4 w-4 text-muted-foreground" />
                        {feeType.name}
                      </div>
                    </TableCell>
                    <TableCell>
                      {feeType.category ? (
                        <Badge
                          variant="secondary"
                          className={getCategoryColor(feeType.category)}
                        >
                          {feeType.category}
                        </Badge>
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </TableCell>
                    <TableCell className="max-w-[300px] truncate">
                      {feeType.description || "-"}
                    </TableCell>
                    <TableCell>
                      <Badge variant={feeType.is_active ? "default" : "secondary"}>
                        {feeType.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleOpenDialog(feeType)}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setDeleteId(feeType.id)}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="flex h-[200px] flex-col items-center justify-center gap-2 text-muted-foreground">
              <Tag className="h-12 w-12" />
              <p>No fee types found</p>
              <p className="text-sm text-center max-w-md">
                Create fee types to use when building fee structures. Common
                examples include Tuition, Examination, PTA, and Transport fees.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create/Edit Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editingFeeType ? "Edit Fee Type" : "Create Fee Type"}
            </DialogTitle>
            <DialogDescription>
              {editingFeeType
                ? "Update the fee type details below."
                : "Add a new fee type to use in fee structures."}
            </DialogDescription>
          </DialogHeader>

          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Name *</FormLabel>
                    <FormControl>
                      <Input placeholder="e.g., Tuition Fee" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="category"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Category</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Select category" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {CATEGORY_OPTIONS.map((opt) => (
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

              <FormField
                control={form.control}
                name="description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Description</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Optional description for this fee type"
                        rows={3}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="is_active"
                render={({ field }) => (
                  <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
                    <div className="space-y-0.5">
                      <FormLabel className="text-base">Active</FormLabel>
                      <FormDescription>
                        Active fee types can be used in fee structures
                      </FormDescription>
                    </div>
                    <FormControl>
                      <Switch
                        checked={field.value}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                  </FormItem>
                )}
              />

              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsDialogOpen(false)}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  {editingFeeType ? "Save Changes" : "Create Fee Type"}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog open={!!deleteId} onOpenChange={() => setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Fee Type?</AlertDialogTitle>
            <AlertDialogDescription>
              This action cannot be undone. Fee structures using this fee type
              will retain their existing fee items, but new items cannot use this
              type.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isSubmitting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={isSubmitting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
