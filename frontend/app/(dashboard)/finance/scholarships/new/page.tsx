"use client";

import { useState, useEffect, useTransition, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
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
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
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
import { Switch } from "@/components/ui/switch";
import { Checkbox } from "@/components/ui/checkbox";
import {
  ArrowLeft,
  Loader2,
  GraduationCap,
  Trophy,
  Heart,
  Medal,
  Sparkles,
  Star,
  Percent,
  Banknote,
  Users,
  CheckCircle2,
  Info,
  Calculator,
} from "lucide-react";
import { createScholarship, getFeeTypes } from "@/actions/finance.action";
import { getAcademicYears, getCurrentAcademicYear } from "@/actions/academic.action";
import type { AcademicYear } from "@/types";
import type { FeeType } from "@/types/finance.type";
import { formatCurrency } from "@/lib/format";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";

const scholarshipSchema = z.object({
  name: z.string().min(1, "Name is required").max(100),
  code: z.string().min(1, "Code is required").max(20),
  description: z.string().optional(),
  scholarship_type: z.enum([
    "full",
    "partial",
    "merit",
    "need_based",
    "athletic",
    "special",
  ]),
  coverage_type: z.enum(["percentage", "fixed_amount"]),
  coverage_value: z.coerce.number().min(0, "Coverage value must be positive"),
  max_recipients: z.coerce.number().int().min(0).optional().nullable(),
  academic_year_id: z.string().optional(),
  applicable_fees: z.array(z.string()).optional(),
  is_active: z.boolean(),
});

type ScholarshipFormData = z.infer<typeof scholarshipSchema>;

// Scholarship type configuration with dark mode support
const SCHOLARSHIP_TYPES = [
  {
    value: "full",
    label: "Full",
    description: "100% coverage of all fees",
    icon: Star,
    color: "text-amber-600 dark:text-amber-400",
    iconBgColor: "bg-amber-200 dark:bg-amber-900",
    borderColor: "border-amber-300 dark:border-amber-700",
    selectedBg: "bg-amber-50 dark:bg-amber-950/50",
  },
  {
    value: "partial",
    label: "Partial",
    description: "Covers a portion of fees",
    icon: GraduationCap,
    color: "text-blue-600 dark:text-blue-400",
    iconBgColor: "bg-blue-200 dark:bg-blue-900",
    borderColor: "border-blue-300 dark:border-blue-700",
    selectedBg: "bg-blue-50 dark:bg-blue-950/50",
  },
  {
    value: "merit",
    label: "Merit",
    description: "Based on academic excellence",
    icon: Trophy,
    color: "text-purple-600 dark:text-purple-400",
    iconBgColor: "bg-purple-200 dark:bg-purple-900",
    borderColor: "border-purple-300 dark:border-purple-700",
    selectedBg: "bg-purple-50 dark:bg-purple-950/50",
  },
  {
    value: "need_based",
    label: "Need-Based",
    description: "For financial assistance",
    icon: Heart,
    color: "text-rose-600 dark:text-rose-400",
    iconBgColor: "bg-rose-200 dark:bg-rose-900",
    borderColor: "border-rose-300 dark:border-rose-700",
    selectedBg: "bg-rose-50 dark:bg-rose-950/50",
  },
  {
    value: "athletic",
    label: "Athletic",
    description: "Sports achievement award",
    icon: Medal,
    color: "text-green-600 dark:text-green-400",
    iconBgColor: "bg-green-200 dark:bg-green-900",
    borderColor: "border-green-300 dark:border-green-700",
    selectedBg: "bg-green-50 dark:bg-green-950/50",
  },
  {
    value: "special",
    label: "Special",
    description: "Other special awards",
    icon: Sparkles,
    color: "text-teal-600 dark:text-teal-400",
    iconBgColor: "bg-teal-200 dark:bg-teal-900",
    borderColor: "border-teal-300 dark:border-teal-700",
    selectedBg: "bg-teal-50 dark:bg-teal-950/50",
  },
];

// Quick percentage presets
const QUICK_PERCENTAGES = [25, 50, 75, 100];

// Quick amount presets
const QUICK_AMOUNTS = [100, 250, 500, 1000];

export default function NewScholarshipPage() {
  const router = useRouter();
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const [academicYears, setAcademicYears] = useState<AcademicYear[]>([]);
  const [feeTypes, setFeeTypes] = useState<FeeType[]>([]);

  const form = useForm<ScholarshipFormData>({
    resolver: zodResolver(scholarshipSchema),
    defaultValues: {
      name: "",
      code: "",
      description: "",
      scholarship_type: "partial",
      coverage_type: "percentage",
      coverage_value: 0,
      max_recipients: null,
      academic_year_id: "",
      applicable_fees: ["all"],
      is_active: true,
    },
  });

  const scholarshipType = form.watch("scholarship_type");
  const coverageType = form.watch("coverage_type");
  const coverageValue = form.watch("coverage_value");
  const name = form.watch("name");
  const code = form.watch("code");
  const maxRecipients = form.watch("max_recipients");
  const isActive = form.watch("is_active");
  const applicableFees = form.watch("applicable_fees");

  // Get selected type config
  const selectedTypeConfig = useMemo(
    () => SCHOLARSHIP_TYPES.find((t) => t.value === scholarshipType),
    [scholarshipType]
  );

  // Calculate form completion percentage
  const formCompletion = useMemo(() => {
    let completed = 0;
    const total = 4; // type, name, code, coverage
    if (scholarshipType) completed++;
    if (name?.trim()) completed++;
    if (code?.trim()) completed++;
    if (coverageValue > 0) completed++;
    return Math.round((completed / total) * 100);
  }, [scholarshipType, name, code, coverageValue]);

  // Calculate example discount
  const exampleDiscount = useMemo(() => {
    const exampleFee = 1000;
    if (coverageType === "percentage") {
      return (exampleFee * coverageValue) / 100;
    }
    return Math.min(coverageValue, exampleFee);
  }, [coverageType, coverageValue]);

  useEffect(() => {
    const loadData = async () => {
      setIsInitialLoading(true);
      try {
        const [yearsResult, currentYearResult, feeTypesResult] = await Promise.all([
          getAcademicYears(),
          getCurrentAcademicYear(),
          getFeeTypes({ isActive: true }),
        ]);

        if (yearsResult.success && yearsResult.data) {
          setAcademicYears(yearsResult.data);
        }

        if (currentYearResult.success && currentYearResult.data) {
          form.setValue("academic_year_id", currentYearResult.data.id);
        }

        if (feeTypesResult.success && feeTypesResult.data) {
          setFeeTypes(feeTypesResult.data.items);
        }
      } finally {
        setIsInitialLoading(false);
      }
    };

    loadData();
  }, [form]);

  const onSubmit = useCallback(
    (data: ScholarshipFormData) => {
      startTransition(async () => {
        const payload = {
          ...data,
          max_recipients: data.max_recipients || undefined,
          academic_year_id: data.academic_year_id || undefined,
          applicable_fees:
            !data.applicable_fees || data.applicable_fees.length === 0
              ? ["all"]
              : data.applicable_fees,
        };

        const result = await createScholarship(payload);

        if (result.success) {
          toast({
            title: "Scholarship created",
            description: "The scholarship has been created successfully.",
          });
          router.push("/finance/scholarships");
        } else {
          toast({
            title: "Error",
            description: result.error || "Failed to create scholarship",
            variant: "destructive",
          });
        }
      });
    },
    [toast, router]
  );

  const handleQuickValue = useCallback(
    (value: number) => {
      form.setValue("coverage_value", value);
    },
    [form]
  );

  // Auto-set coverage to 100% when Full scholarship is selected
  useEffect(() => {
    if (scholarshipType === "full" && coverageType === "percentage") {
      form.setValue("coverage_value", 100);
    }
  }, [scholarshipType, coverageType, form]);

  if (isInitialLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Skeleton className="h-10 w-10 rounded-md" />
          <div className="space-y-2">
            <Skeleton className="h-6 w-48" />
            <Skeleton className="h-4 w-64" />
          </div>
        </div>
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2 space-y-6">
            <Card>
              <CardHeader>
                <Skeleton className="h-6 w-40" />
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-3 gap-3">
                  {[1, 2, 3, 4, 5, 6].map((i) => (
                    <Skeleton key={i} className="h-24 w-full" />
                  ))}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <Skeleton className="h-6 w-32" />
              </CardHeader>
              <CardContent className="space-y-4">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </CardContent>
            </Card>
          </div>
          <div>
            <Card>
              <CardHeader>
                <Skeleton className="h-6 w-32" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-40 w-full" />
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link href="/finance/scholarships">
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">New Scholarship</h1>
            <p className="text-muted-foreground">
              Create a new scholarship program
            </p>
          </div>
        </div>
        {/* Progress indicator */}
        <div className="hidden md:flex items-center gap-3">
          <div className="text-sm text-muted-foreground">
            {formCompletion}% complete
          </div>
          <div className="w-24 h-2 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-primary transition-all duration-300"
              style={{ width: `${formCompletion}%` }}
            />
          </div>
        </div>
      </div>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)}>
          <div className="grid gap-6 lg:grid-cols-3">
            {/* Main Form */}
            <div className="lg:col-span-2 space-y-6">
              {/* Scholarship Type Selection */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Scholarship Type</CardTitle>
                  <CardDescription>
                    Select the category that best describes this scholarship
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <FormField
                    control={form.control}
                    name="scholarship_type"
                    render={({ field }) => (
                      <FormItem>
                        <FormControl>
                          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                            {SCHOLARSHIP_TYPES.map((type) => {
                              const Icon = type.icon;
                              const isSelected = field.value === type.value;
                              return (
                                <button
                                  key={type.value}
                                  type="button"
                                  onClick={() => field.onChange(type.value)}
                                  className={cn(
                                    "relative flex flex-col items-start gap-2 rounded-lg border-2 p-4 text-left transition-all",
                                    isSelected
                                      ? `${type.borderColor} ${type.selectedBg}`
                                      : "border-border hover:border-muted-foreground/50 hover:bg-muted/50"
                                  )}
                                >
                                  {isSelected && (
                                    <CheckCircle2
                                      className={cn("absolute top-2 right-2 h-5 w-5", type.color)}
                                    />
                                  )}
                                  <div className={cn("p-2 rounded-md", type.iconBgColor)}>
                                    <Icon className={cn("h-5 w-5", type.color)} />
                                  </div>
                                  <div>
                                    <div className={cn("font-medium", isSelected && type.color)}>
                                      {type.label}
                                    </div>
                                    <div className="text-xs text-muted-foreground line-clamp-2">
                                      {type.description}
                                    </div>
                                  </div>
                                </button>
                              );
                            })}
                          </div>
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </CardContent>
              </Card>

              {/* Basic Information */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Basic Information</CardTitle>
                  <CardDescription>
                    Enter the scholarship name and identifier
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-4 md:grid-cols-2">
                    <FormField
                      control={form.control}
                      name="name"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Scholarship Name *</FormLabel>
                          <FormControl>
                            <Input
                              placeholder="e.g., Academic Excellence Award"
                              {...field}
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="code"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Code *</FormLabel>
                          <FormControl>
                            <Input placeholder="e.g., AEA-2026" {...field} />
                          </FormControl>
                          <FormDescription>
                            Unique identifier
                          </FormDescription>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>

                  <FormField
                    control={form.control}
                    name="description"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Description</FormLabel>
                        <FormControl>
                          <Textarea
                            placeholder="Describe the scholarship criteria, eligibility requirements, and benefits..."
                            rows={3}
                            className="resize-none"
                            {...field}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="academic_year_id"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Academic Year</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue placeholder="Select year" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {academicYears.map((year) => (
                              <SelectItem key={year.id} value={year.id}>
                                {year.name}
                                {year.is_current && (
                                  <Badge variant="secondary" className="ml-2 text-xs">
                                    Current
                                  </Badge>
                                )}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <FormDescription>
                          Leave empty to apply to all academic years
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </CardContent>
              </Card>

              {/* Coverage */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Coverage Amount</CardTitle>
                  <CardDescription>
                    Define how much this scholarship covers
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <FormField
                    control={form.control}
                    name="coverage_type"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Coverage Type</FormLabel>
                        <FormControl>
                          <div className="grid gap-3 md:grid-cols-2">
                            <button
                              type="button"
                              onClick={() => field.onChange("percentage")}
                              className={cn(
                                "flex items-center gap-3 rounded-lg border-2 p-4 text-left transition-all",
                                field.value === "percentage"
                                  ? "border-primary bg-primary/5"
                                  : "border-border hover:border-muted-foreground/50"
                              )}
                            >
                              <div className={cn(
                                "p-2 rounded-md",
                                field.value === "percentage"
                                  ? "bg-primary/20"
                                  : "bg-muted"
                              )}>
                                <Percent className={cn(
                                  "h-5 w-5",
                                  field.value === "percentage"
                                    ? "text-primary"
                                    : "text-muted-foreground"
                                )} />
                              </div>
                              <div>
                                <div className="font-medium">Percentage</div>
                                <div className="text-xs text-muted-foreground">
                                  Cover a percentage of fees
                                </div>
                              </div>
                            </button>
                            <button
                              type="button"
                              onClick={() => field.onChange("fixed_amount")}
                              className={cn(
                                "flex items-center gap-3 rounded-lg border-2 p-4 text-left transition-all",
                                field.value === "fixed_amount"
                                  ? "border-primary bg-primary/5"
                                  : "border-border hover:border-muted-foreground/50"
                              )}
                            >
                              <div className={cn(
                                "p-2 rounded-md",
                                field.value === "fixed_amount"
                                  ? "bg-primary/20"
                                  : "bg-muted"
                              )}>
                                <Banknote className={cn(
                                  "h-5 w-5",
                                  field.value === "fixed_amount"
                                    ? "text-primary"
                                    : "text-muted-foreground"
                                )} />
                              </div>
                              <div>
                                <div className="font-medium">Fixed Amount</div>
                                <div className="text-xs text-muted-foreground">
                                  Deduct a specific amount
                                </div>
                              </div>
                            </button>
                          </div>
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="coverage_value"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>
                          {coverageType === "percentage" ? "Percentage" : "Amount"} *
                        </FormLabel>
                        <FormControl>
                          <div className="space-y-3">
                            <div className="relative">
                              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground font-medium">
                                {coverageType === "percentage" ? "%" : "GHS"}
                              </span>
                              <Input
                                type="number"
                                step={coverageType === "percentage" ? "1" : "0.01"}
                                min="0"
                                max={coverageType === "percentage" ? "100" : undefined}
                                placeholder="0"
                                className="pl-12 text-lg font-semibold h-12"
                                {...field}
                                onChange={(e) => field.onChange(e.target.valueAsNumber || 0)}
                              />
                            </div>
                            {/* Quick value buttons */}
                            <div className="flex flex-wrap gap-2">
                              <span className="text-xs text-muted-foreground self-center mr-1">
                                Quick:
                              </span>
                              {(coverageType === "percentage" ? QUICK_PERCENTAGES : QUICK_AMOUNTS).map(
                                (value) => (
                                  <Button
                                    key={value}
                                    type="button"
                                    variant={coverageValue === value ? "default" : "outline"}
                                    size="sm"
                                    onClick={() => handleQuickValue(value)}
                                    className="h-7 px-3 text-xs"
                                  >
                                    {coverageType === "percentage" ? `${value}%` : formatCurrency(value)}
                                  </Button>
                                )
                              )}
                            </div>
                          </div>
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  {/* Coverage Preview */}
                  {coverageValue > 0 && (
                    <div className="rounded-lg border bg-muted/30 p-4">
                      <div className="flex items-start gap-3">
                        <Calculator className="h-5 w-5 text-muted-foreground mt-0.5" />
                        <div className="flex-1">
                          <div className="text-sm font-medium">Coverage Preview</div>
                          <div className="text-xs text-muted-foreground mt-1">
                            For an example fee of {formatCurrency(1000)}:
                          </div>
                          <div className="mt-2 flex items-baseline gap-2">
                            <span className={cn("text-lg font-bold", selectedTypeConfig?.color)}>
                              {formatCurrency(exampleDiscount)}
                            </span>
                            <span className="text-sm text-muted-foreground">
                              discount applied
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  <Separator />

                  <FormField
                    control={form.control}
                    name="max_recipients"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Maximum Recipients</FormLabel>
                        <FormControl>
                          <div className="relative">
                            <Users className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                            <Input
                              type="number"
                              min="0"
                              placeholder="Unlimited"
                              className="pl-9"
                              {...field}
                              value={field.value || ""}
                              onChange={(e) =>
                                field.onChange(e.target.value ? parseInt(e.target.value) : null)
                              }
                            />
                          </div>
                        </FormControl>
                        <FormDescription>
                          Leave empty for unlimited recipients
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </CardContent>
              </Card>

              {/* Applicable Fees */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Applicable Fees</CardTitle>
                  <CardDescription>
                    Choose which fee components this scholarship covers
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <FormField
                    control={form.control}
                    name="applicable_fees"
                    render={({ field }) => {
                      const values = field.value || ["all"];
                      return (
                        <FormItem>
                          <div className="space-y-3">
                            <div
                              className={cn(
                                "flex items-center justify-between rounded-lg border p-4 cursor-pointer transition-colors",
                                values.includes("all")
                                  ? "border-primary bg-primary/5"
                                  : "hover:bg-muted/50"
                              )}
                              onClick={() => {
                                if (!values.includes("all")) {
                                  field.onChange(["all"]);
                                }
                              }}
                            >
                              <div className="flex items-center space-x-3">
                                <Checkbox
                                  id="all-fees"
                                  checked={values.includes("all")}
                                  onCheckedChange={(checked) => {
                                    if (checked) {
                                      field.onChange(["all"]);
                                    } else {
                                      field.onChange([]);
                                    }
                                  }}
                                />
                                <div>
                                  <label
                                    htmlFor="all-fees"
                                    className="text-sm font-medium cursor-pointer"
                                  >
                                    All Fees
                                  </label>
                                  <p className="text-xs text-muted-foreground">
                                    Applies to the entire invoice amount
                                  </p>
                                </div>
                              </div>
                              <Badge variant="secondary">Recommended</Badge>
                            </div>

                            {!values.includes("all") && feeTypes.length > 0 && (
                              <div className="grid gap-2 sm:grid-cols-2">
                                {feeTypes.map((feeType) => (
                                  <div
                                    key={feeType.id}
                                    className={cn(
                                      "flex items-center space-x-3 rounded-lg border p-3 cursor-pointer transition-colors",
                                      values.includes(feeType.id)
                                        ? "border-primary bg-primary/5"
                                        : "hover:bg-muted/50"
                                    )}
                                    onClick={() => {
                                      if (values.includes(feeType.id)) {
                                        field.onChange(values.filter((v) => v !== feeType.id));
                                      } else {
                                        field.onChange([...values, feeType.id]);
                                      }
                                    }}
                                  >
                                    <Checkbox
                                      id={`fee-type-${feeType.id}`}
                                      checked={values.includes(feeType.id)}
                                      onCheckedChange={(checked) => {
                                        if (checked) {
                                          field.onChange([...values, feeType.id]);
                                        } else {
                                          field.onChange(values.filter((v) => v !== feeType.id));
                                        }
                                      }}
                                    />
                                    <div>
                                      <label
                                        htmlFor={`fee-type-${feeType.id}`}
                                        className="text-sm font-medium cursor-pointer"
                                      >
                                        {feeType.name}
                                      </label>
                                      {feeType.category && (
                                        <p className="text-xs text-muted-foreground">
                                          {feeType.category}
                                        </p>
                                      )}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            )}

                            {!values.includes("all") && feeTypes.length === 0 && (
                              <div className="rounded-lg border border-dashed p-4 text-center">
                                <p className="text-sm text-muted-foreground">
                                  No fee types configured. Create fee types in Finance Settings first.
                                </p>
                              </div>
                            )}
                          </div>
                          <FormMessage />
                        </FormItem>
                      );
                    }}
                  />
                </CardContent>
              </Card>

              {/* Status */}
              <Card>
                <CardContent className="pt-6">
                  <FormField
                    control={form.control}
                    name="is_active"
                    render={({ field }) => (
                      <FormItem className="flex flex-row items-center justify-between">
                        <div className="space-y-0.5">
                          <FormLabel className="text-base">Active Status</FormLabel>
                          <FormDescription>
                            Enable this scholarship for new awards
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
                </CardContent>
              </Card>
            </div>

            {/* Sidebar */}
            <div className="space-y-6">
              {/* Summary Card */}
              <Card className="sticky top-6">
                <CardHeader className="pb-3">
                  <CardTitle className="text-lg flex items-center gap-2">
                    <GraduationCap className="h-5 w-5" />
                    Scholarship Summary
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Type */}
                  <div className="flex items-start gap-3">
                    {selectedTypeConfig && (
                      <>
                        <div className={cn("p-2 rounded-md", selectedTypeConfig.iconBgColor)}>
                          <selectedTypeConfig.icon
                            className={cn("h-4 w-4", selectedTypeConfig.color)}
                          />
                        </div>
                        <div>
                          <div className={cn("text-sm font-medium", selectedTypeConfig.color)}>
                            {selectedTypeConfig.label} Scholarship
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {selectedTypeConfig.description}
                          </div>
                        </div>
                      </>
                    )}
                  </div>

                  <Separator />

                  {/* Name & Code */}
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">Name</div>
                    {name ? (
                      <div className="font-medium">{name}</div>
                    ) : (
                      <div className="text-sm text-muted-foreground italic">Not set</div>
                    )}
                    {code && (
                      <Badge variant="outline" className="mt-1">
                        {code}
                      </Badge>
                    )}
                  </div>

                  <Separator />

                  {/* Coverage */}
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">Coverage</div>
                    <div
                      className={cn(
                        "text-2xl font-bold",
                        coverageValue > 0 ? selectedTypeConfig?.color : "text-muted-foreground"
                      )}
                    >
                      {coverageValue > 0
                        ? coverageType === "percentage"
                          ? `${coverageValue}%`
                          : formatCurrency(coverageValue)
                        : "Not set"}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {coverageType === "percentage" ? "of applicable fees" : "fixed discount"}
                    </div>
                  </div>

                  {/* Recipients */}
                  {maxRecipients && (
                    <div>
                      <div className="text-xs text-muted-foreground mb-1">Max Recipients</div>
                      <div className="font-medium">{maxRecipients} students</div>
                    </div>
                  )}

                  {/* Applicable Fees */}
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">Applies To</div>
                    <div className="text-sm">
                      {applicableFees?.includes("all")
                        ? "All fee types"
                        : `${applicableFees?.length || 0} specific fee type(s)`}
                    </div>
                  </div>

                  {/* Status */}
                  <div className="flex items-center gap-2">
                    <div
                      className={cn(
                        "h-2 w-2 rounded-full",
                        isActive ? "bg-green-500" : "bg-gray-400"
                      )}
                    />
                    <span className="text-sm">{isActive ? "Active" : "Inactive"}</span>
                  </div>

                  {/* Info message */}
                  <div className="rounded-md bg-blue-100 dark:bg-blue-950 border border-blue-300 dark:border-blue-800 p-3">
                    <div className="flex gap-2">
                      <Info className="h-4 w-4 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" />
                      <p className="text-xs text-blue-700 dark:text-blue-300">
                        After creating, you can award this scholarship to individual students
                        from the scholarship detail page.
                      </p>
                    </div>
                  </div>

                  {/* Action Buttons */}
                  <div className="space-y-2 pt-2">
                    <Button
                      type="submit"
                      className="w-full"
                      size="lg"
                      disabled={isPending || formCompletion < 100}
                    >
                      {isPending ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Creating...
                        </>
                      ) : (
                        <>
                          <GraduationCap className="mr-2 h-4 w-4" />
                          Create Scholarship
                        </>
                      )}
                    </Button>
                    <Button type="button" variant="outline" className="w-full" asChild>
                      <Link href="/finance/scholarships">Cancel</Link>
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </form>
      </Form>
    </div>
  );
}
