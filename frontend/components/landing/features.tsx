import { Card, CardContent } from "@/components/ui/card";
import {
  Users,
  BookOpen,
  Wallet,
  CalendarCheck,
  Building2,
  UserCog,
} from "lucide-react";

const features = [
  {
    icon: Users,
    title: "Student Management",
    description:
      "Complete student lifecycle management from enrollment to graduation. Track records, guardians, transfers, and more.",
  },
  {
    icon: BookOpen,
    title: "Academic Module",
    description:
      "Manage classes, subjects, exams, grading, and generate report cards. Support for GES curriculum standards.",
  },
  {
    icon: Wallet,
    title: "Finance & Payments",
    description:
      "Handle fees, invoices, and accept payments via Mobile Money (MTN, Vodafone, AirtelTigo). Real-time tracking.",
  },
  {
    icon: CalendarCheck,
    title: "Attendance Tracking",
    description:
      "Daily attendance for students and staff. Generate reports, track patterns, and notify parents of absences.",
  },
  {
    icon: Building2,
    title: "Boarding Management",
    description:
      "Manage dormitories, bed assignments, exeats, and conduct roll calls. Perfect for boarding schools.",
  },
  {
    icon: UserCog,
    title: "Staff & HR",
    description:
      "Staff profiles, leave management, payroll integration, and role-based access control for your team.",
  },
];

export function Features() {
  return (
    <section id="features" className="py-20">
      <div className="container mx-auto px-4">
        {/* Section Header */}
        <div className="mx-auto mb-16 max-w-2xl text-center">
          <h2 className="mb-4 text-3xl font-bold text-foreground sm:text-4xl">
            Everything you need to run your school
          </h2>
          <p className="text-lg text-muted-foreground">
            SIMS Plus provides comprehensive tools designed specifically for
            the needs of educational institutions worldwide.
          </p>
        </div>

        {/* Features Grid */}
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((feature) => (
            <Card
              key={feature.title}
              className="border-2 transition-colors hover:border-primary/50"
            >
              <CardContent className="p-6">
                <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10">
                  <feature.icon className="h-6 w-6 text-primary" />
                </div>
                <h3 className="mb-2 text-xl font-semibold text-foreground">
                  {feature.title}
                </h3>
                <p className="text-muted-foreground">{feature.description}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
}
