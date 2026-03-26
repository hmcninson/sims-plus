"use client";

import { BarChart3, GraduationCap, Globe } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import type { DualTrackReportData } from "@/types/curriculum.type";

interface DualTrackReportViewerProps {
  data: DualTrackReportData;
  caWeight?: number;
  examWeight?: number;
  showPosition?: boolean;
}

export function DualTrackReportViewer({
  data,
  caWeight = 50,
  examWeight = 50,
  showPosition = true,
}: DualTrackReportViewerProps) {
  return (
    <div className="space-y-6">
      {/* Two-column layout on desktop, stacked on mobile */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* GES Results */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <GraduationCap className="h-5 w-5" />
              GES Results
            </CardTitle>
            <CardDescription>
              Ghana Education Service assessment
            </CardDescription>
          </CardHeader>
          <CardContent>
            {data.ges_results.length > 0 ? (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Subject</TableHead>
                      <TableHead className="text-center">
                        Class ({caWeight}%)
                      </TableHead>
                      <TableHead className="text-center">
                        Exam ({examWeight}%)
                      </TableHead>
                      <TableHead className="text-center">Total</TableHead>
                      <TableHead className="text-center">Grade</TableHead>
                      {showPosition && (
                        <TableHead className="hidden sm:table-cell text-center">
                          Pos.
                        </TableHead>
                      )}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.ges_results.map((subject, index) => (
                      <TableRow key={`ges-${index}`}>
                        <TableCell className="font-medium">
                          {subject.subject_name}
                        </TableCell>
                        <TableCell className="text-center">
                          {subject.class_score !== undefined
                            ? Number(subject.class_score).toFixed(1)
                            : "-"}
                        </TableCell>
                        <TableCell className="text-center">
                          {subject.exams_score !== undefined
                            ? Number(subject.exams_score).toFixed(1)
                            : "-"}
                        </TableCell>
                        <TableCell className="text-center font-semibold">
                          {subject.total_score !== undefined
                            ? Number(subject.total_score).toFixed(1)
                            : "-"}
                        </TableCell>
                        <TableCell className="text-center">
                          {subject.grade ? (
                            <Badge variant="outline">{subject.grade}</Badge>
                          ) : (
                            "-"
                          )}
                        </TableCell>
                        {showPosition && (
                          <TableCell className="hidden sm:table-cell text-center">
                            {subject.subject_position || "-"}
                          </TableCell>
                        )}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            ) : (
              <p className="py-8 text-center text-sm text-muted-foreground">
                No GES results available
              </p>
            )}
          </CardContent>
        </Card>

        {/* International Results */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Globe className="h-5 w-5" />
              {data.international_curriculum_name} Results
            </CardTitle>
            <CardDescription>
              International curriculum assessment
            </CardDescription>
          </CardHeader>
          <CardContent>
            {data.international_results.length > 0 ? (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Subject</TableHead>
                      {data.international_components.map((comp) => (
                        <TableHead key={comp.component_type} className="text-center">
                          <div className="text-xs">
                            <div>{comp.name}</div>
                            <div className="text-muted-foreground">
                              ({comp.weight}%)
                            </div>
                          </div>
                        </TableHead>
                      ))}
                      <TableHead className="text-center">Final</TableHead>
                      <TableHead className="text-center">Grade</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.international_results.map((subject, index) => (
                      <TableRow key={`intl-${index}`}>
                        <TableCell className="font-medium">
                          {subject.subject_name}
                        </TableCell>
                        {data.international_components.map((comp) => (
                          <TableCell
                            key={comp.component_type}
                            className="text-center"
                          >
                            {subject.component_scores?.[comp.component_type] !== undefined
                              ? Number(
                                  subject.component_scores[comp.component_type]
                                ).toFixed(1)
                              : "-"}
                          </TableCell>
                        ))}
                        <TableCell className="text-center font-semibold">
                          {subject.final_score !== undefined
                            ? Number(subject.final_score).toFixed(1)
                            : "-"}
                        </TableCell>
                        <TableCell className="text-center">
                          {subject.grade ? (
                            <Badge variant="outline">{subject.grade}</Badge>
                          ) : (
                            "-"
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            ) : (
              <p className="py-8 text-center text-sm text-muted-foreground">
                No international results available
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Combined Summary */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <BarChart3 className="h-5 w-5" />
            Combined Summary
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 md:grid-cols-4">
            <div className="rounded-lg border p-4">
              <p className="text-sm text-muted-foreground">GES Average</p>
              <p className="text-2xl font-bold">
                {data.ges_average !== undefined
                  ? `${Number(data.ges_average).toFixed(1)}%`
                  : "--"}
              </p>
            </div>
            {showPosition && (
              <div className="rounded-lg border p-4">
                <p className="text-sm text-muted-foreground">GES Position</p>
                <p className="text-2xl font-bold">
                  {data.ges_position || "--"}
                </p>
              </div>
            )}
            <div className="rounded-lg border p-4">
              <p className="text-sm text-muted-foreground">
                {data.international_curriculum_name} Average
              </p>
              <p className="text-2xl font-bold">
                {data.international_average !== undefined
                  ? `${Number(data.international_average).toFixed(1)}%`
                  : "--"}
              </p>
            </div>
            {data.gpa !== undefined && (
              <div className="rounded-lg border p-4">
                <p className="text-sm text-muted-foreground">GPA</p>
                <p className="text-2xl font-bold">
                  {Number(data.gpa).toFixed(2)}
                </p>
              </div>
            )}
            {data.ib_total_points !== undefined && (
              <div className="rounded-lg border p-4">
                <p className="text-sm text-muted-foreground">IB Total</p>
                <p className="text-2xl font-bold">
                  {data.ib_total_points}/45
                </p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
