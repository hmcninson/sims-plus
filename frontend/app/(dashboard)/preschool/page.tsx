import Link from "next/link";
import {
  Star,
  BookOpen,
  CalendarDays,
  FileHeart,
  ArrowRight,
  Baby,
} from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export const metadata = {
  title: "Preschool - SIMS Plus",
  description: "Preschool assessment and developmental tracking",
};

const preschoolModules = [
  {
    title: "Skill Assessment",
    description: "Assess students on developmental skills across learning areas",
    href: "/preschool/assessment",
    icon: Star,
    color: "text-amber-600",
    bgColor: "bg-amber-100 dark:bg-amber-900/30",
  },
  {
    title: "Observations",
    description: "Record anecdotes, milestones, and progress observations",
    href: "/preschool/observations",
    icon: BookOpen,
    color: "text-blue-600",
    bgColor: "bg-blue-100 dark:bg-blue-900/30",
  },
  {
    title: "Daily Logs",
    description: "Track daily activities: meals, naps, moods, and more",
    href: "/preschool/daily-logs",
    icon: CalendarDays,
    color: "text-green-600",
    bgColor: "bg-green-100 dark:bg-green-900/30",
  },
  {
    title: "Progress Reports",
    description: "Generate narrative-based developmental progress reports",
    href: "/preschool/reports",
    icon: FileHeart,
    color: "text-purple-600",
    bgColor: "bg-purple-100 dark:bg-purple-900/30",
  },
];

export default function PreschoolPage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
          <Baby className="h-6 w-6 text-primary" />
        </div>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Preschool</h1>
          <p className="text-muted-foreground">
            Developmental assessment and daily tracking for early learners
          </p>
        </div>
      </div>

      {/* Module Cards */}
      <div className="grid gap-6 md:grid-cols-2">
        {preschoolModules.map((module) => (
          <Card key={module.href} className="group hover:shadow-md transition-shadow">
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between">
                <div className={`rounded-lg p-2.5 ${module.bgColor}`}>
                  <module.icon className={`h-5 w-5 ${module.color}`} />
                </div>
              </div>
              <CardTitle className="text-lg">{module.title}</CardTitle>
              <CardDescription>{module.description}</CardDescription>
            </CardHeader>
            <CardContent>
              <Link href={module.href}>
                <Button variant="outline" className="w-full group-hover:bg-primary group-hover:text-primary-foreground transition-colors">
                  Open {module.title}
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </Link>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Quick Info */}
      <Card className="border-dashed">
        <CardContent className="pt-6">
          <div className="flex items-start gap-4">
            <div className="rounded-full bg-muted p-2">
              <Baby className="h-5 w-5 text-muted-foreground" />
            </div>
            <div className="space-y-1">
              <h3 className="font-medium">About Preschool Assessment</h3>
              <p className="text-sm text-muted-foreground">
                Preschool assessment focuses on developmental milestones rather than traditional grades.
                Use <strong>Learning Areas</strong> (Social-Emotional, Language & Literacy, etc.)
                and <strong>Rating Scales</strong> (Emerging, Developing, Proficient) to track each child&apos;s
                progress. Configure these in{" "}
                <Link href="/settings/preschool" className="text-primary hover:underline">
                  Preschool Settings
                </Link>.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
