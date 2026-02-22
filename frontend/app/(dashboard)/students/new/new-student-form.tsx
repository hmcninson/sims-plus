"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Loader2,
  ChevronLeft,
  ChevronRight,
  User,
  Phone,
  GraduationCap,
  Heart,
  CheckCircle2,
  Check,
  RefreshCw,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
} from "@/components/ui/card";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";

import { createStudent, generateStudentId } from "@/actions/students.action";
import type { Class } from "@/types";

// Ghana's 16 regions
const GHANA_REGIONS = [
  "Ahafo",
  "Ashanti",
  "Bono",
  "Bono East",
  "Central",
  "Eastern",
  "Greater Accra",
  "North East",
  "Northern",
  "Oti",
  "Savannah",
  "Upper East",
  "Upper West",
  "Volta",
  "Western",
  "Western North",
];

const BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"];

const studentFormSchema = z.object({
  student_id: z.string().min(1, "Student ID is required"),
  first_name: z.string().min(1, "First name is required"),
  middle_name: z.string().optional(),
  last_name: z.string().min(1, "Last name is required"),
  date_of_birth: z.string().min(1, "Date of birth is required"),
  gender: z.enum(["male", "female"]),
  email: z.string().email("Invalid email").optional().or(z.literal("")),
  phone: z.string().optional(),
  address: z.string().optional(),
  city: z.string().optional(),
  region: z.string().optional(),
  class_id: z.string().optional(),
  section_id: z.string().optional(),
  admission_date: z.string().optional(),
  admission_number: z.string().optional(),
  is_boarder: z.boolean(),
  ghana_card_number: z.string().optional(),
  nhis_number: z.string().optional(),
  blood_group: z.string().optional(),
  medical_conditions: z.string().optional(),
  allergies: z.string().optional(),
  notes: z.string().optional(),
});

type StudentFormValues = z.infer<typeof studentFormSchema>;

const steps = [
  {
    id: 1,
    title: "Personal",
    icon: User,
    fields: ["student_id", "first_name", "last_name", "date_of_birth", "gender"],
  },
  {
    id: 2,
    title: "Contact",
    icon: Phone,
    fields: ["email", "phone", "address", "city", "region"],
  },
  {
    id: 3,
    title: "Academic",
    icon: GraduationCap,
    fields: ["class_id", "section_id", "admission_date", "admission_number", "is_boarder"],
  },
  {
    id: 4,
    title: "Health",
    icon: Heart,
    fields: ["ghana_card_number", "nhis_number", "blood_group", "medical_conditions", "allergies", "notes"],
  },
  {
    id: 5,
    title: "Review",
    icon: CheckCircle2,
    fields: [],
  },
];

interface NewStudentFormProps {
  classes: Class[];
}

