"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Search,
  BookOpen,
  CheckCircle,
  Clock,
  Users,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Progress } from "@/components/ui/progress";

import type {
  ExamWithContext,
  ExamSubjectWithDetails,
  Class,
  ExamSubjectStatus,
} from "@/types";

const STATUS_CONFIG: Record<
  ExamSubjectStatus,
  { label: string; color: string; icon: React.ElementType }
> = {
  pending: { label: "Not Started", color: "text-gray-500", icon: Clock },
  scores_entered: { label: "In Progress", color: "text-amber-500", icon: Clock },
  submitted: { label: "Submitted", color: "text-blue-500", icon: CheckCircle },
  published: { label: "Published", color: "text-green-500", icon: CheckCircle },
};

interface ScoreEntrySelectorProps {
  exam: ExamWithContext;
  examSubjects: ExamSubjectWithDetails[];
  classes: Class[];
}

export function ScoreEntrySelector({
  exam,
  examSubjects,
  classes,
}: ScoreEntrySelectorProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [classFilter, setClassFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<ExamSubjectStatus | "all">("all");

  // Group subjects by class
  const subjectsByClass = useMemo(() => {
    const grouped: Record<string, ExamSubjectWithDetails[]> = {};
    for (const subject of examSubjects) {
      if (!grouped[subject.class_id]) {
        grouped[subject.class_id] = [];
      }
      grouped[subject.class_id].push(subject);
    }
    return grouped;
  }, [examSubjects]);

  // Get unique class IDs that have subjects
  const classesWithSubjects = useMemo(() => {
    const classIds = [...new Set(examSubjects.map((s) => s.class_id))];
    return classes.filter((c) => classIds.includes(c.id));
  }, [examSubjects, classes]);

  // Filter subjects
  const filteredSubjects = useMemo(() => {
    return examSubjects.filter((subject) => {
      const matchesSearch =
        subject.subject_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        subject.subject_code.toLowerCase().includes(searchQuery.toLowerCase()) ||
        subject.class_name.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesClass = classFilter === "all" || subject.class_id === classFilter;
      const matchesStatus = statusFilter === "all" || subject.status === statusFilter;
      return matchesSearch && matchesClass && matchesStatus;
    });
  }, [examSubjects, searchQuery, classFilter, statusFilter]);

  // Stats
  const stats = {
    total: examSubjects.length,
    pending: examSubjects.filter((s) => s.status === "pending").length,
    inProgress: examSubjects.filter((s) => s.status === "scores_entered").length,
    submitted: examSubjects.filter(
      (s) => s.status === "submitted" || s.status === "published"
    ).length,
  };

  const completionPercentage =
    stats.total > 0 ? Math.round((stats.submitted / stats.total) * 100) : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href="/exams">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold tracking-tight">{exam.name}</h1>
          <p className="text-muted-foreground">
            {[exam.academic_year_name, exam.term_name].filter(Boolean).join(" - ") || "Score Entry"}
          </p>
        </div>
      </div>

      {/* Progress Overview */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-lg">Score Entry Progress</CardTitle>
          <CardDescription>
            {stats.submitted} of {stats.total} subjects completed
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Progress value={completionPercentage} className="h-2" />
          <div className="mt-4 grid grid-cols-3 gap-4 text-center">
            <div>
              <p className="text-2xl font-bold text-gray-500">{stats.pending}</p>
              <p className="text-sm text-muted-foreground">Not Started</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-amber-500">{stats.inProgress}</p>
              <p className="text-sm text-muted-foreground">In Progress</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-green-500">{stats.submitted}</p>
              <p className="text-sm text-muted-foreground">Completed</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search subjects or classes..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={classFilter} onValueChange={setClassFilter}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Filter by class" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Classes</SelectItem>
            {classesWithSubjects.map((c) => (
              <SelectItem key={c.id} value={c.id}>
                {c.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={statusFilter}
          onValueChange={(v) => setStatusFilter(v as ExamSubjectStatus | "all")}
        >
          <SelectTrigger className="w-[150px]">
            <SelectValue placeholder="Filter by status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            {Object.entries(STATUS_CONFIG).map(([key, config]) => (
              <SelectItem key={key} value={key}>
                {config.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Subject Cards */}
      {filteredSubjects.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <BookOpen className="mx-auto h-12 w-12 text-muted-foreground/50" />
            <h3 className="mt-4 text-lg font-semibold">No subjects found</h3>
            <p className="text-muted-foreground">
              {examSubjects.length === 0
                ? "Add subjects to this exam first."
                : "Try adjusting your search or filters."}
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredSubjects.map((subject) => {
            const StatusIcon = STATUS_CONFIG[subject.status]?.icon || Clock;
            const progress =
              subject.students_count > 0
                ? Math.round((subject.scores_count / subject.students_count) * 100)
                : 0;

            return (
              <Card key={subject.id} className="hover:shadow-md transition-shadow">
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle className="text-lg">{subject.subject_name}</CardTitle>
                      <CardDescription>
                        {subject.subject_code} - {subject.class_name}
                      </CardDescription>
                    </div>
                    <Badge
                      variant="outline"
                      className={STATUS_CONFIG[subject.status]?.color}
                    >
                      <StatusIcon className="mr-1 h-3 w-3" />
                      {STATUS_CONFIG[subject.status]?.label}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {/* Progress */}
                    <div>
                      <div className="flex items-center justify-between text-sm mb-1">
                        <span className="text-muted-foreground">Scores Entered</span>
                        <span className="font-medium">
                          {subject.scores_count} / {subject.students_count}
                        </span>
                      </div>
                      <Progress value={progress} className="h-1.5" />
                    </div>

                    {/* Details */}
                    <div className="flex items-center justify-between text-sm">
                      <div className="flex items-center gap-1 text-muted-foreground">
                        <Users className="h-4 w-4" />
                        <span>{subject.students_count} students</span>
                      </div>
                      <span className="text-muted-foreground">
                        Max: {subject.max_score} | Pass: {subject.pass_mark}
                      </span>
                    </div>

                    {/* Action Button */}
                    <Link
                      href={`/exams/${exam.id}/scores/${subject.id}`}
                      className="block"
                    >
                      <Button className="w-full" variant={progress === 100 ? "outline" : "default"}>
                        {progress === 0
                          ? "Enter Scores"
                          : progress === 100
                          ? "View/Edit Scores"
                          : "Continue Entry"}
                      </Button>
                    </Link>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
