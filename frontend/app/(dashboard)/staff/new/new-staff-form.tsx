"use client";

import { useState } from "react";
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
  Briefcase,
  CreditCard,
  CheckCircle2,
  Check,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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
import { Badge } from "@/components/ui/badge";

import { createStaff } from "@/actions/staff.action";

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

const STAFF_TYPES = [
  { value: "teaching", label: "Teaching Staff" },
  { value: "non_teaching", label: "Non-Teaching Staff" },
  { value: "administrative", label: "Administrative Staff" },
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
  job_title: z.string().min(1, "Job title is required"),
  department: z.string().optional(),
  employment_date: z.string().min(1, "Employment date is required"),
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
    fields: ["staff_type", "job_title", "department", "employment_date", "ghana_card_number", "ssnit_number", "teacher_license_number"],
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

export function NewStaffForm() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);

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
      job_title: "",
      department: "",
      employment_date: "",
      bank_name: "",
      bank_branch: "",
      account_number: "",
      notes: "",
    },
  });

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
      bank_name: data.bank_name || undefined,
      bank_branch: data.bank_branch || undefined,
      account_number: data.account_number || undefined,
      notes: data.notes || undefined,
    };

    const result = await createStaff(cleanData);

    if (result.success) {
      toast.success(`Staff member created successfully (ID: ${result.data?.staff_id})`);
      router.push(`/staff/${result.data?.id}`);
    } else {
      toast.error(result.error || "Failed to create staff member");
    }

    setIsSubmitting(false);
  };

  const formValues = form.watch();

  const getStaffTypeLabel = (type: string) => {
    return STAFF_TYPES.find((t) => t.value === type)?.label || type;
  };

  return (
    <Card>
      <CardContent className="p-6">
        <div className="flex gap-8">
          {/* Left Side - Step Indicator */}
          <div className="w-48 shrink-0">
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
                        Contact details and emergency contact
                      </p>
                    </div>

                    {/* Email and Phone */}
                    <div className="grid gap-4 sm:grid-cols-2">
                      <FormField
                        control={form.control}
                        name="email"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Email Address *</FormLabel>
                            <FormControl>
                              <Input type="email" placeholder="staff@email.com" {...field} />
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
                              <Input placeholder="+233 XX XXX XXXX" {...field} />
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
                            <Input placeholder="+233 XX XXX XXXX" {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

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

                    {/* Emergency Contact */}
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
                                <Input placeholder="Full name" {...field} />
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
                                <Input placeholder="+233 XX XXX XXXX" {...field} />
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
                                <Input placeholder="e.g. Spouse, Parent" {...field} />
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

                    {/* Staff Type and Job Title */}
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
                                  <SelectValue placeholder="Select type" />
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
                        name="job_title"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Job Title *</FormLabel>
                            <FormControl>
                              <Input placeholder="e.g. Mathematics Teacher" {...field} />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    </div>

                    {/* Department and Employment Date */}
                    <div className="grid gap-4 sm:grid-cols-2">
                      <FormField
                        control={form.control}
                        name="department"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Department</FormLabel>
                            <FormControl>
                              <Input placeholder="e.g. Science Department" {...field} />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

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
                    </div>

                    {/* IDs */}
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
                                <Input {...field} />
                              </FormControl>
                              <FormDescription>GES license number</FormDescription>
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

                    {/* Bank Details */}
                    <div className="grid gap-4 sm:grid-cols-3">
                      <FormField
                        control={form.control}
                        name="bank_name"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Bank Name</FormLabel>
                            <FormControl>
                              <Input placeholder="e.g. GCB Bank" {...field} />
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
                              <Input placeholder="e.g. Accra Main" {...field} />
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
                              rows={4}
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
                        Please review all information before creating the staff record
                      </p>
                    </div>

                    {/* Personal Info */}
                    <div className="rounded-lg border p-4 space-y-3">
                      <h4 className="font-medium flex items-center gap-2">
                        <User className="h-4 w-4" />
                        Personal Information
                      </h4>
                      <div className="grid grid-cols-2 gap-3 text-sm">
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
                      <div className="grid grid-cols-2 gap-3 text-sm">
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
                          <div className="col-span-2">
                            <span className="text-muted-foreground">Address:</span>{" "}
                            <span className="font-medium">
                              {[formValues.address, formValues.city, formValues.region]
                                .filter(Boolean)
                                .join(", ")}
                            </span>
                          </div>
                        )}
                        {formValues.emergency_contact_name && (
                          <div className="col-span-2">
                            <span className="text-muted-foreground">Emergency Contact:</span>{" "}
                            <span className="font-medium">
                              {formValues.emergency_contact_name}
                              {formValues.emergency_contact_phone && ` (${formValues.emergency_contact_phone})`}
                              {formValues.emergency_contact_relationship && ` - ${formValues.emergency_contact_relationship}`}
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
                      <div className="grid grid-cols-2 gap-3 text-sm">
                        <div>
                          <span className="text-muted-foreground">Staff Type:</span>{" "}
                          <Badge variant="secondary">{getStaffTypeLabel(formValues.staff_type)}</Badge>
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
                        {formValues.ghana_card_number && (
                          <div>
                            <span className="text-muted-foreground">Ghana Card:</span>{" "}
                            <span className="font-medium font-mono">{formValues.ghana_card_number}</span>
                          </div>
                        )}
                        {formValues.ssnit_number && (
                          <div>
                            <span className="text-muted-foreground">SSNIT:</span>{" "}
                            <span className="font-medium">{formValues.ssnit_number}</span>
                          </div>
                        )}
                        {formValues.teacher_license_number && (
                          <div>
                            <span className="text-muted-foreground">Teacher License:</span>{" "}
                            <span className="font-medium">{formValues.teacher_license_number}</span>
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
                        <div className="grid grid-cols-2 gap-3 text-sm">
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
                    onClick={currentStep === 1 ? () => router.push("/staff") : handleBack}
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
                      Create Staff Member
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
