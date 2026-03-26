"use client";

import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { format, subDays } from "date-fns";
import {
  Loader2,
  Calendar,
  DollarSign,
  ClipboardList,
} from "lucide-react";

import { Button } from "@/components/ui/button";
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Calendar as CalendarPicker } from "@/components/ui/calendar";
import { Skeleton } from "@/components/ui/skeleton";
import { formatGhanaDate } from "@/lib/format";
import { ExtendedCareCheckIn } from "@/components/preschool/ExtendedCareCheckIn";
import {
  listExtendedCareSessions,
  getExtendedCareBillingSummary,
} from "@/actions/preschool.action";
import type { Class, ExtendedCareSession, ExtendedCareBillingSummary } from "@/types";

interface ExtendedCareManagerProps {
  classes: Class[];
}

export function ExtendedCareManager({ classes }: ExtendedCareManagerProps) {
  return (
    <Tabs defaultValue="check-in" className="w-full">
      <TabsList className="grid w-full grid-cols-3">
        <TabsTrigger value="check-in">Check In / Out</TabsTrigger>
        <TabsTrigger value="history">Session History</TabsTrigger>
        <TabsTrigger value="billing">Billing Summary</TabsTrigger>
      </TabsList>

      <TabsContent value="check-in" className="mt-6">
        <ExtendedCareCheckIn classes={classes} />
      </TabsContent>

      <TabsContent value="history" className="mt-6">
        <SessionHistory classes={classes} />
      </TabsContent>

      <TabsContent value="billing" className="mt-6">
        <BillingSummary classes={classes} />
      </TabsContent>
    </Tabs>
  );
}

