"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
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
import { register } from "@/actions/auth.action";
import { toast } from "sonner";
import {
  Check,
  X,
  Loader2,
  GraduationCap,
  Globe,
  ArrowLeft,
  ArrowRight,
  Eye,
  EyeOff,
  School,
  Building2,
  UserCog,
  ClipboardCheck,
  Pencil,
} from "lucide-react";

// Reserved subdomains that cannot be used
const RESERVED_SUBDOMAINS = [
  "www",
  "app",
  "api",
  "admin",
  "mail",
  "ftp",
  "status",
  "blog",
  "help",
  "support",
  "docs",
  "cdn",
  "assets",
  "staging",
  "dev",
  "test",
  "demo",
  "sandbox",
];

// School types
const SCHOOL_TYPES = [
  { value: "preschool", label: "Preschool Only" },
  { value: "primary", label: "Primary School" },
  { value: "preschool_primary", label: "Preschool + Primary" },
  { value: "jhs", label: "Junior High School (JHS)" },
  { value: "shs", label: "Senior High School (SHS)" },
  { value: "basic", label: "Basic School (Primary + JHS)" },
  { value: "basic_preschool", label: "Basic School (Preschool to JHS)" },
  { value: "basic_shs", label: "Basic + SHS (Preschool to SHS)" },
  { value: "international", label: "International School" },
  { value: "technical", label: "Technical/Vocational" },
];

// Subscription plans
const PLANS = {
  trial: { name: "Trial", price: "Free", period: "30 days" },
  starter: { name: "Starter", price: "GHS 500", period: "/month" },
  professional: { name: "Professional", price: "GHS 1,500", period: "/month" },
  enterprise: { name: "Enterprise", price: "Custom", period: "" },
};

