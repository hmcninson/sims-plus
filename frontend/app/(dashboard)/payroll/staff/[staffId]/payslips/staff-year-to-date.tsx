"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Download,
  Loader2,
  TrendingUp,
  AlertCircle,
  FileText,
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { toast } from "sonner";
import { getYearToDate } from "@/actions/payroll.action";
import { formatGHS } from "@/lib/format";
import type { YearToDateReport } from "@/types/payroll.type";

const currentYear = new Date().getFullYear();

interface StaffYearToDateProps {
  staffId: string;
}

export function StaffYearToDate({ staffId }: StaffYearToDateProps) {
  const [year, setYear] = useState(String(currentYear));
  const [data, setData] = useState<YearToDateReport | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [downloadingMonth, setDownloadingMonth] = useState<number | null>(null);

  const years = Array.from({ length: 5 }, (_, i) => String(currentYear - i));

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    const result = await getYearToDate(staffId, Number(year));
    setIsLoading(false);
    if (result.success) {
      setData(result.data);
    } else {
      toast.error(result.error);
    }
  }, [staffId, year]);

  function handleDownloadPayslip(payslipUrl: string | null, month: number) {
    if (!payslipUrl) {
      toast.error("Payslip not available for this month");
      return;
    }
    setDownloadingMonth(month);
    window.open(payslipUrl, "_blank");
    setTimeout(() => setDownloadingMonth(null), 1000);
  }

  const chartData = data?.entries.map((entry) => ({
    month: entry.month_name.slice(0, 3),
    gross: entry.gross_salary,
    net: entry.net_salary,
    paye: entry.paye_tax,
  })) ?? [];

  // Running cumulative totals for display
  let cumulativeGross = 0;
  let cumulativePaye = 0;
  let cumulativeSsnit = 0;
  let cumulativeNet = 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" asChild>
            <Link href={`/payroll/staff/${staffId}/salary`}>
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              {data ? data.staff_name : "Staff"} - Year to Date
            </h1>
            {data && (
              <p className="text-sm text-muted-foreground">{data.staff_code}</p>
            )}
          </div>
        </div>

        <div className="flex items-end gap-3">
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Year</label>
            <Select value={year} onValueChange={setYear}>
              <SelectTrigger className="w-full sm:w-[120px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {years.map((y) => (
                  <SelectItem key={y} value={y}>{y}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button onClick={fetchData} disabled={isLoading} className="gap-1.5">
            {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <TrendingUp className="h-4 w-4" />}
            {isLoading ? "Loading..." : "Fetch"}
          </Button>
        </div>
      </div>

      {isLoading && (
        <div className="space-y-6">
          <Skeleton className="h-[300px] w-full" />
          <Skeleton className="h-[400px] w-full" />
        </div>
      )}

      {data && !isLoading && (
        <>
          {/* Net Salary Trend Chart */}
          {chartData.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Salary Trend - {year}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                      <XAxis dataKey="month" tick={{ fontSize: 12 }} />
                      <YAxis tick={{ fontSize: 12 }} tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}k`} />
                      <Tooltip
                        content={({ active, payload, label }) => {
                          if (!active || !payload?.length) return null;
                          return (
                            <div className="rounded-lg border bg-background p-3 shadow-md">
                              <p className="text-sm font-medium mb-1">{label}</p>
                              {payload.map((p) => (
                                <p key={p.dataKey as string} className="text-xs" style={{ color: p.color }}>
                                  {p.name}: {formatGHS(p.value as number)}
                                </p>
                              ))}
                            </div>
                          );
                        }}
                      />
                      <Legend />
                      <Line type="monotone" dataKey="gross" name="Gross" stroke="#3b82f6" strokeWidth={2} dot={{ r: 3 }} />
                      <Line type="monotone" dataKey="net" name="Net" stroke="#10b981" strokeWidth={2} dot={{ r: 3 }} />
                      <Line type="monotone" dataKey="paye" name="PAYE" stroke="#f59e0b" strokeWidth={2} dot={{ r: 3 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Monthly Breakdown Table */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Monthly Breakdown - {year}</CardTitle>
            </CardHeader>
            <CardContent>
              {data.entries.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-8 text-center">
                  <FileText className="h-10 w-10 text-muted-foreground mb-3" />
                  <p className="text-sm text-muted-foreground">No payroll data for {year}</p>
                </div>
              ) : (
                <div className="overflow-x-auto -mx-6">
                  <div className="min-w-[800px] px-6">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Month</TableHead>
                          <TableHead className="text-right">Gross</TableHead>
                          <TableHead className="text-right">PAYE</TableHead>
                          <TableHead className="text-right">SSNIT</TableHead>
                          <TableHead className="text-right">Deductions</TableHead>
                          <TableHead className="text-right">Net Pay</TableHead>
                          <TableHead className="text-right w-[80px]">Payslip</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {data.entries.map((entry) => {
                          cumulativeGross += entry.gross_salary;
                          cumulativePaye += entry.paye_tax;
                          cumulativeSsnit += entry.ssnit_employee;
                          cumulativeNet += entry.net_salary;
                          return (
                            <TableRow key={entry.month}>
                              <TableCell className="text-sm font-medium">{entry.month_name}</TableCell>
                              <TableCell className="text-right text-sm">{formatGHS(entry.gross_salary)}</TableCell>
                              <TableCell className="text-right text-sm">{formatGHS(entry.paye_tax)}</TableCell>
                              <TableCell className="text-right text-sm">{formatGHS(entry.ssnit_employee)}</TableCell>
                              <TableCell className="text-right text-sm">{formatGHS(entry.total_deductions)}</TableCell>
                              <TableCell className="text-right text-sm font-medium">{formatGHS(entry.net_salary)}</TableCell>
                              <TableCell className="text-right">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleDownloadPayslip(entry.payslip_url, entry.month)}
                                  disabled={downloadingMonth === entry.month || !entry.payslip_url}
                                  className="h-7 w-7 p-0"
                                >
                                  {downloadingMonth === entry.month ? (
                                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                  ) : (
                                    <Download className="h-3.5 w-3.5" />
                                  )}
                                </Button>
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                      <TableFooter>
                        <TableRow>
                          <TableCell className="font-semibold">YTD Totals</TableCell>
                          <TableCell className="text-right font-semibold">{formatGHS(data.totals.gross_salary)}</TableCell>
                          <TableCell className="text-right font-semibold">{formatGHS(data.totals.paye_tax)}</TableCell>
                          <TableCell className="text-right font-semibold">{formatGHS(data.totals.ssnit_employee)}</TableCell>
                          <TableCell className="text-right font-semibold">{formatGHS(data.totals.total_deductions)}</TableCell>
                          <TableCell className="text-right font-semibold">{formatGHS(data.totals.net_salary)}</TableCell>
                          <TableCell />
                        </TableRow>
                      </TableFooter>
                    </Table>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}

      {!data && !isLoading && (
        <Card>
          <CardContent className="p-8 text-center">
            <TrendingUp className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
            <p className="text-sm text-muted-foreground">
              Select a year and click "Fetch" to view the year-to-date salary breakdown.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
