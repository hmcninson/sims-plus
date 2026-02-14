"use client";

import { useEffect, useState, useTransition } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  ArrowLeft,
  Award,
  AlertCircle,
  Plus,
  Percent,
  DollarSign,
  Calendar,
} from "lucide-react";
import { getStudent } from "@/actions/students.action";
import { getStudentScholarships } from "@/actions/finance.action";
import type { StudentWithGuardians, StudentScholarshipWithDetails } from "@/types";
import { formatCurrency, formatDate } from "@/lib/format";

export default function StudentScholarshipsPage() {
  const params = useParams();
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [student, setStudent] = useState<StudentWithGuardians | null>(null);
  const [scholarships, setScholarships] = useState<StudentScholarshipWithDetails[]>([]);
  const [error, setError] = useState<string | null>(null);

  const studentId = params.id as string;

  useEffect(() => {
    startTransition(async () => {
      const [studentResult, scholarshipsResult] = await Promise.all([
        getStudent(studentId),
        getStudentScholarships(studentId),
      ]);

      if (studentResult.success && studentResult.data) {
        setStudent(studentResult.data);
      } else {
        setError(studentResult.error || "Failed to load student");
        return;
      }

      if (scholarshipsResult.success && scholarshipsResult.data) {
        setScholarships(scholarshipsResult.data.items);
      }
    });
  }, [studentId]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case "active":
        return "bg-green-100 text-green-800";
      case "suspended":
        return "bg-yellow-100 text-yellow-800";
      case "revoked":
        return "bg-red-100 text-red-800";
      case "expired":
        return "bg-gray-100 text-gray-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  const getTypeColor = (type: string) => {
    switch (type) {
      case "full":
        return "bg-green-100 text-green-800";
      case "partial":
        return "bg-blue-100 text-blue-800";
      case "merit":
        return "bg-purple-100 text-purple-800";
      case "need_based":
        return "bg-orange-100 text-orange-800";
      case "athletic":
        return "bg-red-100 text-red-800";
      case "special":
        return "bg-gray-100 text-gray-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  if (isPending && !student) {
    return (
      <div className="flex h-[400px] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-[400px] flex-col items-center justify-center gap-4">
        <AlertCircle className="h-12 w-12 text-destructive" />
        <p className="text-muted-foreground">{error}</p>
        <Button onClick={() => router.push("/students")}>
          Back to Students
        </Button>
      </div>
    );
  }

  if (!student) return null;

  const fullName = student.middle_name
    ? `${student.first_name} ${student.middle_name} ${student.last_name}`
    : `${student.first_name} ${student.last_name}`;

  const activeScholarships = scholarships.filter((s) => s.status === "active");

  // Calculate total discount value
  const totalDiscount = activeScholarships.reduce((sum, s) => {
    if (s.coverage_type === "fixed_amount") {
      return sum + (s.coverage_override || s.coverage_value);
    }
    return sum; // Can't sum percentages
  }, 0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link href={`/students/${studentId}`}>
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              Scholarships
            </h1>
            <p className="text-muted-foreground">
              Scholarships for {fullName}
            </p>
          </div>
        </div>
        <Button asChild>
          <Link href="/finance/scholarships">
            <Plus className="mr-2 h-4 w-4" />
            View All Scholarships
          </Link>
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              Active Scholarships
            </CardTitle>
            <Award className="h-4 w-4 text-green-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {activeScholarships.length}
            </div>
            <p className="text-xs text-muted-foreground">
              of {scholarships.length} total
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              Fixed Discounts
            </CardTitle>
            <DollarSign className="h-4 w-4 text-blue-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">
              {formatCurrency(totalDiscount)}
            </div>
            <p className="text-xs text-muted-foreground">
              From fixed amount scholarships
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              Percentage Scholarships
            </CardTitle>
            <Percent className="h-4 w-4 text-purple-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-purple-600">
              {activeScholarships.filter((s) => s.coverage_type === "percentage").length}
            </div>
            <p className="text-xs text-muted-foreground">
              Active percentage discounts
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Scholarships Table */}
      <Card>
        <CardHeader>
          <CardTitle>Scholarship History</CardTitle>
          <CardDescription>
            All scholarships awarded to this student
          </CardDescription>
        </CardHeader>
        <CardContent>
          {scholarships.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Scholarship</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Coverage</TableHead>
                  <TableHead>Effective Period</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {scholarships.map((scholarship) => (
                  <TableRow key={scholarship.id}>
                    <TableCell>
                      <div>
                        <Link
                          href={`/finance/scholarships/${scholarship.scholarship_id}`}
                          className="font-medium hover:underline"
                        >
                          {scholarship.scholarship_name}
                        </Link>
                        <p className="text-xs text-muted-foreground">
                          {scholarship.scholarship_code}
                        </p>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant="secondary"
                        className={getTypeColor(scholarship.scholarship_type)}
                      >
                        {scholarship.scholarship_type.replace("_", " ")}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        {scholarship.coverage_type === "percentage" ? (
                          <Percent className="h-3 w-3 text-muted-foreground" />
                        ) : (
                          <DollarSign className="h-3 w-3 text-muted-foreground" />
                        )}
                        <span className="font-medium">
                          {scholarship.coverage_override
                            ? scholarship.coverage_type === "percentage"
                              ? `${scholarship.coverage_override}%`
                              : formatCurrency(scholarship.coverage_override)
                            : scholarship.coverage_type === "percentage"
                              ? `${scholarship.coverage_value}%`
                              : formatCurrency(scholarship.coverage_value)}
                        </span>
                        {scholarship.coverage_override && (
                          <span className="text-xs text-muted-foreground">
                            (override)
                          </span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1 text-sm">
                        <Calendar className="h-3 w-3 text-muted-foreground" />
                        {formatDate(scholarship.effective_from)}
                        {scholarship.effective_to && (
                          <>
                            <span className="text-muted-foreground">to</span>
                            {formatDate(scholarship.effective_to)}
                          </>
                        )}
                        {!scholarship.effective_to && (
                          <span className="text-xs text-muted-foreground">
                            (ongoing)
                          </span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant="secondary"
                        className={getStatusColor(scholarship.status)}
                      >
                        {scholarship.status}
                      </Badge>
                      {scholarship.status === "revoked" && scholarship.revoke_reason && (
                        <p className="text-xs text-muted-foreground mt-1">
                          Reason: {scholarship.revoke_reason}
                        </p>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="flex h-[200px] flex-col items-center justify-center gap-2 text-muted-foreground">
              <Award className="h-12 w-12" />
              <p>No scholarships awarded yet</p>
              <p className="text-sm text-center max-w-md">
                Scholarships can be awarded from the{" "}
                <Link href="/finance/scholarships" className="text-primary hover:underline">
                  Scholarships page
                </Link>
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Notes about scholarships */}
      {activeScholarships.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">How Scholarship Discounts Work</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground space-y-2">
            <p>
              Active scholarships are automatically applied when generating invoices for this student.
            </p>
            <ul className="list-disc list-inside space-y-1">
              <li>
                <strong>Percentage scholarships</strong> reduce the invoice subtotal by the specified percentage.
              </li>
              <li>
                <strong>Fixed amount scholarships</strong> deduct a specific amount from the invoice total.
              </li>
              <li>
                Multiple scholarships can be combined, with percentage discounts applied first.
              </li>
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
