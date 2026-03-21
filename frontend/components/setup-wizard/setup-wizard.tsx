"use client";

import { useState, useTransition } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Building2,
  Calendar,
  GraduationCap,
  Users,
  UserPlus,
  DollarSign,
  Settings,
  BookOpen,
  ClipboardList,
  ArrowRight,
  ArrowLeft,
  Check,
  CheckCircle2,
  Loader2,
  Sparkles,
  Plus,
  Minus,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Progress } from "@/components/ui/progress";

import { SubjectTemplateSelector } from "@/components/academic/SubjectTemplateSelector";
import { updateSchoolProfile } from "@/actions/school.action";
import {
  createAcademicYear,
  createClass,
  createSection,
  createTerm,
} from "@/actions/academic.action";
import type { SchoolProfile } from "@/types";

const STEPS = [
  { id: "welcome", title: "Welcome", icon: Sparkles },
  { id: "school-profile", title: "School Profile", icon: Building2 },
  { id: "academic-year", title: "Academic Year", icon: Calendar },
  { id: "terms", title: "Terms", icon: ClipboardList },
  { id: "classes", title: "Classes", icon: GraduationCap },
  { id: "subjects", title: "Subjects", icon: BookOpen },
  { id: "complete", title: "Complete", icon: Check },
];

interface SetupWizardProps {
  schoolProfile: SchoolProfile | null;
  onComplete: () => void;
}

interface TermData {
  name: string;
  short_name: string;
  sequence: number;
  start_date: string;
  end_date: string;
}

