"use client";

import { useState, useTransition, useEffect, useMemo } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  Search,
  Trophy,
  Medal,
  Award,
  BarChart3,
  Users,
  Loader2,
  TrendingUp,
  TrendingDown,
  GraduationCap,
  Layers,
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
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";

import { getClassResults } from "@/actions/exams.action";
import type {
  ExamWithContext,
  ClassResultsResponse,
  StudentExamResult,
  SubjectResult,
} from "@/types";

interface ExamResultsProps {
  exam: ExamWithContext;
  classes: { id: string; name: string }[];
}

const POSITION_ICONS: Record<number, { icon: React.ElementType; color: string }> = {
  1: { icon: Trophy, color: "text-yellow-500" },
  2: { icon: Medal, color: "text-gray-400" },
  3: { icon: Award, color: "text-amber-600" },
};

export function ExamResults({ exam, classes }: ExamResultsProps) {
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();

  // Get initial class from URL query parameter or default to first class
  const initialClassId = searchParams.get("class") || classes[0]?.id || "";

  // Selection state
  const [selectedClassId, setSelectedClassId] = useState(initialClassId);
  const [selectedSectionId, setSelectedSectionId] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");

  // Results state
  const [results, setResults] = useState<ClassResultsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Get unique sections from results
  const sections = useMemo(() => {
    if (!results?.students) return [];
    const sectionMap = new Map<string, string>();
    for (const student of results.students) {
      if (student.section_name) {
        // Use section_name as both ID and name since we don't have section_id in results
        sectionMap.set(student.section_name, student.section_name);
      }
    }
    return Array.from(sectionMap.entries()).map(([id, name]) => ({ id, name }));
  }, [results?.students]);

  // Load results when class changes
  useEffect(() => {
    if (selectedClassId) {
      setSelectedSectionId("all"); // Reset section when class changes
      loadResults();
    } else {
      setResults(null);
    }
  }, [selectedClassId]);

  const loadResults = async () => {
    startTransition(async () => {
      setError(null);
      const result = await getClassResults(exam.id, selectedClassId);
      if (result.success && result.data) {
        setResults(result.data);
      } else {
        setError(result.error || "Failed to load results");
        setResults(null);
      }
    });
  };

  // Get all unique subjects from results for column headers
  const allSubjects: { id: string; name: string; code?: string }[] = [];
  if (results?.students && results.students.length > 0) {
    const subjectMap = new Map<string, { id: string; name: string; code?: string }>();
    for (const student of results.students) {
      for (const subject of student.subjects || []) {
        if (!subjectMap.has(subject.subject_id)) {
          subjectMap.set(subject.subject_id, {
            id: subject.subject_id,
            name: subject.subject_name,
            code: subject.subject_code,
          });
        }
      }
    }
    allSubjects.push(...Array.from(subjectMap.values()));
  }

  // Filter results by search and section
  const filteredResults =
    results?.students.filter((r) => {
      // Filter by section
      if (selectedSectionId !== "all" && r.section_name !== selectedSectionId) {
        return false;
      }
      // Filter by search
      if (searchQuery) {
        return (
          r.student_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          r.student_id_number.toLowerCase().includes(searchQuery.toLowerCase())
        );
      }
      return true;
    }) || [];

  const getPositionBadge = (position: number) => {
    const config = POSITION_ICONS[position];
    if (config) {
      const Icon = config.icon;
      return (
        <div className="flex items-center gap-1">
          <Icon className={`h-4 w-4 ${config.color}`} />
          <span className="font-bold">{position}</span>
        </div>
      );
    }
    return <span className="font-medium">{position}</span>;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href={`/exams/${exam.id}`}>
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold tracking-tight">{exam.name} - Results</h1>
          <p className="text-muted-foreground">
            {exam.academic_year_name} - {exam.term_name}
          </p>
        </div>
      </div>

      {/* Class & Section Selection */}
      <div className="flex flex-wrap items-center gap-4 p-4 rounded-lg border bg-card">
        <div className="flex items-center gap-2">
          <GraduationCap className="h-5 w-5 text-muted-foreground" />
          <span className="text-sm font-medium">Class:</span>
        </div>
        <Select value={selectedClassId} onValueChange={setSelectedClassId}>
          <SelectTrigger className="w-full sm:w-[200px]">
            <SelectValue placeholder="Select a class" />
          </SelectTrigger>
          <SelectContent>
            {classes.map((c) => (
              <SelectItem key={c.id} value={c.id}>
                {c.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {sections.length > 0 && (
          <>
            <div className="flex items-center gap-2">
              <Layers className="h-5 w-5 text-muted-foreground" />
              <span className="text-sm font-medium">Section:</span>
            </div>
            <Select value={selectedSectionId} onValueChange={setSelectedSectionId}>
              <SelectTrigger className="w-full sm:w-[150px]">
                <SelectValue placeholder="All sections" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Sections</SelectItem>
                {sections.map((s) => (
                  <SelectItem key={s.id} value={s.id}>
                    {s.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </>
        )}

        <span className="text-sm text-muted-foreground ml-auto">
          {classes.length} classes available
        </span>
      </div>

      {/* Loading State */}
      {isPending && (
        <div className="flex h-64 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      )}

      {/* Error State */}
      {error && !isPending && (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">{error}</p>
          </CardContent>
        </Card>
      )}

      {/* No Classes */}
      {classes.length === 0 && !isPending && (
        <Card>
          <CardContent className="py-12 text-center">
            <BarChart3 className="mx-auto h-12 w-12 text-muted-foreground/50" />
            <h3 className="mt-4 text-lg font-semibold">No subjects added</h3>
            <p className="text-muted-foreground">
              Add subjects to this exam to view results.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Results */}
      {results && !isPending && (
        <>
          {/* Summary Stats */}
          <div className="grid gap-4 md:grid-cols-4">
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Total Students</CardDescription>
                <CardTitle className="text-2xl flex items-center gap-2">
                  <Users className="h-5 w-5 text-muted-foreground" />
                  {results.students?.length || 0}
                </CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Class Average</CardDescription>
                <CardTitle className="text-2xl flex items-center gap-2 text-blue-600">
                  <BarChart3 className="h-5 w-5" />
                  {Number(results.class_average || 0).toFixed(1)}%
                </CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Highest Score</CardDescription>
                <CardTitle className="text-2xl flex items-center gap-2 text-green-600">
                  <TrendingUp className="h-5 w-5" />
                  {Number(results.highest_score || 0).toFixed(1)}%
                </CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Lowest Score</CardDescription>
                <CardTitle className="text-2xl flex items-center gap-2 text-red-600">
                  <TrendingDown className="h-5 w-5" />
                  {Number(results.lowest_score || 0).toFixed(1)}%
                </CardTitle>
              </CardHeader>
            </Card>
          </div>

          {/* Results Table */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Class Rankings - {results.class_name}</CardTitle>
                <CardDescription>
                  Students ranked by total score across {allSubjects.length} subjects
                </CardDescription>
              </div>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search students..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9 w-full sm:w-[250px]"
                />
              </div>
            </CardHeader>
            <CardContent>
              {filteredResults.length === 0 ? (
                <div className="text-center py-12">
                  <BarChart3 className="mx-auto h-12 w-12 text-muted-foreground/50" />
                  <h3 className="mt-4 text-lg font-semibold">No results found</h3>
                  <p className="text-muted-foreground">
                    {results.students?.length === 0
                      ? "No scores have been entered for this class yet."
                      : "No students match your search."}
                  </p>
                </div>
              ) : (
                <ScrollArea className="w-full">
                  <div className="min-w-max">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-[80px] sticky left-0 bg-background z-10">Pos</TableHead>
                          <TableHead className="min-w-[200px] sticky left-[80px] bg-background z-10">Student</TableHead>
                          {allSubjects.map((subject) => (
                            <TableHead key={subject.id} className="text-center min-w-[70px]">
                              {subject.code || subject.name.slice(0, 4)}
                            </TableHead>
                          ))}
                          <TableHead className="text-center min-w-[80px]">Total</TableHead>
                          <TableHead className="text-center min-w-[80px]">Avg</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {filteredResults
                          .sort((a, b) => {
                            // Sort by section position when filtering by section
                            if (selectedSectionId !== "all") {
                              const aPos = a.section_position ?? a.class_position;
                              const bPos = b.section_position ?? b.class_position;
                              return aPos - bPos;
                            }
                            return a.class_position - b.class_position;
                          })
                          .map((student) => (
                            <TableRow key={student.student_id}>
                              <TableCell className="sticky left-0 bg-background z-10">
                                <div className="flex flex-col">
                                  {getPositionBadge(
                                    selectedSectionId !== "all" && student.section_position
                                      ? student.section_position
                                      : student.class_position
                                  )}
                                  {selectedSectionId !== "all" && student.section_position && (
                                    <span className="text-[10px] text-muted-foreground">
                                      Class: {student.class_position}
                                    </span>
                                  )}
                                </div>
                              </TableCell>
                              <TableCell className="sticky left-[80px] bg-background z-10">
                                <div className="flex items-center gap-3">
                                  <Avatar className="h-8 w-8">
                                    <AvatarFallback>
                                      {student.student_name
                                        .split(" ")
                                        .map((n) => n[0])
                                        .join("")
                                        .slice(0, 2)}
                                    </AvatarFallback>
                                  </Avatar>
                                  <div>
                                    <p className="font-medium text-sm">
                                      {student.student_name}
                                    </p>
                                    <div className="flex items-center gap-1 text-xs text-muted-foreground">
                                      <span>{student.student_id_number}</span>
                                      {student.section_name && (
                                        <>
                                          <span>•</span>
                                          <span>{student.section_name}</span>
                                        </>
                                      )}
                                    </div>
                                  </div>
                                </div>
                              </TableCell>
                              {allSubjects.map((subject) => {
                                const subjectResult = student.subjects?.find(
                                  (s) => s.subject_id === subject.id
                                );
                                return (
                                  <TableCell key={subject.id} className="text-center">
                                    {subjectResult ? (
                                      <div className="flex flex-col items-center">
                                        <span className="text-sm">
                                          {subjectResult.total_score != null
                                            ? Number(subjectResult.total_score).toFixed(0)
                                            : "-"}
                                        </span>
                                        {subjectResult.grade && (
                                          <span className="text-xs text-muted-foreground">
                                            {subjectResult.grade}
                                          </span>
                                        )}
                                      </div>
                                    ) : (
                                      <span className="text-muted-foreground">-</span>
                                    )}
                                  </TableCell>
                                );
                              })}
                              <TableCell className="text-center font-semibold">
                                {Number(student.total_score || 0).toFixed(0)}
                              </TableCell>
                              <TableCell className="text-center">
                                <Badge
                                  variant={
                                    Number(student.average_score) >= 70
                                      ? "default"
                                      : Number(student.average_score) >= 50
                                      ? "secondary"
                                      : "destructive"
                                  }
                                >
                                  {Number(student.average_score || 0).toFixed(1)}%
                                </Badge>
                              </TableCell>
                            </TableRow>
                          ))}
                      </TableBody>
                    </Table>
                  </div>
                  <ScrollBar orientation="horizontal" />
                </ScrollArea>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
