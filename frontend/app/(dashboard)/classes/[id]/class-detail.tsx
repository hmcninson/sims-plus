"use client";

import { useMemo } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Users,
  BookOpen,
  UserCheck,
  Clock,
  GraduationCap,
  ChevronRight,
  Pencil,
  LayoutGrid,
} from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";

import type { Class, ClassSection, ClassSubject, SubjectCategory } from "@/types";

// Level display configuration
const LEVEL_CONFIG: Record<string, { label: string; color: string }> = {
  preschool: { label: "Preschool", color: "bg-amber-500" },
  primary: { label: "Primary", color: "bg-blue-500" },
  jhs: { label: "JHS", color: "bg-green-500" },
  shs: { label: "SHS", color: "bg-rose-500" },
};

const CATEGORY_CONFIG: Record<SubjectCategory, { label: string; color: string }> = {
  core: { label: "Core", color: "bg-blue-500" },
  elective: { label: "Elective", color: "bg-green-500" },
  vocational: { label: "Vocational", color: "bg-amber-500" },
  extra: { label: "Extra", color: "bg-purple-500" },
};

interface ClassDetailProps {
  classData: Class;
  sections: ClassSection[];
  classSubjects: ClassSubject[];
}

export function ClassDetail({ classData, sections, classSubjects }: ClassDetailProps) {
  // Compute stats
  const stats = useMemo(() => {
    const totalStudents = classData.student_count || 0;
    const maleStudents = classData.male_count || 0;
    const femaleStudents = classData.female_count || 0;
    const totalSections = sections.length;
    const activeSections = sections.filter((s) => s.is_active).length;
    const totalSubjects = classSubjects.length;
    const compulsorySubjects = classSubjects.filter((cs) => cs.is_compulsory).length;
    const optionalSubjects = totalSubjects - compulsorySubjects;
    const totalCapacity = classData.capacity || 0;
    const capacityPercent = totalCapacity > 0 ? Math.round((totalStudents / totalCapacity) * 100) : 0;
    const averageClassSize = totalSections > 0 ? Math.round(totalStudents / totalSections) : totalStudents;

    return {
      totalStudents,
      maleStudents,
      femaleStudents,
      totalSections,
      activeSections,
      totalSubjects,
      compulsorySubjects,
      optionalSubjects,
      totalCapacity,
      capacityPercent,
      averageClassSize,
    };
  }, [classData, sections, classSubjects]);

  const levelConfig = classData.level ? LEVEL_CONFIG[classData.level] : null;

  return (
    <div className="space-y-6">
      {/* Header with back button */}
      <div className="flex items-center gap-4">
        <Link href="/classes">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-2xl font-bold tracking-tight">{classData.name}</h1>
            {classData.short_name && (
              <Badge variant="outline">{classData.short_name}</Badge>
            )}
            {levelConfig && (
              <Badge className={`${levelConfig.color} text-white`}>
                {levelConfig.label}
              </Badge>
            )}
            {!classData.is_active && (
              <Badge variant="secondary">Inactive</Badge>
            )}
          </div>
          <p className="text-muted-foreground">
            Class overview, sections, subjects, and teacher assignments.
          </p>
        </div>
        <div className="hidden sm:flex items-center gap-2">
          <Button variant="outline" size="sm" asChild>
            <Link href={`/classes/${classData.id}/subjects`}>
              <BookOpen className="mr-2 h-4 w-4" />
              Manage Subjects
            </Link>
          </Button>
          <Button variant="outline" size="sm" asChild>
            <Link href={`/classes/${classData.id}/teachers`}>
              <UserCheck className="mr-2 h-4 w-4" />
              Manage Teachers
            </Link>
          </Button>
        </div>
      </div>

      {/* Overview Stats Cards */}
      <div className="grid gap-4 grid-cols-2 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center gap-1">
              <Users className="h-3.5 w-3.5" />
              Total Students
            </CardDescription>
            <CardTitle className="text-3xl">{stats.totalStudents}</CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <p className="text-xs text-muted-foreground">
              {stats.maleStudents} male, {stats.femaleStudents} female
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center gap-1">
              <LayoutGrid className="h-3.5 w-3.5" />
              Sections
            </CardDescription>
            <CardTitle className="text-3xl">{stats.totalSections}</CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <p className="text-xs text-muted-foreground">
              {stats.activeSections} active
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center gap-1">
              <BookOpen className="h-3.5 w-3.5" />
              Subjects
            </CardDescription>
            <CardTitle className="text-3xl">{stats.totalSubjects}</CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <p className="text-xs text-muted-foreground">
              {stats.compulsorySubjects} core, {stats.optionalSubjects} elective
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center gap-1">
              <GraduationCap className="h-3.5 w-3.5" />
              Avg. Class Size
            </CardDescription>
            <CardTitle className="text-3xl">{stats.averageClassSize}</CardTitle>
          </CardHeader>
          {stats.totalCapacity > 0 && (
            <CardContent className="pt-0 space-y-1">
              <Progress
                value={Math.min(stats.capacityPercent, 100)}
                className="h-1.5"
              />
              <p className="text-xs text-muted-foreground">
                {stats.totalStudents} / {stats.totalCapacity} capacity ({stats.capacityPercent}%)
              </p>
            </CardContent>
          )}
        </Card>
      </div>

      {/* Mobile quick actions */}
      <div className="flex sm:hidden gap-2">
        <Button variant="outline" size="sm" className="flex-1" asChild>
          <Link href={`/classes/${classData.id}/subjects`}>
            <BookOpen className="mr-2 h-4 w-4" />
            Subjects
          </Link>
        </Button>
        <Button variant="outline" size="sm" className="flex-1" asChild>
          <Link href={`/classes/${classData.id}/teachers`}>
            <UserCheck className="mr-2 h-4 w-4" />
            Teachers
          </Link>
        </Button>
        <Button variant="outline" size="sm" className="flex-1" asChild>
          <Link href={`/classes/timetable?class=${classData.id}`}>
            <Clock className="mr-2 h-4 w-4" />
            Timetable
          </Link>
        </Button>
      </div>

      {/* Tabbed Content */}
      <Tabs defaultValue="sections" className="space-y-4">
        <TabsList>
          <TabsTrigger value="sections">
            <LayoutGrid className="mr-2 h-4 w-4" />
            Sections ({stats.totalSections})
          </TabsTrigger>
          <TabsTrigger value="subjects">
            <BookOpen className="mr-2 h-4 w-4" />
            Subjects ({stats.totalSubjects})
          </TabsTrigger>
        </TabsList>

        {/* Sections Tab */}
        <TabsContent value="sections" className="space-y-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
              <div>
                <CardTitle>Class Sections</CardTitle>
                <CardDescription>
                  Sections within {classData.name} and their enrollment status.
                </CardDescription>
              </div>
              <Button variant="outline" size="sm" asChild>
                <Link href="/classes">
                  <Pencil className="mr-2 h-4 w-4" />
                  Edit Sections
                </Link>
              </Button>
            </CardHeader>
            <CardContent>
              {sections.length === 0 ? (
                <div className="text-center py-12">
                  <LayoutGrid className="mx-auto h-12 w-12 text-muted-foreground/50" />
                  <h3 className="mt-4 text-lg font-semibold">No sections yet</h3>
                  <p className="text-muted-foreground">
                    Create sections to organize students within this class.
                  </p>
                  <Button className="mt-4" asChild>
                    <Link href="/classes">
                      Go to Classes to Add Sections
                    </Link>
                  </Button>
                </div>
              ) : (
                <div className="rounded-md border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Section</TableHead>
                        <TableHead>Students</TableHead>
                        <TableHead className="hidden sm:table-cell">Male</TableHead>
                        <TableHead className="hidden sm:table-cell">Female</TableHead>
                        <TableHead>Capacity</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead className="w-[100px]">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {sections.map((section) => {
                        const sectionStudents = section.student_count || 0;
                        const sectionCapacity = section.capacity || 0;
                        const sectionPercent = sectionCapacity > 0
                          ? Math.round((sectionStudents / sectionCapacity) * 100)
                          : 0;

                        return (
                          <TableRow key={section.id}>
                            <TableCell className="font-medium">{section.name}</TableCell>
                            <TableCell>
                              <span className="font-medium">{sectionStudents}</span>
                            </TableCell>
                            <TableCell className="hidden sm:table-cell">
                              {section.male_count || 0}
                            </TableCell>
                            <TableCell className="hidden sm:table-cell">
                              {section.female_count || 0}
                            </TableCell>
                            <TableCell>
                              {sectionCapacity > 0 ? (
                                <div className="flex items-center gap-2">
                                  <Progress
                                    value={Math.min(sectionPercent, 100)}
                                    className="h-1.5 w-16"
                                  />
                                  <span className="text-xs text-muted-foreground">
                                    {sectionStudents}/{sectionCapacity}
                                  </span>
                                </div>
                              ) : (
                                <span className="text-xs text-muted-foreground">No limit</span>
                              )}
                            </TableCell>
                            <TableCell>
                              <Badge variant={section.is_active ? "default" : "secondary"}>
                                {section.is_active ? "Active" : "Inactive"}
                              </Badge>
                            </TableCell>
                            <TableCell>
                              <Button variant="ghost" size="sm" asChild>
                                <Link href={`/students?class_id=${classData.id}&section_id=${section.id}`}>
                                  <Users className="mr-1 h-3.5 w-3.5" />
                                  View
                                </Link>
                              </Button>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
              )}

              {/* Unassigned students warning */}
              {sections.length > 0 && (() => {
                const assignedToSections = sections.reduce(
                  (sum, s) => sum + (s.student_count || 0),
                  0
                );
                const unassigned = stats.totalStudents - assignedToSections;
                if (unassigned > 0) {
                  return (
                    <div className="mt-4 flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950 p-3 text-sm text-amber-700 dark:text-amber-400">
                      <Users className="h-4 w-4 shrink-0" />
                      <span>
                        <strong>{unassigned}</strong> student{unassigned !== 1 ? "s" : ""} enrolled in this class but not assigned to any section.
                      </span>
                    </div>
                  );
                }
                return null;
              })()}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Subjects Tab */}
        <TabsContent value="subjects" className="space-y-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
              <div>
                <CardTitle>Assigned Subjects</CardTitle>
                <CardDescription>
                  Subjects taught in {classData.name}. Students will be examined on these.
                </CardDescription>
              </div>
              <Button variant="outline" size="sm" asChild>
                <Link href={`/classes/${classData.id}/subjects`}>
                  <Pencil className="mr-2 h-4 w-4" />
                  Manage Subjects
                </Link>
              </Button>
            </CardHeader>
            <CardContent>
              {classSubjects.length === 0 ? (
                <div className="text-center py-12">
                  <BookOpen className="mx-auto h-12 w-12 text-muted-foreground/50" />
                  <h3 className="mt-4 text-lg font-semibold">No subjects assigned</h3>
                  <p className="text-muted-foreground">
                    Add subjects to enable examinations and grading.
                  </p>
                  <Button className="mt-4" asChild>
                    <Link href={`/classes/${classData.id}/subjects`}>
                      <BookOpen className="mr-2 h-4 w-4" />
                      Add Subjects
                    </Link>
                  </Button>
                </div>
              ) : (
                <div className="rounded-md border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Code</TableHead>
                        <TableHead>Subject Name</TableHead>
                        <TableHead>Category</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead className="hidden sm:table-cell">Periods/Week</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {classSubjects.map((cs) => {
                        const subject = cs.subject;
                        const category = subject?.category || "core";
                        const categoryConfig = CATEGORY_CONFIG[category as SubjectCategory];

                        return (
                          <TableRow key={cs.id}>
                            <TableCell className="font-mono font-medium text-sm">
                              {subject?.code || "---"}
                            </TableCell>
                            <TableCell className="font-medium">
                              {subject?.name || "Unknown Subject"}
                            </TableCell>
                            <TableCell>
                              {categoryConfig && (
                                <Badge className={`${categoryConfig.color} text-white`}>
                                  {categoryConfig.label}
                                </Badge>
                              )}
                            </TableCell>
                            <TableCell>
                              <Badge variant={cs.is_compulsory ? "default" : "secondary"}>
                                {cs.is_compulsory ? "Compulsory" : "Optional"}
                              </Badge>
                            </TableCell>
                            <TableCell className="hidden sm:table-cell">
                              {cs.periods_per_week || "-"}
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Quick Links */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Quick Links</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <Link
            href={`/students?class_id=${classData.id}`}
            className="flex items-center justify-between rounded-lg border p-3 hover:bg-muted/50 transition-colors"
          >
            <div className="flex items-center gap-3">
              <Users className="h-5 w-5 text-muted-foreground" />
              <div>
                <p className="text-sm font-medium">View Students</p>
                <p className="text-xs text-muted-foreground">{stats.totalStudents} enrolled</p>
              </div>
            </div>
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          </Link>

          <Link
            href={`/classes/${classData.id}/subjects`}
            className="flex items-center justify-between rounded-lg border p-3 hover:bg-muted/50 transition-colors"
          >
            <div className="flex items-center gap-3">
              <BookOpen className="h-5 w-5 text-muted-foreground" />
              <div>
                <p className="text-sm font-medium">Manage Subjects</p>
                <p className="text-xs text-muted-foreground">{stats.totalSubjects} assigned</p>
              </div>
            </div>
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          </Link>

          <Link
            href={`/classes/${classData.id}/teachers`}
            className="flex items-center justify-between rounded-lg border p-3 hover:bg-muted/50 transition-colors"
          >
            <div className="flex items-center gap-3">
              <UserCheck className="h-5 w-5 text-muted-foreground" />
              <div>
                <p className="text-sm font-medium">Teacher Assignments</p>
                <p className="text-xs text-muted-foreground">{stats.totalSections} section(s)</p>
              </div>
            </div>
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          </Link>

          <Link
            href="/classes/timetable"
            className="flex items-center justify-between rounded-lg border p-3 hover:bg-muted/50 transition-colors"
          >
            <div className="flex items-center gap-3">
              <Clock className="h-5 w-5 text-muted-foreground" />
              <div>
                <p className="text-sm font-medium">Class Timetable</p>
                <p className="text-xs text-muted-foreground">View weekly schedule</p>
              </div>
            </div>
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}