export function SetupWizard({ schoolProfile, onComplete }: SetupWizardProps) {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(0);
  const [isPending, startTransition] = useTransition();

  // Context passed between steps
  const [createdAcademicYear, setCreatedAcademicYear] = useState<{
    id: string;
    name: string;
  } | null>(null);

  // School profile state
  const [schoolData, setSchoolData] = useState({
    motto: schoolProfile?.motto || "",
    description: schoolProfile?.description || "",
    phone: schoolProfile?.phone || "",
    email: schoolProfile?.email || "",
    address: schoolProfile?.address || "",
    city: schoolProfile?.city || "",
    category: schoolProfile?.category || "",
    boarding_type: schoolProfile?.boarding_type || "",
  });

  // Academic year state
  const [academicYearData, setAcademicYearData] = useState({
    name: `${new Date().getFullYear()}/${new Date().getFullYear() + 1} Academic Year`,
    start_date: `${new Date().getFullYear()}-09-01`,
    end_date: `${new Date().getFullYear() + 1}-07-31`,
  });

  // Terms state — pre-filled with Ghana standard 3 terms
  const [termsData, setTermsData] = useState<TermData[]>([
    {
      name: "First Term",
      short_name: "T1",
      sequence: 1,
      start_date: "",
      end_date: "",
    },
    {
      name: "Second Term",
      short_name: "T2",
      sequence: 2,
      start_date: "",
      end_date: "",
    },
    {
      name: "Third Term",
      short_name: "T3",
      sequence: 3,
      start_date: "",
      end_date: "",
    },
  ]);
  const [termsLoading, setTermsLoading] = useState(false);

  // Classes state
  const [classesData, setClassesData] = useState([
    { name: "Class 1", short_name: "P1", level: "primary", sections: ["A"] },
    { name: "Class 2", short_name: "P2", level: "primary", sections: ["A"] },
    { name: "Class 3", short_name: "P3", level: "primary", sections: ["A"] },
  ]);

  const progress = ((currentStep + 1) / STEPS.length) * 100;

  const handleNext = async () => {
    if (currentStep === 1) {
      // Save school profile
      if (!schoolProfile) {
        setCurrentStep(currentStep + 1);
        return;
      }
      startTransition(async () => {
        const result = await updateSchoolProfile({
          motto: schoolData.motto || undefined,
          description: schoolData.description || undefined,
          phone: schoolData.phone || undefined,
          email: schoolData.email || undefined,
          address: schoolData.address || undefined,
          city: schoolData.city || undefined,
          category: (schoolData.category || undefined) as
            | "public"
            | "private"
            | "international"
            | "faith_based"
            | undefined,
          boarding_type: (schoolData.boarding_type || undefined) as
            | "day_only"
            | "boarding_only"
            | "mixed"
            | undefined,
        });

        if (result.success) {
          setCurrentStep(currentStep + 1);
        } else {
          toast.error("Failed to save school profile", {
            description: result.error,
          });
        }
      });
    } else if (currentStep === 2) {
      // Create academic year
      startTransition(async () => {
        const result = await createAcademicYear({
          name: academicYearData.name,
          start_date: academicYearData.start_date,
          end_date: academicYearData.end_date,
          is_current: true,
        });

        if (result.success && result.data) {
          setCreatedAcademicYear({
            id: result.data.id,
            name: result.data.name,
          });
          setCurrentStep(currentStep + 1);
        } else {
          toast.error("Failed to create academic year", {
            description: result.error,
          });
        }
      });
    } else if (currentStep === 4) {
      // Create classes and sections (step index 4 now)
      startTransition(async () => {
        let createdCount = 0;
        let skippedCount = 0;
        const errors: string[] = [];

        for (const classItem of classesData) {
          const classResult = await createClass({
            name: classItem.name,
            short_name: classItem.short_name,
            level: classItem.level as "primary" | "jhs" | "shs" | "preschool",
            sequence: classesData.indexOf(classItem) + 1,
          });

          if (classResult.success && classResult.data) {
            createdCount++;
            for (const sectionName of classItem.sections) {
              await createSection({
                class_id: classResult.data.id,
                name: sectionName,
              });
            }
          } else {
            const errorMsg = classResult.error || "Unknown error";
            const isDuplicate =
              errorMsg.toLowerCase().includes("already exists") ||
              errorMsg.toLowerCase().includes("duplicate");
            if (isDuplicate) {
              skippedCount++;
              continue;
            }
            errors.push(`${classItem.name}: ${errorMsg}`);
          }
        }

        if (errors.length === 0) {
          if (skippedCount > 0) {
            toast.info(
              `${skippedCount} class(es) already existed and were skipped.`
            );
          }
          setCurrentStep(currentStep + 1);
        } else {
          toast.error(`Failed to create ${errors.length} class(es)`, {
            description: errors.join("; "),
          });
          if (createdCount > 0 || skippedCount > 0) {
            toast.info(
              "You can add the remaining classes later from the Classes page."
            );
            setCurrentStep(currentStep + 1);
          }
        }
      });
    } else {
      setCurrentStep(currentStep + 1);
    }
  };

  const handlePrevious = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleComplete = () => {
    onComplete();
    router.push("/dashboard");
    router.refresh();
  };

  // --- Terms step handlers ---

  const handleCreateTerms = async () => {
    if (!createdAcademicYear) {
      toast.error("No academic year found. Please go back and create one.");
      return;
    }

    setTermsLoading(true);
    try {
      let created = 0;
      for (const term of termsData) {
        if (!term.start_date || !term.end_date) continue;

        const result = await createTerm({
          academic_year_id: createdAcademicYear.id,
          name: term.name,
          short_name: term.short_name,
          sequence: term.sequence,
          start_date: term.start_date,
          end_date: term.end_date,
        });

        if (!result.success) {
          if (!result.error?.includes("already exists")) {
            toast.error(`Failed to create ${term.name}: ${result.error}`);
          }
        } else {
          created++;
        }
      }

      if (created > 0) {
        toast.success(`${created} term(s) created successfully`);
      }
      setCurrentStep(currentStep + 1);
    } finally {
      setTermsLoading(false);
    }
  };

  const addTerm = () => {
    setTermsData([
      ...termsData,
      {
        name: `Term ${termsData.length + 1}`,
        short_name: `T${termsData.length + 1}`,
        sequence: termsData.length + 1,
        start_date: "",
        end_date: "",
      },
    ]);
  };

  const removeTerm = () => {
    if (termsData.length > 1) {
      setTermsData(termsData.slice(0, -1));
    }
  };

  const updateTermField = (
    index: number,
    field: keyof TermData,
    value: string | number
  ) => {
    const updated = [...termsData];
    updated[index] = { ...updated[index], [field]: value };
    setTermsData(updated);
  };

  // --- Classes step handlers ---

  const addClass = () => {
    const newIndex = classesData.length + 1;
    setClassesData([
      ...classesData,
      {
        name: `Class ${newIndex}`,
        short_name: `P${newIndex}`,
        level: "primary",
        sections: ["A"],
      },
    ]);
  };

  const removeClass = (index: number) => {
    setClassesData(classesData.filter((_, i) => i !== index));
  };

  const updateClass = (index: number, field: string, value: string) => {
    const updated = [...classesData];
    updated[index] = { ...updated[index], [field]: value };
    setClassesData(updated);
  };

  // Determine whether we're on a step with custom navigation (Terms, Subjects, Complete)
  const isCustomNavStep = currentStep === 3 || currentStep === 5 || currentStep === 6;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/95 backdrop-blur-sm overflow-y-auto">
      <div className="w-full max-w-2xl mx-auto p-6">
        {/* Progress Bar */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium">
              Step {currentStep + 1} of {STEPS.length}
            </span>
            <span className="text-sm text-muted-foreground">
              {STEPS[currentStep].title}
            </span>
          </div>
          <Progress value={progress} className="h-2" />
        </div>

        {/* Step Indicators — hidden on mobile for 7 steps */}
        <div className="hidden sm:flex items-center justify-center gap-2 mb-8">
          {STEPS.map((step, index) => {
            const StepIcon = step.icon;
            const isActive = index === currentStep;
            const isComplete = index < currentStep;

            return (
              <div
                key={step.id}
                className={`flex items-center justify-center w-10 h-10 rounded-full border-2 transition-colors ${
                  isActive
                    ? "border-primary bg-primary text-primary-foreground"
                    : isComplete
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-muted text-muted-foreground"
                }`}
              >
                {isComplete ? (
                  <Check className="h-5 w-5" />
                ) : (
                  <StepIcon className="h-5 w-5" />
                )}
              </div>
            );
          })}
        </div>

        {/* Step Content */}
        <Card className="shadow-lg">
          {/* Step 0: Welcome */}
          {currentStep === 0 && (
            <>
              <CardHeader className="text-center pb-2">
                <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
                  <Sparkles className="h-8 w-8 text-primary" />
                </div>
                <CardTitle className="text-2xl">
                  Welcome to SIMS Plus!
                </CardTitle>
                <CardDescription className="text-base">
                  Let&apos;s set up your school in just a few steps.
                </CardDescription>
              </CardHeader>
              <CardContent className="pt-4">
                <div className="space-y-4 text-center">
                  <p className="text-muted-foreground">
                    We&apos;ll help you configure:
                  </p>
                  <div className="grid grid-cols-2 gap-4 max-w-sm mx-auto">
                    <div className="flex items-center gap-2 p-3 rounded-lg border bg-muted/30">
                      <Building2 className="h-5 w-5 text-primary" />
                      <span className="text-sm">School Profile</span>
                    </div>
                    <div className="flex items-center gap-2 p-3 rounded-lg border bg-muted/30">
                      <Calendar className="h-5 w-5 text-primary" />
                      <span className="text-sm">Academic Year</span>
                    </div>
                    <div className="flex items-center gap-2 p-3 rounded-lg border bg-muted/30">
                      <ClipboardList className="h-5 w-5 text-primary" />
                      <span className="text-sm">Terms</span>
                    </div>
                    <div className="flex items-center gap-2 p-3 rounded-lg border bg-muted/30">
                      <GraduationCap className="h-5 w-5 text-primary" />
                      <span className="text-sm">Classes</span>
                    </div>
                    <div className="flex items-center gap-2 p-3 rounded-lg border bg-muted/30 col-span-2 justify-center">
                      <BookOpen className="h-5 w-5 text-primary" />
                      <span className="text-sm">Subjects</span>
                    </div>
                  </div>
                  <p className="text-sm text-muted-foreground pt-2">
                    This will only take about 5 minutes.
                  </p>
                </div>
              </CardContent>
            </>
          )}

          {/* Step 1: School Profile */}
          {currentStep === 1 && (
            <>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Building2 className="h-5 w-5" />
                  School Profile
                </CardTitle>
                <CardDescription>
                  Add some basic information about your school.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {schoolProfile && (
                  <div className="space-y-2">
                    <Label htmlFor="school_name">School Name</Label>
                    <Input
                      id="school_name"
                      value={schoolProfile.name}
                      disabled
                      className="bg-muted"
                    />
                  </div>
                )}
                <div className="space-y-2">
                  <Label htmlFor="motto">School Motto</Label>
                  <Input
                    id="motto"
                    placeholder="Enter your school's motto"
                    value={schoolData.motto}
                    onChange={(e) =>
                      setSchoolData((prev) => ({
                        ...prev,
                        motto: e.target.value,
                      }))
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="description">Brief Description</Label>
                  <Textarea
                    id="description"
                    placeholder="A short description of your school..."
                    value={schoolData.description}
                    onChange={(e) =>
                      setSchoolData((prev) => ({
                        ...prev,
                        description: e.target.value,
                      }))
                    }
                  />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="phone">Phone</Label>
                    <Input
                      id="phone"
                      type="tel"
                      placeholder="+233 XX XXX XXXX"
                      value={schoolData.phone}
                      onChange={(e) =>
                        setSchoolData((prev) => ({
                          ...prev,
                          phone: e.target.value,
                        }))
                      }
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="email">Email</Label>
                    <Input
                      id="email"
                      type="email"
                      placeholder="school@example.com"
                      value={schoolData.email}
                      onChange={(e) =>
                        setSchoolData((prev) => ({
                          ...prev,
                          email: e.target.value,
                        }))
                      }
                    />
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="city">City/Town</Label>
                    <Input
                      id="city"
                      placeholder="e.g., Accra"
                      value={schoolData.city}
                      onChange={(e) =>
                        setSchoolData((prev) => ({
                          ...prev,
                          city: e.target.value,
                        }))
                      }
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="address">Address</Label>
                    <Input
                      id="address"
                      placeholder="Street address"
                      value={schoolData.address}
                      onChange={(e) =>
                        setSchoolData((prev) => ({
                          ...prev,
                          address: e.target.value,
                        }))
                      }
                    />
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>School Category</Label>
                    <Select
                      value={schoolData.category}
                      onValueChange={(val) =>
                        setSchoolData((prev) => ({ ...prev, category: val }))
                      }
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select category" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="public">
                          Public (Government)
                        </SelectItem>
                        <SelectItem value="private">Private</SelectItem>
                        <SelectItem value="international">
                          International
                        </SelectItem>
                        <SelectItem value="faith_based">
                          Faith-Based
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Boarding Type</Label>
                    <Select
                      value={schoolData.boarding_type}
                      onValueChange={(val) =>
                        setSchoolData((prev) => ({
                          ...prev,
                          boarding_type: val,
                        }))
                      }
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select boarding type" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="day_only">
                          Day School Only
                        </SelectItem>
                        <SelectItem value="boarding_only">
                          Boarding School Only
                        </SelectItem>
                        <SelectItem value="mixed">
                          Mixed (Day & Boarding)
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <p className="text-xs text-muted-foreground">
                  Category and boarding type are optional. You can set these
                  later in Settings.
                </p>
              </CardContent>
            </>
          )}

          {/* Step 2: Academic Year */}
          {currentStep === 2 && (
            <>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Calendar className="h-5 w-5" />
                  Academic Year
                </CardTitle>
                <CardDescription>
                  Set up your current academic year.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="year_name">Academic Year Name</Label>
                  <Input
                    id="year_name"
                    placeholder="e.g., 2025/2026 Academic Year"
                    value={academicYearData.name}
                    onChange={(e) =>
                      setAcademicYearData((prev) => ({
                        ...prev,
                        name: e.target.value,
                      }))
                    }
                  />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="start_date">Start Date</Label>
                    <Input
                      id="start_date"
                      type="date"
                      value={academicYearData.start_date}
                      onChange={(e) =>
                        setAcademicYearData((prev) => ({
                          ...prev,
                          start_date: e.target.value,
                        }))
                      }
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="end_date">End Date</Label>
                    <Input
                      id="end_date"
                      type="date"
                      value={academicYearData.end_date}
                      onChange={(e) =>
                        setAcademicYearData((prev) => ({
                          ...prev,
                          end_date: e.target.value,
                        }))
                      }
                    />
                  </div>
                </div>
              </CardContent>
            </>
          )}

          {/* Step 3: Terms */}
          {currentStep === 3 && (
            <>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ClipboardList className="h-5 w-5" />
                  Set Up Terms
                </CardTitle>
                <CardDescription>
                  Define the terms for{" "}
                  {createdAcademicYear?.name || "your academic year"}. Ghana
                  typically uses 3 terms.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-3 max-h-[300px] overflow-y-auto pr-2">
                  {termsData.map((term, index) => (
                    <div
                      key={index}
                      className="rounded-lg border p-4 space-y-3"
                    >
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div className="space-y-1">
                          <Label className="text-xs">Term Name</Label>
                          <Input
                            value={term.name}
                            onChange={(e) =>
                              updateTermField(index, "name", e.target.value)
                            }
                            placeholder="e.g., First Term"
                          />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Short Name</Label>
                          <Input
                            value={term.short_name}
                            onChange={(e) =>
                              updateTermField(
                                index,
                                "short_name",
                                e.target.value
                              )
                            }
                            placeholder="e.g., T1"
                          />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Start Date</Label>
                          <Input
                            type="date"
                            value={term.start_date}
                            onChange={(e) =>
                              updateTermField(
                                index,
                                "start_date",
                                e.target.value
                              )
                            }
                          />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">End Date</Label>
                          <Input
                            type="date"
                            value={term.end_date}
                            onChange={(e) =>
                              updateTermField(
                                index,
                                "end_date",
                                e.target.value
                              )
                            }
                          />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="flex gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={addTerm}
                  >
                    <Plus className="mr-1 h-4 w-4" />
                    Add Term
                  </Button>
                  {termsData.length > 1 && (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={removeTerm}
                    >
                      <Minus className="mr-1 h-4 w-4" />
                      Remove Last
                    </Button>
                  )}
                </div>

                <div className="flex justify-between pt-2">
                  <Button
                    variant="ghost"
                    onClick={() => setCurrentStep(currentStep + 1)}
                  >
                    Skip for now
                  </Button>
                  <Button
                    onClick={handleCreateTerms}
                    disabled={termsLoading}
                  >
                    {termsLoading ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Creating terms...
                      </>
                    ) : (
                      "Create Terms & Continue"
                    )}
                  </Button>
                </div>
              </CardContent>
            </>
          )}

          {/* Step 4: Classes */}
          {currentStep === 4 && (
            <>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <GraduationCap className="h-5 w-5" />
                  Classes
                </CardTitle>
                <CardDescription>
                  Add the classes for your school. You can modify these later.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-3 max-h-[300px] overflow-y-auto pr-2">
                  {classesData.map((classItem, index) => (
                    <div
                      key={index}
                      className="flex flex-wrap items-center gap-3 p-3 rounded-lg border bg-muted/30"
                    >
                      <Input
                        placeholder="Class name"
                        value={classItem.name}
                        onChange={(e) =>
                          updateClass(index, "name", e.target.value)
                        }
                        className="flex-1 min-w-[120px]"
                      />
                      <Input
                        placeholder="Short"
                        value={classItem.short_name}
                        onChange={(e) =>
                          updateClass(index, "short_name", e.target.value)
                        }
                        className="w-20"
                      />
                      <Select
                        value={classItem.level}
                        onValueChange={(value) =>
                          updateClass(index, "level", value)
                        }
                      >
                        <SelectTrigger className="w-28">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="preschool">Preschool</SelectItem>
                          <SelectItem value="primary">Primary</SelectItem>
                          <SelectItem value="jhs">JHS</SelectItem>
                          <SelectItem value="shs">SHS</SelectItem>
                        </SelectContent>
                      </Select>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => removeClass(index)}
                        disabled={classesData.length <= 1}
                      >
                        Remove
                      </Button>
                    </div>
                  ))}
                </div>
                <Button
                  type="button"
                  variant="outline"
                  onClick={addClass}
                  className="w-full"
                >
                  Add Another Class
                </Button>
                <p className="text-sm text-muted-foreground">
                  Each class will be created with a default section &quot;A&quot;.
                  You can add more sections later.
                </p>
              </CardContent>
            </>
          )}

          {/* Step 5: Subjects */}
          {currentStep === 5 && (
            <>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BookOpen className="h-5 w-5" />
                  Set Up Subjects
                </CardTitle>
                <CardDescription>
                  Load standard GES curriculum subjects for your school, or skip
                  to add them later.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <SubjectTemplateSelector
                  schoolType={
                    schoolProfile?.school_type || "primary"
                  }
                  onComplete={() => setCurrentStep(currentStep + 1)}
                />
                <Button
                  variant="ghost"
                  onClick={() => setCurrentStep(currentStep + 1)}
                  className="w-full"
                >
                  Skip -- I&apos;ll add subjects later
                </Button>
              </CardContent>
            </>
          )}

          {/* Step 6: Complete */}
          {currentStep === 6 && (
            <>
              <CardHeader className="text-center pb-2">
                <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/20">
                  <CheckCircle2 className="h-8 w-8 text-green-600 dark:text-green-400" />
                </div>
                <CardTitle className="text-2xl">Setup Complete!</CardTitle>
                <CardDescription className="text-base">
                  Your school is ready. Here are your recommended next steps:
                </CardDescription>
              </CardHeader>
              <CardContent className="pt-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <NextStepCard
                    icon={<Users className="h-5 w-5" />}
                    title="Import Students"
                    description="Upload student data from CSV/Excel"
                    href="/students?import=true"
                  />
                  <NextStepCard
                    icon={<UserPlus className="h-5 w-5" />}
                    title="Add Staff"
                    description="Create teacher and staff accounts"
                    href="/staff"
                  />
                  <NextStepCard
                    icon={<DollarSign className="h-5 w-5" />}
                    title="Fee Structures"
                    description="Set up tuition and fee schedules"
                    href="/finance/fee-structures"
                  />
                  <NextStepCard
                    icon={<Settings className="h-5 w-5" />}
                    title="School Settings"
                    description="Logo, branding, and preferences"
                    href="/settings/school"
                  />
                </div>
              </CardContent>
            </>
          )}

          {/* Navigation Buttons — hidden on steps with custom nav */}
          {!isCustomNavStep && (
            <div className="flex items-center justify-between p-6 pt-0">
              <Button
                type="button"
                variant="outline"
                onClick={handlePrevious}
                disabled={currentStep === 0 || isPending}
              >
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back
              </Button>

              <Button onClick={handleNext} disabled={isPending}>
                {isPending && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                {currentStep === 0 ? "Get Started" : "Continue"}
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </div>
          )}

          {/* Terms step: show back + skip/create buttons are inline above */}
          {currentStep === 3 && (
            <div className="flex items-center justify-start p-6 pt-0">
              <Button
                type="button"
                variant="outline"
                onClick={handlePrevious}
                disabled={termsLoading}
              >
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back
              </Button>
            </div>
          )}

          {/* Subjects step: back button */}
          {currentStep === 5 && (
            <div className="flex items-center justify-start p-6 pt-0">
              <Button
                type="button"
                variant="outline"
                onClick={handlePrevious}
              >
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back
              </Button>
            </div>
          )}

          {/* Complete step: Go to Dashboard */}
          {currentStep === 6 && (
            <div className="flex items-center justify-center p-6 pt-0">
              <Button onClick={handleComplete}>
                Go to Dashboard
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

function NextStepCard({
  icon,
  title,
  description,
  href,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  href: string;
}) {
  return (
    <Link href={href}>
      <Card className="hover:bg-muted/50 transition-colors cursor-pointer h-full">
        <CardContent className="pt-4 flex items-start gap-3">
          <div className="text-muted-foreground mt-0.5">{icon}</div>
          <div>
            <p className="font-medium text-sm">{title}</p>
            <p className="text-xs text-muted-foreground">{description}</p>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
