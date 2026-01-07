"use client";

import { useState, useEffect } from "react";
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
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { createGuardian, updateGuardian } from "@/actions/students.action";
import type { Guardian } from "@/types";

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

const guardianFormSchema = z.object({
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
  notes: z.string().optional(),
});

type GuardianFormValues = z.infer<typeof guardianFormSchema>;

const steps = [
  { id: 1, title: "Personal", icon: User, fields: ["first_name", "last_name", "ghana_card_number"] },
  { id: 2, title: "Contact", icon: Phone, fields: ["phone", "phone_secondary", "email", "address", "city", "region"] },
  { id: 3, title: "Work", icon: Briefcase, fields: ["occupation", "workplace", "work_phone"] },
  { id: 4, title: "Review", icon: CheckCircle2, fields: [] },
];

interface AddGuardianDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  guardian?: Guardian;
  onSuccess: () => void;
}

export function AddGuardianDialog({
  open,
  onOpenChange,
  guardian,
  onSuccess,
}: AddGuardianDialogProps) {
  const [currentStep, setCurrentStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const isEditing = !!guardian;

  const form = useForm<GuardianFormValues>({
    resolver: zodResolver(guardianFormSchema),
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
      notes: "",
    },
  });

  // Reset form when guardian changes (for edit mode)
  useEffect(() => {
    if (guardian) {
      form.reset({
        first_name: guardian.first_name,
        last_name: guardian.last_name,
        phone: guardian.phone,
        phone_secondary: guardian.phone_secondary || "",
        email: guardian.email || "",
        address: guardian.address || "",
        city: guardian.city || "",
        region: guardian.region || "",
        occupation: guardian.occupation || "",
        workplace: guardian.workplace || "",
        work_phone: guardian.work_phone || "",
        ghana_card_number: guardian.ghana_card_number || "",
        notes: guardian.notes || "",
      });
    } else {
      form.reset({
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
        notes: "",
      });
    }
  }, [guardian, form]);

  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen) {
      form.reset();
      setCurrentStep(1);
    }
    onOpenChange(newOpen);
  };

  const validateCurrentStep = async (): Promise<boolean> => {
    const currentStepFields = steps[currentStep - 1].fields as (keyof GuardianFormValues)[];
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
    // Clean up empty strings
    const cleanData = {
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
      notes: data.notes || undefined,
    };

    let result;
    if (isEditing && guardian) {
      result = await updateGuardian(guardian.id, cleanData);
    } else {
      result = await createGuardian(cleanData);
    }

    if (result.success) {
      toast.success(isEditing ? "Guardian updated successfully" : "Guardian created successfully");
      handleOpenChange(false);
      onSuccess();
    } else {
      toast.error(result.error || `Failed to ${isEditing ? "update" : "create"} guardian`);
    }

    setIsSubmitting(false);
  };

  const formValues = form.watch();

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>{isEditing ? "Edit Guardian" : "Add New Guardian"}</DialogTitle>
          <DialogDescription>
            {isEditing
              ? "Update guardian information."
              : "Enter the guardian details. Required fields are marked with *."}
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
                    className={`h-0.5 w-8 mx-1 mt-[-16px] ${
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
                  name="notes"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Notes</FormLabel>
                      <FormControl>
                        <Textarea rows={2} placeholder="Any additional notes..." {...field} />
                      </FormControl>
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

            {/* Step 4: Review */}
            {currentStep === 4 && (
              <div className="space-y-4">
                <p className="text-sm text-muted-foreground mb-4">
                  Please review the information before {isEditing ? "updating" : "adding"} the guardian.
                </p>

                {/* Personal Info */}
                <div className="rounded-lg border p-3 space-y-2">
                  <h4 className="font-medium text-sm flex items-center gap-2">
                    <User className="h-4 w-4" />
                    Personal Information
                  </h4>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div>
                      <span className="text-muted-foreground">Name:</span>{" "}
                      <span className="font-medium">{formValues.first_name} {formValues.last_name}</span>
                    </div>
                    {formValues.ghana_card_number && (
                      <div>
                        <span className="text-muted-foreground">Ghana Card:</span>{" "}
                        <span className="font-medium">{formValues.ghana_card_number}</span>
                      </div>
                    )}
                    {formValues.notes && (
                      <div className="col-span-2">
                        <span className="text-muted-foreground">Notes:</span>{" "}
                        <span className="font-medium">{formValues.notes}</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Contact Info */}
                <div className="rounded-lg border p-3 space-y-2">
                  <h4 className="font-medium text-sm flex items-center gap-2">
                    <Phone className="h-4 w-4" />
                    Contact Information
                  </h4>
                  <div className="grid grid-cols-2 gap-2 text-sm">
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
                      <div className="col-span-2">
                        <span className="text-muted-foreground">Email:</span>{" "}
                        <span className="font-medium">{formValues.email}</span>
                      </div>
                    )}
                    {(formValues.address || formValues.city || formValues.region) && (
                      <div className="col-span-2">
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
                    <div className="grid grid-cols-2 gap-2 text-sm">
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
                  {isEditing ? "Update Guardian" : "Add Guardian"}
                </Button>
              )}
            </div>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
