"use client";

import { useEffect, useState, useTransition } from "react";
import { useForm, type Resolver } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Loader2, Search, Pencil, Play, BarChart3 } from "lucide-react";

import {
  getLeaveBalances,
  getLeaveTypes,
  adjustLeaveBalance,
  initializeLeaveBalances,
} from "@/actions/leave.action";
import { getAcademicYears } from "@/actions/academic.action";
import type { LeaveBalance, LeaveType } from "@/types/leave.type";
import type { AcademicYear } from "@/types";
import { useToast } from "@/hooks/use-toast";

const adjustSchema = z.object({
  entitled_days: z.coerce.number().min(0, "Must be 0 or more").optional(),
  carried_over: z.coerce.number().min(0, "Must be 0 or more").optional(),
  reason: z.string().min(3, "Reason must be at least 3 characters").max(500),
});

type AdjustFormValues = z.infer<typeof adjustSchema>;

const initSchema = z.object({
  academic_year_id: z.string().min(1, "Academic year is required"),
  carry_over_from_previous: z.boolean(),
});

type InitFormValues = z.infer<typeof initSchema>;

export default function LeaveBalancesPage() {
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();
  const [balances, setBalances] = useState<LeaveBalance[]>([]);
  const [leaveTypes, setLeaveTypes] = useState<LeaveType[]>([]);
  const [academicYears, setAcademicYears] = useState<AcademicYear[]>([]);

  // Filters
  const [filterYear, setFilterYear] = useState<string>("all");
  const [filterLeaveType, setFilterLeaveType] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");

  // Adjust dialog
  const [adjustBalance, setAdjustBalance] = useState<LeaveBalance | null>(null);
  const [isAdjustOpen, setIsAdjustOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Initialize dialog
  const [isInitOpen, setIsInitOpen] = useState(false);

  const adjustForm = useForm<AdjustFormValues>({
    resolver: zodResolver(adjustSchema) as Resolver<AdjustFormValues>,
    defaultValues: { reason: "" },
  });

  const initForm = useForm<InitFormValues>({
    resolver: zodResolver(initSchema) as Resolver<InitFormValues>,
    defaultValues: {
      academic_year_id: "",
      carry_over_from_previous: false,
    },
  });

  const loadData = () => {
    startTransition(async () => {
      const [balResult, typesResult, yearsResult] = await Promise.all([
        getLeaveBalances({
          academic_year_id: filterYear !== "all" ? filterYear : undefined,
          leave_type_id: filterLeaveType !== "all" ? filterLeaveType : undefined,
        }),
        getLeaveTypes(false),
        getAcademicYears(),
      ]);
      if (balResult.success && balResult.data) {
        setBalances(balResult.data);
      }
      if (typesResult.success && typesResult.data) {
        setLeaveTypes(typesResult.data);
      }
      if (yearsResult.success && yearsResult.data) {
        setAcademicYears(yearsResult.data);
      }
    });
  };

  useEffect(() => {
    loadData();
  }, [filterYear, filterLeaveType]);

  const filteredBalances = searchQuery
    ? balances.filter((b) =>
        b.staff_name?.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : balances;

  const handleAdjust = (balance: LeaveBalance) => {
    setAdjustBalance(balance);
    adjustForm.reset({
      entitled_days: balance.entitled_days,
      carried_over: balance.carried_over,
      reason: "",
    });
    setIsAdjustOpen(true);
  };

  const onAdjustSubmit = async (data: AdjustFormValues) => {
    if (!adjustBalance) return;
    setIsSubmitting(true);
    try {
      const result = await adjustLeaveBalance(adjustBalance.id, {
        entitled_days: data.entitled_days,
        carried_over: data.carried_over,
        reason: data.reason,
      });
      if (result.success) {
        toast({ title: "Balance adjusted", description: "Leave balance has been updated." });
        setIsAdjustOpen(false);
        loadData();
      } else {
        toast({ title: "Error", description: result.error, variant: "destructive" });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const onInitSubmit = async (data: InitFormValues) => {
    setIsSubmitting(true);
    try {
      const result = await initializeLeaveBalances({
        academic_year_id: data.academic_year_id,
        carry_over_from_previous: data.carry_over_from_previous,
      });
      if (result.success && result.data) {
        toast({
          title: "Balances initialized",
          description: result.data.message,
        });
        setIsInitOpen(false);
        loadData();
      } else {
        toast({
          title: "Error",
          description: result.error,
          variant: "destructive",
        });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Leave Balances</h1>
          <p className="text-muted-foreground">
            View and manage staff leave balances
          </p>
        </div>
        <Button onClick={() => setIsInitOpen(true)}>
          <Play className="mr-2 h-4 w-4" />
          Initialize Balances
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Filters</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-4 md:flex-row">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search by staff name..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select value={filterYear} onValueChange={setFilterYear}>
              <SelectTrigger className="w-full md:w-[200px]">
                <SelectValue placeholder="Academic Year" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Years</SelectItem>
                {academicYears.map((year) => (
                  <SelectItem key={year.id} value={year.id}>
                    {year.name} {year.is_current ? "(Current)" : ""}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={filterLeaveType} onValueChange={setFilterLeaveType}>
              <SelectTrigger className="w-full md:w-[180px]">
                <SelectValue placeholder="Leave Type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Types</SelectItem>
                {leaveTypes.map((lt) => (
                  <SelectItem key={lt.id} value={lt.id}>
                    {lt.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Balances</CardTitle>
          <CardDescription>
            {filteredBalances.length} balance record{filteredBalances.length !== 1 ? "s" : ""}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isPending ? (
            <div className="flex h-[200px] items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : filteredBalances.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Staff</TableHead>
                  <TableHead>Leave Type</TableHead>
                  <TableHead className="hidden sm:table-cell text-right">Entitled</TableHead>
                  <TableHead className="hidden md:table-cell text-right">Used</TableHead>
                  <TableHead className="hidden md:table-cell text-right">Pending</TableHead>
                  <TableHead className="text-right">Remaining</TableHead>
                  <TableHead className="hidden sm:table-cell">Usage</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredBalances.map((balance) => {
                  const total = balance.entitled_days + balance.carried_over;
                  const used = balance.used_days + balance.pending_days;
                  const usagePercent = total > 0 ? Math.min((used / total) * 100, 100) : 0;

                  return (
                    <TableRow key={balance.id}>
                      <TableCell className="font-medium">
                        {balance.staff_name || "--"}
                      </TableCell>
                      <TableCell>{balance.leave_type_name || "--"}</TableCell>
                      <TableCell className="hidden sm:table-cell text-right">
                        {total}
                      </TableCell>
                      <TableCell className="hidden md:table-cell text-right">
                        {balance.used_days}
                      </TableCell>
                      <TableCell className="hidden md:table-cell text-right">
                        {balance.pending_days > 0 ? (
                          <Badge variant="secondary">{balance.pending_days}</Badge>
                        ) : (
                          "0"
                        )}
                      </TableCell>
                      <TableCell className="text-right font-medium">
                        {balance.remaining_days}
                      </TableCell>
                      <TableCell className="hidden sm:table-cell">
                        <div className="flex items-center gap-2">
                          <Progress value={usagePercent} className="h-2 w-16" />
                          <span className="text-xs text-muted-foreground">
                            {Math.round(usagePercent)}%
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleAdjust(balance)}
                          title="Adjust balance"
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          ) : (
            <div className="flex h-[200px] flex-col items-center justify-center gap-2 text-muted-foreground">
              <BarChart3 className="h-12 w-12" />
              <p>No leave balances found</p>
              <p className="text-sm text-center max-w-md">
                Initialize balances for an academic year to get started.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Adjust Balance Dialog */}
      <Dialog open={isAdjustOpen} onOpenChange={setIsAdjustOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Adjust Leave Balance</DialogTitle>
            <DialogDescription>
              Adjust balance for {adjustBalance?.staff_name} - {adjustBalance?.leave_type_name}
            </DialogDescription>
          </DialogHeader>
          <Form {...adjustForm}>
            <form onSubmit={adjustForm.handleSubmit(onAdjustSubmit)} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={adjustForm.control}
                  name="entitled_days"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Entitled Days</FormLabel>
                      <FormControl>
                        <Input type="number" min={0} step={0.5} {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={adjustForm.control}
                  name="carried_over"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Carried Over</FormLabel>
                      <FormControl>
                        <Input type="number" min={0} step={0.5} {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <FormField
                control={adjustForm.control}
                name="reason"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Reason *</FormLabel>
                    <FormControl>
                      <Textarea
                        rows={3}
                        placeholder="Reason for adjustment..."
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsAdjustOpen(false)}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Save Adjustment
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* Initialize Balances Dialog */}
      <Dialog open={isInitOpen} onOpenChange={setIsInitOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Initialize Leave Balances</DialogTitle>
            <DialogDescription>
              Create leave balances for all active staff for a selected academic year.
            </DialogDescription>
          </DialogHeader>
          <Form {...initForm}>
            <form onSubmit={initForm.handleSubmit(onInitSubmit)} className="space-y-4">
              <FormField
                control={initForm.control}
                name="academic_year_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Academic Year *</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Select academic year" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {academicYears.map((year) => (
                          <SelectItem key={year.id} value={year.id}>
                            {year.name} {year.is_current ? "(Current)" : ""}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={initForm.control}
                name="carry_over_from_previous"
                render={({ field }) => (
                  <FormItem className="flex items-center justify-between rounded-lg border p-3">
                    <div>
                      <FormLabel className="text-sm font-medium">
                        Carry Over from Previous Year
                      </FormLabel>
                      <p className="text-xs text-muted-foreground">
                        Transfer remaining balances (up to max carryover) from the previous year
                      </p>
                    </div>
                    <FormControl>
                      <Switch
                        checked={field.value}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                  </FormItem>
                )}
              />
              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsInitOpen(false)}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Initialize
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
