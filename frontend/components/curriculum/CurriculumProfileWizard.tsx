"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useForm , type Resolver} from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Loader2,
  Check,
  BookTemplate,
  Pencil,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { TemplateSelector } from "@/components/curriculum/TemplateSelector";
import { AssessmentStructureEditor } from "@/components/curriculum/AssessmentStructureEditor";
import {
  getCurriculumTemplates,
  createFromTemplate,
  createCurriculumProfile,
  createAssessmentStructure,
} from "@/actions/curriculum.action";
import { cn } from "@/lib/utils";
import type {
  CurriculumTemplateInfo,
  CurriculumType,
  ScoreDisplayMode,
  AcademicCalendarType,
  AssessmentComponentCreate,
} from "@/types/curriculum.type";

// ===========================
// Zod Schema
// ===========================

const profileFormSchema = z.object({
  name: z.string().min(1, "Profile name is required"),
  curriculum_type: z.enum(
    [
      "ges",
      "cambridge",
      "edexcel",
      "american",
      "ib",
      "french",
      "montessori",
      "custom",
    ],
    { message: "Select a curriculum type" },
  ),
  description: z.string().optional(),
  academic_calendar_type: z.enum(["terms", "semesters", "quarters"], {
    message: "Select a calendar type",
  }),
  periods_per_year: z.coerce.number().min(1).max(6),
  score_display_mode: z.enum(
    [
      "percentage",
      "grade_only",
      "grade_and_score",
      "level",
      "gpa",
      "narrative",
      "mention",
    ],
    { message: "Select a display mode" },
  ),
  show_position: z.boolean(),
  show_class_average: z.boolean(),
  use_gpa: z.boolean(),
  use_credits: z.boolean(),
  use_criterion_grading: z.boolean(),
  is_default: z.boolean(),
});

type ProfileFormValues = z.infer<typeof profileFormSchema>;

const CURRICULUM_TYPE_LABELS: Record<CurriculumType, string> = {
  ges: "GES (Ghana Education Service)",
  cambridge: "Cambridge International",
  edexcel: "Edexcel / Pearson",
  american: "American Curriculum",
  ib: "International Baccalaureate",
  french: "French Curriculum",
  montessori: "Montessori",
  custom: "Custom",
};

const DISPLAY_MODE_LABELS: Record<ScoreDisplayMode, string> = {
  percentage: "Percentage",
  grade_only: "Grade Only",
  grade_and_score: "Grade + Score",
  level: "Level",
  gpa: "GPA",
  narrative: "Narrative",
  mention: "Mention",
};

const CALENDAR_TYPE_LABELS: Record<AcademicCalendarType, string> = {
  terms: "Terms (3 per year)",
  semesters: "Semesters (2 per year)",
  quarters: "Quarters (4 per year)",
};

// Steps
const STEPS = [
  { title: "Method", description: "Choose how to start" },
  { title: "Settings", description: "Configure profile" },
  { title: "Assessment", description: "Define components" },
  { title: "Review", description: "Confirm & create" },
];

