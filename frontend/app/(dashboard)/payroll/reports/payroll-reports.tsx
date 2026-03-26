"use client";

import { useState, useCallback } from "react";
import {
  FileText,
  Download,
  Loader2,
  BarChart3,
  Shield,
  Receipt,
  Building2,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart as RechartsPieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
import {
  getMonthlySummary,
  getSSNITReturns,
  exportSSNITReturns,
  getPAYEReturns,
  exportPAYEReturns,
  getDepartmentSummary,
} from "@/actions/payroll.action";
import { formatGHS } from "@/lib/format";
import type {
  MonthlySummary,
  SSNITReturnReport,
  PAYEReturnReport,
  DepartmentSummaryReport,
} from "@/types/payroll.type";

const MONTH_OPTIONS = [
  { value: "1", label: "January" },
  { value: "2", label: "February" },
  { value: "3", label: "March" },
  { value: "4", label: "April" },
  { value: "5", label: "May" },
  { value: "6", label: "June" },
  { value: "7", label: "July" },
  { value: "8", label: "August" },
  { value: "9", label: "September" },
  { value: "10", label: "October" },
  { value: "11", label: "November" },
  { value: "12", label: "December" },
];

const PAYMENT_METHOD_COLORS = [
  "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4",
];

const DEPARTMENT_COLORS = [
  "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
  "#06b6d4", "#f97316", "#ec4899", "#84cc16", "#6366f1",
];

const currentDate = new Date();
const currentYear = currentDate.getFullYear();
const currentMonth = currentDate.getMonth() + 1;

function YearMonthSelector({
  year,
  month,
  onYearChange,
  onMonthChange,
  onFetch,
  isLoading,
}: {
  year: string;
  month: string;
  onYearChange: (v: string) => void;
  onMonthChange: (v: string) => void;
  onFetch: () => void;
  isLoading: boolean;
}) {
  const years = Array.from({ length: 5 }, (_, i) => String(currentYear - i));

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
      <div className="space-y-1.5">
        <label className="text-sm font-medium">Year</label>
        <Select value={year} onValueChange={onYearChange}>
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
      <div className="space-y-1.5">
        <label className="text-sm font-medium">Month</label>
        <Select value={month} onValueChange={onMonthChange}>
          <SelectTrigger className="w-full sm:w-[160px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {MONTH_OPTIONS.map((m) => (
              <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <Button onClick={onFetch} disabled={isLoading} className="gap-1.5">
        {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <BarChart3 className="h-4 w-4" />}
        {isLoading ? "Loading..." : "Fetch Report"}
      </Button>
    </div>
  );
}

// ===== Monthly Summary Tab =====

