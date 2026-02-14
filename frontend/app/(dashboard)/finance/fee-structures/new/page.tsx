"use client";

import { useState, useEffect, useTransition, useCallback, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useForm, useFieldArray } from "react-hook-form";
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
  CommandSeparator,
} from "@/components/ui/command";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Checkbox } from "@/components/ui/checkbox";
import { ArrowLeft, Check, ChevronsUpDown, GripVertical, Loader2, Plus, Trash } from "lucide-react";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  createFeeStructure,
  getFeeStructure,
  getFeeTypes,
  createFeeType,
} from "@/actions/finance.action";
import {
  getAcademicYears,
  getTerms,
  getClasses,
  getCurrentAcademicYear,
} from "@/actions/academic.action";
import type { AcademicYear, Term, Class, FeeType, FeeTypeCategory } from "@/types";
import { formatCurrency } from "@/lib/format";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";

const feeItemSchema = z.object({
  fee_type_id: z.string().optional(),
  name: z.string().min(1, "Name is required"),
  amount: z.number().min(0, "Amount must be positive"),
  is_optional: z.boolean(),
  sequence: z.number(),
});

const feeStructureSchema = z.object({
  name: z.string().min(1, "Name is required").max(100),
  academic_year_id: z.string().min(1, "Academic year is required"),
  term_id: z.string().min(1, "Term is required"),
  class_id: z.string().optional(),
  level_category: z.string().optional(),
  student_type: z.string(),
  is_active: z.boolean(),
  items: z.array(feeItemSchema).min(1, "At least one fee item is required"),
});

type FeeStructureFormData = z.infer<typeof feeStructureSchema>;

const LEVEL_CATEGORIES = [
  { value: "preschool", label: "Preschool", description: "Creche, Nursery & KG" },
  { value: "primary", label: "Primary", description: "Primary 1-6" },
  { value: "jhs", label: "JHS", description: "JHS 1-3" },
  { value: "shs", label: "SHS", description: "SHS 1-3" },
];

const STUDENT_TYPES = [
  { value: "all", label: "All Students" },
  { value: "boarding", label: "Boarding Students" },
  { value: "day", label: "Day Students" },
];

const FEE_TYPE_CATEGORIES: { value: FeeTypeCategory; label: string; color: string }[] = [
  { value: "tuition", label: "Tuition", color: "bg-blue-100 text-blue-800" },
  { value: "examination", label: "Examination", color: "bg-purple-100 text-purple-800" },
  { value: "facilities", label: "Facilities", color: "bg-green-100 text-green-800" },
  { value: "activities", label: "Activities", color: "bg-orange-100 text-orange-800" },
  { value: "other", label: "Other", color: "bg-gray-100 text-gray-800" },
];

interface FeeTypeComboboxProps {
  value?: string;
  currentName?: string;
  feeTypes: FeeType[];
  onSelect: (feeType: FeeType | null, name: string) => void;
  onCreateNew: (name: string) => void;
  disabled?: boolean;
  hasError?: boolean;
}

