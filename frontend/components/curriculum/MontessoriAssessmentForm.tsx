"use client";

import { useState, useTransition, useCallback, useEffect } from "react";
import Link from "next/link";
import { useForm, useFieldArray, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import {
  ArrowLeft,
  Save,
  Loader2,
  Plus,
  Trash2,
  GraduationCap,
  Sparkles,
  Target,
  FileText,
  MessageSquare,
  User,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Separator } from "@/components/ui/separator";

import {
  saveMontessoriAssessment,
  getMontessoriAssessment,
} from "@/actions/exams.action";
import type { ExamWithContext, ScoreEntryStudent } from "@/types";
import type {
  MontessoriProgressLevel,
  MontessoriAssessmentData,
  MontessoriAssessmentResponse,
} from "@/types/curriculum.type";

// =========================
// Progress Level Config
// =========================

const PROGRESS_LEVELS: {
  value: MontessoriProgressLevel;
  label: string;
  color: string;
}[] = [
  { value: "emerging", label: "Emerging", color: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200" },
  { value: "developing", label: "Developing", color: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200" },
  { value: "practicing", label: "Practicing", color: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200" },
  { value: "mastery", label: "Mastery", color: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200" },
];

// =========================
// Default Developmental Areas
// =========================

const DEFAULT_MONTESSORI_AREAS: MontessoriAssessmentData["developmental_areas"] = [
  {
    name: "Practical Life",
    skills: [
      { name: "Care of self", progress_level: "emerging" },
      { name: "Care of environment", progress_level: "emerging" },
      { name: "Grace and courtesy", progress_level: "emerging" },
    ],
    narrative: "",
  },
  {
    name: "Sensorial",
    skills: [
      { name: "Visual discrimination", progress_level: "emerging" },
      { name: "Auditory discrimination", progress_level: "emerging" },
      { name: "Tactile awareness", progress_level: "emerging" },
    ],
    narrative: "",
  },
  {
    name: "Language",
    skills: [
      { name: "Phonemic awareness", progress_level: "emerging" },
      { name: "Reading comprehension", progress_level: "emerging" },
      { name: "Writing", progress_level: "emerging" },
    ],
    narrative: "",
  },
  {
    name: "Mathematics",
    skills: [
      { name: "Number concepts", progress_level: "emerging" },
      { name: "Operations", progress_level: "emerging" },
      { name: "Geometry", progress_level: "emerging" },
    ],
    narrative: "",
  },
  {
    name: "Cultural Studies",
    skills: [
      { name: "Geography", progress_level: "emerging" },
      { name: "Science", progress_level: "emerging" },
      { name: "Art & Music", progress_level: "emerging" },
    ],
    narrative: "",
  },
];

// =========================
// Zod Schema
// =========================

const skillSchema = z.object({
  name: z.string().min(1, "Skill name is required"),
  progress_level: z.enum(["emerging", "developing", "practicing", "mastery"], {
    message: "Select a progress level",
  }),
});

const areaSchema = z.object({
  name: z.string().min(1, "Area name is required"),
  skills: z.array(skillSchema).min(1, "At least one skill is required"),
  narrative: z.string().max(2000, "Narrative must be 2000 characters or fewer"),
});

const workSampleSchema = z.object({
  description: z.string().min(1, "Description is required").max(500),
});

const montessoriFormSchema = z.object({
  developmental_areas: z.array(areaSchema).min(1, "At least one developmental area is required"),
  work_samples: z.array(workSampleSchema),
  goals: z.array(z.object({ value: z.string().min(1, "Goal is required").max(500) })),
  general_narrative: z.string().max(3000, "General narrative must be 3000 characters or fewer"),
});

type MontessoriFormValues = z.infer<typeof montessoriFormSchema>;

// =========================
// Component Props
// =========================

interface MontessoriAssessmentFormProps {
  exam: ExamWithContext;
  classId: string;
  sectionId?: string;
  students: ScoreEntryStudent[];
  backHref: string;
}

// =========================
// Component
// =========================

export function MontessoriAssessmentForm({
  exam,
  classId,
  sectionId,
  students,
  backHref,
}: MontessoriAssessmentFormProps) {
  const [selectedStudentId, setSelectedStudentId] = useState<string>("");
  const [loadingExisting, setLoadingExisting] = useState(false);
  const [existingData, setExistingData] = useState<MontessoriAssessmentResponse | null>(null);
  const [isPending, startTransition] = useTransition();

  const selectedStudent = students.find((s) => s.student_id === selectedStudentId);

  const form = useForm<MontessoriFormValues>({
    resolver: zodResolver(montessoriFormSchema),
    defaultValues: {
      developmental_areas: DEFAULT_MONTESSORI_AREAS,
      work_samples: [],
      goals: [],
      general_narrative: "",
    },
  });

  const areasFieldArray = useFieldArray({
    control: form.control,
    name: "developmental_areas",
  });

  const workSamplesFieldArray = useFieldArray({
    control: form.control,
    name: "work_samples",
  });

  const goalsFieldArray = useFieldArray({
    control: form.control,
    name: "goals",
  });

  // Load existing assessment when student changes
  const loadExistingAssessment = useCallback(
    async (studentId: string) => {
      if (!exam.academic_year_id || !exam.term_id) return;

      setLoadingExisting(true);
      setExistingData(null);

      const result = await getMontessoriAssessment(
        exam.academic_year_id,
        exam.term_id,
        studentId
      );

      if (result.success && result.data) {
        setExistingData(result.data);
        // Populate form with existing data
        form.reset({
          developmental_areas: result.data.developmental_areas.length > 0
            ? result.data.developmental_areas
            : DEFAULT_MONTESSORI_AREAS,
          work_samples: result.data.work_samples.length > 0
            ? result.data.work_samples
            : [],
          goals: result.data.goals.length > 0
            ? result.data.goals.map((g) => ({ value: g }))
            : [],
          general_narrative: result.data.general_narrative || "",
        });
      } else {
        // Reset to defaults for new assessment
        form.reset({
          developmental_areas: DEFAULT_MONTESSORI_AREAS,
          work_samples: [],
          goals: [],
          general_narrative: "",
        });
      }

      setLoadingExisting(false);
    },
    [exam.academic_year_id, exam.term_id, form]
  );

  useEffect(() => {
    if (selectedStudentId) {
      loadExistingAssessment(selectedStudentId);
    }
  }, [selectedStudentId, loadExistingAssessment]);

  const onSubmit = async (values: MontessoriFormValues) => {
    if (!selectedStudentId || !exam.academic_year_id || !exam.term_id) {
      toast.error("Please select a student first");
      return;
    }

    startTransition(async () => {
      const result = await saveMontessoriAssessment(
        exam.academic_year_id!,
        exam.term_id!,
        classId,
        sectionId,
        {
          student_id: selectedStudentId,
          developmental_areas: values.developmental_areas,
          work_samples: values.work_samples,
          goals: values.goals.map((g) => g.value),
          general_narrative: values.general_narrative,
        }
      );

      if (result.success) {
        toast.success("Assessment saved", {
          description: `Montessori assessment saved for ${selectedStudent?.first_name} ${selectedStudent?.last_name}`,
        });
        setExistingData(result.data);
      } else {
        toast.error("Failed to save assessment", {
          description: result.error,
        });
      }
    });
  };

  const getProgressBadge = (level: MontessoriProgressLevel) => {
    const config = PROGRESS_LEVELS.find((p) => p.value === level);
    if (!config) return null;
    return (
      <Badge variant="outline" className={config.color}>
        {config.label}
      </Badge>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <Link href={backHref}>
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              Montessori Assessment
            </h1>
            <p className="text-muted-foreground">
              {exam.name} - Narrative-based developmental assessment
            </p>
          </div>
        </div>
        {selectedStudentId && (
          <Button
            onClick={form.handleSubmit(onSubmit)}
            disabled={isPending || !form.formState.isDirty}
          >
            {isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Save className="mr-2 h-4 w-4" />
            )}
            Save Assessment
          </Button>
        )}
      </div>

      {/* Student Selector */}
      <Card>
        <CardHeader className="pb-4">
          <CardTitle className="flex items-center gap-2 text-lg">
            <User className="h-5 w-5" />
            Select Student
          </CardTitle>
          <CardDescription>
            Choose a student to enter or edit their Montessori assessment
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Select value={selectedStudentId} onValueChange={setSelectedStudentId}>
            <SelectTrigger className="w-full md:w-[400px]">
              <SelectValue placeholder="Select a student..." />
            </SelectTrigger>
            <SelectContent>
              {students.map((student) => (
                <SelectItem key={student.student_id} value={student.student_id}>
                  {student.first_name} {student.last_name}{" "}
                  <span className="text-muted-foreground">({student.student_number})</span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {existingData && (
            <p className="mt-2 text-sm text-muted-foreground">
              Last updated: {existingData.updated_at
                ? new Date(existingData.updated_at).toLocaleDateString("en-GB")
                : "N/A"}
            </p>
          )}
        </CardContent>
      </Card>

      {/* Loading State */}
      {loadingExisting && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          <span className="ml-3 text-muted-foreground">Loading assessment...</span>
        </div>
      )}

      {/* Assessment Form */}
      {selectedStudentId && !loadingExisting && (
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
            {/* Developmental Areas */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <GraduationCap className="h-5 w-5" />
                  Developmental Areas
                </CardTitle>
                <CardDescription>
                  Assess each skill within developmental domains. Add custom areas or skills as needed.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Accordion type="multiple" defaultValue={areasFieldArray.fields.map((_, i) => `area-${i}`)}>
                  {areasFieldArray.fields.map((area, areaIndex) => (
                    <AccordionItem key={area.id} value={`area-${areaIndex}`}>
                      <AccordionTrigger className="text-base font-semibold">
                        <div className="flex items-center gap-3">
                          <span>{form.watch(`developmental_areas.${areaIndex}.name`)}</span>
                          <Badge variant="secondary" className="text-xs font-normal">
                            {form.watch(`developmental_areas.${areaIndex}.skills`)?.length || 0} skills
                          </Badge>
                        </div>
                      </AccordionTrigger>
                      <AccordionContent className="space-y-4 pt-2">
                        {/* Area Name (editable) */}
                        <FormField
                          control={form.control}
                          name={`developmental_areas.${areaIndex}.name`}
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>Area Name</FormLabel>
                              <FormControl>
                                <Input {...field} />
                              </FormControl>
                              <FormMessage />
                            </FormItem>
                          )}
                        />

                        {/* Skills */}
                        <div className="space-y-3">
                          <div className="flex items-center justify-between">
                            <FormLabel>Skills Assessment</FormLabel>
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              onClick={() => {
                                const currentSkills = form.getValues(`developmental_areas.${areaIndex}.skills`);
                                form.setValue(
                                  `developmental_areas.${areaIndex}.skills`,
                                  [...currentSkills, { name: "", progress_level: "emerging" as const }],
                                  { shouldDirty: true }
                                );
                              }}
                            >
                              <Plus className="mr-1 h-3 w-3" />
                              Add Skill
                            </Button>
                          </div>

                          {form.watch(`developmental_areas.${areaIndex}.skills`)?.map((_, skillIndex) => (
                            <div
                              key={skillIndex}
                              className="flex flex-col gap-2 rounded-md border p-3 md:flex-row md:items-center"
                            >
                              <div className="flex-1">
                                <FormField
                                  control={form.control}
                                  name={`developmental_areas.${areaIndex}.skills.${skillIndex}.name`}
                                  render={({ field }) => (
                                    <FormItem>
                                      <FormControl>
                                        <Input
                                          placeholder="Skill name"
                                          {...field}
                                        />
                                      </FormControl>
                                      <FormMessage />
                                    </FormItem>
                                  )}
                                />
                              </div>
                              <div className="flex items-center gap-2">
                                <FormField
                                  control={form.control}
                                  name={`developmental_areas.${areaIndex}.skills.${skillIndex}.progress_level`}
                                  render={({ field }) => (
                                    <FormItem>
                                      <Select
                                        value={field.value}
                                        onValueChange={field.onChange}
                                      >
                                        <FormControl>
                                          <SelectTrigger className="w-full md:w-[160px]">
                                            <SelectValue placeholder="Level" />
                                          </SelectTrigger>
                                        </FormControl>
                                        <SelectContent>
                                          {PROGRESS_LEVELS.map((level) => (
                                            <SelectItem key={level.value} value={level.value}>
                                              {level.label}
                                            </SelectItem>
                                          ))}
                                        </SelectContent>
                                      </Select>
                                      <FormMessage />
                                    </FormItem>
                                  )}
                                />
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="icon"
                                  className="shrink-0 text-muted-foreground hover:text-destructive"
                                  onClick={() => {
                                    const currentSkills = form.getValues(
                                      `developmental_areas.${areaIndex}.skills`
                                    );
                                    if (currentSkills.length > 1) {
                                      form.setValue(
                                        `developmental_areas.${areaIndex}.skills`,
                                        currentSkills.filter((_, i) => i !== skillIndex),
                                        { shouldDirty: true }
                                      );
                                    } else {
                                      toast.error("At least one skill is required per area");
                                    }
                                  }}
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </div>
                            </div>
                          ))}
                        </div>

                        {/* Area Narrative */}
                        <FormField
                          control={form.control}
                          name={`developmental_areas.${areaIndex}.narrative`}
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>Observation Narrative</FormLabel>
                              <FormControl>
                                <Textarea
                                  placeholder="Write your observation for this developmental area..."
                                  className="min-h-[100px] resize-y"
                                  {...field}
                                />
                              </FormControl>
                              <FormMessage />
                              <p className="text-xs text-muted-foreground">
                                {field.value?.length || 0}/2000 characters
                              </p>
                            </FormItem>
                          )}
                        />

                        {/* Remove Area */}
                        {areasFieldArray.fields.length > 1 && (
                          <>
                            <Separator />
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              className="text-destructive hover:text-destructive"
                              onClick={() => areasFieldArray.remove(areaIndex)}
                            >
                              <Trash2 className="mr-1 h-3 w-3" />
                              Remove Area
                            </Button>
                          </>
                        )}
                      </AccordionContent>
                    </AccordionItem>
                  ))}
                </Accordion>

                <Button
                  type="button"
                  variant="outline"
                  className="mt-4 w-full"
                  onClick={() =>
                    areasFieldArray.append({
                      name: "",
                      skills: [{ name: "", progress_level: "emerging" }],
                      narrative: "",
                    })
                  }
                >
                  <Plus className="mr-2 h-4 w-4" />
                  Add Developmental Area
                </Button>
              </CardContent>
            </Card>

            {/* Work Samples */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Sparkles className="h-5 w-5" />
                  Work Samples
                </CardTitle>
                <CardDescription>
                  Document notable work samples that demonstrate the student's progress
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {workSamplesFieldArray.fields.length === 0 && (
                  <p className="py-4 text-center text-sm text-muted-foreground">
                    No work samples added yet. Click below to add one.
                  </p>
                )}
                {workSamplesFieldArray.fields.map((field, index) => (
                  <div key={field.id} className="flex gap-2">
                    <FormField
                      control={form.control}
                      name={`work_samples.${index}.description`}
                      render={({ field }) => (
                        <FormItem className="flex-1">
                          <FormControl>
                            <Input
                              placeholder="Describe the work sample..."
                              {...field}
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="shrink-0 text-muted-foreground hover:text-destructive"
                      onClick={() => workSamplesFieldArray.remove(index)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => workSamplesFieldArray.append({ description: "" })}
                >
                  <Plus className="mr-1 h-3 w-3" />
                  Add Work Sample
                </Button>
              </CardContent>
            </Card>

            {/* Goals */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Target className="h-5 w-5" />
                  Goals for Next Term
                </CardTitle>
                <CardDescription>
                  Set learning objectives for the student to work towards
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {goalsFieldArray.fields.length === 0 && (
                  <p className="py-4 text-center text-sm text-muted-foreground">
                    No goals added yet. Click below to add one.
                  </p>
                )}
                {goalsFieldArray.fields.map((field, index) => (
                  <div key={field.id} className="flex gap-2">
                    <FormField
                      control={form.control}
                      name={`goals.${index}.value`}
                      render={({ field }) => (
                        <FormItem className="flex-1">
                          <FormControl>
                            <Input
                              placeholder="Enter a learning goal..."
                              {...field}
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="shrink-0 text-muted-foreground hover:text-destructive"
                      onClick={() => goalsFieldArray.remove(index)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => goalsFieldArray.append({ value: "" })}
                >
                  <Plus className="mr-1 h-3 w-3" />
                  Add Goal
                </Button>
              </CardContent>
            </Card>

            {/* General Narrative */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <MessageSquare className="h-5 w-5" />
                  General Comments
                </CardTitle>
                <CardDescription>
                  Overall observations about the student's progress, behaviour, and engagement
                </CardDescription>
              </CardHeader>
              <CardContent>
                <FormField
                  control={form.control}
                  name="general_narrative"
                  render={({ field }) => (
                    <FormItem>
                      <FormControl>
                        <Textarea
                          placeholder="Write overall observations about the student..."
                          className="min-h-[150px] resize-y"
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                      <p className="text-xs text-muted-foreground">
                        {field.value?.length || 0}/3000 characters
                      </p>
                    </FormItem>
                  )}
                />
              </CardContent>
            </Card>

            {/* Bottom Save Button (mobile-friendly) */}
            <div className="flex flex-col gap-3 sm:flex-row sm:justify-end">
              <Link href={backHref}>
                <Button type="button" variant="outline" className="w-full sm:w-auto">
                  Cancel
                </Button>
              </Link>
              <Button
                type="submit"
                disabled={isPending || !form.formState.isDirty}
                className="w-full sm:w-auto"
              >
                {isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Save className="mr-2 h-4 w-4" />
                )}
                Save Assessment
              </Button>
            </div>
          </form>
        </Form>
      )}

      {/* Empty State */}
      {!selectedStudentId && (
        <Card>
          <CardContent className="py-12 text-center">
            <FileText className="mx-auto h-12 w-12 text-muted-foreground/50" />
            <h3 className="mt-4 text-lg font-semibold">Select a Student</h3>
            <p className="text-muted-foreground">
              Choose a student above to begin entering their Montessori narrative assessment.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
