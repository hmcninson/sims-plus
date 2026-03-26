"use client";

import { useState, useEffect, useTransition, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useForm , type Resolver} from "react-hook-form";
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
import { ArrowLeft, Loader2, AlertCircle } from "lucide-react";
import { getScholarship, updateScholarship, getFeeTypes } from "@/actions/finance.action";
import { getAcademicYears } from "@/actions/academic.action";
import type { AcademicYear, Scholarship } from "@/types";
import type { FeeType } from "@/types/finance.type";
import { useToast } from "@/hooks/use-toast";

// ============================================
// Schema (outside component)
// ============================================

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

// ============================================
// Constants
// ============================================

const SCHOLARSHIP_TYPES = [
  { value: "full", label: "Full Scholarship" },
  { value: "partial", label: "Partial Scholarship" },
  { value: "merit", label: "Merit-Based" },
  { value: "need_based", label: "Need-Based" },
  { value: "athletic", label: "Athletic" },
  { value: "special", label: "Special" },
];

const COVERAGE_TYPES = [
  { value: "percentage", label: "Percentage of Fees" },
  { value: "fixed_amount", label: "Fixed Amount" },
];

// ============================================
// Main Component
// ============================================

export default function EditScholarshipPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();
  const [isSaving, setIsSaving] = useState(false);
  const [academicYears, setAcademicYears] = useState<AcademicYear[]>([]);
  const [feeTypes, setFeeTypes] = useState<FeeType[]>([]);
  const [scholarship, setScholarship] = useState<Scholarship | null>(null);
  const [error, setError] = useState<string | null>(null);
  const hasLoadedRef = useRef(false);

  const scholarshipId = params.id as string;

  const form = useForm<ScholarshipFormData>({
    resolver: zodResolver(scholarshipSchema) as Resolver<ScholarshipFormData>,
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

  // Load initial data
  useEffect(() => {
    if (hasLoadedRef.current) return;
    hasLoadedRef.current = true;

    startTransition(async () => {
      const [scholarshipResult, yearsResult, feeTypesResult] = await Promise.all([
        getScholarship(scholarshipId),
        getAcademicYears(),
        getFeeTypes({ isActive: true }),
      ]);

      if (yearsResult.success && yearsResult.data) {
        setAcademicYears(yearsResult.data);
      }

      if (feeTypesResult.success && feeTypesResult.data) {
        setFeeTypes(feeTypesResult.data.items);
      }

      if (scholarshipResult.success && scholarshipResult.data) {
        const s = scholarshipResult.data;
        setScholarship(s);
        form.reset({
          name: s.name,
          code: s.code,
          description: s.description || "",
          scholarship_type: s.scholarship_type as ScholarshipFormData["scholarship_type"],
          coverage_type: s.coverage_type as ScholarshipFormData["coverage_type"],
          coverage_value: s.coverage_value,
          max_recipients: s.max_recipients || null,
          academic_year_id: s.academic_year_id || "",
          applicable_fees: s.applicable_fees && s.applicable_fees.length > 0 ? s.applicable_fees : ["all"],
          is_active: s.is_active,
        });
      } else {
        setError(scholarshipResult.error || "Failed to load scholarship");
      }
    });
  }, [scholarshipId, form]);

  // Handle form submission
  const onSubmit = useCallback((data: ScholarshipFormData) => {
    setIsSaving(true);
    startTransition(async () => {
      const payload = {
        ...data,
        max_recipients: data.max_recipients || undefined,
        academic_year_id: data.academic_year_id || undefined,
        applicable_fees:
          !data.applicable_fees || data.applicable_fees.length === 0 ? ["all"] : data.applicable_fees,
      };

      const result = await updateScholarship(scholarshipId, payload);

      if (result.success) {
        toast({
          title: "Scholarship updated",
          description: "The scholarship has been updated successfully.",
        });
        router.push(`/finance/scholarships/${scholarshipId}`);
      } else {
        toast({
          title: "Error",
          description: result.error || "Failed to update scholarship",
          variant: "destructive",
        });
      }
      setIsSaving(false);
    });
  }, [scholarshipId, toast, router]);

  // Handle validation errors
  const onInvalid = useCallback(() => {
    toast({
      title: "Validation Error",
      description: "Please fill in all required fields correctly.",
      variant: "destructive",
    });
  }, [toast]);

  const coverageType = form.watch("coverage_type");

  // Loading state
  if (isPending && !scholarship) {
    return (
      <div className="flex h-[400px] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="flex h-[400px] flex-col items-center justify-center gap-4">
        <AlertCircle className="h-12 w-12 text-destructive" />
        <p className="text-muted-foreground">{error}</p>
        <Button onClick={() => router.push("/finance/scholarships")}>
          Back to Scholarships
        </Button>
      </div>
    );
  }

  if (!scholarship) return null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href={`/finance/scholarships/${scholarshipId}`}>
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Edit Scholarship</h1>
          <p className="text-muted-foreground">Update scholarship details</p>
        </div>
      </div>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit, onInvalid)} className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Basic Information</CardTitle>
              <CardDescription>Update the scholarship details</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Name and Code - same row, aligned at top */}
              <div className="grid gap-4 md:grid-cols-2 items-start">
                <FormField
                  control={form.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Scholarship Name</FormLabel>
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
                      <FormLabel>Code</FormLabel>
                      <FormControl>
                        <Input placeholder="e.g., AEA-2026" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              {/* Description */}
              <FormField
                control={form.control}
                name="description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Description</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Describe the scholarship criteria and benefits..."
                        rows={3}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Type and Academic Year - same row, wider controls */}
              <div className="grid gap-4 md:grid-cols-2 items-start">
                <FormField
                  control={form.control}
                  name="scholarship_type"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Scholarship Type</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder="Select type" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {SCHOLARSHIP_TYPES.map((type) => (
                            <SelectItem key={type.value} value={type.value}>
                              {type.label}
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
                  name="academic_year_id"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Academic Year</FormLabel>
                      <Select
                        onValueChange={(value) => field.onChange(value === "none" ? "" : value)}
                        value={field.value || "none"}
                      >
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder="Select year" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value="none">All Years</SelectItem>
                          {academicYears.map((year) => (
                            <SelectItem key={year.id} value={year.id}>
                              {year.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormDescription>
                        Leave as "All Years" to apply across academic years
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Coverage</CardTitle>
              <CardDescription>Define the scholarship coverage amount</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Coverage Type and Value - same row */}
              <div className="grid gap-4 md:grid-cols-2 items-start">
                <FormField
                  control={form.control}
                  name="coverage_type"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Coverage Type</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder="Select coverage type" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {COVERAGE_TYPES.map((type) => (
                            <SelectItem key={type.value} value={type.value}>
                              {type.label}
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
                  name="coverage_value"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>
                        {coverageType === "percentage" ? "Percentage (%)" : "Amount (GHS)"}
                      </FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          step={coverageType === "percentage" ? "1" : "0.01"}
                          min="0"
                          max={coverageType === "percentage" ? "100" : undefined}
                          placeholder={coverageType === "percentage" ? "e.g., 50" : "e.g., 500"}
                          {...field}
                          onChange={(e) => field.onChange(e.target.valueAsNumber || 0)}
                        />
                      </FormControl>
                      <FormDescription>
                        {coverageType === "percentage"
                          ? "Percentage of fees to cover (0-100)"
                          : "Fixed amount to deduct from fees"}
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              {/* Max Recipients */}
              <FormField
                control={form.control}
                name="max_recipients"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Maximum Recipients</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        min="0"
                        placeholder="Leave empty for unlimited"
                        className="md:w-1/2"
                        {...field}
                        value={field.value || ""}
                        onChange={(e) =>
                          field.onChange(e.target.value ? parseInt(e.target.value) : null)
                        }
                      />
                    </FormControl>
                    <FormDescription>
                      Limit the number of students who can receive this scholarship
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Applicable Fees */}
              <FormField
                control={form.control}
                name="applicable_fees"
                render={({ field }) => {
                  const values = field.value || ["all"];
                  return (
                    <FormItem>
                      <FormLabel>Applicable Fee Components</FormLabel>
                      <FormDescription className="mb-3">
                        Select which fee types this scholarship covers. Leave "All Fees" checked to
                        apply to the entire invoice.
                      </FormDescription>
                      <div className="space-y-3 rounded-lg border p-4">
                        <div className="flex items-center space-x-2">
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
                          <label
                            htmlFor="all-fees"
                            className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                          >
                            All Fees (applies to entire invoice)
                          </label>
                        </div>

                        {!values.includes("all") && feeTypes.length > 0 && (
                          <div className="ml-4 space-y-2 border-l-2 pl-4">
                            {feeTypes.map((feeType) => (
                              <div key={feeType.id} className="flex items-center space-x-2">
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
                                <label
                                  htmlFor={`fee-type-${feeType.id}`}
                                  className="text-sm leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                                >
                                  {feeType.name}
                                  {feeType.category && (
                                    <span className="ml-2 text-xs text-muted-foreground">
                                      ({feeType.category})
                                    </span>
                                  )}
                                </label>
                              </div>
                            ))}
                          </div>
                        )}

                        {!values.includes("all") && feeTypes.length === 0 && (
                          <p className="ml-4 text-sm text-muted-foreground">
                            No fee types configured. Create fee types in Finance Settings first.
                          </p>
                        )}
                      </div>
                      <FormMessage />
                    </FormItem>
                  );
                }}
              />

              {/* Active Switch */}
              <FormField
                control={form.control}
                name="is_active"
                render={({ field }) => (
                  <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
                    <div className="space-y-0.5">
                      <FormLabel className="text-base">Active</FormLabel>
                      <FormDescription>Enable this scholarship for new awards</FormDescription>
                    </div>
                    <FormControl>
                      <Switch checked={field.value} onCheckedChange={field.onChange} />
                    </FormControl>
                  </FormItem>
                )}
              />
            </CardContent>
          </Card>

          {/* Form Actions */}
          <div className="flex justify-end gap-4">
            <Button type="button" variant="outline" asChild>
              <Link href={`/finance/scholarships/${scholarshipId}`}>Cancel</Link>
            </Button>
            <Button type="submit" disabled={isSaving}>
              {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Save Changes
            </Button>
          </div>
        </form>
      </Form>
    </div>
  );
}
