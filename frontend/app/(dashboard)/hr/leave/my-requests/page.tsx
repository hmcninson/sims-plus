"use client";

import { useEffect, useState, useTransition } from "react";
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
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Loader2, Plus, X, FileText } from "lucide-react";

import { LeaveRequestForm } from "@/components/hr/leave-request-form";
import { LeaveBalanceCard } from "@/components/hr/leave-balance-card";
import {
  getLeaveRequests,
  getLeaveTypes,
  getLeaveBalances,
  submitLeaveRequest,
  cancelLeaveRequest,
} from "@/actions/leave.action";
import type { LeaveRequest, LeaveType, LeaveBalance } from "@/types/leave.type";
import { useToast } from "@/hooks/use-toast";
import { formatDate } from "@/lib/format";

function getStatusBadge(status: string) {
  switch (status) {
    case "pending":
      return (
        <Badge className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">
          Pending
        </Badge>
      );
    case "approved":
      return (
        <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
          Approved
        </Badge>
      );
    case "rejected":
      return (
        <Badge className="bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200">
          Rejected
        </Badge>
      );
    case "cancelled":
      return <Badge variant="secondary">Cancelled</Badge>;
    default:
      return <Badge variant="secondary">{status}</Badge>;
  }
}

export default function MyLeavePage() {
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();
  const [requests, setRequests] = useState<LeaveRequest[]>([]);
  const [leaveTypes, setLeaveTypes] = useState<LeaveType[]>([]);
  const [balances, setBalances] = useState<LeaveBalance[]>([]);

  const [isFormOpen, setIsFormOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [cancelId, setCancelId] = useState<string | null>(null);

  const loadData = () => {
    startTransition(async () => {
      // Fetch leave types, own requests, and own balances in parallel.
      // The backend filters requests and balances by the current user's
      // staff profile based on the JWT context.
      const [typesResult, reqResult, balResult] = await Promise.all([
        getLeaveTypes(true),
        getLeaveRequests(),
        getLeaveBalances(),
      ]);

      if (typesResult.success && typesResult.data) {
        setLeaveTypes(typesResult.data);
      }
      if (reqResult.success && reqResult.data) {
        setRequests(reqResult.data);
      }
      if (balResult.success && balResult.data) {
        setBalances(balResult.data);
      }
    });
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSubmit = async (data: {
    leave_type_id: string;
    start_date: string;
    end_date: string;
    reason: string;
  }) => {
    setIsSubmitting(true);
    try {
      const result = await submitLeaveRequest(data);
      if (result.success) {
        toast({
          title: "Leave request submitted",
          description: "Your request has been submitted for approval.",
        });
        setIsFormOpen(false);
        loadData();
      } else {
        toast({ title: "Error", description: result.error, variant: "destructive" });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancel = async () => {
    if (!cancelId) return;
    setIsSubmitting(true);
    try {
      const result = await cancelLeaveRequest(cancelId);
      if (result.success) {
        toast({ title: "Leave request cancelled" });
        loadData();
      } else {
        toast({ title: "Error", description: result.error, variant: "destructive" });
      }
    } finally {
      setIsSubmitting(false);
      setCancelId(null);
    }
  };

  const canCancel = (request: LeaveRequest): boolean => {
    if (request.status === "pending") return true;
    if (request.status === "approved") {
      // Can cancel if leave hasn't started yet
      const startDate = new Date(request.start_date);
      return startDate > new Date();
    }
    return false;
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">My Leave</h1>
          <p className="text-muted-foreground">
            View your leave balances and submit requests
          </p>
        </div>
        <Button onClick={() => setIsFormOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          New Request
        </Button>
      </div>

      {/* Balance Cards */}
      {balances.length > 0 && <LeaveBalanceCard balances={balances} />}

      {/* Requests */}
      <Card>
        <CardHeader>
          <CardTitle>My Requests</CardTitle>
          <CardDescription>
            {requests.length} request{requests.length !== 1 ? "s" : ""}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isPending ? (
            <div className="flex h-[200px] items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : requests.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Leave Type</TableHead>
                  <TableHead className="hidden sm:table-cell">Dates</TableHead>
                  <TableHead className="hidden md:table-cell text-right">Days</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="hidden md:table-cell">Review Notes</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {requests.map((request) => (
                  <TableRow key={request.id}>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {request.leave_type_color && (
                          <div
                            className="h-3 w-3 rounded-full shrink-0"
                            style={{ backgroundColor: request.leave_type_color }}
                          />
                        )}
                        <span className="font-medium">
                          {request.leave_type_name}
                        </span>
                      </div>
                      <div className="sm:hidden text-xs text-muted-foreground mt-0.5">
                        {formatDate(request.start_date)} - {formatDate(request.end_date)}
                      </div>
                    </TableCell>
                    <TableCell className="hidden sm:table-cell text-sm">
                      {formatDate(request.start_date)} - {formatDate(request.end_date)}
                    </TableCell>
                    <TableCell className="hidden md:table-cell text-right">
                      {request.days_requested}
                    </TableCell>
                    <TableCell>{getStatusBadge(request.status)}</TableCell>
                    <TableCell className="hidden md:table-cell text-sm text-muted-foreground max-w-[200px] truncate">
                      {request.review_notes || "--"}
                    </TableCell>
                    <TableCell className="text-right">
                      {canCancel(request) && (
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setCancelId(request.id)}
                          title="Cancel request"
                        >
                          <X className="h-4 w-4 text-destructive" />
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="flex h-[200px] flex-col items-center justify-center gap-2 text-muted-foreground">
              <FileText className="h-12 w-12" />
              <p>No leave requests yet</p>
              <p className="text-sm text-center max-w-md">
                Submit a leave request to get started.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      <LeaveRequestForm
        open={isFormOpen}
        onOpenChange={setIsFormOpen}
        leaveTypes={leaveTypes}
        onSubmit={handleSubmit}
        isSubmitting={isSubmitting}
      />

      {/* Cancel Confirmation */}
      <AlertDialog open={!!cancelId} onOpenChange={() => setCancelId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Cancel Leave Request?</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to cancel this leave request? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isSubmitting}>Keep</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleCancel}
              disabled={isSubmitting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Cancel Request
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
