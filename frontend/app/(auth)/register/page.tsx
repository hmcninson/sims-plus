"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
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
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { register } from "@/actions/auth.action";
import { toast } from "sonner";
import {
  Check,
  X,
  Loader2,
  GraduationCap,
  Globe,
  ArrowLeft,
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
  trial: { name: "Trial", price: "Free", period: "14 days" },
  starter: { name: "Starter", price: "GHS 500", period: "/month" },
  professional: { name: "Professional", price: "GHS 1,500", period: "/month" },
  enterprise: { name: "Enterprise", price: "Custom", period: "" },
};

type SubdomainStatus = "idle" | "checking" | "available" | "taken" | "invalid";

export default function RegisterPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const selectedPlan = searchParams.get("plan") || "trial";

  const [isLoading, setIsLoading] = useState(false);
  const [schoolName, setSchoolName] = useState("");
  const [subdomain, setSubdomain] = useState("");
  const [subdomainStatus, setSubdomainStatus] =
    useState<SubdomainStatus>("idle");
  const [subdomainError, setSubdomainError] = useState("");
  const [schoolType, setSchoolType] = useState("");

  // Generate subdomain from school name
  const generateSubdomain = useCallback((name: string): string => {
    return name
      .toLowerCase()
      .replace(/[^a-z0-9\s-]/g, "") // Remove special characters
      .replace(/\s+/g, "") // Remove spaces
      .replace(/-+/g, "-") // Replace multiple hyphens with single
      .replace(/^-|-$/g, "") // Remove leading/trailing hyphens
      .substring(0, 20); // Limit length
  }, []);

  // Validate subdomain format
  const validateSubdomain = useCallback((value: string): boolean => {
    // Must be 4-63 characters, only lowercase letters, numbers, hyphens
    // Cannot start or end with hyphen
    const regex = /^[a-z0-9][a-z0-9-]{2,61}[a-z0-9]$/;
    return regex.test(value) || (value.length >= 4 && /^[a-z0-9]+$/.test(value));
  }, []);

  // Check subdomain availability via API
  const checkSubdomainAvailability = useCallback(
    async (value: string): Promise<{ available: boolean; reason?: string }> => {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

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
        // Fallback to client-side check if API fails
        if (RESERVED_SUBDOMAINS.includes(value)) {
          return { available: false, reason: "This subdomain is reserved" };
        }
        return { available: true };
      }
    },
    []
  );

  // Handle school name change - auto-generate subdomain
  useEffect(() => {
    if (schoolName) {
      const generated = generateSubdomain(schoolName);
      setSubdomain(generated);
    }
  }, [schoolName, generateSubdomain]);

  // Validate and check subdomain when it changes
  useEffect(() => {
    if (!subdomain || subdomain.length < 4) {
      setSubdomainStatus("idle");
      setSubdomainError("");
      return;
    }

    if (!validateSubdomain(subdomain)) {
      setSubdomainStatus("invalid");
      setSubdomainError(
        "Only lowercase letters, numbers, and hyphens allowed (min 4 characters)"
      );
      return;
    }

    if (RESERVED_SUBDOMAINS.includes(subdomain)) {
      setSubdomainStatus("taken");
      setSubdomainError("This subdomain is reserved");
      return;
    }

    // Check availability via API
    setSubdomainStatus("checking");
    setSubdomainError("");

    const timeoutId = setTimeout(async () => {
      const result = await checkSubdomainAvailability(subdomain);
      if (result.available) {
        setSubdomainStatus("available");
        setSubdomainError("");
      } else {
        setSubdomainStatus("taken");
        setSubdomainError(result.reason || "This subdomain is already taken");
      }
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [subdomain, validateSubdomain, checkSubdomainAvailability]);

  async function handleSubmit(formData: FormData) {
    const password = formData.get("password") as string;
    const confirmPassword = formData.get("confirm_password") as string;

    if (password !== confirmPassword) {
      toast.error("Passwords do not match");
      return;
    }

    if (password.length < 8) {
      toast.error("Password must be at least 8 characters");
      return;
    }

    if (!/[A-Z]/.test(password)) {
      toast.error("Password must contain at least one uppercase letter");
      return;
    }

    if (!/[!@#$%^&*(),.?":{}|<>]/.test(password)) {
      toast.error("Password must contain at least one special character");
      return;
    }

    if (subdomainStatus !== "available") {
      toast.error("Please choose a valid subdomain");
      return;
    }

    setIsLoading(true);

    const result = await register({
      school_name: schoolName,
      subdomain: subdomain,
      school_type: schoolType,
      admin_first_name: formData.get("first_name") as string,
      admin_last_name: formData.get("last_name") as string,
      admin_email: formData.get("email") as string,
      admin_phone: formData.get("phone") as string,
      admin_password: password,
      plan: selectedPlan,
    });

    setIsLoading(false);

    if (result.success) {
      toast.success("School registered successfully!");
      // In production, redirect to the new subdomain
      router.push(`/register/success?subdomain=${subdomain}`);
    } else {
      toast.error(result.error || "Registration failed");
    }
  }

  const plan = PLANS[selectedPlan as keyof typeof PLANS] || PLANS.trial;

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
              {plan.name} Plan • {plan.price}
              {plan.period}
            </Badge>
          </div>

          {/* Registration Form */}
          <Card>
            <CardHeader>
              <CardTitle>School Information</CardTitle>
              <CardDescription>
                Tell us about your school to set up your portal
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form action={handleSubmit} className="space-y-6">
                {/* School Details Section */}
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="school_name">School Name *</Label>
                    <Input
                      id="school_name"
                      name="school_name"
                      type="text"
                      placeholder="e.g., Bright Future Academy"
                      value={schoolName}
                      onChange={(e) => setSchoolName(e.target.value)}
                      required
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="school_type">School Type *</Label>
                    <Select value={schoolType} onValueChange={setSchoolType}>
                      <SelectTrigger>
                        <SelectValue placeholder="Select school type" />
                      </SelectTrigger>
                      <SelectContent>
                        {SCHOOL_TYPES.map((type) => (
                          <SelectItem key={type.value} value={type.value}>
                            {type.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Subdomain Selection */}
                  <div className="space-y-2">
                    <Label htmlFor="subdomain">
                      Choose Your School&apos;s Web Address *
                    </Label>
                    <div className="flex items-center gap-2">
                      <div className="relative flex-1">
                        <Input
                          id="subdomain"
                          name="subdomain"
                          type="text"
                          placeholder="yourschool"
                          value={subdomain}
                          onChange={(e) =>
                            setSubdomain(e.target.value.toLowerCase())
                          }
                          className={`pr-10 ${
                            subdomainStatus === "available"
                              ? "border-green-500 focus-visible:ring-green-500"
                              : subdomainStatus === "taken" ||
                                  subdomainStatus === "invalid"
                                ? "border-red-500 focus-visible:ring-red-500"
                                : ""
                          }`}
                          required
                        />
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
                    {subdomainStatus === "available" && subdomain && (
                      <p className="flex items-center gap-2 text-sm text-green-600">
                        <Check className="h-3 w-3" />
                        {subdomain}.simsplus.io is available!
                      </p>
                    )}
                    {subdomainError && (
                      <p className="flex items-center gap-2 text-sm text-red-600">
                        <X className="h-3 w-3" />
                        {subdomainError}
                      </p>
                    )}

                    {/* URL Preview */}
                    {subdomain && subdomainStatus === "available" && (
                      <div className="mt-3 rounded-lg border bg-muted/50 p-3">
                        <div className="flex items-center gap-2 text-sm">
                          <Globe className="h-4 w-4 text-primary" />
                          <span className="font-medium">
                            Your school portal will be:
                          </span>
                        </div>
                        <code className="mt-1 block text-lg font-semibold text-primary">
                          https://{subdomain}.simsplus.io
                        </code>
                      </div>
                    )}
                  </div>
                </div>

                {/* Divider */}
                <div className="relative">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t" />
                  </div>
                  <div className="relative flex justify-center">
                    <span className="bg-card px-4 text-sm text-muted-foreground">
                      Administrator Account
                    </span>
                  </div>
                </div>

                {/* Admin Details Section */}
                <div className="space-y-4">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="first_name">First Name *</Label>
                      <Input
                        id="first_name"
                        name="first_name"
                        type="text"
                        placeholder="Kwame"
                        required
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="last_name">Last Name *</Label>
                      <Input
                        id="last_name"
                        name="last_name"
                        type="text"
                        placeholder="Asante"
                        required
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="email">Email Address *</Label>
                    <Input
                      id="email"
                      name="email"
                      type="email"
                      placeholder="admin@school.edu.gh"
                      required
                    />
                    <p className="text-xs text-muted-foreground">
                      Login credentials will be sent to this email
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="phone">Phone Number *</Label>
                    <Input
                      id="phone"
                      name="phone"
                      type="tel"
                      placeholder="+233 24 123 4567"
                      required
                    />
                  </div>

                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="password">Password *</Label>
                      <Input
                        id="password"
                        name="password"
                        type="password"
                        placeholder="Min. 8 chars, uppercase, special"
                        required
                        minLength={8}
                      />
                      <p className="text-xs text-muted-foreground">
                        Must include uppercase letter and special character
                      </p>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="confirm_password">
                        Confirm Password *
                      </Label>
                      <Input
                        id="confirm_password"
                        name="confirm_password"
                        type="password"
                        placeholder="Repeat password"
                        required
                      />
                    </div>
                  </div>
                </div>

                {/* Terms */}
                <div className="rounded-lg bg-muted/50 p-4 text-sm text-muted-foreground">
                  By registering, you agree to our{" "}
                  <Link href="/terms" className="text-primary hover:underline">
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

                {/* Submit Button */}
                <Button
                  type="submit"
                  className="w-full"
                  size="lg"
                  disabled={isLoading || subdomainStatus !== "available"}
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

                <p className="text-center text-sm text-muted-foreground">
                  No credit card required • 14-day free trial
                </p>
              </form>

              {/* Sign In Link */}
              <p className="mt-6 text-center text-sm text-muted-foreground">
                Already have an account?{" "}
                <Link
                  href="/login"
                  className="font-medium text-primary hover:underline"
                >
                  Sign in
                </Link>
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </main>
  );
}
