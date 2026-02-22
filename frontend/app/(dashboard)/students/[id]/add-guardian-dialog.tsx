"use client";

import { useState } from "react";
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
  Shield,
  CheckCircle2,
  Check,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";

import { addGuardianToStudent } from "@/actions/students.action";
import type { GuardianRelationship } from "@/types";

// Ghana's 16 regions
const ghanaRegions = [
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

const guardianSchema = z.object({
  // Guardian Information
  first_name: z.string().min(1, "First name is required"),
  last_name: z.string().min(1, "Last name is required"),
  phone: z.string().min(10, "Valid phone number is required"),
  phone_secondary: z.string().optional(),
  email: z.string().email("Invalid email").optional().or(z.literal("")),
  address: z.string().optional(),
  city: z.string().optional(),
  region: z.string().optional(),
  occupation: z.string().optional(),
  workplace: z.string().optional(),
  work_phone: z.string().optional(),
  ghana_card_number: z.string().optional(),

  // Relationship Information
  relationship: z.enum([
    "father",
    "mother",
    "guardian",
    "grandfather",
    "grandmother",
    "uncle",
    "aunt",
    "sibling",
    "other",
  ]),
  is_primary: z.boolean(),
  is_emergency_contact: z.boolean(),
  can_pickup: z.boolean(),
});

type GuardianFormData = z.infer<typeof guardianSchema>;

const relationshipOptions: { value: GuardianRelationship; label: string }[] = [
  { value: "father", label: "Father" },
  { value: "mother", label: "Mother" },
  { value: "guardian", label: "Guardian" },
  { value: "grandfather", label: "Grandfather" },
  { value: "grandmother", label: "Grandmother" },
  { value: "uncle", label: "Uncle" },
  { value: "aunt", label: "Aunt" },
  { value: "sibling", label: "Sibling" },
  { value: "other", label: "Other" },
];

const steps = [
  { id: 1, title: "Personal", icon: User, fields: ["first_name", "last_name", "relationship"] },
  { id: 2, title: "Contact", icon: Phone, fields: ["phone", "phone_secondary", "email", "address", "city", "region"] },
  { id: 3, title: "Work", icon: Briefcase, fields: ["occupation", "workplace", "work_phone"] },
  { id: 4, title: "Permissions", icon: Shield, fields: ["is_primary", "is_emergency_contact", "can_pickup"] },
  { id: 5, title: "Review", icon: CheckCircle2, fields: [] },
];

interface AddGuardianDialogProps {
  studentId: string;
  studentName: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

export function AddGuardianDialog({
  studentId,
  studentName,
  open,
  onOpenChange,
  onSuccess,
}: AddGuardianDialogProps) {
  const [currentStep, setCurrentStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const form = useForm<GuardianFormData>({
    resolver: zodResolver(guardianSchema),
    defaultValues: {
      first_name: "",
      last_name: "",
      phone: "",
      phone_secondary: "",
      email: "",
      address: "",
      city: "",
      region: "",
      occupation: "",
      workplace: "",
      work_phone: "",
      ghana_card_number: "",
      relationship: "guardian",
      is_primary: false,
      is_emergency_contact: true,
      can_pickup: true,
    },
  });

  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen) {
      form.reset();
      setCurrentStep(1);
    }
    onOpenChange(newOpen);
  };

  const validateCurrentStep = async (): Promise<boolean> => {
    const currentStepFields = steps[currentStep - 1].fields as (keyof GuardianFormData)[];
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
    // Validate all fields before submitting
    const isValid = await form.trigger();
    if (!isValid) {
      toast.error("Please fix the errors before submitting");
      return;
    }

    setIsSubmitting(true);

    const data = form.getValues();
    const result = await addGuardianToStudent(studentId, {
      guardian: {
        first_name: data.first_name,
        last_name: data.last_name,
        phone: data.phone,
        phone_secondary: data.phone_secondary || undefined,
        email: data.email || undefined,
        address: data.address || undefined,
        city: data.city || undefined,
        region: data.region || undefined,
        occupation: data.occupation || undefined,
        workplace: data.workplace || undefined,
        work_phone: data.work_phone || undefined,
        ghana_card_number: data.ghana_card_number || undefined,
      },
      relationship: data.relationship,
      is_primary: data.is_primary,
      is_emergency_contact: data.is_emergency_contact,
      can_pickup: data.can_pickup,
    });

    if (result.success) {
      toast.success("Guardian added successfully");
      handleOpenChange(false);
      onSuccess();
    } else {
      toast.error(result.error || "Failed to add guardian");
    }

    setIsSubmitting(false);
  };

  const getRelationshipLabel = (value: string) => {
    return relationshipOptions.find((opt) => opt.value === value)?.label || value;
  };

  const formValues = form.watch();

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Add Guardian</DialogTitle>
          <DialogDescription>
            Add a new guardian for {studentName}
          </DialogDescription>
        </DialogHeader>

        {/* Step Indicator */}
        <div className="flex items-center justify-between mb-2">
          {steps.map((step, index) => {
            const StepIcon = step.icon;
            const isActive = currentStep === step.id;
            const isCompleted = currentStep > step.id;

            return (
              <div key={step.id} className="flex items-center">
                <div className="flex flex-col items-center">
                  <div
                    className={`flex h-8 w-8 items-center justify-center rounded-full border-2 transition-colors ${
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
                  <span
                    className={`mt-1 text-xs ${
                      isActive ? "text-primary font-medium" : "text-muted-foreground"
                    }`}
                  >
                    {step.title}
                  </span>
                </div>
                {index < steps.length - 1 && (
                  <div
                    className={`h-0.5 w-6 mx-1 mt-[-16px] ${
                      currentStep > step.id ? "bg-primary" : "bg-muted-foreground/30"
                    }`}
                  />
                )}
              </div>
            );
          })}
        </div>

        <Form {...form}>
          <form
            onSubmit={(e) => e.preventDefault()}
            onKeyDown={(e) => {
              // Prevent Enter from submitting form
              if (e.key === "Enter") {
                e.preventDefault();
              }
            }}
            className="space-y-4"
          >
            {/* Step 1: Personal Information */}
            {currentStep === 1 && (
              <div className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <FormField
                    control={form.control}
                    name="first_name"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>First Name *</FormLabel>
                        <FormControl>
                          <Input {...field} placeholder="Enter first name" />
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
                          <Input {...field} placeholder="Enter last name" />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>

                <FormField
                  control={form.control}
                  name="relationship"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Relationship to Student *</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder="Select relationship" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {relationshipOptions.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                              {option.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
            )}

            {/* Step 2: Contact Information */}
            {currentStep === 2 && (
              <div className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <FormField
                    control={form.control}
                    name="phone"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Phone Number *</FormLabel>
                        <FormControl>
                          <Input {...field} placeholder="+233 XX XXX XXXX" />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="phone_secondary"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Secondary Phone</FormLabel>
                        <FormControl>
                          <Input {...field} placeholder="Optional" />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>

                <FormField
                  control={form.control}
                  name="email"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Email Address</FormLabel>
                      <FormControl>
                        <Input {...field} type="email" placeholder="Optional" />
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
                      <FormLabel>Address</FormLabel>
                      <FormControl>
                        <Input {...field} placeholder="Street address" />
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
                        <FormLabel>City</FormLabel>
                        <FormControl>
                          <Input {...field} placeholder="City" />
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
                            {ghanaRegions.map((region) => (
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

            {/* Step 3: Work Information */}
            {currentStep === 3 && (
              <div className="space-y-4">
                <p className="text-sm text-muted-foreground">
                  Work information is optional but helpful for emergency contact purposes.
                </p>

                <div className="grid gap-4 sm:grid-cols-2">
                  <FormField
                    control={form.control}
                    name="occupation"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Occupation</FormLabel>
                        <FormControl>
                          <Input {...field} placeholder="e.g., Teacher, Engineer" />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="workplace"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Workplace</FormLabel>
                        <FormControl>
                          <Input {...field} placeholder="Company/Organization" />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>

                <FormField
                  control={form.control}
                  name="work_phone"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Work Phone</FormLabel>
                      <FormControl>
                        <Input {...field} placeholder="Office phone number" />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
            )}

            {/* Step 4: Permissions */}
            {currentStep === 4 && (
              <div className="space-y-4">
                <FormField
                  control={form.control}
                  name="is_primary"
                  render={({ field }) => (
                    <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3">
                      <div className="space-y-0.5">
                        <FormLabel className="text-base">Primary Guardian</FormLabel>
                        <FormDescription>
                          Main contact for school communications
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
                  name="is_emergency_contact"
                  render={({ field }) => (
                    <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3">
                      <div className="space-y-0.5">
                        <FormLabel className="text-base">Emergency Contact</FormLabel>
                        <FormDescription>
                          Can be contacted in case of emergency
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
                  name="can_pickup"
                  render={({ field }) => (
                    <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3">
                      <div className="space-y-0.5">
                        <FormLabel className="text-base">Authorized Pickup</FormLabel>
                        <FormDescription>
                          Allowed to pick up student from school
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

            {/* Step 5: Review */}
            {currentStep === 5 && (
              <div className="space-y-4">
                <p className="text-sm text-muted-foreground mb-4">
                  Please review the information before adding the guardian.
                </p>

                {/* Personal Info */}
                <div className="rounded-lg border p-3 space-y-2">
                  <h4 className="font-medium text-sm flex items-center gap-2">
                    <User className="h-4 w-4" />
                    Personal Information
                  </h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
                    <div>
                      <span className="text-muted-foreground">Name:</span>{" "}
                      <span className="font-medium">{formValues.first_name} {formValues.last_name}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Relationship:</span>{" "}
                      <span className="font-medium">{getRelationshipLabel(formValues.relationship)}</span>
                    </div>
                  </div>
                </div>

                {/* Contact Info */}
                <div className="rounded-lg border p-3 space-y-2">
                  <h4 className="font-medium text-sm flex items-center gap-2">
                    <Phone className="h-4 w-4" />
                    Contact Information
                  </h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
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
                    {formValues.email && (
                      <div className="md:col-span-2">
                        <span className="text-muted-foreground">Email:</span>{" "}
                        <span className="font-medium">{formValues.email}</span>
                      </div>
                    )}
                    {(formValues.address || formValues.city || formValues.region) && (
                      <div className="md:col-span-2">
                        <span className="text-muted-foreground">Address:</span>{" "}
                        <span className="font-medium">
                          {[formValues.address, formValues.city, formValues.region].filter(Boolean).join(", ")}
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Work Info */}
                {(formValues.occupation || formValues.workplace || formValues.work_phone) && (
                  <div className="rounded-lg border p-3 space-y-2">
                    <h4 className="font-medium text-sm flex items-center gap-2">
                      <Briefcase className="h-4 w-4" />
                      Work Information
                    </h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
                      {formValues.occupation && (
                        <div>
                          <span className="text-muted-foreground">Occupation:</span>{" "}
                          <span className="font-medium">{formValues.occupation}</span>
                        </div>
                      )}
                      {formValues.workplace && (
                        <div>
                          <span className="text-muted-foreground">Workplace:</span>{" "}
                          <span className="font-medium">{formValues.workplace}</span>
                        </div>
                      )}
                      {formValues.work_phone && (
                        <div>
                          <span className="text-muted-foreground">Work Phone:</span>{" "}
                          <span className="font-medium">{formValues.work_phone}</span>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Permissions */}
                <div className="rounded-lg border p-3 space-y-2">
                  <h4 className="font-medium text-sm flex items-center gap-2">
                    <Shield className="h-4 w-4" />
                    Permissions
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {formValues.is_primary && (
                      <Badge variant="default">Primary Guardian</Badge>
                    )}
                    {formValues.is_emergency_contact && (
                      <Badge variant="secondary">Emergency Contact</Badge>
                    )}
                    {formValues.can_pickup && (
                      <Badge variant="outline">Can Pick Up</Badge>
                    )}
                    {!formValues.is_primary && !formValues.is_emergency_contact && !formValues.can_pickup && (
                      <span className="text-sm text-muted-foreground">No special permissions</span>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Navigation Buttons */}
            <div className="flex justify-between pt-4 border-t">
              <Button
                type="button"
                variant="outline"
                onClick={currentStep === 1 ? () => handleOpenChange(false) : handleBack}
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
                  Add Guardian
                </Button>
              )}
            </div>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