function MonthlySummaryTab() {
  const [year, setYear] = useState(String(currentYear));
  const [month, setMonth] = useState(String(currentMonth));
  const [data, setData] = useState<MonthlySummary | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    const result = await getMonthlySummary(Number(year), Number(month));
    setIsLoading(false);
    if (result.success) {
      setData(result.data);
    } else {
      toast.error(result.error);
    }
  }, [year, month]);

  const pieData = data?.by_payment_method.map((pm) => ({
    name: pm.payment_method.replace("_", " "),
    value: pm.total_net,
    count: pm.staff_count,
  })) ?? [];

  return (
    <div className="space-y-6">
      <YearMonthSelector
        year={year}
        month={month}
        onYearChange={setYear}
        onMonthChange={setMonth}
        onFetch={fetchData}
        isLoading={isLoading}
      />

      {isLoading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="p-4 space-y-2">
                <Skeleton className="h-4 w-20" />
                <Skeleton className="h-8 w-32" />
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {data && !isLoading && (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card>
              <CardContent className="p-4">
                <p className="text-xs text-muted-foreground">Total Gross</p>
                <p className="text-lg font-bold">{formatGHS(data.total_gross)}</p>
                <p className="text-xs text-muted-foreground mt-0.5">{data.total_staff} staff</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <p className="text-xs text-muted-foreground">Net Pay</p>
                <p className="text-lg font-bold">{formatGHS(data.total_net)}</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <p className="text-xs text-muted-foreground">PAYE Tax</p>
                <p className="text-lg font-bold">{formatGHS(data.total_paye)}</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <p className="text-xs text-muted-foreground">SSNIT (EE + ER)</p>
                <p className="text-lg font-bold">
                  {formatGHS(data.total_ssnit_ee + data.total_ssnit_er)}
                </p>
              </CardContent>
            </Card>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Department Breakdown Table */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Department Breakdown</CardTitle>
              </CardHeader>
              <CardContent>
                {data.by_department.length === 0 ? (
                  <p className="text-sm text-muted-foreground text-center py-6">No department data</p>
                ) : (
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Department</TableHead>
                          <TableHead className="text-right">Staff</TableHead>
                          <TableHead className="text-right">Gross</TableHead>
                          <TableHead className="text-right">Net</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {data.by_department.map((dept) => (
                          <TableRow key={dept.department_name}>
                            <TableCell className="text-sm">{dept.department_name}</TableCell>
                            <TableCell className="text-right text-sm">{dept.staff_count}</TableCell>
                            <TableCell className="text-right text-sm">{formatGHS(dept.total_gross)}</TableCell>
                            <TableCell className="text-right text-sm">{formatGHS(dept.total_net)}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Payment Method Pie Chart */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Payment Method Distribution</CardTitle>
              </CardHeader>
              <CardContent>
                {pieData.length === 0 ? (
                  <p className="text-sm text-muted-foreground text-center py-6">No data available</p>
                ) : (
                  <div className="h-[300px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <RechartsPieChart>
                        <Pie
                          data={pieData}
                          cx="50%"
                          cy="50%"
                          labelLine={false}
                          outerRadius={100}
                          dataKey="value"
                          label
                        >
                          {pieData.map((_, index) => (
                            <Cell key={index} fill={PAYMENT_METHOD_COLORS[index % PAYMENT_METHOD_COLORS.length]} />
                          ))}
                        </Pie>
                        <Tooltip
                          content={({ active, payload }) => {
                            if (!active || !payload?.length) return null;
                            const d = payload[0].payload as { name: string; value: number; count: number };
                            return (
                              <div className="rounded-lg border bg-background p-3 shadow-md">
                                <p className="text-sm font-medium capitalize">{d.name}</p>
                                <p className="text-sm">{formatGHS(d.value)}</p>
                                <p className="text-xs text-muted-foreground">{d.count} staff</p>
                              </div>
                            );
                          }}
                        />
                        <Legend />
                      </RechartsPieChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </>
      )}

      {!data && !isLoading && (
        <Card>
          <CardContent className="p-8 text-center">
            <BarChart3 className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
            <p className="text-sm text-muted-foreground">
              Select a year and month, then click "Fetch Report" to view the monthly summary.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ===== SSNIT Returns Tab =====

function SSNITReturnsTab() {
  const [year, setYear] = useState(String(currentYear));
  const [month, setMonth] = useState(String(currentMonth));
  const [data, setData] = useState<SSNITReturnReport | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isExporting, setIsExporting] = useState(false);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    const result = await getSSNITReturns(Number(year), Number(month));
    setIsLoading(false);
    if (result.success) {
      setData(result.data);
    } else {
      toast.error(result.error);
    }
  }, [year, month]);

  async function handleExport() {
    setIsExporting(true);
    const result = await exportSSNITReturns(Number(year), Number(month));
    setIsExporting(false);
    if (result.success) {
      window.open(result.data.url, "_blank");
      toast.success("SSNIT returns exported");
    } else {
      toast.error(result.error);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <YearMonthSelector
          year={year}
          month={month}
          onYearChange={setYear}
          onMonthChange={setMonth}
          onFetch={fetchData}
          isLoading={isLoading}
        />
        {data && (
          <Button
            variant="outline"
            onClick={handleExport}
            disabled={isExporting}
            className="gap-1.5"
          >
            {isExporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
            Export to Excel
          </Button>
        )}
      </div>

      {isLoading && <Skeleton className="h-[400px] w-full" />}

      {data && !isLoading && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Shield className="h-4 w-4" />
              SSNIT Returns - {MONTH_OPTIONS[data.month - 1]?.label} {data.year}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {data.entries.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">No SSNIT data for this period</p>
            ) : (
              <div className="overflow-x-auto -mx-6">
                <div className="min-w-[700px] px-6">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Staff Name</TableHead>
                        <TableHead>SSNIT No.</TableHead>
                        <TableHead className="text-right">Basic Salary</TableHead>
                        <TableHead className="text-right">EE (5.5%)</TableHead>
                        <TableHead className="text-right">ER (13%)</TableHead>
                        <TableHead className="text-right">Tier 2 (5%)</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {data.entries.map((entry) => (
                        <TableRow key={entry.staff_id}>
                          <TableCell className="text-sm">
                            <div>
                              <p className="font-medium">{entry.staff_name}</p>
                              <p className="text-xs text-muted-foreground">{entry.staff_code}</p>
                            </div>
                          </TableCell>
                          <TableCell className="text-sm">{entry.ssnit_number || "--"}</TableCell>
                          <TableCell className="text-right text-sm">{formatGHS(entry.basic_salary)}</TableCell>
                          <TableCell className="text-right text-sm">{formatGHS(entry.ssnit_employee)}</TableCell>
                          <TableCell className="text-right text-sm">{formatGHS(entry.ssnit_employer)}</TableCell>
                          <TableCell className="text-right text-sm">{formatGHS(entry.tier2_employer)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                    <TableFooter>
                      <TableRow>
                        <TableCell colSpan={2} className="font-semibold">Totals</TableCell>
                        <TableCell className="text-right font-semibold">{formatGHS(data.totals.basic_salary)}</TableCell>
                        <TableCell className="text-right font-semibold">{formatGHS(data.totals.ssnit_employee)}</TableCell>
                        <TableCell className="text-right font-semibold">{formatGHS(data.totals.ssnit_employer)}</TableCell>
                        <TableCell className="text-right font-semibold">{formatGHS(data.totals.tier2_employer)}</TableCell>
                      </TableRow>
                    </TableFooter>
                  </Table>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {!data && !isLoading && (
        <Card>
          <CardContent className="p-8 text-center">
            <Shield className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
            <p className="text-sm text-muted-foreground">
              Select a period and click "Fetch Report" to view SSNIT contribution returns.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ===== PAYE Returns Tab =====

function PAYEReturnsTab() {
  const [year, setYear] = useState(String(currentYear));
  const [month, setMonth] = useState(String(currentMonth));
  const [data, setData] = useState<PAYEReturnReport | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isExporting, setIsExporting] = useState(false);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    const result = await getPAYEReturns(Number(year), Number(month));
    setIsLoading(false);
    if (result.success) {
      setData(result.data);
    } else {
      toast.error(result.error);
    }
  }, [year, month]);

  async function handleExport() {
    setIsExporting(true);
    const result = await exportPAYEReturns(Number(year), Number(month));
    setIsExporting(false);
    if (result.success) {
      window.open(result.data.url, "_blank");
      toast.success("PAYE returns exported");
    } else {
      toast.error(result.error);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <YearMonthSelector
          year={year}
          month={month}
          onYearChange={setYear}
          onMonthChange={setMonth}
          onFetch={fetchData}
          isLoading={isLoading}
        />
        {data && (
          <Button
            variant="outline"
            onClick={handleExport}
            disabled={isExporting}
            className="gap-1.5"
          >
            {isExporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
            Export to Excel
          </Button>
        )}
      </div>

      {isLoading && <Skeleton className="h-[400px] w-full" />}

      {data && !isLoading && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Receipt className="h-4 w-4" />
              PAYE Returns - {MONTH_OPTIONS[data.month - 1]?.label} {data.year}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {data.entries.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">No PAYE data for this period</p>
            ) : (
              <div className="overflow-x-auto -mx-6">
                <div className="min-w-[600px] px-6">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Staff Name</TableHead>
                        <TableHead>TIN</TableHead>
                        <TableHead className="text-right">Taxable Income</TableHead>
                        <TableHead className="text-right">PAYE Tax</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {data.entries.map((entry) => (
                        <TableRow key={entry.staff_id}>
                          <TableCell className="text-sm">
                            <div>
                              <p className="font-medium">{entry.staff_name}</p>
                              <p className="text-xs text-muted-foreground">{entry.staff_code}</p>
                            </div>
                          </TableCell>
                          <TableCell className="text-sm">{entry.tin_number || "--"}</TableCell>
                          <TableCell className="text-right text-sm">{formatGHS(entry.taxable_income)}</TableCell>
                          <TableCell className="text-right text-sm">{formatGHS(entry.paye_tax)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                    <TableFooter>
                      <TableRow>
                        <TableCell colSpan={2} className="font-semibold">Totals</TableCell>
                        <TableCell className="text-right font-semibold">{formatGHS(data.totals.taxable_income)}</TableCell>
                        <TableCell className="text-right font-semibold">{formatGHS(data.totals.paye_tax)}</TableCell>
                      </TableRow>
                    </TableFooter>
                  </Table>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {!data && !isLoading && (
        <Card>
          <CardContent className="p-8 text-center">
            <Receipt className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
            <p className="text-sm text-muted-foreground">
              Select a period and click "Fetch Report" to view PAYE tax returns.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ===== Department Summary Tab =====

function DepartmentSummaryTab() {
  const [year, setYear] = useState(String(currentYear));
  const [month, setMonth] = useState(String(currentMonth));
  const [data, setData] = useState<DepartmentSummaryReport | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    const result = await getDepartmentSummary(Number(year), Number(month));
    setIsLoading(false);
    if (result.success) {
      setData(result.data);
    } else {
      toast.error(result.error);
    }
  }, [year, month]);

  const chartData = data?.departments.map((dept) => ({
    name: dept.department_name.length > 12
      ? dept.department_name.slice(0, 12) + "..."
      : dept.department_name,
    fullName: dept.department_name,
    gross: dept.total_gross,
    net: dept.total_net,
    employer: dept.total_employer_cost,
  })) ?? [];

  return (
    <div className="space-y-6">
      <YearMonthSelector
        year={year}
        month={month}
        onYearChange={setYear}
        onMonthChange={setMonth}
        onFetch={fetchData}
        isLoading={isLoading}
      />

      {isLoading && <Skeleton className="h-[400px] w-full" />}

      {data && !isLoading && (
        <>
          {/* Bar Chart */}
          {chartData.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Department Cost Comparison</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-[350px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                      <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                      <YAxis tick={{ fontSize: 12 }} tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}k`} />
                      <Tooltip
                        content={({ active, payload }) => {
                          if (!active || !payload?.length) return null;
                          const d = payload[0].payload as { fullName: string; gross: number; net: number; employer: number };
                          return (
                            <div className="rounded-lg border bg-background p-3 shadow-md">
                              <p className="text-sm font-medium mb-1">{d.fullName}</p>
                              <p className="text-xs">Gross: {formatGHS(d.gross)}</p>
                              <p className="text-xs">Net: {formatGHS(d.net)}</p>
                              <p className="text-xs">Employer Cost: {formatGHS(d.employer)}</p>
                            </div>
                          );
                        }}
                      />
                      <Legend />
                      <Bar dataKey="gross" name="Gross Pay" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="net" name="Net Pay" fill="#10b981" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="employer" name="Employer Cost" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Table */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Building2 className="h-4 w-4" />
                Department Breakdown
              </CardTitle>
            </CardHeader>
            <CardContent>
              {data.departments.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">No department data</p>
              ) : (
                <div className="overflow-x-auto -mx-6">
                  <div className="min-w-[700px] px-6">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Department</TableHead>
                          <TableHead className="text-right">Staff</TableHead>
                          <TableHead className="text-right">Total Gross</TableHead>
                          <TableHead className="text-right">Total Net</TableHead>
                          <TableHead className="text-right">Employer Cost</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {data.departments.map((dept) => (
                          <TableRow key={dept.department_name}>
                            <TableCell className="text-sm font-medium">{dept.department_name}</TableCell>
                            <TableCell className="text-right text-sm">{dept.staff_count}</TableCell>
                            <TableCell className="text-right text-sm">{formatGHS(dept.total_gross)}</TableCell>
                            <TableCell className="text-right text-sm">{formatGHS(dept.total_net)}</TableCell>
                            <TableCell className="text-right text-sm">{formatGHS(dept.total_employer_cost)}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                      <TableFooter>
                        <TableRow>
                          <TableCell className="font-semibold">Totals</TableCell>
                          <TableCell className="text-right font-semibold">{data.totals.staff_count}</TableCell>
                          <TableCell className="text-right font-semibold">{formatGHS(data.totals.total_gross)}</TableCell>
                          <TableCell className="text-right font-semibold">{formatGHS(data.totals.total_net)}</TableCell>
                          <TableCell className="text-right font-semibold">{formatGHS(data.totals.total_employer_cost)}</TableCell>
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
            <Building2 className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
            <p className="text-sm text-muted-foreground">
              Select a period and click "Fetch Report" to view department cost summary.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ===== Main Component =====

export function PayrollReports() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Payroll Reports</h1>
        <p className="text-sm text-muted-foreground">
          Monthly summaries, statutory returns, and department analysis
        </p>
      </div>

      <Tabs defaultValue="monthly" className="space-y-6">
        <TabsList className="grid w-full grid-cols-2 md:grid-cols-4">
          <TabsTrigger value="monthly" className="gap-1.5">
            <BarChart3 className="h-3.5 w-3.5 hidden sm:block" />
            Monthly
          </TabsTrigger>
          <TabsTrigger value="ssnit" className="gap-1.5">
            <Shield className="h-3.5 w-3.5 hidden sm:block" />
            SSNIT
          </TabsTrigger>
          <TabsTrigger value="paye" className="gap-1.5">
            <Receipt className="h-3.5 w-3.5 hidden sm:block" />
            PAYE
          </TabsTrigger>
          <TabsTrigger value="department" className="gap-1.5">
            <Building2 className="h-3.5 w-3.5 hidden sm:block" />
            Department
          </TabsTrigger>
        </TabsList>

        <TabsContent value="monthly">
          <MonthlySummaryTab />
        </TabsContent>
        <TabsContent value="ssnit">
          <SSNITReturnsTab />
        </TabsContent>
        <TabsContent value="paye">
          <PAYEReturnsTab />
        </TabsContent>
        <TabsContent value="department">
          <DepartmentSummaryTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
