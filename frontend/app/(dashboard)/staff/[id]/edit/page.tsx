"use client";

import { useState, useEffect } from "react";
import { useRouter, useParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import Link from "next/link";
import {
  Loader2,
  ChevronLeft,
  ChevronRight,
  User,
  Phone,
  Briefcase,
  CreditCard,
  CheckCircle2,
  Check,
  ArrowLeft,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Form,
  FormControl,
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
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

import { getStaffMember, updateStaff, getDepartments, type Department } from "@/actions/staff.action";

const GHANA_REGIONS = [
  "Ahafo", "Ashanti", "Bono", "Bono East", "Central", "Eastern",
  "Greater Accra", "North East", "Northern", "Oti", "Savannah",
  "Upper East", "Upper West", "Volta", "Western", "Western North",
];

const STAFF_TYPES = [
  { value: "teaching", label: "Teaching Staff" },
  { value: "non_teaching", label: "Non-Teaching Staff" },
  { value: "administrative", label: "Administrative Staff" },
];

const STAFF_STATUSES = [
  { value: "active", label: "Active" },
  { value: "on_leave", label: "On Leave" },
  { value: "suspended", label: "Suspended" },
  { value: "terminated", label: "Terminated" },
  { value: "retired", label: "Retired" },
];

const EMPLOYMENT_TYPES = [
  { value: "full_time", label: "Full Time" },
  { value: "part_time", label: "Part Time" },
  { value: "contract", label: "Contract" },
  { value: "temporary", label: "Temporary" },
  { value: "intern", label: "Intern" },
];

const MARITAL_STATUSES = [
  { value: "single", label: "Single" },
  { value: "married", label: "Married" },
  { value: "divorced", label: "Divorced" },
  { value: "widowed", label: "Widowed" },
];

const staffFormSchema = z.object({
  first_name: z.string().min(1, "First name is required"),
  middle_name: z.string().optional(),
  last_name: z.string().min(1, "Last name is required"),
  date_of_birth: z.string().optional(),
  gender: z.enum(["male", "female"]),
  email: z.string().email("Invalid email"),
  phone: z.string().min(1, "Phone number is required"),
  phone_secondary: z.string().optional(),
  address: z.string().optional(),
  city: z.string().optional(),
  region: z.string().optional(),
  emergency_contact_name: z.string().optional(),
  emergency_contact_phone: z.string().optional(),
  emergency_contact_relationship: z.string().optional(),
  ghana_card_number: z.string().optional(),
  ssnit_number: z.string().optional(),
  teacher_license_number: z.string().optional(),
  staff_type: z.enum(["teaching", "non_teaching", "administrative"]),
  status: z.enum(["active", "on_leave", "suspended", "terminated", "retired"]),
  employment_type: z.string().optional(),
  job_title: z.string().min(1, "Job title is required"),
  department: z.string().optional(),
  employment_date: z.string().min(1, "Employment date is required"),
  termination_date: z.string().optional(),
  ges_staff_id: z.string().optional(),
  tin_number: z.string().optional(),
  nationality: z.string().optional(),
  marital_status: z.string().optional(),
  bank_name: z.string().optional(),
  bank_branch: z.string().optional(),
  account_number: z.string().optional(),
  notes: z.string().optional(),
});

type StaffFormValues = z.infer<typeof staffFormSchema>;

const steps = [
  {
    id: 1,
    title: "Personal",
    icon: User,
    fields: ["first_name", "last_name", "date_of_birth", "gender"],
  },
  {
    id: 2,
    title: "Contact",
    icon: Phone,
    fields: ["email", "phone", "phone_secondary", "address", "city", "region", "emergency_contact_name", "emergency_contact_phone", "emergency_contact_relationship"],
  },
  {
    id: 3,
    title: "Employment",
    icon: Briefcase,
    fields: ["staff_type", "status", "employment_type", "job_title", "department", "employment_date", "termination_date", "ges_staff_id", "tin_number", "nationality", "marital_status", "ghana_card_number", "ssnit_number", "teacher_license_number"],
  },
  {
    id: 4,
    title: "Banking",
    icon: CreditCard,
    fields: ["bank_name", "bank_branch", "account_number", "notes"],
  },
  {
    id: 5,
    title: "Review",
    icon: CheckCircle2,
    fields: [],
  },
];

export default function EditStaffPage() {
  const router = useRouter();
  const params = useParams();
  const staffId = params.id as string;

  const [currentStep, setCurrentStep] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [departments, setDepartments] = useState<Department[]>([]);

  const form = useForm<StaffFormValues>({
    resolver: zodResolver(staffFormSchema),
    defaultValues: {
      first_name: "",
      middle_name: "",
      last_name: "",
      date_of_birth: "",
      gender: "male",
      email: "",
      phone: "",
      phone_secondary: "",
      address: "",
      city: "",
      region: "",
      emergency_contact_name: "",
      emergency_contact_phone: "",
      emergency_contact_relationship: "",
      ghana_card_number: "",
      ssnit_number: "",
      teacher_license_number: "",
      staff_type: "teaching",
      status: "active",
      employment_type: "",
      job_title: "",
      department: "",
      employment_date: "",
      termination_date: "",
      ges_staff_id: "",
      tin_number: "",
      nationality: "",
      marital_status: "",
      bank_name: "",
      bank_branch: "",
      account_number: "",
      notes: "",
    },
  });

  useEffect(() => {
    const fetchData = async () => {
      const [staffResult, deptResult] = await Promise.all([
        getStaffMember(staffId),
        getDepartments(),
      ]);

      if (deptResult.success && deptResult.data) {
        setDepartments(deptResult.data);
      }

      if (staffResult.success && staffResult.data) {
        const staff = staffResult.data;
        form.reset({
          first_name: staff.first_name,
          middle_name: staff.middle_name || "",
          last_name: staff.last_name,
          date_of_birth: staff.date_of_birth || "",
          gender: staff.gender as "male" | "female",
          email: staff.email,
          phone: staff.phone,
          phone_secondary: staff.phone_secondary || "",
          address: staff.address || "",
          city: staff.city || "",
          region: staff.region || "",
          emergency_contact_name: staff.emergency_contact_name || "",
          emergency_contact_phone: staff.emergency_contact_phone || "",
          emergency_contact_relationship: staff.emergency_contact_relationship || "",
          ghana_card_number: staff.ghana_card_number || "",
          ssnit_number: staff.ssnit_number || "",
          teacher_license_number: staff.teacher_license_number || "",
          staff_type: staff.staff_type as "teaching" | "non_teaching" | "administrative",
          status: staff.status as "active" | "on_leave" | "suspended" | "terminated" | "retired",
          job_title: staff.job_title,
          department: staff.department || "",
          employment_type: staff.employment_type || "",
          employment_date: staff.employment_date,
          termination_date: staff.termination_date || "",
          ges_staff_id: staff.ges_staff_id || "",
          tin_number: staff.tin_number || "",
          nationality: staff.nationality || "",
          marital_status: staff.marital_status || "",
          bank_name: staff.bank_name || "",
          bank_branch: staff.bank_branch || "",
          account_number: staff.account_number || "",
          notes: staff.notes || "",
        });
      } else {
        toast.error("Failed to load staff data");
        router.push("/staff");
      }

      setIsLoading(false);
    };

    fetchData();
  }, [staffId, form, router]);

  const validateCurrentStep = async (): Promise<boolean> => {
    const currentStepFields = steps[currentStep - 1].fields as (keyof StaffFormValues)[];
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
      date_of_birth: data.date_of_birth || undefined,
      phone_secondary: data.phone_secondary || undefined,
      address: data.address || undefined,
      city: data.city || undefined,
      region: data.region || undefined,
      emergency_contact_name: data.emergency_contact_name || undefined,
      emergency_contact_phone: data.emergency_contact_phone || undefined,
      emergency_contact_relationship: data.emergency_contact_relationship || undefined,
      ghana_card_number: data.ghana_card_number || undefined,
      ssnit_number: data.ssnit_number || undefined,
      teacher_license_number: data.teacher_license_number || undefined,
      department: data.department || undefined,
      employment_type: (data.employment_type || undefined) as "full_time" | "part_time" | "contract" | "temporary" | "intern" | undefined,
      termination_date: data.termination_date || undefined,
      ges_staff_id: data.ges_staff_id || undefined,
      tin_number: data.tin_number || undefined,
      nationality: data.nationality || undefined,
      marital_status: data.marital_status || undefined,
      bank_name: data.bank_name || undefined,
      bank_branch: data.bank_branch || undefined,
      account_number: data.account_number || undefined,
      notes: data.notes || undefined,
    };

    const result = await updateStaff(staffId, cleanData);

    if (result.success) {
      toast.success("Staff member updated successfully");
      router.push(`/staff/${staffId}`);
    } else {
      toast.error(result.error || "Failed to update staff member");
    }

    setIsSubmitting(false);
  };

  const formValues = form.watch();

  const getStaffTypeLabel = (type: string) => {
    return STAFF_TYPES.find((t) => t.value === type)?.label || type;
  };

  const getStatusLabel = (status: string) => {
    return STAFF_STATUSES.find((s) => s.value === status)?.label || status;
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Skeleton className="h-10 w-10" />
          <div>
            <Skeleton className="h-8 w-48" />
            <Skeleton className="h-4 w-64 mt-2" />
          </div>
        </div>
        <Card>
          <CardContent className="p-6">
            <div className="flex gap-8">
              <div className="w-48 space-y-4">
                {[1, 2, 3, 4, 5].map((i) => (
                  <Skeleton key={i} className="h-16 w-full" />
                ))}
              </div>
              <div className="flex-1 space-y-4">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href={`/staff/${staffId}`}>
            <ArrowLeft className="h-5 w-5" />
          </Link>
        </Button>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Edit Staff Member</h1>
          <p className="text-muted-foreground">
            Update staff member information
          </p>
        </div>
      </div>

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
                          Basic details about the staff member
                        </p>
                      </div>

                      <div className="grid gap-4 sm:grid-cols-3">
                        <FormField
                          control={form.control}
                          name="first_name"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>First Name *</FormLabel>
                              <FormControl>
                                <Input {...field} />
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
                                <Input {...field} />
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
                                <Input {...field} />
                              </FormControl>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                      </div>

                      <div className="grid gap-4 sm:grid-cols-2">
                        <FormField
                          control={form.control}
                          name="date_of_birth"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>Date of Birth</FormLabel>
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
                                    <SelectValue />
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
                          Contact details and emergency contact
                        </p>
                      </div>

                      <div className="grid gap-4 sm:grid-cols-2">
                        <FormField
                          control={form.control}
                          name="email"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>Email Address *</FormLabel>
                              <FormControl>
                                <Input type="email" {...field} />
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
                              <FormLabel>Phone Number *</FormLabel>
                              <FormControl>
                                <Input {...field} />
                              </FormControl>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                      </div>

                      <FormField
                        control={form.control}
                        name="phone_secondary"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Secondary Phone</FormLabel>
                            <FormControl>
                              <Input {...field} />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

                      <FormField
                        control={form.control}
                        name="address"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Street Address</FormLabel>
                            <FormControl>
                              <Input {...field} />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

                      <div className="grid gap-4 sm:grid-cols-2">
                        <FormField
                          control={form.control}
                          name="city"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>City / Town</FormLabel>
                              <FormControl>
                                <Input {...field} />
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

                      <div className="border-t pt-6">
                        <h4 className="text-sm font-medium mb-4">Emergency Contact</h4>
                        <div className="grid gap-4 sm:grid-cols-3">
                          <FormField
                            control={form.control}
                            name="emergency_contact_name"
                            render={({ field }) => (
                              <FormItem>
                                <FormLabel>Contact Name</FormLabel>
                                <FormControl>
                                  <Input {...field} />
                                </FormControl>
                                <FormMessage />
                              </FormItem>
                            )}
                          />
                          <FormField
                            control={form.control}
                            name="emergency_contact_phone"
                            render={({ field }) => (
                              <FormItem>
                                <FormLabel>Contact Phone</FormLabel>
                                <FormControl>
                                  <Input {...field} />
                                </FormControl>
                                <FormMessage />
                              </FormItem>
                            )}
                          />
                          <FormField
                            control={form.control}
                            name="emergency_contact_relationship"
                            render={({ field }) => (
                              <FormItem>
                                <FormLabel>Relationship</FormLabel>
                                <FormControl>
                                  <Input {...field} />
                                </FormControl>
                                <FormMessage />
                              </FormItem>
                            )}
                          />
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Step 3: Employment Information */}
                  {currentStep === 3 && (
                    <div className="space-y-6">
                      <div>
                        <h3 className="text-lg font-medium">Employment Information</h3>
                        <p className="text-sm text-muted-foreground">
                          Job details and identification numbers
                        </p>
                      </div>

                      <div className="grid gap-4 sm:grid-cols-2">
                        <FormField
                          control={form.control}
                          name="staff_type"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>Staff Type *</FormLabel>
                              <Select onValueChange={field.onChange} value={field.value}>
                                <FormControl>
                                  <SelectTrigger className="w-full">
                                    <SelectValue />
                                  </SelectTrigger>
                                </FormControl>
                                <SelectContent>
                                  {STAFF_TYPES.map((type) => (
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
                          name="status"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>Status *</FormLabel>
                              <Select onValueChange={field.onChange} value={field.value}>
                                <FormControl>
                                  <SelectTrigger className="w-full">
                                    <SelectValue />
                                  </SelectTrigger>
                                </FormControl>
                                <SelectContent>
                                  {STAFF_STATUSES.map((status) => (
                                    <SelectItem key={status.value} value={status.value}>
                                      {status.label}
                                    </SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                      </div>

                      <div className="grid gap-4 sm:grid-cols-2">
                        <FormField
                          control={form.control}
                          name="job_title"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>Job Title *</FormLabel>
                              <FormControl>
                                <Input {...field} />
                              </FormControl>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                        <FormField
                          control={form.control}
                          name="department"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>Department</FormLabel>
                              <Select onValueChange={field.onChange} value={field.value || ""}>
                                <FormControl>
                                  <SelectTrigger className="w-full">
                                    <SelectValue placeholder="Select department" />
                                  </SelectTrigger>
                                </FormControl>
                                <SelectContent>
                                  {departments.map((dept) => (
                                    <SelectItem key={dept.id} value={dept.name}>
                                      {dept.name}
                                    </SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                      </div>

                      {/* Employment Type and Marital Status */}
                      <div className="grid gap-4 sm:grid-cols-2">
                        <FormField
                          control={form.control}
                          name="employment_type"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>Employment Type</FormLabel>
                              <Select onValueChange={field.onChange} value={field.value || ""}>
                                <FormControl>
                                  <SelectTrigger className="w-full">
                                    <SelectValue placeholder="Select employment type" />
                                  </SelectTrigger>
                                </FormControl>
                                <SelectContent>
                                  {EMPLOYMENT_TYPES.map((type) => (
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
                          name="marital_status"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>Marital Status</FormLabel>
                              <Select onValueChange={field.onChange} value={field.value || ""}>
                                <FormControl>
                                  <SelectTrigger className="w-full">
                                    <SelectValue placeholder="Select marital status" />
                                  </SelectTrigger>
                                </FormControl>
                                <SelectContent>
                                  {MARITAL_STATUSES.map((ms) => (
                                    <SelectItem key={ms.value} value={ms.value}>
                                      {ms.label}
                                    </SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                      </div>

                      <div className="grid gap-4 sm:grid-cols-2">
                        <FormField
                          control={form.control}
                          name="employment_date"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>Employment Date *</FormLabel>
                              <FormControl>
                                <Input type="date" {...field} />
                              </FormControl>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                        <FormField
                          control={form.control}
                          name="termination_date"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>Termination Date</FormLabel>
                              <FormControl>
                                <Input type="date" {...field} />
                              </FormControl>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                      </div>

                      {/* GES Staff ID, TIN, Nationality */}
                      <div className="grid gap-4 sm:grid-cols-3">
                        <FormField
                          control={form.control}
                          name="ges_staff_id"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>GES Staff ID</FormLabel>
                              <FormControl>
                                <Input placeholder="GES staff ID (public schools)" {...field} />
                              </FormControl>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                        <FormField
                          control={form.control}
                          name="tin_number"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>TIN Number</FormLabel>
                              <FormControl>
                                <Input placeholder="Tax Identification Number" {...field} />
                              </FormControl>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                        <FormField
                          control={form.control}
                          name="nationality"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>Nationality</FormLabel>
                              <FormControl>
                                <Input placeholder="e.g. Ghanaian" {...field} />
                              </FormControl>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                      </div>

                      <div className="border-t pt-6">
                        <h4 className="text-sm font-medium mb-4">Identification Numbers</h4>
                        <div className="grid gap-4 sm:grid-cols-3">
                          <FormField
                            control={form.control}
                            name="ghana_card_number"
                            render={({ field }) => (
                              <FormItem>
                                <FormLabel>Ghana Card</FormLabel>
                                <FormControl>
                                  <Input placeholder="GHA-XXXXXXXXX-X" {...field} />
                                </FormControl>
                                <FormMessage />
                              </FormItem>
                            )}
                          />
                          <FormField
                            control={form.control}
                            name="ssnit_number"
                            render={({ field }) => (
                              <FormItem>
                                <FormLabel>SSNIT Number</FormLabel>
                                <FormControl>
                                  <Input {...field} />
                                </FormControl>
                                <FormMessage />
                              </FormItem>
                            )}
                          />
                          <FormField
                            control={form.control}
                            name="teacher_license_number"
                            render={({ field }) => (
                              <FormItem>
                                <FormLabel>Teacher License</FormLabel>
                                <FormControl>
                                  <Input placeholder="GES license number" {...field} />
                                </FormControl>
                                <FormMessage />
                              </FormItem>
                            )}
                          />
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Step 4: Banking Information */}
                  {currentStep === 4 && (
                    <div className="space-y-6">
                      <div>
                        <h3 className="text-lg font-medium">Banking & Additional Info</h3>
                        <p className="text-sm text-muted-foreground">
                          Bank details for salary payments (optional)
                        </p>
                      </div>

                      <div className="grid gap-4 sm:grid-cols-3">
                        <FormField
                          control={form.control}
                          name="bank_name"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>Bank Name</FormLabel>
                              <FormControl>
                                <Input {...field} />
                              </FormControl>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                        <FormField
                          control={form.control}
                          name="bank_branch"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>Branch</FormLabel>
                              <FormControl>
                                <Input {...field} />
                              </FormControl>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                        <FormField
                          control={form.control}
                          name="account_number"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>Account Number</FormLabel>
                              <FormControl>
                                <Input {...field} />
                              </FormControl>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                      </div>

                      <FormField
                        control={form.control}
                        name="notes"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Additional Notes</FormLabel>
                            <FormControl>
                              <Textarea rows={4} {...field} />
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
                          Please review all information before saving changes
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
                            <span className="text-muted-foreground">Full Name:</span>{" "}
                            <span className="font-medium">
                              {formValues.first_name} {formValues.middle_name} {formValues.last_name}
                            </span>
                          </div>
                          {formValues.date_of_birth && (
                            <div>
                              <span className="text-muted-foreground">Date of Birth:</span>{" "}
                              <span className="font-medium">{formValues.date_of_birth}</span>
                            </div>
                          )}
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
                          <div>
                            <span className="text-muted-foreground">Email:</span>{" "}
                            <span className="font-medium">{formValues.email}</span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Phone:</span>{" "}
                            <span className="font-medium">{formValues.phone}</span>
                          </div>
                          {formValues.phone_secondary && (
                            <div>
                              <span className="text-muted-foreground">Secondary:</span>{" "}
                              <span className="font-medium">{formValues.phone_secondary}</span>
                            </div>
                          )}
                          {(formValues.address || formValues.city || formValues.region) && (
                            <div className="md:col-span-2">
                              <span className="text-muted-foreground">Address:</span>{" "}
                              <span className="font-medium">
                                {[formValues.address, formValues.city, formValues.region]
                                  .filter(Boolean)
                                  .join(", ")}
                              </span>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Employment Info */}
                      <div className="rounded-lg border p-4 space-y-3">
                        <h4 className="font-medium flex items-center gap-2">
                          <Briefcase className="h-4 w-4" />
                          Employment Information
                        </h4>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                          <div>
                            <span className="text-muted-foreground">Staff Type:</span>{" "}
                            <Badge variant="secondary">{getStaffTypeLabel(formValues.staff_type)}</Badge>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Status:</span>{" "}
                            <Badge variant="outline">{getStatusLabel(formValues.status)}</Badge>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Job Title:</span>{" "}
                            <span className="font-medium">{formValues.job_title}</span>
                          </div>
                          {formValues.department && (
                            <div>
                              <span className="text-muted-foreground">Department:</span>{" "}
                              <span className="font-medium">{formValues.department}</span>
                            </div>
                          )}
                          <div>
                            <span className="text-muted-foreground">Employment Date:</span>{" "}
                            <span className="font-medium">{formValues.employment_date}</span>
                          </div>
                          {formValues.termination_date && (
                            <div>
                              <span className="text-muted-foreground">Termination Date:</span>{" "}
                              <span className="font-medium">{formValues.termination_date}</span>
                            </div>
                          )}
                          {formValues.employment_type && (
                            <div>
                              <span className="text-muted-foreground">Employment Type:</span>{" "}
                              <span className="font-medium capitalize">{formValues.employment_type.replace("_", " ")}</span>
                            </div>
                          )}
                          {formValues.nationality && (
                            <div>
                              <span className="text-muted-foreground">Nationality:</span>{" "}
                              <span className="font-medium">{formValues.nationality}</span>
                            </div>
                          )}
                          {formValues.marital_status && (
                            <div>
                              <span className="text-muted-foreground">Marital Status:</span>{" "}
                              <span className="font-medium capitalize">{formValues.marital_status}</span>
                            </div>
                          )}
                          {formValues.ges_staff_id && (
                            <div>
                              <span className="text-muted-foreground">GES Staff ID:</span>{" "}
                              <span className="font-medium">{formValues.ges_staff_id}</span>
                            </div>
                          )}
                          {formValues.tin_number && (
                            <div>
                              <span className="text-muted-foreground">TIN Number:</span>{" "}
                              <span className="font-medium">{formValues.tin_number}</span>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Banking Info */}
                      {(formValues.bank_name || formValues.account_number) && (
                        <div className="rounded-lg border p-4 space-y-3">
                          <h4 className="font-medium flex items-center gap-2">
                            <CreditCard className="h-4 w-4" />
                            Banking Information
                          </h4>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                            {formValues.bank_name && (
                              <div>
                                <span className="text-muted-foreground">Bank:</span>{" "}
                                <span className="font-medium">{formValues.bank_name}</span>
                              </div>
                            )}
                            {formValues.bank_branch && (
                              <div>
                                <span className="text-muted-foreground">Branch:</span>{" "}
                                <span className="font-medium">{formValues.bank_branch}</span>
                              </div>
                            )}
                            {formValues.account_number && (
                              <div>
                                <span className="text-muted-foreground">Account:</span>{" "}
                                <span className="font-medium font-mono">{formValues.account_number}</span>
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Navigation Buttons */}
                  <div className="flex justify-between pt-6 border-t">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={currentStep === 1 ? () => router.push(`/staff/${staffId}`) : handleBack}
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
                        Save Changes
                      </Button>
                    )}
                  </div>
                </form>
              </Form>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
