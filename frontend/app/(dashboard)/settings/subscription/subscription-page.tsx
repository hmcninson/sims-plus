"use client";

import { useState, useTransition } from "react";
import { toast } from "sonner";
import {
  Crown,
  Users,
  GraduationCap,
  Clock,
  Check,
  Loader2,
  Zap,
  Building2,
  Bus,
  Baby,
  ArrowRight,
  AlertCircle,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";

import {
  initiateUpgrade,
  purchaseAddon,
  type SubscriptionStatus,
} from "@/actions/subscription.action";

// ============================================================================
// Constants
// ============================================================================

const TIER_ORDER = ["trial", "starter", "professional", "enterprise"] as const;

type TierKey = (typeof TIER_ORDER)[number];

interface TierInfo {
  name: string;
  description: string;
  pricePerStudentTerm: number;
  pricePerStudentYear: number;
  maxStudents: string;
  maxUsers: string;
  storage: string;
  sms: string;
  support: string;
  features: string[];
}

const TIERS: Record<TierKey, TierInfo> = {
  trial: {
    name: "Trial",
    description: "Try SIMS Plus risk-free for 90 days",
    pricePerStudentTerm: 0,
    pricePerStudentYear: 0,
    maxStudents: "100",
    maxUsers: "10",
    storage: "5 GB",
    sms: "50/month",
    support: "Email",
    features: [
      "Student management",
      "Attendance (offline PWA)",
      "Basic report cards",
      "Basic finance (tuition, MTN MoMo)",
      "Staff records & attendance",
    ],
  },
  starter: {
    name: "Starter",
    description: "For small schools getting started",
    pricePerStudentTerm: 5,
    pricePerStudentYear: 13.5,
    maxStudents: "300",
    maxUsers: "10",
    storage: "5 GB",
    sms: "50/month",
    support: "Email",
    features: [
      "Everything in Trial",
      "Teachers portal",
      "Basic enrollment & admissions",
    ],
  },
  professional: {
    name: "Professional",
    description: "For growing schools that need more",
    pricePerStudentTerm: 10,
    pricePerStudentYear: 27,
    maxStudents: "Unlimited",
    maxUsers: "50",
    storage: "20 GB",
    sms: "200/month",
    support: "Email + Chat",
    features: [
      "Everything in Starter",
      "Customizable report cards",
      "Timetable & PDF export",
      "Grade moderation workflow",
      "Scholarships & discounts",
      "Vodafone Cash & AirtelTigo",
      "Parent portal",
      "Mobile apps",
      "Push notifications",
      "HR leave management",
      "Advanced admissions",
    ],
  },
  enterprise: {
    name: "Enterprise",
    description: "For large schools and school chains",
    pricePerStudentTerm: 15,
    pricePerStudentYear: 40.5,
    maxStudents: "Unlimited",
    maxUsers: "Unlimited",
    storage: "100 GB",
    sms: "Unlimited",
    support: "Priority + Phone",
    features: [
      "Everything in Professional",
      "Multi-curriculum support",
      "Asset & inventory management",
      "Chain / multi-school management",
      "API access",
      "Custom domain",
      "SSO integration",
      "Full admissions suite",
      "Boarding, Transport, Preschool included",
      "99.9% uptime SLA",
    ],
  },
};

const ADDONS = [
  {
    key: "boarding",
    name: "Boarding / Hostel Management",
    description: "Dormitories, exeats, roll calls, visitor management",
    pricePerTerm: 300,
    icon: Building2,
  },
  {
    key: "transport",
    name: "Transport Management",
    description: "Vehicles, routes, student transport assignments",
    pricePerTerm: 200,
    icon: Bus,
  },
  {
    key: "preschool",
    name: "Preschool Module",
    description: "Developmental milestones, observations, daily logs",
    pricePerTerm: 200,
    icon: Baby,
  },
];

// ============================================================================
// Component
// ============================================================================

interface SubscriptionPageProps {
  initialStatus: SubscriptionStatus | null;
}

export function SubscriptionPage({ initialStatus }: SubscriptionPageProps) {
  const [billingPeriod, setBillingPeriod] = useState<"term" | "year">("term");
  const [isPending, startTransition] = useTransition();
  const [upgradingTier, setUpgradingTier] = useState<string | null>(null);
  const [purchasingAddon, setPurchasingAddon] = useState<string | null>(null);

  if (!initialStatus) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-12 gap-3">
          <AlertCircle className="h-10 w-10 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            Unable to load subscription status. Please try again later.
          </p>
        </CardContent>
      </Card>
    );
  }

  const currentTier = initialStatus.plan as TierKey;
  const currentTierIndex = TIER_ORDER.indexOf(currentTier);
  const currentTierInfo = TIERS[currentTier];

  const studentUsagePercent =
    initialStatus.max_students > 0
      ? Math.min(
          100,
          Math.round(
            (initialStatus.current_student_count / initialStatus.max_students) * 100
          )
        )
      : 0;

  const staffUsagePercent =
    initialStatus.max_staff > 0
      ? Math.min(
          100,
          Math.round(
            (initialStatus.current_staff_count / initialStatus.max_staff) * 100
          )
        )
      : 0;

  function handleUpgrade(tier: string) {
    setUpgradingTier(tier);
    startTransition(async () => {
      const callbackUrl = `${window.location.origin}/settings/subscription?upgraded=true`;
      const result = await initiateUpgrade(tier, billingPeriod, callbackUrl);

      if (result.success && result.data.payment_url) {
        window.location.href = result.data.payment_url;
      } else {
        toast.error(result.success ? "No payment URL received" : result.error);
        setUpgradingTier(null);
      }
    });
  }

  function handleAddonPurchase(addonKey: string) {
    setPurchasingAddon(addonKey);
    startTransition(async () => {
      const callbackUrl = `${window.location.origin}/settings/subscription?addon=${addonKey}`;
      const result = await purchaseAddon(addonKey, callbackUrl);

      if (result.success && result.data.payment_url) {
        window.location.href = result.data.payment_url;
      } else {
        toast.error(result.success ? "No payment URL received" : result.error);
        setPurchasingAddon(null);
      }
    });
  }

  const statusBadgeVariant = (status: string) => {
    switch (status) {
      case "trial":
        return "secondary" as const;
      case "active":
        return "default" as const;
      case "suspended":
      case "cancelled":
        return "destructive" as const;
      default:
        return "outline" as const;
    }
  };

  return (
    <div className="space-y-8">
      {/* Current Plan Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Crown className="h-5 w-5" />
                Current Plan
              </CardTitle>
              <CardDescription className="mt-1">
                {currentTierInfo?.description || "Manage your subscription"}
              </CardDescription>
            </div>
            <Badge variant={statusBadgeVariant(initialStatus.status)}>
              {initialStatus.status === "trial"
                ? "Free Trial"
                : initialStatus.status.charAt(0).toUpperCase() +
                  initialStatus.status.slice(1)}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Plan Name and Days */}
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-2xl font-bold">
                {currentTierInfo?.name || initialStatus.plan}
              </p>
              {initialStatus.days_remaining !== null && (
                <p className="flex items-center gap-1.5 mt-1 text-sm text-muted-foreground">
                  <Clock className="h-3.5 w-3.5" />
                  {initialStatus.days_remaining > 0
                    ? `${initialStatus.days_remaining} day${initialStatus.days_remaining !== 1 ? "s" : ""} remaining`
                    : "Expired"}
                </p>
              )}
            </div>
            {currentTier !== "enterprise" && (
              <Button
                variant="default"
                onClick={() => {
                  const section = document.getElementById("upgrade-plans");
                  section?.scrollIntoView({ behavior: "smooth" });
                }}
              >
                <Zap className="mr-2 h-4 w-4" />
                Upgrade Plan
              </Button>
            )}
          </div>

          {/* Usage Stats */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {/* Students */}
            <div className="space-y-2 rounded-lg border p-4">
              <div className="flex items-center justify-between text-sm">
                <span className="flex items-center gap-1.5 text-muted-foreground">
                  <GraduationCap className="h-4 w-4" />
                  Students
                </span>
                <span className="font-medium">
                  {initialStatus.current_student_count}
                  {initialStatus.max_students > 0 && (
                    <span className="text-muted-foreground">
                      {" "}
                      / {initialStatus.max_students}
                    </span>
                  )}
                  {initialStatus.max_students === 0 && (
                    <span className="text-muted-foreground"> (unlimited)</span>
                  )}
                </span>
              </div>
              {initialStatus.max_students > 0 && (
                <Progress value={studentUsagePercent} className="h-2" />
              )}
            </div>

            {/* Staff */}
            <div className="space-y-2 rounded-lg border p-4">
              <div className="flex items-center justify-between text-sm">
                <span className="flex items-center gap-1.5 text-muted-foreground">
                  <Users className="h-4 w-4" />
                  Staff / User Accounts
                </span>
                <span className="font-medium">
                  {initialStatus.current_staff_count}
                  {initialStatus.max_staff > 0 && (
                    <span className="text-muted-foreground">
                      {" "}
                      / {initialStatus.max_staff}
                    </span>
                  )}
                  {initialStatus.max_staff === 0 && (
                    <span className="text-muted-foreground"> (unlimited)</span>
                  )}
                </span>
              </div>
              {initialStatus.max_staff > 0 && (
                <Progress value={staffUsagePercent} className="h-2" />
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Upgrade Plans Section */}
      {currentTier !== "enterprise" && (
        <div id="upgrade-plans" className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h3 className="text-lg font-semibold">Choose a Plan</h3>
              <p className="text-sm text-muted-foreground">
                Per-student pricing. Pay only for what you use.
              </p>
            </div>

            {/* Billing Period Toggle */}
            <Tabs
              value={billingPeriod}
              onValueChange={(v) => setBillingPeriod(v as "term" | "year")}
            >
              <TabsList>
                <TabsTrigger value="term">Per Term</TabsTrigger>
                <TabsTrigger value="year">
                  Annual
                  <Badge variant="secondary" className="ml-1.5 text-[10px] px-1.5 py-0">
                    10% off
                  </Badge>
                </TabsTrigger>
              </TabsList>
            </Tabs>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            {TIER_ORDER.filter((t) => t !== "trial").map((tierKey) => {
              const tier = TIERS[tierKey];
              const tierIndex = TIER_ORDER.indexOf(tierKey);
              const isCurrent = tierKey === currentTier;
              const isDowngrade = tierIndex <= currentTierIndex;
              const isRecommended = tierKey === "professional";

              const price =
                billingPeriod === "year"
                  ? tier.pricePerStudentYear
                  : tier.pricePerStudentTerm;

              return (
                <Card
                  key={tierKey}
                  className={`relative ${
                    isRecommended
                      ? "border-primary shadow-md"
                      : ""
                  }`}
                >
                  {isRecommended && (
                    <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                      <Badge className="px-3">Most Popular</Badge>
                    </div>
                  )}
                  <CardHeader className="pb-3">
                    <CardTitle className="text-lg">{tier.name}</CardTitle>
                    <CardDescription className="text-xs">
                      {tier.description}
                    </CardDescription>
                    <div className="mt-3">
                      <span className="text-3xl font-bold">
                        GHS {price % 1 === 0 ? price : price.toFixed(2)}
                      </span>
                      <span className="text-sm text-muted-foreground">
                        /student/{billingPeriod === "year" ? "year" : "term"}
                      </span>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {/* Limits */}
                    <div className="space-y-1.5 text-sm">
                      <p>
                        <span className="font-medium">{tier.maxStudents}</span>{" "}
                        students
                      </p>
                      <p>
                        <span className="font-medium">{tier.maxUsers}</span>{" "}
                        user accounts
                      </p>
                      <p>
                        <span className="font-medium">{tier.storage}</span>{" "}
                        storage
                      </p>
                      <p>
                        <span className="font-medium">{tier.sms}</span> SMS
                      </p>
                      <p>
                        <span className="font-medium">{tier.support}</span>{" "}
                        support
                      </p>
                    </div>

                    {/* Features */}
                    <ul className="space-y-1.5 text-sm">
                      {tier.features.map((feature) => (
                        <li key={feature} className="flex items-start gap-2">
                          <Check className="h-4 w-4 text-green-600 shrink-0 mt-0.5" />
                          <span>{feature}</span>
                        </li>
                      ))}
                    </ul>

                    {/* CTA */}
                    <Button
                      className="w-full"
                      variant={isRecommended ? "default" : "outline"}
                      disabled={
                        isCurrent || isDowngrade || isPending
                      }
                      onClick={() => handleUpgrade(tierKey)}
                    >
                      {isPending && upgradingTier === tierKey ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Processing...
                        </>
                      ) : isCurrent ? (
                        "Current Plan"
                      ) : isDowngrade ? (
                        "Current or Lower"
                      ) : (
                        <>
                          Upgrade to {tier.name}
                          <ArrowRight className="ml-2 h-4 w-4" />
                        </>
                      )}
                    </Button>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>
      )}

      {/* Add-ons Section (Professional tier only) */}
      {currentTier === "professional" && (
        <div className="space-y-4">
          <div>
            <h3 className="text-lg font-semibold">Add-ons</h3>
            <p className="text-sm text-muted-foreground">
              Enhance your Professional plan with additional modules.
            </p>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            {ADDONS.map((addon) => {
              const isEnabled =
                initialStatus.features[addon.key] === true ||
                initialStatus.features[addon.key] === "true";

              return (
                <Card key={addon.key}>
                  <CardHeader className="pb-3">
                    <div className="flex items-center gap-2">
                      <addon.icon className="h-5 w-5 text-muted-foreground" />
                      <CardTitle className="text-base">{addon.name}</CardTitle>
                    </div>
                    <CardDescription className="text-xs">
                      {addon.description}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="mb-4">
                      <span className="text-2xl font-bold">
                        GHS {addon.pricePerTerm}
                      </span>
                      <span className="text-sm text-muted-foreground">
                        /term
                      </span>
                    </div>
                    {isEnabled ? (
                      <Badge
                        variant="secondary"
                        className="w-full justify-center py-2"
                      >
                        <Check className="mr-1.5 h-3.5 w-3.5" />
                        Active
                      </Badge>
                    ) : (
                      <Button
                        variant="outline"
                        className="w-full"
                        disabled={isPending}
                        onClick={() => handleAddonPurchase(addon.key)}
                      >
                        {isPending && purchasingAddon === addon.key ? (
                          <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            Processing...
                          </>
                        ) : (
                          <>
                            Add to Plan
                            <ArrowRight className="ml-2 h-4 w-4" />
                          </>
                        )}
                      </Button>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>
      )}

      {/* Enterprise note for Enterprise users */}
      {currentTier === "enterprise" && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-8 gap-2">
            <Crown className="h-8 w-8 text-primary" />
            <p className="text-sm text-muted-foreground text-center">
              You are on the Enterprise plan with access to all features.
              <br />
              Contact{" "}
              <a
                href="mailto:support@simsplus.io"
                className="text-primary hover:underline"
              >
                support@simsplus.io
              </a>{" "}
              for billing inquiries.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
