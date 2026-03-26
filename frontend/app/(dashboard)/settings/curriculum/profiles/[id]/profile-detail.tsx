"use client";

import { useState, useTransition } from "react";
import { useForm , type Resolver} from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Loader2,
  Save,
  Star,
  Pencil,
  BookOpen,
  FileText,
} from "lucide-react";
import { toast } from "sonner";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AssessmentStructureEditor } from "@/components/curriculum/AssessmentStructureEditor";
import {
  updateCurriculumProfile,
  setDefaultProfile,
  createAssessmentStructure,
  syncAssessmentComponents,
  updateReportConfig,
  deleteAssessmentComponent,
} from "@/actions/curriculum.action";
import type {
  CurriculumProfileDetail as CurriculumProfileDetailType,
  CurriculumType,
  ScoreDisplayMode,
  AcademicCalendarType,
  AssessmentComponentCreate,
  ReportCardConfigUpdate,
} from "@/types/curriculum.type";

const CURRICULUM_TYPE_LABELS: Record<CurriculumType, string> = {
  ges: "GES",
  cambridge: "Cambridge",
  edexcel: "Edexcel",
  american: "American",
  ib: "IB",
  french: "French",
  montessori: "Montessori",
  custom: "Custom",
};

const CURRICULUM_TYPE_COLORS: Record<CurriculumType, string> = {
  ges: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  cambridge: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  edexcel: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
  american: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  ib: "bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-200",
  french: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200",
  montessori: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
  custom: "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200",
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
  terms: "Terms",
  semesters: "Semesters",
  quarters: "Quarters",
};

const profileUpdateSchema = z.object({
  name: z.string().min(1, "Profile name is required"),
  description: z.string().optional(),
  academic_calendar_type: z.enum(["terms", "semesters", "quarters"]),
  periods_per_year: z.coerce.number().min(1).max(6),
  score_display_mode: z.enum([
    "percentage",
    "grade_only",
    "grade_and_score",
    "level",
    "gpa",
    "narrative",
    "mention",
  ]),
  show_position: z.boolean(),
  show_class_average: z.boolean(),
  use_gpa: z.boolean(),
  use_credits: z.boolean(),
  use_criterion_grading: z.boolean(),
  is_active: z.boolean(),
});

type ProfileUpdateValues = z.infer<typeof profileUpdateSchema>;

interface ProfileDetailProps {
  profile: CurriculumProfileDetailType;
}

