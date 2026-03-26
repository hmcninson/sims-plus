"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { ReturnIntentCampaignForm } from "@/components/admissions/return-intent-campaign-form";
import {
  Plus,
  Loader2,
  ClipboardList,
  Send,
  Info,
  Eye,
  ArrowLeft,
  CheckCircle,
  XCircle,
  HelpCircle,
  Clock,
} from "lucide-react";
import {
  getReturnIntentCampaigns,
  sendReturnIntentCampaign,
} from "@/actions/admissions.action";
import type {
  ReturnIntentCampaign,
  ReturnIntentStatus,
} from "@/types/admissions.type";

const STATUS_CONFIG: Record<
  ReturnIntentStatus,
  { label: string; className: string }
> = {
  draft: {
    label: "Draft",
    className:
      "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
  },
  sent: {
    label: "Sent",
    className:
      "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  },
  completed: {
    label: "Completed",
    className:
      "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  },
};

export function ReturnIntentsManagement() {
  const [campaigns, setCampaigns] = useState<ReturnIntentCampaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [selectedCampaign, setSelectedCampaign] =
    useState<ReturnIntentCampaign | null>(null);
  const [showSendDialog, setShowSendDialog] = useState(false);
  const [sendingId, setSendingId] = useState<string | null>(null);

  const loadCampaigns = useCallback(async () => {
    const result = await getReturnIntentCampaigns({ page_size: 50 });
    if (result.success && result.data) {
      setCampaigns(result.data.items);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadCampaigns();
  }, [loadCampaigns]);

  async function handleSend(campaignId: string) {
    setSendingId(campaignId);
    try {
      const result = await sendReturnIntentCampaign(campaignId);
      if (result.success) {
        toast.success("Survey sent successfully");
        setShowSendDialog(false);
        loadCampaigns();
        // Update selected campaign if viewing it
        if (selectedCampaign?.id === campaignId && result.data) {
          setSelectedCampaign(result.data);
        }
      } else {
        toast.error(result.error);
      }
    } finally {
      setSendingId(null);
    }
  }

  function formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  }

  if (loading) {
    return (
      <div className="p-4 md:p-6 space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-[400px]" />
      </div>
    );
  }

  // Detail view
  if (selectedCampaign) {
    const statusConfig = STATUS_CONFIG[selectedCampaign.status];
    const totalResponses =
      (selectedCampaign.returning_count ?? 0) +
      (selectedCampaign.not_returning_count ?? 0) +
      (selectedCampaign.undecided_count ?? 0);
    const totalStudents = selectedCampaign.total_students ?? 0;
    const responseRate =
      totalStudents > 0
        ? Math.round((totalResponses / totalStudents) * 100)
        : 0;

    return (
      <div className="p-4 md:p-6 space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setSelectedCampaign(null)}
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div className="flex-1">
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-bold">{selectedCampaign.name}</h1>
              <Badge variant="outline" className={statusConfig.className}>
                {statusConfig.label}
              </Badge>
            </div>
            {selectedCampaign.deadline && (
              <p className="text-sm text-muted-foreground">
                Deadline: {formatDate(selectedCampaign.deadline)}
              </p>
            )}
          </div>
          {selectedCampaign.status === "draft" && (
            <Button
              onClick={() => setShowSendDialog(true)}
              disabled={!!sendingId}
            >
              <Send className="mr-2 h-4 w-4" />
              Send Survey
            </Button>
          )}
        </div>

        <Alert>
          <Info className="h-4 w-4" />
          <AlertDescription>
            These results are informational only and do not affect promotions or
            enrollment.
          </AlertDescription>
        </Alert>

        {/* Stats */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
          <Card>
            <CardContent className="pt-6 text-center">
              <p className="text-2xl font-bold">{totalStudents}</p>
              <p className="text-xs text-muted-foreground">Total Students</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6 text-center">
              <CheckCircle className="h-5 w-5 mx-auto text-green-500 mb-1" />
              <p className="text-2xl font-bold">
                {selectedCampaign.returning_count ?? 0}
              </p>
              <p className="text-xs text-muted-foreground">Returning</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6 text-center">
              <XCircle className="h-5 w-5 mx-auto text-red-500 mb-1" />
              <p className="text-2xl font-bold">
                {selectedCampaign.not_returning_count ?? 0}
              </p>
              <p className="text-xs text-muted-foreground">Not Returning</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6 text-center">
              <HelpCircle className="h-5 w-5 mx-auto text-amber-500 mb-1" />
              <p className="text-2xl font-bold">
                {selectedCampaign.undecided_count ?? 0}
              </p>
              <p className="text-xs text-muted-foreground">Undecided</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6 text-center">
              <Clock className="h-5 w-5 mx-auto text-muted-foreground mb-1" />
              <p className="text-2xl font-bold">
                {selectedCampaign.pending_count ?? 0}
              </p>
              <p className="text-xs text-muted-foreground">Pending</p>
            </CardContent>
          </Card>
        </div>

        {/* Progress */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Response Progress</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex justify-between text-sm">
              <span>
                {totalResponses} of {totalStudents} responded
              </span>
              <span className="font-medium">{responseRate}%</span>
            </div>
            <Progress value={responseRate} />
            {totalStudents > 0 && (
              <div className="grid grid-cols-3 gap-4 pt-2">
                <div className="text-center">
                  <div className="h-2 w-full rounded-full bg-green-200 dark:bg-green-900 mb-1">
                    <div
                      className="h-2 rounded-full bg-green-500"
                      style={{
                        width: `${totalStudents > 0 ? ((selectedCampaign.returning_count ?? 0) / totalStudents) * 100 : 0}%`,
                      }}
                    />
                  </div>
                  <span className="text-xs text-muted-foreground">
                    Returning
                  </span>
                </div>
                <div className="text-center">
                  <div className="h-2 w-full rounded-full bg-red-200 dark:bg-red-900 mb-1">
                    <div
                      className="h-2 rounded-full bg-red-500"
                      style={{
                        width: `${totalStudents > 0 ? ((selectedCampaign.not_returning_count ?? 0) / totalStudents) * 100 : 0}%`,
                      }}
                    />
                  </div>
                  <span className="text-xs text-muted-foreground">
                    Not Returning
                  </span>
                </div>
                <div className="text-center">
                  <div className="h-2 w-full rounded-full bg-amber-200 dark:bg-amber-900 mb-1">
                    <div
                      className="h-2 rounded-full bg-amber-500"
                      style={{
                        width: `${totalStudents > 0 ? ((selectedCampaign.undecided_count ?? 0) / totalStudents) * 100 : 0}%`,
                      }}
                    />
                  </div>
                  <span className="text-xs text-muted-foreground">
                    Undecided
                  </span>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Send Confirmation */}
        <AlertDialog open={showSendDialog} onOpenChange={setShowSendDialog}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Send Return Intent Survey</AlertDialogTitle>
              <AlertDialogDescription>
                This will send the survey to all students in the selected
                classes. Their parents/guardians will receive a notification.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={!!sendingId}>
                Cancel
              </AlertDialogCancel>
              <AlertDialogAction
                onClick={() => handleSend(selectedCampaign.id)}
                disabled={!!sendingId}
              >
                {sendingId && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                Send Survey
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    );
  }

  // List view
  return (
    <div className="p-4 md:p-6 space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Return Intent Surveys</h1>
          <p className="text-sm text-muted-foreground">
            Survey parents on intent to return for the next academic year
          </p>
        </div>
        <Button onClick={() => setShowCreateDialog(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Create Survey
        </Button>
      </div>

      <Alert>
        <Info className="h-4 w-4" />
        <AlertDescription>
          Return intent surveys are informational only. Results do not affect
          promotions, enrollment, or any other processes.
        </AlertDescription>
      </Alert>

      {/* Campaigns Table */}
      <Card>
        <CardContent className="p-0">
          {campaigns.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 gap-3">
              <ClipboardList className="h-10 w-10 text-muted-foreground" />
              <p className="text-sm font-medium">No campaigns yet</p>
              <p className="text-sm text-muted-foreground">
                Create a return intent survey to gauge enrollment projections
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="hidden sm:table-cell">
                      Responses
                    </TableHead>
                    <TableHead className="hidden md:table-cell">
                      Deadline
                    </TableHead>
                    <TableHead className="w-[80px]">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {campaigns.map((campaign) => {
                    const statusConfig = STATUS_CONFIG[campaign.status];
                    const totalResponses =
                      (campaign.returning_count ?? 0) +
                      (campaign.not_returning_count ?? 0) +
                      (campaign.undecided_count ?? 0);

                    return (
                      <TableRow key={campaign.id}>
                        <TableCell>
                          <p className="font-medium">{campaign.name}</p>
                          <p className="text-xs text-muted-foreground">
                            {campaign.target_classes?.length ?? 0} classes,{" "}
                            {campaign.total_students ?? 0} students
                          </p>
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant="outline"
                            className={statusConfig.className}
                          >
                            {statusConfig.label}
                          </Badge>
                        </TableCell>
                        <TableCell className="hidden sm:table-cell text-sm">
                          {totalResponses} / {campaign.total_students ?? 0}
                        </TableCell>
                        <TableCell className="hidden md:table-cell text-sm text-muted-foreground">
                          {campaign.deadline
                            ? formatDate(campaign.deadline)
                            : "-"}
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setSelectedCampaign(campaign)}
                          >
                            <Eye className="mr-1 h-4 w-4" />
                            View
                          </Button>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create Campaign Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Create Return Intent Survey</DialogTitle>
          </DialogHeader>
          <ReturnIntentCampaignForm
            onSuccess={() => {
              setShowCreateDialog(false);
              loadCampaigns();
            }}
            onCancel={() => setShowCreateDialog(false)}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}