function FeeTypeCombobox({ value, currentName, feeTypes, onSelect, onCreateNew, disabled, hasError }: FeeTypeComboboxProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");

  const selectedFeeType = feeTypes.find((ft) => ft.id === value);
  const filteredFeeTypes = feeTypes.filter((ft) =>
    ft.name.toLowerCase().includes(search.toLowerCase())
  );
  const showCreateOption = search.trim() && !filteredFeeTypes.some(
    (ft) => ft.name.toLowerCase() === search.toLowerCase()
  );

  const getCategoryBadge = (category?: FeeTypeCategory) => {
    const cat = FEE_TYPE_CATEGORIES.find((c) => c.value === category);
    if (!cat) return null;
    return (
      <Badge variant="secondary" className={cn("text-xs", cat.color)}>
        {cat.label}
      </Badge>
    );
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className={cn(
            "h-9 w-full justify-between font-normal",
            hasError && "border-destructive focus:ring-destructive"
          )}
          disabled={disabled}
        >
          {selectedFeeType ? (
            <span className="flex items-center gap-2">
              {selectedFeeType.name}
              {getCategoryBadge(selectedFeeType.category as FeeTypeCategory)}
            </span>
          ) : currentName ? (
            <span className="flex items-center gap-2">
              {currentName}
              {(() => {
                // Try to find a matching fee type by name to show its category
                const matchingFeeType = feeTypes.find(
                  (ft) => ft.name.toLowerCase() === currentName.toLowerCase()
                );
                return matchingFeeType
                  ? getCategoryBadge(matchingFeeType.category as FeeTypeCategory)
                  : <Badge variant="outline" className="text-xs text-muted-foreground">Custom</Badge>;
              })()}
            </span>
          ) : (
            <span className="text-muted-foreground">Select fee type...</span>
          )}
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[350px] p-0" align="start">
        <Command shouldFilter={false}>
          <CommandInput
            placeholder="Search fee types..."
            value={search}
            onValueChange={setSearch}
          />
          <CommandList>
            <CommandEmpty>
              {search ? "No fee type found." : "Start typing to search..."}
            </CommandEmpty>
            {filteredFeeTypes.length > 0 && (
              <CommandGroup heading="Fee Types">
                {filteredFeeTypes.map((feeType) => (
                  <CommandItem
                    key={feeType.id}
                    value={feeType.id}
                    onSelect={() => {
                      onSelect(feeType, feeType.name);
                      setOpen(false);
                      setSearch("");
                    }}
                  >
                    <Check
                      className={cn(
                        "mr-2 h-4 w-4",
                        value === feeType.id ? "opacity-100" : "opacity-0"
                      )}
                    />
                    <div className="flex flex-1 items-center justify-between">
                      <span>{feeType.name}</span>
                      {getCategoryBadge(feeType.category as FeeTypeCategory)}
                    </div>
                  </CommandItem>
                ))}
              </CommandGroup>
            )}
            {showCreateOption && (
              <>
                <CommandSeparator />
                <CommandGroup heading="Create New">
                  <CommandItem
                    onSelect={() => {
                      onCreateNew(search.trim());
                      setOpen(false);
                      setSearch("");
                    }}
                    className="text-primary"
                  >
                    <Plus className="mr-2 h-4 w-4" />
                    Create &quot;{search.trim()}&quot;
                  </CommandItem>
                </CommandGroup>
              </>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

interface CreateFeeTypeDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialName: string;
  onCreated: (feeType: FeeType) => void;
}

interface SortableItemProps {
  id: string;
  children: React.ReactNode;
}

function SortableItem({ id, children }: SortableItemProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        "grid grid-cols-[32px_1fr_120px_64px_40px] items-center gap-2 py-1.5 border-b",
        isDragging && "bg-muted rounded"
      )}
    >
      <button
        type="button"
        className="flex h-8 w-8 cursor-grab items-center justify-center rounded hover:bg-muted active:cursor-grabbing"
        {...attributes}
        {...listeners}
      >
        <GripVertical className="h-4 w-4 text-muted-foreground" />
      </button>
      {children}
    </div>
  );
}

