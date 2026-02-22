import Link from "next/link";
import { DollarSign, Users, BarChart3, GraduationCap } from "lucide-react";

import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export const metadata = {
  title: "Reports",
};

interface ReportCategory {
  title: string;
  description: string;
  icon: React.ElementType;
  href: string;
  color: string;
  bgColor: string;
  disabled?: boolean;
}

const reportCategories: ReportCategory[] = [
  {
    title: "Financial Reports",
    description: "Fee collection, outstanding fees, and payment summaries",
    icon: DollarSign,
    href: "/reports/financial",
    color: "text-green-600",
    bgColor: "bg-green-50 dark:bg-green-950",
  },
  {
    title: "Attendance Reports",
    description: "Student attendance summaries and trends",
    icon: Users,
    href: "/reports/attendance",
    color: "text-blue-600",
    bgColor: "bg-blue-50 dark:bg-blue-950",
  },
  {
    title: "Academic Reports",
    description: "Performance analysis and class statistics",
    icon: GraduationCap,
    href: "#",
    color: "text-purple-600",
    bgColor: "bg-purple-50 dark:bg-purple-950",
    disabled: true,
  },
  {
    title: "Student Reports",
    description: "Enrollment statistics and demographics",
    icon: BarChart3,
    href: "#",
    color: "text-orange-600",
    bgColor: "bg-orange-50 dark:bg-orange-950",
    disabled: true,
  },
];

export default function ReportsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Reports</h1>
        <p className="text-muted-foreground">
          Generate and download reports for your school
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {reportCategories.map((category) => {
          const Icon = category.icon;

          if (category.disabled) {
            return (
              <Card
                key={category.title}
                className="cursor-not-allowed opacity-60"
              >
                <CardHeader className="flex flex-row items-center gap-4">
                  <div className={`shrink-0 rounded-lg p-3 ${category.bgColor}`}>
                    <Icon className={`h-6 w-6 ${category.color}`} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <CardTitle className="text-lg">{category.title}</CardTitle>
                    <CardDescription>{category.description}</CardDescription>
                  </div>
                  <Badge variant="secondary" className="shrink-0">
                    Coming Soon
                  </Badge>
                </CardHeader>
              </Card>
            );
          }

          return (
            <Link key={category.title} href={category.href}>
              <Card className="transition-shadow hover:shadow-md">
                <CardHeader className="flex flex-row items-center gap-4">
                  <div className={`shrink-0 rounded-lg p-3 ${category.bgColor}`}>
                    <Icon className={`h-6 w-6 ${category.color}`} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <CardTitle className="text-lg">{category.title}</CardTitle>
                    <CardDescription>{category.description}</CardDescription>
                  </div>
                </CardHeader>
              </Card>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
