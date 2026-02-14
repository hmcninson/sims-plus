"use client";

import { useEffect, useState, useTransition } from "react";
import Link from "next/link";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Wallet,
  Receipt,
  FileText,
  Award,
  TrendingUp,
  TrendingDown,
  AlertCircle,
  Plus,
  ArrowRight,
} from "lucide-react";
import { getFinanceDashboard } from "@/actions/finance.action";
import { getCurrentAcademicYear, getCurrentTerm } from "@/actions/academic.action";
import type { FinanceDashboard, AcademicYear, Term } from "@/types";
import { formatCurrency, formatDate } from "@/lib/format";

export function FinanceDashboard() {
  const [isPending, startTransition] = useTransition();
  const [dashboard, setDashboard] = useState<FinanceDashboard | null>(null);
  const [academicYear, setAcademicYear] = useState<AcademicYear | null>(null);
  const [term, setTerm] = useState<Term | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    startTransition(async () => {
      // Get current academic context
      const yearResult = await getCurrentAcademicYear();
      const termResult = await getCurrentTerm();

      if (yearResult.success && yearResult.data) {
        setAcademicYear(yearResult.data);
      }
      if (termResult.success && termResult.data) {
        setTerm(termResult.data);
      }

      // Get dashboard data
      const result = await getFinanceDashboard(
        yearResult.data?.id,
        termResult.data?.id
      );
      if (result.success && result.data) {
        setDashboard(result.data);
      } else {
        setError(result.error || "Failed to load dashboard");
      }
    });
  }, []);

  if (isPending && !dashboard) {
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
        <Button onClick={() => window.location.reload()}>Retry</Button>
      </div>
    );
  }

  const stats = dashboard?.stats;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Finance Overview</h1>
          <p className="text-muted-foreground">
            {academicYear?.name} - {term?.name || "All Terms"}
          </p>
        </div>
        <div className="flex gap-2">
          <Button asChild variant="outline">
            <Link href="/finance/invoices/generate">
              <FileText className="mr-2 h-4 w-4" />
              Generate Invoices
            </Link>
          </Button>
          <Button asChild>
            <Link href="/finance/payments/record">
              <Plus className="mr-2 h-4 w-4" />
              Record Payment
            </Link>
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Expected Revenue</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatCurrency(stats?.expected_revenue || 0)}
            </div>
            <p className="text-xs text-muted-foreground">
              Total invoiced this term
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Collected</CardTitle>
            <Wallet className="h-4 w-4 text-green-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {formatCurrency(stats?.collected_revenue || 0)}
            </div>
            <p className="text-xs text-muted-foreground">
              {stats?.total_payments || 0} payments received
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Outstanding</CardTitle>
            <TrendingDown className="h-4 w-4 text-orange-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-orange-600">
              {formatCurrency(stats?.outstanding_balance || 0)}
            </div>
            <p className="text-xs text-muted-foreground">
              {stats?.overdue_invoices || 0} overdue invoices
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Scholarships</CardTitle>
            <Award className="h-4 w-4 text-blue-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">
              {stats?.scholarship_recipients || 0}
            </div>
            <p className="text-xs text-muted-foreground">
              Active scholarship recipients
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Two Column Layout */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Recent Payments */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Recent Payments</CardTitle>
              <CardDescription>Latest payment transactions</CardDescription>
            </div>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/finance/payments">
                View All
                <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent>
            {dashboard?.recent_payments && dashboard.recent_payments.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Student</TableHead>
                    <TableHead>Amount</TableHead>
                    <TableHead>Method</TableHead>
                    <TableHead>Date</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {dashboard.recent_payments.map((payment) => (
                    <TableRow key={payment.id}>
                      <TableCell className="font-medium">
                        {payment.student_name}
                      </TableCell>
                      <TableCell>{formatCurrency(payment.amount)}</TableCell>
                      <TableCell className="capitalize">
                        {payment.payment_method.replace("_", " ")}
                      </TableCell>
                      <TableCell>
                        {formatDate(payment.payment_date)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <div className="flex h-[200px] items-center justify-center text-muted-foreground">
                No recent payments
              </div>
            )}
          </CardContent>
        </Card>

        {/* Outstanding by Class */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Outstanding by Class</CardTitle>
              <CardDescription>Balance breakdown by class</CardDescription>
            </div>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/finance/invoices?status=overdue">
                View Overdue
                <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent>
            {dashboard?.outstanding_by_class && dashboard.outstanding_by_class.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Class</TableHead>
                    <TableHead className="text-right">Students</TableHead>
                    <TableHead className="text-right">Outstanding</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {dashboard.outstanding_by_class.map((item) => (
                    <TableRow key={item.class_id}>
                      <TableCell className="font-medium">
                        {item.class_name}
                      </TableCell>
                      <TableCell className="text-right">
                        {item.student_count}
                      </TableCell>
                      <TableCell className="text-right text-orange-600">
                        {formatCurrency(item.total_outstanding)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <div className="flex h-[200px] items-center justify-center text-muted-foreground">
                No outstanding balances
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <CardTitle>Quick Actions</CardTitle>
          <CardDescription>Common finance tasks</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Button variant="outline" className="h-auto flex-col gap-2 p-4" asChild>
              <Link href="/finance/fee-structures">
                <Receipt className="h-6 w-6" />
                <span>Manage Fee Structures</span>
              </Link>
            </Button>
            <Button variant="outline" className="h-auto flex-col gap-2 p-4" asChild>
              <Link href="/finance/invoices/generate">
                <FileText className="h-6 w-6" />
                <span>Bulk Generate Invoices</span>
              </Link>
            </Button>
            <Button variant="outline" className="h-auto flex-col gap-2 p-4" asChild>
              <Link href="/finance/scholarships">
                <Award className="h-6 w-6" />
                <span>Manage Scholarships</span>
              </Link>
            </Button>
            <Button variant="outline" className="h-auto flex-col gap-2 p-4" asChild>
              <Link href="/finance/reports">
                <TrendingUp className="h-6 w-6" />
                <span>Financial Reports</span>
              </Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