function CreateFeeTypeDialog({ open, onOpenChange, initialName, onCreated }: CreateFeeTypeDialogProps) {
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();
  const [name, setName] = useState(initialName);
  const [category, setCategory] = useState<FeeTypeCategory>("other");
  const [description, setDescription] = useState("");

  useEffect(() => {
    if (open) {
      setName(initialName);
      setCategory("other");
      setDescription("");
    }
  }, [open, initialName]);

  const handleCreate = () => {
    if (!name.trim()) return;

    startTransition(async () => {
      const result = await createFeeType({
        name: name.trim(),
        category,
        description: description.trim() || undefined,
      });

      if (result.success && result.data) {
        toast({
          title: "Fee type created",
          description: `"${result.data.name}" has been added.`,
        });
        onCreated(result.data);
        onOpenChange(false);
      } else {
        toast({
          title: "Error",
          description: result.error || "Failed to create fee type",
          variant: "destructive",
        });
      }
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create New Fee Type</DialogTitle>
          <DialogDescription>
            Add a new fee type that can be reused across fee structures.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Name</label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Tuition Fee"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Category</label>
            <Select value={category} onValueChange={(v) => setCategory(v as FeeTypeCategory)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {FEE_TYPE_CATEGORIES.map((cat) => (
                  <SelectItem key={cat.value} value={cat.value}>
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary" className={cn("text-xs", cat.color)}>
                        {cat.label}
                      </Badge>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Description (Optional)</label>
            <Input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief description..."
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleCreate} disabled={isPending || !name.trim()}>
            {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Create Fee Type
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function NewFeeStructurePage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const copyId = searchParams.get("copy");
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();
  const [academicYears, setAcademicYears] = useState<AcademicYear[]>([]);
  const [terms, setTerms] = useState<Term[]>([]);
  const [classes, setClasses] = useState<Class[]>([]);
  const [feeTypes, setFeeTypes] = useState<FeeType[]>([]);
  const [createFeeTypeDialog, setCreateFeeTypeDialog] = useState<{
    open: boolean;
    name: string;
    itemIndex: number;
  }>({ open: false, name: "", itemIndex: -1 });

  const form = useForm<FeeStructureFormData>({
    resolver: zodResolver(feeStructureSchema),
    defaultValues: {
      name: "",
      academic_year_id: "",
      term_id: "",
      class_id: "",
      level_category: "",
      student_type: "all",
      is_active: true,
      items: [{ fee_type_id: "", name: "", amount: 0, is_optional: false, sequence: 0 }],
    },
  });

  const { fields, append, remove, move } = useFieldArray({
    control: form.control,
    name: "items",
  });

  // Drag and drop sensors
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event;

      if (over && active.id !== over.id) {
        const oldIndex = fields.findIndex((field) => field.id === active.id);
        const newIndex = fields.findIndex((field) => field.id === over.id);
        move(oldIndex, newIndex);
      }
    },
    [fields, move]
  );

  useEffect(() => {
    startTransition(async () => {
      const [yearsResult, termsResult, classesResult, currentYearResult, feeTypesResult] =
        await Promise.all([
          getAcademicYears(),
          getTerms(),
          getClasses(true),
          getCurrentAcademicYear(),
          getFeeTypes({ isActive: true }),
        ]);

      if (yearsResult.success && yearsResult.data) {
        setAcademicYears(yearsResult.data);
      }

      if (termsResult.success && termsResult.data) {
        setTerms(termsResult.data);
      }

      if (classesResult.success && classesResult.data) {
        setClasses(classesResult.data);
      }

      if (feeTypesResult.success && feeTypesResult.data) {
        setFeeTypes(feeTypesResult.data.items);
      }

      if (currentYearResult.success && currentYearResult.data) {
        form.setValue("academic_year_id", currentYearResult.data.id);
      }

      // If copying, load the source fee structure
      if (copyId) {
        const sourceResult = await getFeeStructure(copyId);
        if (sourceResult.success && sourceResult.data) {
          const source = sourceResult.data;
          form.setValue("name", `${source.name} (Copy)`);
          form.setValue("academic_year_id", source.academic_year_id || "");
          form.setValue("term_id", source.term_id || "__all__");
          form.setValue("class_id", source.class_id || "__none__");
          form.setValue("level_category", source.level_category || "__none__");
          form.setValue("student_type", source.student_type || "all");
          form.setValue("is_active", source.is_active);
          if (source.items && source.items.length > 0) {
            form.setValue(
              "items",
              source.items.map((item, index) => ({
                fee_type_id: item.fee_type_id || "",
                name: item.name,
                amount: Number(item.amount) || 0,
                is_optional: item.is_optional,
                sequence: index,
              }))
            );
          }
        }
      }
    });
  }, [form, copyId]);

  const handleFeeTypeSelect = useCallback(
    (index: number, feeType: FeeType | null, name: string) => {
      form.setValue(`items.${index}.fee_type_id`, feeType?.id || "");
      form.setValue(`items.${index}.name`, name);
    },
    [form]
  );

  const handleCreateNewFeeType = useCallback((index: number, name: string) => {
    setCreateFeeTypeDialog({ open: true, name, itemIndex: index });
  }, []);

  const handleFeeTypeCreated = useCallback(
    (feeType: FeeType) => {
      setFeeTypes((prev) => [...prev, feeType]);
      const index = createFeeTypeDialog.itemIndex;
      if (index >= 0) {
        form.setValue(`items.${index}.fee_type_id`, feeType.id);
        form.setValue(`items.${index}.name`, feeType.name);
      }
    },
    [createFeeTypeDialog.itemIndex, form]
  );

  const onSubmit = (data: FeeStructureFormData) => {
    startTransition(async () => {
      // Convert placeholder values to undefined
      const cleanValue = (val: string | undefined) =>
        val && val !== "__all__" && val !== "__none__" && val !== "" ? val : undefined;

      const levelCategory = cleanValue(data.level_category);
      const studentType = data.student_type as "all" | "boarding" | "day";

      const payload = {
        name: data.name,
        academic_year_id: cleanValue(data.academic_year_id),
        term_id: cleanValue(data.term_id),
        class_id: cleanValue(data.class_id),
        level_category: levelCategory as "preschool" | "primary" | "jhs" | "shs" | undefined,
        student_type: studentType,
        is_active: data.is_active,
        items: data.items.map((item, index) => ({
          fee_type_id: item.fee_type_id || undefined,
          name: item.name,
          amount: item.amount,
          is_optional: item.is_optional,
          sequence: index,
        })),
      };

      const result = await createFeeStructure(payload);

      if (result.success) {
        toast({
          title: "Fee structure created",
          description: "The fee structure has been created successfully.",
        });
        router.push("/finance/fee-structures");
      } else {
        toast({
          title: "Error",
          description: result.error || "Failed to create fee structure",
          variant: "destructive",
        });
      }
    });
  };

  const onInvalid = (errors: Record<string, unknown>) => {
    // Build a list of error messages
    const errorMessages: string[] = [];

    if (errors.name) {
      errorMessages.push("Fee structure name is required");
    }

    if (errors.academic_year_id) {
      errorMessages.push("Academic year is required");
    }

    if (errors.term_id) {
      errorMessages.push("Term is required");
    }

    if (errors.items) {
      const itemsError = errors.items as { message?: string; root?: { message?: string } } | Array<{ name?: { message?: string } }>;
      if (Array.isArray(itemsError)) {
        const hasNameErrors = itemsError.some((item) => item?.name);
        if (hasNameErrors) {
          errorMessages.push("All fee items must have a fee type selected");
        }
      } else if (itemsError.message) {
        errorMessages.push(itemsError.message);
      } else if (itemsError.root?.message) {
        errorMessages.push(itemsError.root.message);
      }
    }

    toast({
      title: "Validation Error",
      description: errorMessages.length > 0
        ? errorMessages.join(". ")
        : "Please fix the errors in the form",
      variant: "destructive",
    });
  };

  const watchedItems = form.watch("items");
  const { totalAmount, totalWithOptional } = useMemo(() => {
    let required = 0;
    let total = 0;
    for (const item of watchedItems) {
      const amount = item.amount || 0;
      total += amount;
      if (!item.is_optional) required += amount;
    }
    return { totalAmount: required, totalWithOptional: total };
  }, [watchedItems]);

  const selectedYearId = form.watch("academic_year_id");
  const filteredTerms = useMemo(
    () => terms.filter((t) => !selectedYearId || t.academic_year_id === selectedYearId),
    [terms, selectedYearId]
  );

  // Watch applicability fields once for the summary
  const watchedStudentType = form.watch("student_type");
  const watchedLevelCategory = form.watch("level_category");
  const watchedClassId = form.watch("class_id");

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/finance/fee-structures">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            {copyId ? "Duplicate Fee Structure" : "New Fee Structure"}
          </h1>
          <p className="text-muted-foreground">
            Create a fee template for a class or level
          </p>
        </div>
      </div>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit, onInvalid)} className="space-y-6">
          {/* Basic Information */}
          <Card>
            <CardHeader className="pb-4">
              <CardTitle>Basic Information</CardTitle>
              <CardDescription>
                Name and academic period for this fee structure
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Name and Status Row */}
              <div className="space-y-4">
                <FormField
                  control={form.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel className="text-base font-medium">Fee Structure Name</FormLabel>
                      <FormControl>
                        <Input
                          placeholder="e.g., Term 1 Fees 2025/2026 - JHS Boarding"
                          className="h-11 text-base"
                          {...field}
                        />
                      </FormControl>
                      <FormDescription>
                        Use a descriptive name that includes the term, year, and target group
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="is_active"
                  render={({ field }) => (
                    <FormItem className="flex flex-row items-center justify-between rounded-xl border bg-muted/30 p-4">
                      <div className="flex items-center gap-3">
                        <div className={cn(
                          "flex h-10 w-10 items-center justify-center rounded-full",
                          field.value ? "bg-green-100 text-green-600" : "bg-gray-100 text-gray-400"
                        )}>
                          <Check className="h-5 w-5" />
                        </div>
                        <div className="space-y-0.5">
                          <FormLabel className="text-base font-medium">Status</FormLabel>
                          <FormDescription>
                            {field.value ? "This fee structure is active and can be used for invoices" : "This fee structure is inactive"}
                          </FormDescription>
                        </div>
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
              </div>

              {/* Academic Period Section */}
              <div className="space-y-4">
                <h4 className="text-sm font-medium text-muted-foreground">Academic Period</h4>
                <div className="grid gap-4 md:grid-cols-2">
                  <FormField
                    control={form.control}
                    name="academic_year_id"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Academic Year</FormLabel>
                        <Select
                          onValueChange={field.onChange}
                          value={field.value}
                        >
                          <FormControl>
                            <SelectTrigger className="h-11 w-full">
                              <SelectValue placeholder="Select academic year" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {academicYears.map((year) => (
                              <SelectItem key={year.id} value={year.id}>
                                {year.name}
                                {year.is_current && (
                                  <Badge variant="secondary" className="ml-2 text-xs">Current</Badge>
                                )}
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
                    name="term_id"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Term</FormLabel>
                        <Select
                          onValueChange={field.onChange}
                          value={field.value}
                        >
                          <FormControl>
                            <SelectTrigger className="h-11 w-full">
                              <SelectValue placeholder="Select term" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            <SelectItem value="__all__">
                              <span className="font-medium">All Terms</span>
                              <span className="ml-2 text-muted-foreground">- Applies to entire year</span>
                            </SelectItem>
                            {filteredTerms.map((term) => (
                              <SelectItem key={term.id} value={term.id}>
                                {term.name}
                                {term.is_current && (
                                  <Badge variant="secondary" className="ml-2 text-xs">Current</Badge>
                                )}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Applicability */}
          <Card>
            <CardHeader className="pb-4">
              <CardTitle>Applies To</CardTitle>
              <CardDescription>
                Define which students this fee structure applies to
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                <FormField
                  control={form.control}
                  name="level_category"
                  render={({ field }) => (
                    <FormItem className="w-full">
                      <FormLabel>Level</FormLabel>
                      <Select
                        onValueChange={field.onChange}
                        value={field.value}
                      >
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder="All levels" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value="__none__">All Levels</SelectItem>
                          {LEVEL_CATEGORIES.map((cat) => (
                            <SelectItem key={cat.value} value={cat.value}>
                              {cat.label}
                              <span className="ml-1 text-muted-foreground text-xs">
                                ({cat.description})
                              </span>
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormDescription>
                        School level category
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="class_id"
                  render={({ field }) => (
                    <FormItem className="w-full">
                      <FormLabel>Class</FormLabel>
                      <Select
                        onValueChange={field.onChange}
                        value={field.value}
                      >
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder="All classes" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value="__none__">All Classes</SelectItem>
                          {classes.map((cls) => (
                            <SelectItem key={cls.id} value={cls.id}>
                              {cls.name}
                              {cls.sections && cls.sections.length > 0 && (
                                <span className="ml-1 text-muted-foreground">
                                  ({cls.sections.length} section{cls.sections.length > 1 ? "s" : ""})
                                </span>
                              )}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormDescription>
                        Specific class (optional)
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="student_type"
                  render={({ field }) => (
                    <FormItem className="w-full">
                      <FormLabel>Student Type</FormLabel>
                      <Select
                        onValueChange={field.onChange}
                        value={field.value}
                      >
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder="All students" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {STUDENT_TYPES.map((type) => (
                            <SelectItem key={type.value} value={type.value}>
                              {type.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormDescription>
                        Boarding or day students
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              {/* Summary of applicability */}
              <div className="rounded-lg bg-muted/50 p-4">
                <p className="text-sm text-muted-foreground">
                  <span className="font-medium text-foreground">This fee structure applies to: </span>
                  {watchedStudentType === "all" ? "All students" :
                   watchedStudentType === "boarding" ? "Boarding students" : "Day students"}
                  {watchedLevelCategory && watchedLevelCategory !== "__none__" && (
                    <> in <span className="font-medium text-foreground">
                      {LEVEL_CATEGORIES.find(c => c.value === watchedLevelCategory)?.label}
                    </span></>
                  )}
                  {watchedClassId && watchedClassId !== "__none__" && (
                    <> specifically in <span className="font-medium text-foreground">
                      {classes.find(c => c.id === watchedClassId)?.name}
                    </span></>
                  )}
                  {(!watchedLevelCategory || watchedLevelCategory === "__none__") &&
                   (!watchedClassId || watchedClassId === "__none__") && (
                    <> across <span className="font-medium text-foreground">all levels and classes</span></>
                  )}
                </p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-4">
              <div>
                <CardTitle>Fee Items</CardTitle>
                <CardDescription>
                  Select from existing fee types or create new ones
                </CardDescription>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() =>
                  append({
                    fee_type_id: "",
                    name: "",
                    amount: 0,
                    is_optional: false,
                    sequence: fields.length,
                  })
                }
              >
                <Plus className="mr-2 h-4 w-4" />
                Add Item
              </Button>
            </CardHeader>
            <CardContent>
              {fields.length > 0 ? (
                <DndContext
                  sensors={sensors}
                  collisionDetection={closestCenter}
                  onDragEnd={handleDragEnd}
                >
                  {/* Header */}
                  <div className="grid grid-cols-[32px_1fr_120px_64px_40px] items-center gap-2 pb-2 text-sm font-medium text-muted-foreground border-b">
                    <div></div>
                    <div>Fee Type</div>
                    <div>Amount (GHS)</div>
                    <div className="text-center">Optional</div>
                    <div></div>
                  </div>

                  {/* Items */}
                  <SortableContext
                    items={fields.map((f) => f.id)}
                    strategy={verticalListSortingStrategy}
                  >
                    {fields.map((field, index) => (
                      <SortableItem key={field.id} id={field.id}>
                        <div className="flex items-center min-w-0">
                          <FormField
                            control={form.control}
                            name={`items.${index}.name`}
                            render={({ fieldState }) => (
                              <FormControl>
                                <FeeTypeCombobox
                                  value={form.watch(`items.${index}.fee_type_id`)}
                                  currentName={form.watch(`items.${index}.name`)}
                                  feeTypes={feeTypes}
                                  onSelect={(ft, name) => handleFeeTypeSelect(index, ft, name)}
                                  onCreateNew={(name) => handleCreateNewFeeType(index, name)}
                                  hasError={!!fieldState.error}
                                />
                              </FormControl>
                            )}
                          />
                        </div>
                        <div className="flex items-center">
                          <FormField
                            control={form.control}
                            name={`items.${index}.amount`}
                            render={({ field }) => (
                              <FormControl>
                                <Input
                                  type="number"
                                  step="0.01"
                                  min="0"
                                  placeholder="0.00"
                                  className="h-9"
                                  {...field}
                                  onChange={(e) => field.onChange(e.target.valueAsNumber || 0)}
                                />
                              </FormControl>
                            )}
                          />
                        </div>
                        <div className="flex items-center justify-center">
                          <FormField
                            control={form.control}
                            name={`items.${index}.is_optional`}
                            render={({ field }) => (
                              <FormControl>
                                <Checkbox
                                  checked={field.value}
                                  onCheckedChange={field.onChange}
                                />
                              </FormControl>
                            )}
                          />
                        </div>
                        <div className="flex items-center justify-center">
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            onClick={() => remove(index)}
                            disabled={fields.length === 1}
                          >
                            <Trash className="h-4 w-4 text-destructive" />
                          </Button>
                        </div>
                      </SortableItem>
                    ))}
                  </SortableContext>
                </DndContext>
              ) : (
                <div className="flex h-[100px] items-center justify-center text-muted-foreground">
                  No fee items added
                </div>
              )}

              {/* Totals */}
              <div className="mt-4 flex justify-end gap-8 border-t pt-4">
                <div className="text-right">
                  <p className="text-sm text-muted-foreground">
                    Required Total
                  </p>
                  <p className="text-xl font-bold">
                    {formatCurrency(totalAmount)}
                  </p>
                </div>
                {totalWithOptional !== totalAmount && (
                  <div className="text-right">
                    <p className="text-sm text-muted-foreground">
                      With Optional
                    </p>
                    <p className="text-xl font-bold text-muted-foreground">
                      {formatCurrency(totalWithOptional)}
                    </p>
                  </div>
                )}
              </div>

              {form.formState.errors.items && (
                <p className="mt-2 text-sm text-destructive">
                  {form.formState.errors.items.message}
                </p>
              )}
            </CardContent>
          </Card>

          <div className="flex justify-end gap-4">
            <Button type="button" variant="outline" asChild>
              <Link href="/finance/fee-structures">Cancel</Link>
            </Button>
            <Button type="submit" disabled={isPending}>
              {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Create Fee Structure
            </Button>
          </div>
        </form>
      </Form>

      <CreateFeeTypeDialog
        open={createFeeTypeDialog.open}
        onOpenChange={(open) => setCreateFeeTypeDialog((prev) => ({ ...prev, open }))}
        initialName={createFeeTypeDialog.name}
        onCreated={handleFeeTypeCreated}
      />
    </div>
  );
}
