"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import {
  Building2,
  Calendar,
  GraduationCap,
  Users,
  ArrowRight,
  ArrowLeft,
  Check,
  Loader2,
  Sparkles,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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

import { updateSchoolProfile } from "@/actions/school.action";
import { createAcademicYear, createClass, createSection } from "@/actions/academic.action";
import { createUser } from "@/actions/users.action";
import type { SchoolProfile, UserRole } from "@/types";

const STEPS = [
  { id: "welcome", title: "Welcome", icon: Sparkles },
  { id: "school", title: "School Profile", icon: Building2 },
  { id: "academic-year", title: "Academic Year", icon: Calendar },
  { id: "classes", title: "Classes", icon: GraduationCap },
  { id: "complete", title: "Complete", icon: Check },
];

interface SetupWizardProps {
  schoolProfile: SchoolProfile;
  onComplete: () => void;
}

export function SetupWizard({ schoolProfile, onComplete }: SetupWizardProps) {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(0);
  const [isPending, startTransition] = useTransition();

  // School profile state
  const [schoolData, setSchoolData] = useState({
    motto: schoolProfile.motto || "",
    description: schoolProfile.description || "",
    phone: schoolProfile.phone || "",
    email: schoolProfile.email || "",
    address: schoolProfile.address || "",
    city: schoolProfile.city || "",
  });

  // Academic year state
  const [academicYearData, setAcademicYearData] = useState({
    name: `${new Date().getFullYear()}/${new Date().getFullYear() + 1} Academic Year`,
    start_date: `${new Date().getFullYear()}-09-01`,
    end_date: `${new Date().getFullYear() + 1}-07-31`,
  });

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
      startTransition(async () => {
        const result = await updateSchoolProfile({
          motto: schoolData.motto || undefined,
          description: schoolData.description || undefined,
          phone: schoolData.phone || undefined,
          email: schoolData.email || undefined,
          address: schoolData.address || undefined,
          city: schoolData.city || undefined,
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

        if (result.success) {
          setCurrentStep(currentStep + 1);
        } else {
          toast.error("Failed to create academic year", {
            description: result.error,
          });
        }
      });
    } else if (currentStep === 3) {
      // Create classes and sections
      startTransition(async () => {
        let allSuccess = true;

        for (const classItem of classesData) {
          const classResult = await createClass({
            name: classItem.name,
            short_name: classItem.short_name,
            level: classItem.level as "primary" | "jhs" | "shs" | "preschool",
            sequence: classesData.indexOf(classItem) + 1,
          });

          if (classResult.success && classResult.data) {
            // Create sections for this class
            for (const sectionName of classItem.sections) {
              await createSection({
                class_id: classResult.data.id,
                name: sectionName,
              });
            }
          } else {
            allSuccess = false;
            break;
          }
        }

        if (allSuccess) {
          setCurrentStep(currentStep + 1);
        } else {
          toast.error("Failed to create some classes");
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

  const addClass = () => {
    const newIndex = classesData.length + 1;
    setClassesData([
      ...classesData,
      { name: `Class ${newIndex}`, short_name: `P${newIndex}`, level: "primary", sections: ["A"] },
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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/95 backdrop-blur-sm">
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

        {/* Step Indicators */}
        <div className="flex items-center justify-center gap-2 mb-8">
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
                <CardTitle className="text-2xl">Welcome to SIMS Plus!</CardTitle>
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
                      <GraduationCap className="h-5 w-5 text-primary" />
                      <span className="text-sm">Classes</span>
                    </div>
                    <div className="flex items-center gap-2 p-3 rounded-lg border bg-muted/30">
                      <Users className="h-5 w-5 text-primary" />
                      <span className="text-sm">Staff</span>
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
                <div className="space-y-2">
                  <Label htmlFor="school_name">School Name</Label>
                  <Input
                    id="school_name"
                    value={schoolProfile.name}
                    disabled
                    className="bg-muted"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="motto">School Motto</Label>
                  <Input
                    id="motto"
                    placeholder="Enter your school's motto"
                    value={schoolData.motto}
                    onChange={(e) =>
                      setSchoolData((prev) => ({ ...prev, motto: e.target.value }))
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
                      setSchoolData((prev) => ({ ...prev, description: e.target.value }))
                    }
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="phone">Phone</Label>
                    <Input
                      id="phone"
                      type="tel"
                      placeholder="+233 XX XXX XXXX"
                      value={schoolData.phone}
                      onChange={(e) =>
                        setSchoolData((prev) => ({ ...prev, phone: e.target.value }))
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
                        setSchoolData((prev) => ({ ...prev, email: e.target.value }))
                      }
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="city">City/Town</Label>
                    <Input
                      id="city"
                      placeholder="e.g., Accra"
                      value={schoolData.city}
                      onChange={(e) =>
                        setSchoolData((prev) => ({ ...prev, city: e.target.value }))
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
                        setSchoolData((prev) => ({ ...prev, address: e.target.value }))
                      }
                    />
                  </div>
                </div>
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
                      setAcademicYearData((prev) => ({ ...prev, name: e.target.value }))
                    }
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="start_date">Start Date</Label>
                    <Input
                      id="start_date"
                      type="date"
                      value={academicYearData.start_date}
                      onChange={(e) =>
                        setAcademicYearData((prev) => ({ ...prev, start_date: e.target.value }))
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
                        setAcademicYearData((prev) => ({ ...prev, end_date: e.target.value }))
                      }
                    />
                  </div>
                </div>
                <p className="text-sm text-muted-foreground">
                  You can add terms and customize the academic calendar later in Settings.
                </p>
              </CardContent>
            </>
          )}

          {/* Step 3: Classes */}
          {currentStep === 3 && (
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
                      className="flex items-center gap-3 p-3 rounded-lg border bg-muted/30"
                    >
                      <Input
                        placeholder="Class name"
                        value={classItem.name}
                        onChange={(e) => updateClass(index, "name", e.target.value)}
                        className="flex-1"
                      />
                      <Input
                        placeholder="Short"
                        value={classItem.short_name}
                        onChange={(e) => updateClass(index, "short_name", e.target.value)}
                        className="w-20"
                      />
                      <Select
                        value={classItem.level}
                        onValueChange={(value) => updateClass(index, "level", value)}
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
                <Button type="button" variant="outline" onClick={addClass} className="w-full">
                  Add Another Class
                </Button>
                <p className="text-sm text-muted-foreground">
                  Each class will be created with a default section &quot;A&quot;. You can add more sections later.
                </p>
              </CardContent>
            </>
          )}

          {/* Step 4: Complete */}
          {currentStep === 4 && (
            <>
              <CardHeader className="text-center pb-2">
                <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/20">
                  <Check className="h-8 w-8 text-green-600 dark:text-green-400" />
                </div>
                <CardTitle className="text-2xl">You&apos;re All Set!</CardTitle>
                <CardDescription className="text-base">
                  Your school has been configured successfully.
                </CardDescription>
              </CardHeader>
              <CardContent className="pt-4">
                <div className="space-y-4 text-center">
                  <div className="space-y-2">
                    <p className="font-medium">{schoolProfile.name}</p>
                    <p className="text-sm text-muted-foreground">
                      {classesData.length} classes created
                    </p>
                  </div>
                  <div className="pt-4">
                    <p className="text-sm text-muted-foreground mb-4">
                      Next steps you might want to take:
                    </p>
                    <div className="grid grid-cols-1 gap-2 max-w-xs mx-auto text-left">
                      <div className="flex items-center gap-2 text-sm">
                        <Check className="h-4 w-4 text-green-500" />
                        <span>Upload your school logo</span>
                      </div>
                      <div className="flex items-center gap-2 text-sm">
                        <Check className="h-4 w-4 text-green-500" />
                        <span>Invite your staff members</span>
                      </div>
                      <div className="flex items-center gap-2 text-sm">
                        <Check className="h-4 w-4 text-green-500" />
                        <span>Add subjects</span>
                      </div>
                      <div className="flex items-center gap-2 text-sm">
                        <Check className="h-4 w-4 text-green-500" />
                        <span>Enroll students</span>
                      </div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </>
          )}

          {/* Navigation Buttons */}
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

            {currentStep < STEPS.length - 1 ? (
              <Button onClick={handleNext} disabled={isPending}>
                {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {currentStep === 0 ? "Get Started" : "Continue"}
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            ) : (
              <Button onClick={handleComplete}>
                Go to Dashboard
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
