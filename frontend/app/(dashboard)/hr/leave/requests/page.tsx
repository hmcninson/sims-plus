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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Loader2, Search, Check, X, FileText } from "lucide-react";

import { CollapsibleFilters } from "@/components/filters/collapsible-filters";
import { LeaveApprovalDialog } from "@/components/hr/leave-approval-dialog";
import {
  getLeaveRequests,
  getLeaveTypes,
  approveLeaveRequest,
  rejectLeaveRequest,
} from "@/actions/leave.action";
import type { LeaveRequest, LeaveType } from "@/types/leave.type";
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

export default function LeaveRequestsPage() {
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();
  const [requests, setRequests] = useState<LeaveRequest[]>([]);
  const [leaveTypes, setLeaveTypes] = useState<LeaveType[]>([]);

  // Filters
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [filterLeaveType, setFilterLeaveType] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");

  // Approval dialog
  const [approvalAction, setApprovalAction] = useState<"approve" | "reject">("approve");
  const [selectedRequest, setSelectedRequest] = useState<LeaveRequest | null>(null);
  const [isApprovalOpen, setIsApprovalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const loadData = () => {
    startTransition(async () => {
      const [reqResult, typesResult] = await Promise.all([
        getLeaveRequests({
          status: filterStatus !== "all" ? filterStatus : undefined,
          leave_type_id: filterLeaveType !== "all" ? filterLeaveType : undefined,
        }),
        getLeaveTypes(false),
      ]);
      if (reqResult.success && reqResult.data) {
        setRequests(reqResult.data);
      }
      if (typesResult.success && typesResult.data) {
        setLeaveTypes(typesResult.data);
      }
    });
  };

  useEffect(() => {
    loadData();
  }, [filterStatus, filterLeaveType]);

  const filteredRequests = searchQuery
    ? requests.filter(
        (r) =>
          r.staff_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
          r.leave_type_name?.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : requests;

  const pendingCount = requests.filter((r) => r.status === "pending").length;

  const handleApprovalAction = (request: LeaveRequest, action: "approve" | "reject") => {
    setSelectedRequest(request);
    setApprovalAction(action);
    setIsApprovalOpen(true);
  };

  const handleConfirmApproval = async (notes?: string) => {
    if (!selectedRequest) return;
    setIsSubmitting(true);
    try {
      const actionFn =
        approvalAction === "approve" ? approveLeaveRequest : rejectLeaveRequest;
      const result = await actionFn(selectedRequest.id, { notes });
      if (result.success) {
        toast({
          title: `Leave request ${approvalAction === "approve" ? "approved" : "rejected"}`,
          description: `${selectedRequest.staff_name}'s request has been ${approvalAction === "approve" ? "approved" : "rejected"}.`,
        });
        setIsApprovalOpen(false);
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

  const activeFilterCount =
    (filterStatus !== "all" ? 1 : 0) + (filterLeaveType !== "all" ? 1 : 0);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Leave Requests
            {pendingCount > 0 && (
              <Badge className="ml-2 bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">
                {pendingCount} pending
              </Badge>
            )}
          </h1>
          <p className="text-muted-foreground">
            Review and manage staff leave requests
          </p>
        </div>
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
                placeholder="Search by staff name or leave type..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <CollapsibleFilters activeFilterCount={activeFilterCount}>
              <Select value={filterStatus} onValueChange={setFilterStatus}>
                <SelectTrigger className="w-full md:w-[150px]">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="pending">Pending</SelectItem>
                  <SelectItem value="approved">Approved</SelectItem>
                  <SelectItem value="rejected">Rejected</SelectItem>
                  <SelectItem value="cancelled">Cancelled</SelectItem>
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
            </CollapsibleFilters>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Requests</CardTitle>
          <CardDescription>
            {filteredRequests.length} request{filteredRequests.length !== 1 ? "s" : ""}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isPending ? (
            <div className="flex h-[200px] items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : filteredRequests.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Staff</TableHead>
                  <TableHead className="hidden sm:table-cell">Leave Type</TableHead>
                  <TableHead className="hidden md:table-cell">Dates</TableHead>
                  <TableHead className="hidden md:table-cell text-right">Days</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredRequests.map((request) => (
                  <TableRow key={request.id}>
                    <TableCell className="font-medium">
                      {request.staff_name || "--"}
                      <div className="sm:hidden text-xs text-muted-foreground mt-0.5">
                        {request.leave_type_name}
                      </div>
                    </TableCell>
                    <TableCell className="hidden sm:table-cell">
                      <div className="flex items-center gap-2">
                        {request.leave_type_color && (
                          <div
                            className="h-3 w-3 rounded-full shrink-0"
                            style={{ backgroundColor: request.leave_type_color }}
                          />
                        )}
                        {request.leave_type_name}
                      </div>
                    </TableCell>
                    <TableCell className="hidden md:table-cell text-sm">
                      {formatDate(request.start_date)} - {formatDate(request.end_date)}
                    </TableCell>
                    <TableCell className="hidden md:table-cell text-right">
                      {request.days_requested}
                    </TableCell>
                    <TableCell>{getStatusBadge(request.status)}</TableCell>
                    <TableCell className="text-right">
                      {request.status === "pending" && (
                        <div className="flex justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            className="text-green-600 hover:text-green-700"
                            onClick={() => handleApprovalAction(request, "approve")}
                            title="Approve"
                          >
                            <Check className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="text-red-600 hover:text-red-700"
                            onClick={() => handleApprovalAction(request, "reject")}
                            title="Reject"
                          >
                            <X className="h-4 w-4" />
                          </Button>
                        </div>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="flex h-[200px] flex-col items-center justify-center gap-2 text-muted-foreground">
              <FileText className="h-12 w-12" />
              <p>No leave requests found</p>
              <p className="text-sm text-center max-w-md">
                Leave requests submitted by staff will appear here for review.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      <LeaveApprovalDialog
        open={isApprovalOpen}
        onOpenChange={setIsApprovalOpen}
        action={approvalAction}
        staffName={selectedRequest?.staff_name}
        onConfirm={handleConfirmApproval}
        isSubmitting={isSubmitting}
      />
    </div>
  );
}