// Password requirements for live checklist
const passwordRequirements = [
  { regex: /.{8,}/, label: "At least 8 characters" },
  { regex: /[A-Z]/, label: "One uppercase letter" },
  { regex: /[a-z]/, label: "One lowercase letter" },
  { regex: /\d/, label: "One number" },
  { regex: /[!@#$%^&*(),.?":{}|<>]/, label: "One special character" },
];

// Wizard step definitions
const STEPS = [
  { number: 1, label: "School Info", icon: School },
  { number: 2, label: "Admin Account", icon: UserCog },
  { number: 3, label: "Review", icon: ClipboardCheck },
] as const;

// Step 1 field names
const STEP_1_FIELDS = [
  "tenant_type",
  "school_name",
  "subdomain",
  "school_type",
] as const;

// Step 2 field names
const STEP_2_FIELDS = [
  "first_name",
  "last_name",
  "email",
  "password",
  "confirm_password",
] as const;

type SubdomainStatus = "idle" | "checking" | "available" | "taken" | "invalid";

// Zod schema for the full registration form
const registerSchema = z
  .object({
    // Step 1
    tenant_type: z.enum(["single_school", "school_chain"]),
    school_name: z.string().min(2, "School name is required").max(255),
    subdomain: z
      .string()
      .min(4, "Subdomain must be at least 4 characters")
      .max(63)
      .regex(
        /^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]+$/,
        "Only lowercase letters, numbers, and hyphens"
      ),
    school_type: z.string().min(1, "Please select a school type"),
    phone: z.string().optional(),
    // Step 2
    first_name: z.string().min(1, "First name is required"),
    last_name: z.string().min(1, "Last name is required"),
    email: z.string().email("Please enter a valid email"),
    password: z
      .string()
      .min(8, "Password must be at least 8 characters")
      .regex(/[A-Z]/, "Must contain an uppercase letter")
      .regex(/[a-z]/, "Must contain a lowercase letter")
      .regex(/\d/, "Must contain a number")
      .regex(/[!@#$%^&*(),.?":{}|<>]/, "Must contain a special character"),
    confirm_password: z.string(),
  })
  .refine((data) => data.password === data.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  });

type RegisterFormValues = z.infer<typeof registerSchema>;

export default function RegisterPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const selectedPlan = searchParams.get("plan") || "trial";

  const [step, setStep] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [subdomainStatus, setSubdomainStatus] =
    useState<SubdomainStatus>("idle");
  const [subdomainError, setSubdomainError] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const form = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      tenant_type: "single_school",
      school_name: "",
      subdomain: "",
      school_type: "",
      phone: "",
      first_name: "",
      last_name: "",
      email: "",
      password: "",
      confirm_password: "",
    },
    mode: "onTouched",
  });

  const watchedPassword = form.watch("password");
  const watchedSubdomain = form.watch("subdomain");
  const watchedSchoolName = form.watch("school_name");

  // Generate subdomain from school name
  const generateSubdomain = useCallback((name: string): string => {
    return name
      .toLowerCase()
      .replace(/[^a-z0-9\s-]/g, "")
      .replace(/\s+/g, "")
      .replace(/-+/g, "-")
      .replace(/^-|-$/g, "")
      .substring(0, 20);
  }, []);

  // Validate subdomain format
  const validateSubdomain = useCallback((value: string): boolean => {
    const regex = /^[a-z0-9][a-z0-9-]{2,61}[a-z0-9]$/;
    return regex.test(value) || (value.length >= 4 && /^[a-z0-9]+$/.test(value));
  }, []);

  // Check subdomain availability via API
  const checkSubdomainAvailability = useCallback(
    async (value: string): Promise<{ available: boolean; reason?: string }> => {
      const apiUrl =
        process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

      try {
        const response = await fetch(
          `${apiUrl}/tenant/check-subdomain?subdomain=${encodeURIComponent(value)}`,
          {
            method: "GET",
            headers: {
              "Content-Type": "application/json",
            },
          }
        );

        if (!response.ok) {
          return { available: false, reason: "Failed to check availability" };
        }

        const data = await response.json();
        return {
          available: data.available,
          reason: data.reason || undefined,
        };
      } catch (error) {
        console.error("Subdomain check failed:", error);
        if (RESERVED_SUBDOMAINS.includes(value)) {
          return { available: false, reason: "This subdomain is reserved" };
        }
        // Safe default: treat as unavailable when we cannot verify
        return { available: false, reason: "Unable to verify availability. Please try again." };
      }
    },
    []
  );

  // Auto-generate subdomain from school name
  useEffect(() => {
    if (watchedSchoolName) {
      const generated = generateSubdomain(watchedSchoolName);
      form.setValue("subdomain", generated, { shouldValidate: true });
    }
  }, [watchedSchoolName, generateSubdomain, form]);

  // Validate and check subdomain availability when it changes
  useEffect(() => {
    if (!watchedSubdomain || watchedSubdomain.length < 4) {
      setSubdomainStatus("idle");
      setSubdomainError("");
      return;
    }

    if (!validateSubdomain(watchedSubdomain)) {
      setSubdomainStatus("invalid");
      setSubdomainError(
        "Only lowercase letters, numbers, and hyphens allowed (min 4 characters)"
      );
      return;
    }

    if (RESERVED_SUBDOMAINS.includes(watchedSubdomain)) {
      setSubdomainStatus("taken");
      setSubdomainError("This subdomain is reserved");
      return;
    }

    setSubdomainStatus("checking");
    setSubdomainError("");

    const timeoutId = setTimeout(async () => {
      const result = await checkSubdomainAvailability(watchedSubdomain);
      if (result.available) {
        setSubdomainStatus("available");
        setSubdomainError("");
      } else {
        setSubdomainStatus("taken");
        setSubdomainError(result.reason || "This subdomain is already taken");
      }
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [watchedSubdomain, validateSubdomain, checkSubdomainAvailability]);

  // Navigate to the next step after validating current step fields
  async function handleNext() {
    if (step === 1) {
      const valid = await form.trigger(
        STEP_1_FIELDS as unknown as (keyof RegisterFormValues)[]
      );
      if (!valid) return;
      if (subdomainStatus !== "available") {
        toast.error("Please choose a valid, available subdomain");
        return;
      }
      setStep(2);
    } else if (step === 2) {
      const valid = await form.trigger(
        STEP_2_FIELDS as unknown as (keyof RegisterFormValues)[]
      );
      if (!valid) return;
      setStep(3);
    }
  }

  function handleBack() {
    if (step > 1) {
      setStep(step - 1);
    }
  }

  function goToStep(targetStep: number) {
    setStep(targetStep);
  }

  async function onSubmit(values: RegisterFormValues) {
    if (subdomainStatus !== "available") {
      toast.error("Please choose a valid subdomain");
      return;
    }

    setIsLoading(true);

    const result = await register({
      school_name: values.school_name,
      subdomain: values.subdomain,
      school_type: values.school_type,
      admin_first_name: values.first_name,
      admin_last_name: values.last_name,
      admin_email: values.email,
      admin_phone: values.phone || "",
      admin_password: values.password,
      tenant_type: values.tenant_type,
      plan: selectedPlan,
    });

    setIsLoading(false);

    if (result.success) {
      toast.success("School registered successfully!");
      router.push(`/register/success?school=${values.subdomain}`);
    } else {
      // Handle specific error codes
      if (result.code === 409) {
        setSubdomainStatus("taken");
        setSubdomainError("This subdomain is already taken");
        setStep(1);
        toast.error("This subdomain is already taken. Please choose another.");
      } else {
        toast.error(result.error || "Registration failed");
      }
    }
  }

  const plan = PLANS[selectedPlan as keyof typeof PLANS] || PLANS.trial;

  // Helper to get the school type label from value
  function getSchoolTypeLabel(value: string): string {
    return SCHOOL_TYPES.find((t) => t.value === value)?.label || value;
  }

  return (
    <main className="min-h-screen bg-muted py-8">
      <div className="container mx-auto px-4">
        <div className="mx-auto max-w-2xl">
          {/* Back Link */}
          <Link
            href="/"
            className="mb-6 inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to home
          </Link>

          {/* Header */}
          <div className="mb-8 text-center">
            <div className="mb-4 flex justify-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-primary">
                <GraduationCap className="h-8 w-8 text-primary-foreground" />
              </div>
            </div>
            <h1 className="text-3xl font-bold text-foreground">
              Register Your School
            </h1>
            <p className="mt-2 text-muted-foreground">
              Get started with SIMS Plus in minutes
            </p>

            {/* Selected Plan Badge */}
            <Badge variant="secondary" className="mt-4">
              {plan.name} Plan &bull; {plan.price}
              {plan.period}
            </Badge>
          </div>

          {/* Step Progress Indicator */}
          <div className="mb-8">
            <div className="flex items-center justify-between">
              {STEPS.map((s, index) => {
                const StepIcon = s.icon;
                const isCompleted = step > s.number;
                const isCurrent = step === s.number;

                return (
                  <div key={s.number} className="flex flex-1 items-center">
                    {/* Step circle and label */}
                    <div className="flex flex-col items-center">
                      <div
                        className={`flex h-10 w-10 items-center justify-center rounded-full border-2 transition-colors ${
                          isCompleted
                            ? "border-primary bg-primary text-primary-foreground"
                            : isCurrent
                              ? "border-primary bg-background text-primary"
                              : "border-muted-foreground/30 bg-background text-muted-foreground/50"
                        }`}
                      >
                        {isCompleted ? (
                          <Check className="h-5 w-5" />
                        ) : (
                          <StepIcon className="h-5 w-5" />
                        )}
                      </div>
                      <span
                        className={`mt-2 text-xs font-medium ${
                          isCurrent
                            ? "text-primary"
                            : isCompleted
                              ? "text-foreground"
                              : "text-muted-foreground/50"
                        }`}
                      >
                        {s.label}
                      </span>
                    </div>

                    {/* Connector line between steps */}
                    {index < STEPS.length - 1 && (
                      <div className="mx-2 mt-[-1.25rem] h-0.5 flex-1">
                        <div
                          className={`h-full transition-colors ${
                            step > s.number
                              ? "bg-primary"
                              : "bg-muted-foreground/20"
                          }`}
                        />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Registration Form Card */}
          <Card>
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)}>
                {/* Step 1: School Information */}
                {step === 1 && (
                  <>
                    <CardHeader>
                      <CardTitle>School Information</CardTitle>
                      <CardDescription>
                        Tell us about your school to set up your portal
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      {/* Account Type Selector */}
                      <FormField
                        control={form.control}
                        name="tenant_type"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Account Type *</FormLabel>
                            <div className="grid grid-cols-2 gap-3">
                              <button
                                type="button"
                                onClick={() => field.onChange("single_school")}
                                className={`rounded-lg border-2 p-4 text-center transition-colors ${
                                  field.value === "single_school"
                                    ? "border-primary bg-primary/5"
                                    : "border-muted hover:border-muted-foreground/50"
                                }`}
                              >
                                <School className="mx-auto mb-2 size-6" />
                                <div className="text-sm font-medium">
                                  Single School
                                </div>
                                <div className="text-xs text-muted-foreground">
                                  One school, one location
                                </div>
                              </button>
                              <button
                                type="button"
                                onClick={() => field.onChange("school_chain")}
                                className={`rounded-lg border-2 p-4 text-center transition-colors ${
                                  field.value === "school_chain"
                                    ? "border-primary bg-primary/5"
                                    : "border-muted hover:border-muted-foreground/50"
                                }`}
                              >
                                <Building2 className="mx-auto mb-2 size-6" />
                                <div className="text-sm font-medium">
                                  School Chain
                                </div>
                                <div className="text-xs text-muted-foreground">
                                  Multiple schools, one management
                                </div>
                              </button>
                            </div>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

                      <FormField
                        control={form.control}
                        name="school_name"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>
                              {form.watch("tenant_type") === "school_chain"
                                ? "Organization Name *"
                                : "School Name *"}
                            </FormLabel>
                            <FormControl>
                              <Input
                                placeholder={
                                  form.watch("tenant_type") === "school_chain"
                                    ? "e.g., Bright Future Education Group"
                                    : "e.g., Bright Future Academy"
                                }
                                {...field}
                              />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

                      <FormField
                        control={form.control}
                        name="school_type"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>School Type *</FormLabel>
                            <Select
                              onValueChange={field.onChange}
                              value={field.value}
                            >
                              <FormControl>
                                <SelectTrigger>
                                  <SelectValue placeholder="Select school type" />
                                </SelectTrigger>
                              </FormControl>
                              <SelectContent>
                                {SCHOOL_TYPES.map((type) => (
                                  <SelectItem
                                    key={type.value}
                                    value={type.value}
                                  >
                                    {type.label}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

                      {/* Subdomain Selection */}
                      <FormField
                        control={form.control}
                        name="subdomain"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>
                              Choose Your School&apos;s Web Address *
                            </FormLabel>
                            <div className="flex items-center gap-2">
                              <div className="relative flex-1">
                                <FormControl>
                                  <Input
                                    placeholder="yourschool"
                                    {...field}
                                    onChange={(e) =>
                                      field.onChange(
                                        e.target.value.toLowerCase()
                                      )
                                    }
                                    className={`pr-10 ${
                                      subdomainStatus === "available"
                                        ? "border-green-500 focus-visible:ring-green-500"
                                        : subdomainStatus === "taken" ||
                                            subdomainStatus === "invalid"
                                          ? "border-red-500 focus-visible:ring-red-500"
                                          : ""
                                    }`}
                                  />
                                </FormControl>
                                <div className="absolute right-3 top-1/2 -translate-y-1/2">
                                  {subdomainStatus === "checking" && (
                                    <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                                  )}
                                  {subdomainStatus === "available" && (
                                    <Check className="h-4 w-4 text-green-500" />
                                  )}
                                  {(subdomainStatus === "taken" ||
                                    subdomainStatus === "invalid") && (
                                    <X className="h-4 w-4 text-red-500" />
                                  )}
                                </div>
                              </div>
                              <span className="whitespace-nowrap text-sm text-muted-foreground">
                                .simsplus.io
                              </span>
                            </div>

                            {/* Subdomain Status Message */}
                            {subdomainStatus === "available" &&
                              watchedSubdomain && (
                                <p className="flex items-center gap-2 text-sm text-green-600">
                                  <Check className="h-3 w-3" />
                                  {watchedSubdomain}.simsplus.io is available!
                                </p>
                              )}
                            {subdomainError && (
                              <p className="flex items-center gap-2 text-sm text-red-600">
                                <X className="h-3 w-3" />
                                {subdomainError}
                              </p>
                            )}

                            {/* URL Preview */}
                            {watchedSubdomain &&
                              subdomainStatus === "available" && (
                                <div className="mt-3 rounded-lg border bg-muted/50 p-3">
                                  <div className="flex items-center gap-2 text-sm">
                                    <Globe className="h-4 w-4 text-primary" />
                                    <span className="font-medium">
                                      Your school portal will be:
                                    </span>
                                  </div>
                                  <code className="mt-1 block text-lg font-semibold text-primary">
                                    https://{watchedSubdomain}.simsplus.io
                                  </code>
                                </div>
                              )}

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
                              <Input
                                type="tel"
                                placeholder="+233 24 123 4567"
                                {...field}
                              />
                            </FormControl>
                            <FormDescription>
                              School or administrator contact number
                            </FormDescription>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

                      {/* Step 1 Navigation */}
                      <div className="flex justify-end pt-4">
                        <Button
                          type="button"
                          onClick={handleNext}
                          className="min-w-[120px]"
                        >
                          Next
                          <ArrowRight className="ml-2 h-4 w-4" />
                        </Button>
                      </div>
                    </CardContent>
                  </>
                )}

                {/* Step 2: Admin Account */}
                {step === 2 && (
                  <>
                    <CardHeader>
                      <CardTitle>Administrator Account</CardTitle>
                      <CardDescription>
                        Set up the school admin login credentials
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="grid gap-4 sm:grid-cols-2">
                        <FormField
                          control={form.control}
                          name="first_name"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>First Name *</FormLabel>
                              <FormControl>
                                <Input placeholder="Kwame" {...field} />
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
                                <Input placeholder="Asante" {...field} />
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
                            <FormLabel>Email Address *</FormLabel>
                            <FormControl>
                              <Input
                                type="email"
                                placeholder="admin@school.edu.gh"
                                {...field}
                              />
                            </FormControl>
                            <FormDescription>
                              Login credentials will be sent to this email
                            </FormDescription>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

                      <FormField
                        control={form.control}
                        name="password"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Password *</FormLabel>
                            <div className="relative">
                              <FormControl>
                                <Input
                                  type={showPassword ? "text" : "password"}
                                  placeholder="Create a strong password"
                                  autoComplete="new-password"
                                  className="pr-10"
                                  {...field}
                                />
                              </FormControl>
                              <button
                                type="button"
                                onClick={() => setShowPassword(!showPassword)}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                                aria-label={
                                  showPassword
                                    ? "Hide password"
                                    : "Show password"
                                }
                              >
                                {showPassword ? (
                                  <EyeOff className="h-4 w-4" />
                                ) : (
                                  <Eye className="h-4 w-4" />
                                )}
                              </button>
                            </div>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

                      {/* Password Requirements Checklist */}
                      <div className="rounded-lg border bg-muted/50 p-3">
                        <p className="mb-2 text-xs font-medium text-muted-foreground">
                          Password Requirements:
                        </p>
                        <ul className="space-y-1">
                          {passwordRequirements.map((req) => {
                            const isMet = req.regex.test(watchedPassword || "");
                            return (
                              <li
                                key={req.label}
                                className={`flex items-center gap-2 text-xs ${
                                  isMet
                                    ? "text-green-600"
                                    : "text-muted-foreground"
                                }`}
                              >
                                {isMet ? (
                                  <Check className="h-3 w-3" />
                                ) : (
                                  <X className="h-3 w-3" />
                                )}
                                {req.label}
                              </li>
                            );
                          })}
                        </ul>
                      </div>

                      <FormField
                        control={form.control}
                        name="confirm_password"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Confirm Password *</FormLabel>
                            <div className="relative">
                              <FormControl>
                                <Input
                                  type={
                                    showConfirmPassword ? "text" : "password"
                                  }
                                  placeholder="Repeat password"
                                  autoComplete="new-password"
                                  className="pr-10"
                                  {...field}
                                />
                              </FormControl>
                              <button
                                type="button"
                                onClick={() =>
                                  setShowConfirmPassword(!showConfirmPassword)
                                }
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                                aria-label={
                                  showConfirmPassword
                                    ? "Hide password"
                                    : "Show password"
                                }
                              >
                                {showConfirmPassword ? (
                                  <EyeOff className="h-4 w-4" />
                                ) : (
                                  <Eye className="h-4 w-4" />
                                )}
                              </button>
                            </div>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

                      {/* Step 2 Navigation */}
                      <div className="flex justify-between pt-4">
                        <Button
                          type="button"
                          variant="outline"
                          onClick={handleBack}
                          className="min-w-[120px]"
                        >
                          <ArrowLeft className="mr-2 h-4 w-4" />
                          Back
                        </Button>
                        <Button
                          type="button"
                          onClick={handleNext}
                          className="min-w-[120px]"
                        >
                          Next
                          <ArrowRight className="ml-2 h-4 w-4" />
                        </Button>
                      </div>
                    </CardContent>
                  </>
                )}

                {/* Step 3: Review & Submit */}
                {step === 3 && (
                  <>
                    <CardHeader>
                      <CardTitle>Review &amp; Confirm</CardTitle>
                      <CardDescription>
                        Please review your information before creating your
                        school portal
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-6">
                      {/* School Information Summary */}
                      <div className="rounded-lg border p-4">
                        <div className="mb-3 flex items-center justify-between">
                          <h3 className="text-sm font-semibold text-foreground">
                            School Information
                          </h3>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => goToStep(1)}
                            className="h-8 text-xs text-muted-foreground hover:text-foreground"
                          >
                            <Pencil className="mr-1 h-3 w-3" />
                            Edit
                          </Button>
                        </div>
                        <dl className="space-y-2 text-sm">
                          <div className="flex justify-between">
                            <dt className="text-muted-foreground">
                              Account Type
                            </dt>
                            <dd className="font-medium text-foreground">
                              {form.getValues("tenant_type") === "school_chain"
                                ? "School Chain"
                                : "Single School"}
                            </dd>
                          </div>
                          <div className="flex justify-between">
                            <dt className="text-muted-foreground">
                              {form.getValues("tenant_type") === "school_chain"
                                ? "Organization Name"
                                : "School Name"}
                            </dt>
                            <dd className="font-medium text-foreground">
                              {form.getValues("school_name")}
                            </dd>
                          </div>
                          <div className="flex justify-between">
                            <dt className="text-muted-foreground">
                              School Type
                            </dt>
                            <dd className="font-medium text-foreground">
                              {getSchoolTypeLabel(form.getValues("school_type"))}
                            </dd>
                          </div>
                          <div className="flex justify-between">
                            <dt className="text-muted-foreground">
                              Portal URL
                            </dt>
                            <dd className="font-medium text-primary">
                              {form.getValues("subdomain")}.simsplus.io
                            </dd>
                          </div>
                          {form.getValues("phone") && (
                            <div className="flex justify-between">
                              <dt className="text-muted-foreground">Phone</dt>
                              <dd className="font-medium text-foreground">
                                {form.getValues("phone")}
                              </dd>
                            </div>
                          )}
                        </dl>
                      </div>

                      {/* Admin Account Summary */}
                      <div className="rounded-lg border p-4">
                        <div className="mb-3 flex items-center justify-between">
                          <h3 className="text-sm font-semibold text-foreground">
                            Administrator Account
                          </h3>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => goToStep(2)}
                            className="h-8 text-xs text-muted-foreground hover:text-foreground"
                          >
                            <Pencil className="mr-1 h-3 w-3" />
                            Edit
                          </Button>
                        </div>
                        <dl className="space-y-2 text-sm">
                          <div className="flex justify-between">
                            <dt className="text-muted-foreground">Name</dt>
                            <dd className="font-medium text-foreground">
                              {form.getValues("first_name")}{" "}
                              {form.getValues("last_name")}
                            </dd>
                          </div>
                          <div className="flex justify-between">
                            <dt className="text-muted-foreground">Email</dt>
                            <dd className="font-medium text-foreground">
                              {form.getValues("email")}
                            </dd>
                          </div>
                          <div className="flex justify-between">
                            <dt className="text-muted-foreground">Password</dt>
                            <dd className="font-medium text-foreground">
                              ••••••••
                            </dd>
                          </div>
                        </dl>
                      </div>

                      {/* Plan Summary */}
                      <div className="rounded-lg border p-4">
                        <h3 className="mb-3 text-sm font-semibold text-foreground">
                          Subscription Plan
                        </h3>
                        <dl className="space-y-2 text-sm">
                          <div className="flex justify-between">
                            <dt className="text-muted-foreground">Plan</dt>
                            <dd className="font-medium text-foreground">
                              {plan.name}
                            </dd>
                          </div>
                          <div className="flex justify-between">
                            <dt className="text-muted-foreground">Price</dt>
                            <dd className="font-medium text-foreground">
                              {plan.price}
                              {plan.period}
                            </dd>
                          </div>
                        </dl>
                      </div>

                      {/* Terms */}
                      <div className="rounded-lg bg-muted/50 p-4 text-sm text-muted-foreground">
                        By registering, you agree to our{" "}
                        <Link
                          href="/terms"
                          className="text-primary hover:underline"
                        >
                          Terms of Service
                        </Link>{" "}
                        and{" "}
                        <Link
                          href="/privacy"
                          className="text-primary hover:underline"
                        >
                          Privacy Policy
                        </Link>
                        .
                      </div>

                      {/* Step 3 Navigation */}
                      <div className="flex justify-between pt-2">
                        <Button
                          type="button"
                          variant="outline"
                          onClick={handleBack}
                          className="min-w-[120px]"
                        >
                          <ArrowLeft className="mr-2 h-4 w-4" />
                          Back
                        </Button>
                        <Button
                          type="submit"
                          className="min-w-[160px]"
                          disabled={
                            isLoading || subdomainStatus !== "available"
                          }
                        >
                          {isLoading ? (
                            <>
                              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                              Creating your school...
                            </>
                          ) : (
                            "Start Free Trial"
                          )}
                        </Button>
                      </div>

                      <p className="text-center text-sm text-muted-foreground">
                        No credit card required &bull; 30-day free trial
                      </p>
                    </CardContent>
                  </>
                )}
              </form>
            </Form>

            {/* Sign In Link (always visible) */}
            <div className="border-t px-6 py-4">
              <p className="text-center text-sm text-muted-foreground">
                Already have an account?{" "}
                <Link
                  href="/login"
                  className="font-medium text-primary hover:underline"
                >
                  Sign in
                </Link>
              </p>
            </div>
          </Card>
        </div>
      </div>
    </main>
  );
}