export function CurriculumProfileWizard() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [method, setMethod] = useState<"template" | "custom" | null>(null);
  const [templates, setTemplates] = useState<CurriculumTemplateInfo[]>([]);
  const [selectedTemplateKey, setSelectedTemplateKey] = useState<string>("");
  const [loadingTemplates, setLoadingTemplates] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [assessmentComponents, setAssessmentComponents] = useState<
    AssessmentComponentCreate[]
  >([]);

  const form = useForm<ProfileFormValues>({
    resolver: zodResolver(profileFormSchema) as Resolver<ProfileFormValues>,
    defaultValues: {
      name: "",
      curriculum_type: "ges",
      description: "",
      academic_calendar_type: "terms",
      periods_per_year: 3,
      score_display_mode: "percentage",
      show_position: true,
      show_class_average: true,
      use_gpa: false,
      use_credits: false,
      use_criterion_grading: false,
      is_default: false,
    },
  });

  // Load templates on mount
  useEffect(() => {
    let mounted = true;
    async function load() {
      setLoadingTemplates(true);
      const result = await getCurriculumTemplates();
      if (mounted && result.success) {
        setTemplates(result.data);
      }
      if (mounted) setLoadingTemplates(false);
    }
    load();
    return () => {
      mounted = false;
    };
  }, []);

  // Pre-fill when template is selected
  useEffect(() => {
    if (!selectedTemplateKey || method !== "template") return;
    const template = templates.find((t) => t.key === selectedTemplateKey);
    if (template) {
      form.setValue("name", template.name);
      form.setValue("curriculum_type", template.curriculum_type);
      form.setValue("description", template.description);
      // Set common defaults per curriculum type
      if (template.curriculum_type === "ges") {
        form.setValue("academic_calendar_type", "terms");
        form.setValue("periods_per_year", 3);
        form.setValue("score_display_mode", "percentage");
      } else if (template.curriculum_type === "cambridge") {
        form.setValue("academic_calendar_type", "terms");
        form.setValue("periods_per_year", 3);
        form.setValue("score_display_mode", "grade_and_score");
      } else if (template.curriculum_type === "ib") {
        form.setValue("academic_calendar_type", "semesters");
        form.setValue("periods_per_year", 2);
        form.setValue("score_display_mode", "level");
        form.setValue("use_criterion_grading", true);
      } else if (template.curriculum_type === "french") {
        form.setValue("academic_calendar_type", "terms");
        form.setValue("periods_per_year", 3);
        form.setValue("score_display_mode", "mention");
      } else if (template.curriculum_type === "american") {
        form.setValue("academic_calendar_type", "semesters");
        form.setValue("periods_per_year", 2);
        form.setValue("score_display_mode", "gpa");
        form.setValue("use_gpa", true);
        form.setValue("use_credits", true);
      }
    }
  }, [selectedTemplateKey, method, templates, form]);

  const handleNext = async () => {
    if (step === 0) {
      if (!method) {
        toast.error("Please choose a method to continue");
        return;
      }
      if (method === "template" && !selectedTemplateKey) {
        toast.error("Please select a template");
        return;
      }
      setStep(1);
      return;
    }

    if (step === 1) {
      const valid = await form.trigger([
        "name",
        "curriculum_type",
        "academic_calendar_type",
        "periods_per_year",
        "score_display_mode",
      ]);
      if (!valid) return;
      setStep(2);
      return;
    }

    if (step === 2) {
      // Validate assessment components
      // Coerce to number — API returns Decimal-serialized strings (e.g. "20.00")
      const totalWeight = assessmentComponents.reduce(
        (sum, c) => sum + (Number(c.weight) || 0),
        0,
      );
      const hasNames = assessmentComponents.every((c) => c.name.trim() !== "");
      if (assessmentComponents.length > 0) {
        if (Math.abs(totalWeight - 100) > 0.01) {
          toast.error("Assessment weights must total 100%");
          return;
        }
        if (!hasNames) {
          toast.error("All assessment components must have a name");
          return;
        }
      }
      setStep(3);
      return;
    }
  };

  const handleBack = () => {
    if (step > 0) setStep(step - 1);
  };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    try {
      if (method === "template") {
        // Create from template, then update with custom name if changed
        const result = await createFromTemplate(
          selectedTemplateKey,
          form.getValues("name"),
        );
        if (result.success) {
          toast.success("Curriculum profile created from template");
          router.push(`/settings/curriculum/profiles/${result.data.id}`);
        } else {
          toast.error("Failed to create profile", {
            description: result.error,
          });
        }
      } else {
        // Custom creation
        const values = form.getValues();
        const profileResult = await createCurriculumProfile({
          name: values.name,
          curriculum_type: values.curriculum_type,
          description: values.description || undefined,
          academic_calendar_type: values.academic_calendar_type,
          periods_per_year: values.periods_per_year,
          score_display_mode: values.score_display_mode,
          show_position: values.show_position,
          show_class_average: values.show_class_average,
          use_gpa: values.use_gpa,
          use_credits: values.use_credits,
          use_criterion_grading: values.use_criterion_grading,
          is_default: values.is_default,
        });

        if (!profileResult.success) {
          toast.error("Failed to create profile", {
            description: profileResult.error,
          });
          return;
        }

        // Create assessment structure if components exist
        if (assessmentComponents.length > 0) {
          const structureResult = await createAssessmentStructure(
            profileResult.data.id,
            {
              name: `${values.name} Assessment`,
              description: `Assessment structure for ${values.name}`,
              components: assessmentComponents,
            },
          );
          if (!structureResult.success) {
            toast.error(
              "Profile created but assessment structure failed. You can add it later.",
              { description: structureResult.error },
            );
          }
        }

        toast.success("Curriculum profile created successfully");
        router.push(`/settings/curriculum/profiles/${profileResult.data.id}`);
      }
    } catch {
      toast.error("An unexpected error occurred");
    } finally {
      setIsSubmitting(false);
    }
  };

  const formValues = form.watch();

  return (
    <div className="space-y-6">
      {/* Desktop stepper */}
      <div className="hidden md:flex items-center gap-2">
        {STEPS.map((s, i) => (
          <div key={s.title} className="flex items-center gap-2">
            <div
              className={cn(
                "flex h-8 w-8 items-center justify-center rounded-full text-xs font-medium",
                i < step
                  ? "bg-primary text-primary-foreground"
                  : i === step
                    ? "bg-primary text-primary-foreground ring-2 ring-primary/30"
                    : "bg-muted text-muted-foreground",
              )}
            >
              {i < step ? <Check className="h-4 w-4" /> : i + 1}
            </div>
            <div className="hidden lg:block">
              <p className="text-sm font-medium">{s.title}</p>
              <p className="text-xs text-muted-foreground">{s.description}</p>
            </div>
            {i < STEPS.length - 1 && (
              <div
                className={cn(
                  "h-px w-8 lg:w-16",
                  i < step ? "bg-primary" : "bg-muted",
                )}
              />
            )}
          </div>
        ))}
      </div>

      {/* Mobile stepper */}
      <div className="md:hidden flex items-center justify-center gap-2">
        {STEPS.map((s, i) => (
          <div key={s.title} className="flex flex-col items-center gap-1">
            <div
              className={cn(
                "flex h-7 w-7 items-center justify-center rounded-full text-[10px] font-medium",
                i < step
                  ? "bg-primary text-primary-foreground"
                  : i === step
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground",
              )}
            >
              {i < step ? <Check className="h-3 w-3" /> : i + 1}
            </div>
            <span className="text-[10px] text-muted-foreground max-w-[60px] text-center truncate">
              {s.title}
            </span>
          </div>
        ))}
      </div>

      <Form {...form}>
        <form onSubmit={(e) => e.preventDefault()}>
          {/* Step 0: Method */}
          {step === 0 && (
            <div className="space-y-6">
              <div>
                <h2 className="text-lg font-semibold">
                  How would you like to create your profile?
                </h2>
                <p className="text-sm text-muted-foreground">
                  Choose a template to get started quickly, or create a custom
                  profile from scratch.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Card
                  role="button"
                  tabIndex={0}
                  aria-pressed={method === "template"}
                  onClick={() => setMethod("template")}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setMethod("template");
                    }
                  }}
                  className={cn(
                    "cursor-pointer transition-all hover:shadow-md",
                    method === "template"
                      ? "ring-2 ring-primary border-primary"
                      : "hover:border-primary/50",
                  )}
                >
                  <CardHeader>
                    <BookTemplate className="h-8 w-8 text-primary" />
                    <CardTitle className="text-base">
                      Start from Template
                    </CardTitle>
                    <CardDescription>
                      Choose from pre-built curriculum profiles (GES, Cambridge,
                      IB, etc.) with recommended assessment structures.
                    </CardDescription>
                  </CardHeader>
                </Card>

                <Card
                  role="button"
                  tabIndex={0}
                  aria-pressed={method === "custom"}
                  onClick={() => setMethod("custom")}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setMethod("custom");
                    }
                  }}
                  className={cn(
                    "cursor-pointer transition-all hover:shadow-md",
                    method === "custom"
                      ? "ring-2 ring-primary border-primary"
                      : "hover:border-primary/50",
                  )}
                >
                  <CardHeader>
                    <Pencil className="h-8 w-8 text-primary" />
                    <CardTitle className="text-base">Create Custom</CardTitle>
                    <CardDescription>
                      Build a curriculum profile from scratch. Full control over
                      all settings and assessment components.
                    </CardDescription>
                  </CardHeader>
                </Card>
              </div>

              {method === "template" && (
                <div className="space-y-3">
                  <h3 className="text-sm font-medium">Select a Template</h3>
                  {loadingTemplates ? (
                    <div className="flex items-center justify-center py-8">
                      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                    </div>
                  ) : (
                    <TemplateSelector
                      templates={templates}
                      selectedKey={selectedTemplateKey}
                      onSelect={setSelectedTemplateKey}
                    />
                  )}
                </div>
              )}
            </div>
          )}

          {/* Step 1: Settings */}
          {step === 1 && (
            <div className="space-y-6">
              <div>
                <h2 className="text-lg font-semibold">Profile Settings</h2>
                <p className="text-sm text-muted-foreground">
                  Configure the curriculum profile details and preferences.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem className="md:col-span-2">
                      <FormLabel>Profile Name</FormLabel>
                      <FormControl>
                        <Input
                          placeholder="e.g., GES Standard, Cambridge IGCSE"
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="curriculum_type"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Curriculum Type</FormLabel>
                      <Select
                        value={field.value}
                        onValueChange={field.onChange}
                        disabled={method === "template"}
                      >
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder="Select type" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {Object.entries(CURRICULUM_TYPE_LABELS).map(
                            ([value, label]) => (
                              <SelectItem key={value} value={value}>
                                {label}
                              </SelectItem>
                            ),
                          )}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="academic_calendar_type"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Calendar Type</FormLabel>
                      <Select
                        value={field.value}
                        onValueChange={(v) => {
                          field.onChange(v);
                          // Auto-set periods
                          if (v === "terms") form.setValue("periods_per_year", 3);
                          if (v === "semesters")
                            form.setValue("periods_per_year", 2);
                          if (v === "quarters")
                            form.setValue("periods_per_year", 4);
                        }}
                      >
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder="Select calendar" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {Object.entries(CALENDAR_TYPE_LABELS).map(
                            ([value, label]) => (
                              <SelectItem key={value} value={value}>
                                {label}
                              </SelectItem>
                            ),
                          )}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="periods_per_year"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Periods per Year</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          min={1}
                          max={6}
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="score_display_mode"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Score Display</FormLabel>
                      <Select
                        value={field.value}
                        onValueChange={field.onChange}
                      >
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder="Select display mode" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {Object.entries(DISPLAY_MODE_LABELS).map(
                            ([value, label]) => (
                              <SelectItem key={value} value={value}>
                                {label}
                              </SelectItem>
                            ),
                          )}
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
                    <FormItem className="md:col-span-2">
                      <FormLabel>Description (Optional)</FormLabel>
                      <FormControl>
                        <Textarea
                          placeholder="Brief description of this curriculum profile"
                          className="resize-none"
                          rows={3}
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <div className="space-y-4">
                <h3 className="text-sm font-medium">Display Options</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <FormField
                    control={form.control}
                    name="show_position"
                    render={({ field }) => (
                      <FormItem className="flex items-center justify-between rounded-lg border p-3">
                        <div className="space-y-0.5">
                          <FormLabel className="text-sm">
                            Show Position
                          </FormLabel>
                          <FormDescription className="text-xs">
                            Display class ranking on report cards
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

                  <FormField
                    control={form.control}
                    name="show_class_average"
                    render={({ field }) => (
                      <FormItem className="flex items-center justify-between rounded-lg border p-3">
                        <div className="space-y-0.5">
                          <FormLabel className="text-sm">
                            Class Average
                          </FormLabel>
                          <FormDescription className="text-xs">
                            Show class average on reports
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

                  <FormField
                    control={form.control}
                    name="use_gpa"
                    render={({ field }) => (
                      <FormItem className="flex items-center justify-between rounded-lg border p-3">
                        <div className="space-y-0.5">
                          <FormLabel className="text-sm">Use GPA</FormLabel>
                          <FormDescription className="text-xs">
                            Calculate Grade Point Average
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

                  <FormField
                    control={form.control}
                    name="use_credits"
                    render={({ field }) => (
                      <FormItem className="flex items-center justify-between rounded-lg border p-3">
                        <div className="space-y-0.5">
                          <FormLabel className="text-sm">
                            Credit Hours
                          </FormLabel>
                          <FormDescription className="text-xs">
                            Use credit-based weighting
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

                  <FormField
                    control={form.control}
                    name="use_criterion_grading"
                    render={({ field }) => (
                      <FormItem className="flex items-center justify-between rounded-lg border p-3">
                        <div className="space-y-0.5">
                          <FormLabel className="text-sm">
                            Criterion Grading
                          </FormLabel>
                          <FormDescription className="text-xs">
                            Grade by criteria (e.g., IB style)
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

                  <FormField
                    control={form.control}
                    name="is_default"
                    render={({ field }) => (
                      <FormItem className="flex items-center justify-between rounded-lg border p-3">
                        <div className="space-y-0.5">
                          <FormLabel className="text-sm">
                            Set as Default
                          </FormLabel>
                          <FormDescription className="text-xs">
                            Use for new classes by default
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
                </div>
              </div>
            </div>
          )}

          {/* Step 2: Assessment */}
          {step === 2 && (
            <div className="space-y-6">
              <div>
                <h2 className="text-lg font-semibold">Assessment Structure</h2>
                <p className="text-sm text-muted-foreground">
                  Define how student assessments are structured and weighted.
                  {method === "template" &&
                    " You can skip this step -- the template includes default components."}
                </p>
              </div>

              <AssessmentStructureEditor
                initialComponents={assessmentComponents}
                onChange={setAssessmentComponents}
              />
            </div>
          )}

          {/* Step 3: Review */}
          {step === 3 && (
            <div className="space-y-6">
              <div>
                <h2 className="text-lg font-semibold">Review & Create</h2>
                <p className="text-sm text-muted-foreground">
                  Review your curriculum profile before creating it.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-muted-foreground">
                      Profile Details
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Name</span>
                      <span className="font-medium">{formValues.name}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Type</span>
                      <Badge variant="secondary">
                        {CURRICULUM_TYPE_LABELS[formValues.curriculum_type]}
                      </Badge>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Calendar</span>
                      <span className="font-medium">
                        {CALENDAR_TYPE_LABELS[formValues.academic_calendar_type]}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">
                        Score Display
                      </span>
                      <span className="font-medium">
                        {DISPLAY_MODE_LABELS[formValues.score_display_mode]}
                      </span>
                    </div>
                    {formValues.description && (
                      <div className="pt-2 border-t">
                        <span className="text-muted-foreground">
                          Description
                        </span>
                        <p className="mt-1">{formValues.description}</p>
                      </div>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-muted-foreground">
                      Options
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">
                        Show Position
                      </span>
                      <Badge
                        variant={
                          formValues.show_position ? "default" : "secondary"
                        }
                      >
                        {formValues.show_position ? "Yes" : "No"}
                      </Badge>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">
                        Class Average
                      </span>
                      <Badge
                        variant={
                          formValues.show_class_average ? "default" : "secondary"
                        }
                      >
                        {formValues.show_class_average ? "Yes" : "No"}
                      </Badge>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">GPA</span>
                      <Badge
                        variant={formValues.use_gpa ? "default" : "secondary"}
                      >
                        {formValues.use_gpa ? "Yes" : "No"}
                      </Badge>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Credits</span>
                      <Badge
                        variant={
                          formValues.use_credits ? "default" : "secondary"
                        }
                      >
                        {formValues.use_credits ? "Yes" : "No"}
                      </Badge>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">
                        Criterion Grading
                      </span>
                      <Badge
                        variant={
                          formValues.use_criterion_grading
                            ? "default"
                            : "secondary"
                        }
                      >
                        {formValues.use_criterion_grading ? "Yes" : "No"}
                      </Badge>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Default</span>
                      <Badge
                        variant={
                          formValues.is_default ? "default" : "secondary"
                        }
                      >
                        {formValues.is_default ? "Yes" : "No"}
                      </Badge>
                    </div>
                  </CardContent>
                </Card>
              </div>

              {assessmentComponents.length > 0 && (
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-muted-foreground">
                      Assessment Components ({assessmentComponents.length})
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-1 text-sm">
                      {assessmentComponents.map((comp, i) => (
                        <div
                          key={i}
                          className="flex justify-between py-1 border-b last:border-0"
                        >
                          <span>{comp.name || "(unnamed)"}</span>
                          <span className="font-medium">{comp.weight}%</span>
                        </div>
                      ))}
                      <div className="flex justify-between pt-2 font-semibold">
                        <span>Total</span>
                        <span>
                          {assessmentComponents.reduce(
                            (s, c) => s + (Number(c.weight) || 0),
                            0,
                          )}
                          %
                        </span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}

              {method === "template" && (
                <div className="rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-800 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-200">
                  Creating from template:{" "}
                  <strong>
                    {templates.find((t) => t.key === selectedTemplateKey)?.name}
                  </strong>
                  . The template&apos;s default assessment structure will be
                  applied.
                </div>
              )}
            </div>
          )}

          {/* Navigation buttons */}
          <div className="flex items-center justify-between pt-6 border-t mt-6">
            <Button
              type="button"
              variant="outline"
              onClick={handleBack}
              disabled={step === 0 || isSubmitting}
            >
              <ChevronLeft className="mr-2 h-4 w-4" />
              Back
            </Button>
            {step < 3 ? (
              <Button type="button" onClick={handleNext}>
                Next
                <ChevronRight className="ml-2 h-4 w-4" />
              </Button>
            ) : (
              <Button
                type="button"
                onClick={handleSubmit}
                disabled={isSubmitting}
              >
                {isSubmitting && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                Create Profile
              </Button>
            )}
          </div>
        </form>
      </Form>
    </div>
  );
}