export function NewStudentForm({ classes }: NewStudentFormProps) {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isGeneratingId, setIsGeneratingId] = useState(false);
  const [selectedClassId, setSelectedClassId] = useState<string>("");

  const form = useForm<StudentFormValues>({
    resolver: zodResolver(studentFormSchema),
    defaultValues: {
      student_id: "",
      first_name: "",
      middle_name: "",
      last_name: "",
      date_of_birth: "",
      gender: "male",
      email: "",
      phone: "",
      address: "",
      city: "",
      region: "",
      class_id: "",
      section_id: "",
      admission_date: "",
      admission_number: "",
      is_boarder: false,
      ghana_card_number: "",
      nhis_number: "",
      blood_group: "",
      medical_conditions: "",
      allergies: "",
      notes: "",
    },
  });

  const selectedClass = classes.find((c) => c.id === selectedClassId);
  const sections = selectedClass?.sections || [];

  // Fetch student ID on mount
  useEffect(() => {
    fetchStudentId();
  }, []);

  const fetchStudentId = async () => {
    setIsGeneratingId(true);
    try {
      const result = await generateStudentId();
      if (result.success && result.data) {
        form.setValue("student_id", result.data);
      } else {
        toast.error(result.error || "Failed to generate student ID");
      }
    } catch {
      toast.error("Failed to generate student ID");
    } finally {
      setIsGeneratingId(false);
    }
  };

  const validateCurrentStep = async (): Promise<boolean> => {
    const currentStepFields = steps[currentStep - 1].fields as (keyof StudentFormValues)[];
    if (currentStepFields.length === 0) return true;

    const result = await form.trigger(currentStepFields);
    return result;
  };

  const handleNext = async () => {
    const isValid = await validateCurrentStep();
    if (isValid && currentStep < steps.length) {
      setCurrentStep(currentStep + 1);
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleSubmit = async () => {
    const isValid = await form.trigger();
    if (!isValid) {
      toast.error("Please fix the errors before submitting");
      return;
    }

    setIsSubmitting(true);

    const data = form.getValues();
    const cleanData = {
      ...data,
      middle_name: data.middle_name || undefined,
      email: data.email || undefined,
      phone: data.phone || undefined,
      address: data.address || undefined,
      city: data.city || undefined,
      region: data.region || undefined,
      class_id: data.class_id || undefined,
      section_id: data.section_id || undefined,
      admission_date: data.admission_date || undefined,
      admission_number: data.admission_number || undefined,
      ghana_card_number: data.ghana_card_number || undefined,
      nhis_number: data.nhis_number || undefined,
      blood_group: data.blood_group || undefined,
      medical_conditions: data.medical_conditions || undefined,
      allergies: data.allergies || undefined,
      notes: data.notes || undefined,
    };

    const result = await createStudent(cleanData);

    if (result.success) {
      toast.success(`Student created successfully (ID: ${result.data?.student_id})`);
      router.push(`/students/${result.data?.id}`);
    } else {
      toast.error(result.error || "Failed to create student");
    }

    setIsSubmitting(false);
  };

  const formValues = form.watch();

  const getClassName = (classId: string) => {
    return classes.find((c) => c.id === classId)?.name || "";
  };

  const getSectionName = (classId: string, sectionId: string) => {
    const cls = classes.find((c) => c.id === classId);
    return cls?.sections?.find((s) => s.id === sectionId)?.name || "";
  };

  return (
    <Card>
      <CardContent className="p-6">
        {/* Mobile: Horizontal step indicator */}
        <div className="md:hidden mb-6">
          <div className="flex items-center justify-between">
            {steps.map((step, index) => {
              const isActive = currentStep === step.id;
              const isCompleted = currentStep > step.id;
              return (
                <div key={step.id} className="flex flex-1 items-center">
                  <button
                    type="button"
                    onClick={() => { if (isCompleted) setCurrentStep(step.id); }}
                    disabled={!isCompleted && !isActive}
                    className="flex flex-col items-center gap-1"
                  >
                    <span
                      className={`flex h-7 w-7 items-center justify-center rounded-full border-2 text-xs font-medium ${
                        isCompleted
                          ? "border-primary bg-primary text-primary-foreground"
                          : isActive
                          ? "border-primary text-primary"
                          : "border-muted-foreground/30 text-muted-foreground"
                      }`}
                    >
                      {isCompleted ? <Check className="h-3 w-3" /> : step.id}
                    </span>
                    <span className={`text-[10px] font-medium text-center leading-tight max-w-[60px] ${
                      isActive ? "text-foreground" : "text-muted-foreground"
                    }`}>
                      {step.title}
                    </span>
                  </button>
                  {index < steps.length - 1 && (
                    <div className={`flex-1 h-0.5 mx-1 ${isCompleted ? "bg-primary" : "bg-muted"}`} />
                  )}
                </div>
              );
            })}
          </div>
          <p className="mt-2 text-xs text-muted-foreground text-center">
            Step {currentStep} of {steps.length}: {steps[currentStep - 1]?.title}
          </p>
        </div>

        <div className="flex gap-8">
          {/* Left Side - Step Indicator (Desktop only) */}
          <div className="hidden md:block w-48 shrink-0">
            <div className="sticky top-6 space-y-2">
              {steps.map((step, index) => {
                const StepIcon = step.icon;
                const isActive = currentStep === step.id;
                const isCompleted = currentStep > step.id;

                return (
                  <div key={step.id}>
                    <button
                      type="button"
                      onClick={() => {
                        if (isCompleted) setCurrentStep(step.id);
                      }}
                      disabled={!isCompleted && !isActive}
                      className={`w-full flex items-center gap-3 p-3 rounded-lg text-left transition-colors ${
                        isActive
                          ? "bg-primary/10 border border-primary"
                          : isCompleted
                          ? "hover:bg-muted cursor-pointer"
                          : "opacity-50 cursor-not-allowed"
                      }`}
                    >
                      <div
                        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full border-2 transition-colors ${
                          isActive
                            ? "border-primary bg-primary text-primary-foreground"
                            : isCompleted
                            ? "border-primary bg-primary text-primary-foreground"
                            : "border-muted-foreground/30 text-muted-foreground"
                        }`}
                      >
                        {isCompleted ? (
                          <Check className="h-4 w-4" />
                        ) : (
                          <StepIcon className="h-4 w-4" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p
                          className={`text-sm font-medium truncate ${
                            isActive ? "text-primary" : isCompleted ? "text-foreground" : "text-muted-foreground"
                          }`}
                        >
                          {step.title}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          Step {step.id} of {steps.length}
                        </p>
                      </div>
                    </button>
                    {index < steps.length - 1 && (
                      <div className="ml-[26px] h-4 w-0.5 bg-muted-foreground/20" />
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right Side - Form Content */}
          <div className="flex-1 min-w-0">
        <Form {...form}>
          <form
            onSubmit={(e) => e.preventDefault()}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
              }
            }}
            className="space-y-6"
          >
            {/* Step 1: Personal Information */}
            {currentStep === 1 && (
              <div className="space-y-6">
                <div>
                  <h3 className="text-lg font-medium">Personal Information</h3>
                  <p className="text-sm text-muted-foreground">
                    Basic details about the student
                  </p>
                </div>

                {/* Student ID */}
                <FormField
                  control={form.control}
                  name="student_id"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Student ID *</FormLabel>
                      <div className="flex gap-2">
                        <FormControl>
                          <Input
                            {...field}
                            disabled
                            className="bg-muted font-mono max-w-xs"
                            placeholder={isGeneratingId ? "Generating..." : ""}
                          />
                        </FormControl>
                        <Button
                          type="button"
                          variant="outline"
                          size="icon"
                          onClick={fetchStudentId}
                          disabled={isGeneratingId}
                        >
                          <RefreshCw className={`h-4 w-4 ${isGeneratingId ? "animate-spin" : ""}`} />
                        </Button>
                      </div>
                      <FormDescription>
                        Auto-generated unique identifier for the student
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                {/* Names */}
                <div className="grid gap-4 sm:grid-cols-3">
                  <FormField
                    control={form.control}
                    name="first_name"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>First Name *</FormLabel>
                        <FormControl>
                          <Input {...field} placeholder="John" />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="middle_name"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Middle Name</FormLabel>
                        <FormControl>
                          <Input {...field} placeholder="Kwame" />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="last_name"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Last Name *</FormLabel>
                        <FormControl>
                          <Input {...field} placeholder="Mensah" />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>

                {/* DOB and Gender */}
                <div className="grid gap-4 sm:grid-cols-2">
                  <FormField
                    control={form.control}
                    name="date_of_birth"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Date of Birth *</FormLabel>
                        <FormControl>
                          <Input type="date" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="gender"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Gender *</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger className="w-full">
                              <SelectValue placeholder="Select gender" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            <SelectItem value="male">Male</SelectItem>
                            <SelectItem value="female">Female</SelectItem>
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
              </div>
            )}

            {/* Step 2: Contact Information */}
            {currentStep === 2 && (
              <div className="space-y-6">
                <div>
                  <h3 className="text-lg font-medium">Contact Information</h3>
                  <p className="text-sm text-muted-foreground">
                    Contact details and address (optional)
                  </p>
                </div>

                {/* Email and Phone */}
                <div className="grid gap-4 sm:grid-cols-2">
                  <FormField
                    control={form.control}
                    name="email"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Email Address</FormLabel>
                        <FormControl>
                          <Input type="email" placeholder="student@email.com" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="phone"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Phone Number</FormLabel>
                        <FormControl>
                          <Input placeholder="+233 XX XXX XXXX" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>

                {/* Address */}
                <FormField
                  control={form.control}
                  name="address"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Street Address</FormLabel>
                      <FormControl>
                        <Input placeholder="House number, street name" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                {/* City and Region */}
                <div className="grid gap-4 sm:grid-cols-2">
                  <FormField
                    control={form.control}
                    name="city"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>City / Town</FormLabel>
                        <FormControl>
                          <Input placeholder="e.g. Accra" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="region"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Region</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value || ""}>
                          <FormControl>
                            <SelectTrigger className="w-full">
                              <SelectValue placeholder="Select region" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {GHANA_REGIONS.map((region) => (
                              <SelectItem key={region} value={region}>
                                {region}
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
            )}

            {/* Step 3: Academic Information */}
            {currentStep === 3 && (
              <div className="space-y-6">
                <div>
                  <h3 className="text-lg font-medium">Academic Information</h3>
                  <p className="text-sm text-muted-foreground">
                    Class assignment and admission details
                  </p>
                </div>

                {/* Class and Section */}
                <div className="grid gap-4 sm:grid-cols-2">
                  <FormField
                    control={form.control}
                    name="class_id"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Class</FormLabel>
                        <Select
                          onValueChange={(value) => {
                            field.onChange(value);
                            setSelectedClassId(value);
                            form.setValue("section_id", "");
                          }}
                          value={field.value}
                        >
                          <FormControl>
                            <SelectTrigger className="w-full">
                              <SelectValue placeholder="Select class" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {classes.map((cls) => (
                              <SelectItem key={cls.id} value={cls.id}>
                                {cls.name}
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
                    name="section_id"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Section</FormLabel>
                        <Select
                          onValueChange={field.onChange}
                          value={field.value}
                          disabled={sections.length === 0}
                        >
                          <FormControl>
                            <SelectTrigger className="w-full">
                              <SelectValue
                                placeholder={sections.length === 0 ? "Select class first" : "Select section"}
                              />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {sections.map((section) => (
                              <SelectItem key={section.id} value={section.id}>
                                {section.name}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>

                {/* Admission Date and Number */}
                <div className="grid gap-4 sm:grid-cols-2">
                  <FormField
                    control={form.control}
                    name="admission_date"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Admission Date</FormLabel>
                        <FormControl>
                          <Input type="date" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="admission_number"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Admission Number</FormLabel>
                        <FormControl>
                          <Input placeholder="Optional" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>

                {/* Boarding Status */}
                <FormField
                  control={form.control}
                  name="is_boarder"
                  render={({ field }) => (
                    <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
                      <div className="space-y-0.5">
                        <FormLabel className="text-base">Boarding Student</FormLabel>
                        <FormDescription>
                          Enable if the student lives on campus
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
            )}

            {/* Step 4: Health & IDs */}
            {currentStep === 4 && (
              <div className="space-y-6">
                <div>
                  <h3 className="text-lg font-medium">Health & Identification</h3>
                  <p className="text-sm text-muted-foreground">
                    Medical information and ID numbers (optional)
                  </p>
                </div>

                {/* Ghana Card and NHIS */}
                <div className="grid gap-4 sm:grid-cols-2">
                  <FormField
                    control={form.control}
                    name="ghana_card_number"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Ghana Card Number</FormLabel>
                        <FormControl>
                          <Input placeholder="GHA-XXXXXXXXX-X" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="nhis_number"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>NHIS Number</FormLabel>
                        <FormControl>
                          <Input {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>

                {/* Blood Group */}
                <FormField
                  control={form.control}
                  name="blood_group"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Blood Group</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value || ""}>
                        <FormControl>
                          <SelectTrigger className="w-full max-w-xs">
                            <SelectValue placeholder="Select blood group" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {BLOOD_GROUPS.map((group) => (
                            <SelectItem key={group} value={group}>
                              {group}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                {/* Medical Conditions */}
                <FormField
                  control={form.control}
                  name="medical_conditions"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Medical Conditions</FormLabel>
                      <FormControl>
                        <Textarea
                          placeholder="Any known medical conditions (e.g., asthma, diabetes)..."
                          rows={3}
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                {/* Allergies */}
                <FormField
                  control={form.control}
                  name="allergies"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Allergies</FormLabel>
                      <FormControl>
                        <Textarea
                          placeholder="Any known allergies (e.g., peanuts, penicillin)..."
                          rows={2}
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                {/* Notes */}
                <FormField
                  control={form.control}
                  name="notes"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Additional Notes</FormLabel>
                      <FormControl>
                        <Textarea
                          placeholder="Any other relevant information..."
                          rows={2}
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
            )}

            {/* Step 5: Review */}
            {currentStep === 5 && (
              <div className="space-y-6">
                <div>
                  <h3 className="text-lg font-medium">Review Information</h3>
                  <p className="text-sm text-muted-foreground">
                    Please review all information before creating the student record
                  </p>
                </div>

                {/* Personal Info */}
                <div className="rounded-lg border p-4 space-y-3">
                  <h4 className="font-medium flex items-center gap-2">
                    <User className="h-4 w-4" />
                    Personal Information
                  </h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                    <div>
                      <span className="text-muted-foreground">Student ID:</span>{" "}
                      <span className="font-mono font-medium">{formValues.student_id}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Full Name:</span>{" "}
                      <span className="font-medium">
                        {formValues.first_name} {formValues.middle_name} {formValues.last_name}
                      </span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Date of Birth:</span>{" "}
                      <span className="font-medium">{formValues.date_of_birth}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Gender:</span>{" "}
                      <span className="font-medium capitalize">{formValues.gender}</span>
                    </div>
                  </div>
                </div>

                {/* Contact Info */}
                <div className="rounded-lg border p-4 space-y-3">
                  <h4 className="font-medium flex items-center gap-2">
                    <Phone className="h-4 w-4" />
                    Contact Information
                  </h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                    {formValues.email && (
                      <div>
                        <span className="text-muted-foreground">Email:</span>{" "}
                        <span className="font-medium">{formValues.email}</span>
                      </div>
                    )}
                    {formValues.phone && (
                      <div>
                        <span className="text-muted-foreground">Phone:</span>{" "}
                        <span className="font-medium">{formValues.phone}</span>
                      </div>
                    )}
                    {(formValues.address || formValues.city || formValues.region) && (
                      <div className="md:col-span-2">
                        <span className="text-muted-foreground">Address:</span>{" "}
                        <span className="font-medium">
                          {[formValues.address, formValues.city, formValues.region]
                            .filter(Boolean)
                            .join(", ") || "-"}
                        </span>
                      </div>
                    )}
                    {!formValues.email && !formValues.phone && !formValues.address && (
                      <div className="md:col-span-2 text-muted-foreground italic">
                        No contact information provided
                      </div>
                    )}
                  </div>
                </div>

                {/* Academic Info */}
                <div className="rounded-lg border p-4 space-y-3">
                  <h4 className="font-medium flex items-center gap-2">
                    <GraduationCap className="h-4 w-4" />
                    Academic Information
                  </h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                    <div>
                      <span className="text-muted-foreground">Class:</span>{" "}
                      <span className="font-medium">
                        {formValues.class_id ? getClassName(formValues.class_id) : "-"}
                      </span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Section:</span>{" "}
                      <span className="font-medium">
                        {formValues.section_id && formValues.class_id
                          ? getSectionName(formValues.class_id, formValues.section_id)
                          : "-"}
                      </span>
                    </div>
                    {formValues.admission_date && (
                      <div>
                        <span className="text-muted-foreground">Admission Date:</span>{" "}
                        <span className="font-medium">{formValues.admission_date}</span>
                      </div>
                    )}
                    {formValues.admission_number && (
                      <div>
                        <span className="text-muted-foreground">Admission No:</span>{" "}
                        <span className="font-medium">{formValues.admission_number}</span>
                      </div>
                    )}
                    <div className="md:col-span-2">
                      <Badge variant={formValues.is_boarder ? "default" : "secondary"}>
                        {formValues.is_boarder ? "Boarding Student" : "Day Student"}
                      </Badge>
                    </div>
                  </div>
                </div>

                {/* Health Info */}
                {(formValues.blood_group ||
                  formValues.ghana_card_number ||
                  formValues.nhis_number ||
                  formValues.medical_conditions ||
                  formValues.allergies) && (
                  <div className="rounded-lg border p-4 space-y-3">
                    <h4 className="font-medium flex items-center gap-2">
                      <Heart className="h-4 w-4" />
                      Health & Identification
                    </h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                      {formValues.ghana_card_number && (
                        <div>
                          <span className="text-muted-foreground">Ghana Card:</span>{" "}
                          <span className="font-medium font-mono">{formValues.ghana_card_number}</span>
                        </div>
                      )}
                      {formValues.nhis_number && (
                        <div>
                          <span className="text-muted-foreground">NHIS:</span>{" "}
                          <span className="font-medium">{formValues.nhis_number}</span>
                        </div>
                      )}
                      {formValues.blood_group && (
                        <div>
                          <span className="text-muted-foreground">Blood Group:</span>{" "}
                          <span className="font-medium">{formValues.blood_group}</span>
                        </div>
                      )}
                      {formValues.medical_conditions && (
                        <div className="md:col-span-2">
                          <span className="text-muted-foreground">Medical Conditions:</span>{" "}
                          <span className="font-medium">{formValues.medical_conditions}</span>
                        </div>
                      )}
                      {formValues.allergies && (
                        <div className="md:col-span-2">
                          <span className="text-muted-foreground">Allergies:</span>{" "}
                          <span className="font-medium">{formValues.allergies}</span>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {formValues.notes && (
                  <div className="rounded-lg border p-4 space-y-3">
                    <h4 className="font-medium">Additional Notes</h4>
                    <p className="text-sm">{formValues.notes}</p>
                  </div>
                )}
              </div>
            )}

            {/* Navigation Buttons */}
            <div className="flex justify-between pt-6 border-t">
              <Button
                type="button"
                variant="outline"
                onClick={currentStep === 1 ? () => router.push("/students") : handleBack}
                disabled={isSubmitting}
              >
                {currentStep === 1 ? (
                  "Cancel"
                ) : (
                  <>
                    <ChevronLeft className="h-4 w-4 mr-1" />
                    Back
                  </>
                )}
              </Button>

              {currentStep < steps.length ? (
                <Button type="button" onClick={handleNext}>
                  Next
                  <ChevronRight className="h-4 w-4 ml-1" />
                </Button>
              ) : (
                <Button type="button" onClick={handleSubmit} disabled={isSubmitting}>
                  {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Create Student
                </Button>
              )}
            </div>
          </form>
        </Form>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
