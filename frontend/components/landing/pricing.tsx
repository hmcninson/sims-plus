import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Check } from "lucide-react";

const plans = [
  {
    name: "Trial",
    price: "Free",
    period: "14 days",
    description: "Try SIMS Plus risk-free",
    students: "Up to 50 students",
    features: [
      "Student management",
      "Basic attendance",
      "Fee tracking",
      "Email support",
    ],
    cta: "Start Free Trial",
    href: "/register?plan=trial",
    highlighted: false,
  },
  {
    name: "Starter",
    price: "GHS 500",
    period: "/month",
    description: "For small schools",
    students: "Up to 300 students",
    features: [
      "Everything in Trial",
      "Academic module",
      "Report cards",
      "Mobile Money payments",
      "SMS notifications",
    ],
    cta: "Get Started",
    href: "/register?plan=starter",
    highlighted: false,
  },
  {
    name: "Professional",
    price: "GHS 1,500",
    period: "/month",
    description: "For growing schools",
    students: "Up to 1,000 students",
    features: [
      "Everything in Starter",
      "Boarding management",
      "Staff & HR module",
      "Advanced reports",
      "Priority support",
      "API access",
    ],
    cta: "Get Started",
    href: "/register?plan=professional",
    highlighted: true,
    badge: "Most Popular",
  },
  {
    name: "Enterprise",
    price: "Custom",
    period: "",
    description: "For school chains",
    students: "Unlimited students",
    features: [
      "Everything in Professional",
      "Multi-school management",
      "Custom integrations",
      "Dedicated support",
      "SLA guarantee",
      "On-premise option",
    ],
    cta: "Contact Sales",
    href: "/contact",
    highlighted: false,
  },
];

export function Pricing() {
  return (
    <section id="pricing" className="bg-muted/30 py-20">
      <div className="container mx-auto px-4">
        {/* Section Header */}
        <div className="mx-auto mb-16 max-w-2xl text-center">
          <h2 className="mb-4 text-3xl font-bold text-foreground sm:text-4xl">
            Simple, transparent pricing
          </h2>
          <p className="text-lg text-muted-foreground">
            Choose the plan that fits your school. All plans include core
            features with no hidden fees.
          </p>
        </div>

        {/* Pricing Grid */}
        <div className="grid gap-6 lg:grid-cols-4">
          {plans.map((plan) => (
            <Card
              key={plan.name}
              className={`relative flex flex-col ${
                plan.highlighted
                  ? "border-2 border-primary shadow-lg"
                  : "border"
              }`}
            >
              {plan.badge && (
                <Badge className="absolute -top-3 left-1/2 -translate-x-1/2">
                  {plan.badge}
                </Badge>
              )}
              <CardHeader className="pb-4">
                <h3 className="text-xl font-semibold">{plan.name}</h3>
                <p className="text-sm text-muted-foreground">
                  {plan.description}
                </p>
                <div className="mt-4">
                  <span className="text-4xl font-bold">{plan.price}</span>
                  <span className="text-muted-foreground">{plan.period}</span>
                </div>
                <p className="mt-2 text-sm font-medium text-primary">
                  {plan.students}
                </p>
              </CardHeader>
              <CardContent className="flex flex-1 flex-col">
                <ul className="mb-6 flex-1 space-y-3">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-start gap-2">
                      <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                      <span className="text-sm text-muted-foreground">
                        {feature}
                      </span>
                    </li>
                  ))}
                </ul>
                <Button
                  asChild
                  variant={plan.highlighted ? "default" : "outline"}
                  className="w-full"
                >
                  <Link href={plan.href}>{plan.cta}</Link>
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Additional Info */}
        <p className="mt-10 text-center text-sm text-muted-foreground">
          All prices are in USD. Annual billing available with 2
          months free.
        </p>
      </div>
    </section>
  );
}