export function ProfileDetail({ profile: initialProfile }: ProfileDetailProps) {
  const [isPending, startTransition] = useTransition();
  const [isEditingProfile, setIsEditingProfile] = useState(false);
  // Local profile state so we can apply updates without router.refresh(),
  // which would re-render the entire dashboard layout and trigger 3-4 API calls
  const [profile, setProfile] = useState(initialProfile);
  // Track component IDs so we can distinguish existing (update) from new (add)
  type ComponentWithOptionalId = AssessmentComponentCreate & { _existingId?: string };
  // Optimistic local state for report config — avoids router.refresh() on each
  // toggle, which caused overlapping re-renders and performance.measure() crashes
  const [localReportConfig, setLocalReportConfig] = useState(
    profile.report_config,
  );

  const [assessmentComponents, setAssessmentComponents] = useState<
    ComponentWithOptionalId[]
  >(
    profile.assessment_structure?.components.map((c) => ({
      _existingId: c.id,
      component_type: c.component_type,
      name: c.name,
      weight: c.weight,
      max_score: c.max_score,
      is_external: c.is_external,
      sequence: c.sequence,
      maps_to_ca: c.maps_to_ca,
      maps_to_exam: c.maps_to_exam,
    })) || [],
  );

  const form = useForm<ProfileUpdateValues>({
    resolver: zodResolver(profileUpdateSchema) as Resolver<ProfileUpdateValues>,
    defaultValues: {
      name: profile.name,
      description: profile.description || "",
      academic_calendar_type: profile.academic_calendar_type,
      periods_per_year: profile.periods_per_year,
      score_display_mode: profile.score_display_mode,
      show_position: profile.show_position,
      show_class_average: profile.show_class_average,
      use_gpa: profile.use_gpa,
      use_credits: profile.use_credits,
      use_criterion_grading: profile.use_criterion_grading,
      is_active: profile.is_active,
    },
  });

  const handleSaveProfile = async (values: ProfileUpdateValues) => {
    startTransition(async () => {
      const result = await updateCurriculumProfile(profile.id, {
        name: values.name,
        description: values.description || undefined,
        academic_calendar_type: values.academic_calendar_type,
        periods_per_year: values.periods_per_year,
        score_display_mode: values.score_display_mode,
        show_position: values.show_position,
        show_class_average: values.show_class_average,
        use_gpa: values.use_gpa,
        use_credits: values.use_credits,
        use_criterion_grading: values.use_criterion_grading,
        is_active: values.is_active,
      });

      if (result.success) {
        toast.success("Profile updated successfully");
        setIsEditingProfile(false);
        // Update local profile state instead of router.refresh() to avoid
        // full layout re-render and unnecessary API re-fetches
        setProfile((prev) => ({
          ...prev,
          name: values.name,
          description: values.description,
          academic_calendar_type: values.academic_calendar_type,
          periods_per_year: values.periods_per_year,
          score_display_mode: values.score_display_mode,
          show_position: values.show_position,
          show_class_average: values.show_class_average,
          use_gpa: values.use_gpa,
          use_credits: values.use_credits,
          use_criterion_grading: values.use_criterion_grading,
          is_active: values.is_active,
        }));
      } else {
        toast.error("Failed to update profile", { description: result.error });
      }
    });
  };

  const handleSetDefault = () => {
    startTransition(async () => {
      const result = await setDefaultProfile(profile.id);
      if (result.success) {
        toast.success("Set as default profile");
        setProfile((prev) => ({ ...prev, is_default: true }));
      } else {
        toast.error("Failed to set default", { description: result.error });
      }
    });
  };

  const handleSaveAssessment = () => {
    // Coerce to number — API returns Decimal-serialized strings (e.g. "20.00")
    const totalWeight = assessmentComponents.reduce(
      (sum, c) => sum + (Number(c.weight) || 0),
      0,
    );
    if (assessmentComponents.length > 0 && Math.abs(totalWeight - 100) > 0.01) {
      toast.error("Assessment weights must total 100%");
      return;
    }

    startTransition(async () => {
      const existingStructure = profile.assessment_structure;

      if (!existingStructure) {
        // No structure exists yet — create a fresh one with all components
        const result = await createAssessmentStructure(profile.id, {
          name: `${profile.name} Assessment`,
          description: `Assessment structure for ${profile.name}`,
          components: assessmentComponents.map(({ _existingId, ...rest }) => rest),
        });
        if (result.success) {
          toast.success("Assessment structure saved");
          // Update local profile with the new structure so the UI reflects
          // the persisted state (including server-assigned component IDs)
          if (result.data) {
            setProfile((prev) => ({
              ...prev,
              assessment_structure: result.data,
            }));
            // Refresh component list with server-assigned IDs
            setAssessmentComponents(
              result.data.components?.map((c) => ({
                _existingId: c.id,
                component_type: c.component_type,
                name: c.name,
                weight: c.weight,
                max_score: c.max_score,
                is_external: c.is_external,
                sequence: c.sequence,
                maps_to_ca: c.maps_to_ca,
                maps_to_exam: c.maps_to_exam,
              })) || [],
            );
          }
        } else {
          toast.error("Failed to save assessment structure", {
            description: result.error,
          });
        }
        return;
      }

      // Structure exists — sync all components in a single request
      // instead of individual add/update/delete calls that hit rate limits
      const result = await syncAssessmentComponents(
        existingStructure.id,
        assessmentComponents.map((comp) => ({
          id: comp._existingId || undefined,
          component_type: comp.component_type,
          name: comp.name,
          weight: comp.weight,
          max_score: comp.max_score,
          is_external: comp.is_external,
          sequence: comp.sequence,
          maps_to_ca: comp.maps_to_ca,
          maps_to_exam: comp.maps_to_exam,
        })),
      );

      if (result.success) {
        toast.success("Assessment structure updated");
        // Update component list with server-assigned IDs for newly added components
        if (result.data?.components) {
          setAssessmentComponents(
            result.data.components.map((c) => ({
              _existingId: c.id,
              component_type: c.component_type,
              name: c.name,
              weight: c.weight,
              max_score: c.max_score,
              is_external: c.is_external,
              sequence: c.sequence,
              maps_to_ca: c.maps_to_ca,
              maps_to_exam: c.maps_to_exam,
            })),
          );
        }
      } else {
        toast.error("Failed to update assessment structure", {
          description: result.error,
        });
      }
    });
  };

  const handleDeleteComponent = async (deleted: AssessmentComponentCreate & { _existingId?: string }) => {
    // Only call the API if the component was previously persisted
    if (!deleted._existingId) return;
    const result = await deleteAssessmentComponent(deleted._existingId);
    if (!result.success) {
      toast.error("Failed to delete component", { description: result.error });
    }
  };

  const handleToggleReportConfig = async (
    key: keyof ReportCardConfigUpdate,
    value: boolean,
  ) => {
    if (!localReportConfig) return;

    // Capture the previous value for this specific key so we can revert it
    // without clobbering other keys that may have been toggled concurrently
    const previousValue = localReportConfig[key];
    setLocalReportConfig({ ...localReportConfig, [key]: value });

    const result = await updateReportConfig(profile.id, { [key]: value });
    if (!result.success) {
      // Revert only the specific key that failed, using the functional updater
      // to read the latest state (not a stale snapshot from before the await)
      setLocalReportConfig(prev => prev ? { ...prev, [key]: previousValue } : prev);
      toast.error("Failed to update report config", {
        description: result.error,
      });
    }
  };

  return (
    <div className="space-y-6">
      {/* Profile header */}
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <CardTitle>{profile.name}</CardTitle>
                <Badge
                  variant="secondary"
                  className={CURRICULUM_TYPE_COLORS[profile.curriculum_type]}
                >
                  {CURRICULUM_TYPE_LABELS[profile.curriculum_type]}
                </Badge>
                {profile.is_default && (
                  <Star className="h-4 w-4 text-amber-500 fill-amber-500" />
                )}
              </div>
              {profile.description && (
                <CardDescription>{profile.description}</CardDescription>
              )}
            </div>
            <div className="flex items-center gap-2">
              {!profile.is_default && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleSetDefault}
                  disabled={isPending}
                >
                  <Star className="mr-2 h-4 w-4" />
                  Set Default
                </Button>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsEditingProfile(!isEditingProfile)}
              >
                <Pencil className="mr-2 h-4 w-4" />
                {isEditingProfile ? "Cancel" : "Edit"}
              </Button>
            </div>
          </div>
        </CardHeader>
      </Card>

      <Tabs defaultValue="settings" className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="settings">Settings</TabsTrigger>
          <TabsTrigger value="assessment">Assessment</TabsTrigger>
          <TabsTrigger value="report">Report Card</TabsTrigger>
        </TabsList>

        {/* Settings tab */}
        <TabsContent value="settings" className="space-y-4">
          {isEditingProfile ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Edit Profile</CardTitle>
              </CardHeader>
              <CardContent>
                <Form {...form}>
                  <form
                    onSubmit={form.handleSubmit(handleSaveProfile)}
                    className="space-y-4"
                  >
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <FormField
                        control={form.control}
                        name="name"
                        render={({ field }) => (
                          <FormItem className="md:col-span-2">
                            <FormLabel>Name</FormLabel>
                            <FormControl>
                              <Input {...field} />
                            </FormControl>
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
                              onValueChange={field.onChange}
                            >
                              <FormControl>
                                <SelectTrigger className="w-full">
                                  <SelectValue />
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
                              <Input type="number" min={1} max={6} {...field} />
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
                                  <SelectValue />
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
                            <FormLabel>Description</FormLabel>
                            <FormControl>
                              <Textarea
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

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      {(
                        [
                          {
                            name: "show_position" as const,
                            label: "Show Position",
                            desc: "Display class ranking",
                          },
                          {
                            name: "show_class_average" as const,
                            label: "Class Average",
                            desc: "Show average on reports",
                          },
                          {
                            name: "use_gpa" as const,
                            label: "Use GPA",
                            desc: "Calculate GPA",
                          },
                          {
                            name: "use_credits" as const,
                            label: "Credit Hours",
                            desc: "Credit-based weighting",
                          },
                          {
                            name: "use_criterion_grading" as const,
                            label: "Criterion Grading",
                            desc: "Grade by criteria",
                          },
                          {
                            name: "is_active" as const,
                            label: "Active",
                            desc: "Profile is available for use",
                          },
                        ] as const
                      ).map(({ name, label, desc }) => (
                        <FormField
                          key={name}
                          control={form.control}
                          name={name}
                          render={({ field }) => (
                            <FormItem className="flex items-center justify-between rounded-lg border p-3">
                              <div className="space-y-0.5">
                                <FormLabel className="text-sm">
                                  {label}
                                </FormLabel>
                                <FormDescription className="text-xs">
                                  {desc}
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
                      ))}
                    </div>

                    <div className="flex justify-end gap-2">
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => setIsEditingProfile(false)}
                      >
                        Cancel
                      </Button>
                      <Button type="submit" disabled={isPending}>
                        {isPending && (
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        )}
                        <Save className="mr-2 h-4 w-4" />
                        Save Changes
                      </Button>
                    </div>
                  </form>
                </Form>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Profile Information</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-muted-foreground">Calendar Type</span>
                    <p className="font-medium">
                      {CALENDAR_TYPE_LABELS[profile.academic_calendar_type]}
                    </p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">
                      Periods per Year
                    </span>
                    <p className="font-medium">{profile.periods_per_year}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Score Display</span>
                    <p className="font-medium">
                      {DISPLAY_MODE_LABELS[profile.score_display_mode]}
                    </p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Status</span>
                    <p>
                      <Badge
                        variant="secondary"
                        className={
                          profile.is_active
                            ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
                            : ""
                        }
                      >
                        {profile.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </p>
                  </div>
                </div>

                <div className="mt-4 flex flex-wrap gap-2">
                  {profile.show_position && (
                    <Badge variant="outline">Position</Badge>
                  )}
                  {profile.show_class_average && (
                    <Badge variant="outline">Class Avg</Badge>
                  )}
                  {profile.use_gpa && <Badge variant="outline">GPA</Badge>}
                  {profile.use_credits && (
                    <Badge variant="outline">Credits</Badge>
                  )}
                  {profile.use_criterion_grading && (
                    <Badge variant="outline">Criterion</Badge>
                  )}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Assessment tab */}
        <TabsContent value="assessment" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-base flex items-center gap-2">
                    <BookOpen className="h-4 w-4" />
                    Assessment Structure
                  </CardTitle>
                  <CardDescription>
                    Define how student assessments are weighted and structured.
                  </CardDescription>
                </div>
                <Button
                  size="sm"
                  onClick={handleSaveAssessment}
                  disabled={isPending}
                >
                  {isPending && (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  )}
                  <Save className="mr-2 h-4 w-4" />
                  Save
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <AssessmentStructureEditor
                initialComponents={assessmentComponents}
                onChange={setAssessmentComponents}
                onDelete={handleDeleteComponent}
              />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Report Card tab */}
        <TabsContent value="report" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <FileText className="h-4 w-4" />
                Report Card Configuration
              </CardTitle>
              <CardDescription>
                Configure what appears on student report cards.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {localReportConfig ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {(
                    [
                      {
                        key: "show_position" as const,
                        label: "Show Position",
                        desc: "Display student ranking",
                      },
                      {
                        key: "show_class_average" as const,
                        label: "Class Average",
                        desc: "Show class average per subject",
                      },
                      {
                        key: "show_subject_position" as const,
                        label: "Subject Position",
                        desc: "Position within each subject",
                      },
                      {
                        key: "show_effort_grade" as const,
                        label: "Effort Grade",
                        desc: "Include effort/conduct grades",
                      },
                      {
                        key: "show_predicted_grades" as const,
                        label: "Predicted Grades",
                        desc: "Show predicted exam grades",
                      },
                      {
                        key: "show_gpa" as const,
                        label: "GPA",
                        desc: "Display Grade Point Average",
                      },
                      {
                        key: "show_credits" as const,
                        label: "Credits",
                        desc: "Show credit hours earned",
                      },
                      {
                        key: "show_honor_roll" as const,
                        label: "Honor Roll",
                        desc: "Indicate honor roll status",
                      },
                      {
                        key: "show_learner_profile" as const,
                        label: "Learner Profile",
                        desc: "IB learner profile attributes",
                      },
                      {
                        key: "show_atl_skills" as const,
                        label: "ATL Skills",
                        desc: "Approaches to Learning skills",
                      },
                    ] as const
                  ).map(({ key, label, desc }) => (
                    <div
                      key={key}
                      className="flex items-center justify-between rounded-lg border p-3"
                    >
                      <div className="space-y-0.5">
                        <p className="text-sm font-medium">{label}</p>
                        <p className="text-xs text-muted-foreground">{desc}</p>
                      </div>
                      <Switch
                        checked={localReportConfig[key]}
                        onCheckedChange={(checked) =>
                          handleToggleReportConfig(key, checked)
                        }
                      />
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-8 gap-3 text-center">
                  <FileText className="h-8 w-8 text-muted-foreground" />
                  <p className="text-sm text-muted-foreground">
                    Report card configuration will be created automatically when
                    you save the profile. Edit settings above first.
                  </p>
                </div>
              )}

              {localReportConfig && (
                <div className="mt-6 space-y-4">
                  <p className="text-xs text-muted-foreground">
                    Changes are saved automatically when you click outside the field.
                  </p>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Header Text</label>
                    <Textarea
                      rows={3}
                      className="resize-none text-sm"
                      placeholder="Enter header text for report cards..."
                      value={localReportConfig.header_text || ""}
                      onChange={(e) =>
                        setLocalReportConfig({
                          ...localReportConfig,
                          header_text: e.target.value,
                        })
                      }
                      onBlur={async (e) => {
                        const previousConfig = localReportConfig;
                        const result = await updateReportConfig(profile.id, {
                          header_text: e.target.value,
                        });
                        if (!result.success) {
                          setLocalReportConfig(previousConfig);
                          toast.error("Failed to update header text", {
                            description: result.error,
                          });
                        }
                      }}
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Footer Text</label>
                    <Textarea
                      rows={3}
                      className="resize-none text-sm"
                      placeholder="Enter footer text for report cards..."
                      value={localReportConfig.footer_text || ""}
                      onChange={(e) =>
                        setLocalReportConfig({
                          ...localReportConfig,
                          footer_text: e.target.value,
                        })
                      }
                      onBlur={async (e) => {
                        const previousConfig = localReportConfig;
                        const result = await updateReportConfig(profile.id, {
                          footer_text: e.target.value,
                        });
                        if (!result.success) {
                          setLocalReportConfig(previousConfig);
                          toast.error("Failed to update footer text", {
                            description: result.error,
                          });
                        }
                      }}
                    />
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