// Session History Tab
function SessionHistory({ classes }: { classes: Class[] }) {
  const [sessions, setSessions] = useState<ExtendedCareSession[]>([]);
  const [loading, setLoading] = useState(false);
  const [classFilter, setClassFilter] = useState("");
  const [dateFrom, setDateFrom] = useState<Date>(subDays(new Date(), 7));
  const [dateTo, setDateTo] = useState<Date>(new Date());

  const loadSessions = useCallback(async () => {
    setLoading(true);
    const result = await listExtendedCareSessions({
      class_id: classFilter || undefined,
      date_from: format(dateFrom, "yyyy-MM-dd"),
      date_to: format(dateTo, "yyyy-MM-dd"),
    });
    if (result.success && result.data) {
      setSessions(result.data);
    } else {
      toast.error(result.error || "Failed to load sessions");
    }
    setLoading(false);
  }, [classFilter, dateFrom, dateTo]);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <Select value={classFilter} onValueChange={setClassFilter}>
          <SelectTrigger className="w-full md:w-[200px]">
            <SelectValue placeholder="All classes" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Classes</SelectItem>
            {classes.map((c) => (
              <SelectItem key={c.id} value={c.id}>
                {c.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <DatePickerButton date={dateFrom} onDateChange={setDateFrom} label="From" />
        <DatePickerButton date={dateTo} onDateChange={setDateTo} label="To" />
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-6 space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : sessions.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12">
              <ClipboardList className="h-10 w-10 text-muted-foreground mb-3" />
              <p className="text-sm text-muted-foreground">No sessions found for this period.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Student</TableHead>
                    <TableHead className="hidden sm:table-cell">Type</TableHead>
                    <TableHead>Check In</TableHead>
                    <TableHead>Check Out</TableHead>
                    <TableHead className="hidden md:table-cell">Duration</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sessions.map((session) => (
                    <TableRow key={session.id}>
                      <TableCell className="text-sm">
                        {formatGhanaDate(session.session_date)}
                      </TableCell>
                      <TableCell className="text-sm font-medium">
                        {session.student_id.slice(0, 8)}...
                      </TableCell>
                      <TableCell className="hidden sm:table-cell">
                        <Badge
                          variant="secondary"
                          className={
                            session.session_type === "before_care"
                              ? "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-300"
                              : "bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-300"
                          }
                        >
                          {session.session_type === "before_care" ? "Before" : "After"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm">{session.check_in_time}</TableCell>
                      <TableCell className="text-sm">
                        {session.check_out_time || "-"}
                      </TableCell>
                      <TableCell className="hidden md:table-cell text-sm">
                        {session.duration_minutes != null
                          ? `${session.duration_minutes} min`
                          : "-"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// Billing Summary Tab
function BillingSummary({ classes }: { classes: Class[] }) {
  const [summaries, setSummaries] = useState<ExtendedCareBillingSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [classFilter, setClassFilter] = useState("");
  const [dateFrom, setDateFrom] = useState<Date>(subDays(new Date(), 30));
  const [dateTo, setDateTo] = useState<Date>(new Date());

  async function loadBilling() {
    setLoading(true);
    const result = await getExtendedCareBillingSummary({
      date_from: format(dateFrom, "yyyy-MM-dd"),
      date_to: format(dateTo, "yyyy-MM-dd"),
      class_id: classFilter || undefined,
    });
    if (result.success && result.data) {
      setSummaries(result.data);
    } else {
      toast.error(result.error || "Failed to load billing summary");
    }
    setLoading(false);
  }

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-end">
        <Select value={classFilter} onValueChange={setClassFilter}>
          <SelectTrigger className="w-full md:w-[200px]">
            <SelectValue placeholder="All classes" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Classes</SelectItem>
            {classes.map((c) => (
              <SelectItem key={c.id} value={c.id}>
                {c.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <DatePickerButton date={dateFrom} onDateChange={setDateFrom} label="From" />
        <DatePickerButton date={dateTo} onDateChange={setDateTo} label="To" />

        <Button onClick={loadBilling} disabled={loading}>
          {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Generate Summary
        </Button>
      </div>

      {/* Summary Table */}
      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-6 space-y-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : summaries.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12">
              <DollarSign className="h-10 w-10 text-muted-foreground mb-3" />
              <p className="text-sm text-muted-foreground">
                Click &quot;Generate Summary&quot; to view billing for the selected period.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Student</TableHead>
                    <TableHead>Sessions</TableHead>
                    <TableHead className="hidden sm:table-cell">Total Hours</TableHead>
                    <TableHead className="hidden md:table-cell">Rate</TableHead>
                    <TableHead className="text-right">Est. Charge</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {summaries.map((s) => (
                    <TableRow key={s.student_id}>
                      <TableCell className="text-sm font-medium">
                        {s.student_name}
                      </TableCell>
                      <TableCell className="text-sm">{s.total_sessions}</TableCell>
                      <TableCell className="hidden sm:table-cell text-sm">
                        {s.total_hours.toFixed(1)}
                      </TableCell>
                      <TableCell className="hidden md:table-cell text-sm">
                        {s.rate_per_hour != null
                          ? `GHS ${s.rate_per_hour.toFixed(2)}/hr`
                          : s.flat_rate != null
                          ? `GHS ${s.flat_rate.toFixed(2)} flat`
                          : "-"}
                      </TableCell>
                      <TableCell className="text-sm text-right font-medium">
                        GHS {s.estimated_charge.toFixed(2)}
                      </TableCell>
                    </TableRow>
                  ))}
                  {/* Totals row */}
                  <TableRow className="font-bold border-t-2">
                    <TableCell>Total</TableCell>
                    <TableCell>
                      {summaries.reduce((sum, s) => sum + s.total_sessions, 0)}
                    </TableCell>
                    <TableCell className="hidden sm:table-cell">
                      {summaries.reduce((sum, s) => sum + s.total_hours, 0).toFixed(1)}
                    </TableCell>
                    <TableCell className="hidden md:table-cell" />
                    <TableCell className="text-right">
                      GHS{" "}
                      {summaries
                        .reduce((sum, s) => sum + s.estimated_charge, 0)
                        .toFixed(2)}
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// Reusable Date Picker Button
function DatePickerButton({
  date,
  onDateChange,
  label,
}: {
  date: Date;
  onDateChange: (d: Date) => void;
  label: string;
}) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" className="w-full md:w-auto justify-start text-left font-normal">
          <Calendar className="mr-2 h-4 w-4" />
          <span className="text-muted-foreground mr-1">{label}:</span>
          {format(date, "dd/MM/yyyy")}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <CalendarPicker
          mode="single"
          selected={date}
          onSelect={(d) => d && onDateChange(d)}
          initialFocus
        />
      </PopoverContent>
    </Popover>
  );
}
