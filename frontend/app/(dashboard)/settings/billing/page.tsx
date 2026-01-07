import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  CreditCard,
  Check,
  Zap,
  Download,
  ExternalLink,
} from "lucide-react";

export const metadata = {
  title: "Billing | SIMS Plus",
};

const invoices = [
  { id: "INV-2026-001", date: "Jan 1, 2026", amount: "$150.00", status: "paid" },
  { id: "INV-2025-012", date: "Dec 1, 2025", amount: "$150.00", status: "paid" },
  { id: "INV-2025-011", date: "Nov 1, 2025", amount: "$150.00", status: "paid" },
];

const plans = [
  {
    name: "Starter",
    price: "$50",
    period: "/month",
    description: "For small schools up to 300 students",
    features: [
      "Up to 300 students",
      "Core modules",
      "50 SMS/month",
      "Email support",
    ],
    current: false,
  },
  {
    name: "Professional",
    price: "$150",
    period: "/month",
    description: "For growing schools up to 1,000 students",
    features: [
      "Up to 1,000 students",
      "All modules",
      "200 SMS/month",
      "Priority support",
      "API access",
      "Boarding & Transport",
    ],
    current: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    period: "",
    description: "For large institutions and school chains",
    features: [
      "Unlimited students",
      "All modules",
      "Unlimited SMS",
      "Dedicated support",
      "Custom domain",
      "Multi-school",
      "White label",
    ],
    current: false,
  },
];

export default function BillingSettingsPage() {
  return (
    <div className="space-y-6">
      {/* Current Plan */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CreditCard className="h-5 w-5" />
            Current Plan
          </CardTitle>
          <CardDescription>
            Your subscription details and usage.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-xl font-bold">Professional</h3>
                <Badge>Current Plan</Badge>
              </div>
              <p className="text-muted-foreground">
                $150/month &middot; Renews on Feb 1, 2026
              </p>
            </div>
            <Button variant="outline">
              Manage Subscription
              <ExternalLink className="ml-2 h-4 w-4" />
            </Button>
          </div>

          <div className="space-y-4">
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span>Students</span>
                <span className="font-medium">456 / 1,000</span>
              </div>
              <Progress value={45.6} />
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span>SMS Credits</span>
                <span className="font-medium">125 / 200</span>
              </div>
              <Progress value={62.5} />
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span>Staff Accounts</span>
                <span className="font-medium">32 / 50</span>
              </div>
              <Progress value={64} />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Available Plans */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Zap className="h-5 w-5" />
            Available Plans
          </CardTitle>
          <CardDescription>
            Compare plans and upgrade when you need more.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-3">
            {plans.map((plan) => (
              <div
                key={plan.name}
                className={`rounded-lg border p-4 ${
                  plan.current ? "border-primary bg-primary/5" : ""
                }`}
              >
                <div className="mb-4">
                  <div className="flex items-center justify-between">
                    <h3 className="font-bold">{plan.name}</h3>
                    {plan.current && (
                      <Badge variant="default" className="text-xs">
                        Current
                      </Badge>
                    )}
                  </div>
                  <div className="mt-2">
                    <span className="text-2xl font-bold">{plan.price}</span>
                    <span className="text-muted-foreground">{plan.period}</span>
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {plan.description}
                  </p>
                </div>

                <ul className="mb-4 space-y-2">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-center gap-2 text-sm">
                      <Check className="h-4 w-4 text-green-600" />
                      {feature}
                    </li>
                  ))}
                </ul>

                {plan.current ? (
                  <Button variant="outline" className="w-full" disabled>
                    Current Plan
                  </Button>
                ) : plan.name === "Enterprise" ? (
                  <Button variant="outline" className="w-full">
                    Contact Sales
                  </Button>
                ) : (
                  <Button className="w-full">
                    {plan.name === "Starter" ? "Downgrade" : "Upgrade"}
                  </Button>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Payment Method */}
      <Card>
        <CardHeader>
          <CardTitle>Payment Method</CardTitle>
          <CardDescription>
            Manage your payment method for subscription billing.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between rounded-lg border p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted">
                <CreditCard className="h-5 w-5" />
              </div>
              <div>
                <p className="font-medium">Visa ending in 4242</p>
                <p className="text-sm text-muted-foreground">Expires 12/2027</p>
              </div>
            </div>
            <Button variant="outline" size="sm">
              Update
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Billing History */}
      <Card>
        <CardHeader>
          <CardTitle>Billing History</CardTitle>
          <CardDescription>
            View and download past invoices.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {invoices.map((invoice) => (
              <div
                key={invoice.id}
                className="flex items-center justify-between rounded-lg border p-4"
              >
                <div>
                  <p className="font-medium">{invoice.id}</p>
                  <p className="text-sm text-muted-foreground">{invoice.date}</p>
                </div>
                <div className="flex items-center gap-4">
                  <div className="text-right">
                    <p className="font-medium">{invoice.amount}</p>
                    <Badge variant="outline" className="text-green-600 border-green-600">
                      {invoice.status}
                    </Badge>
                  </div>
                  <Button variant="ghost" size="icon">
                    <Download className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
