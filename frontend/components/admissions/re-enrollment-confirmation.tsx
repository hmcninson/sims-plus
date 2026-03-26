"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import {
  CheckCircle,
  Loader2,
  AlertTriangle,
  Users,
  Clock,
  XCircle,
  HelpCircle,
} from "lucide-react";
import { confirmReEnrollment } from "@/actions/admissions.action";
import { formatCurrency } from "@/lib/format";
import type {
  ReEnrollmentSummaryResponse,
  ReturnIntentRecord,
} from "@/types/admissions.type";

interface ReEnrollmentConfirmationProps {
  summary: ReEnrollmentSummaryResponse;
  intents: ReturnIntentRecord[];
  onRefresh: () => void;
}

export function ReEnrollmentConfirmation({
  summary,
  intents,
  onRefresh,
}: ReEnrollmentConfirmationProps) {
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [loadingId, setLoadingId] = useState<string | null>(null);

  async function handleConfirm() {
    if (!confirmingId) return;
    setLoadingId(confirmingId);
    const result = await confirmReEnrollment(confirmingId);
    setLoadingId(null);
    setConfirmingId(null);

    if (result.success) {
      toast.success("Re-enrollment confirmed");
      onRefresh();
    } else {
      toast.error(result.error);
    }
  }

  const returningIntents = intents.filter((i) => i.intent === "returning");

  return (
    <div className="space-y-6">
      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <Card>
          <CardContent className="pt-6 text-center">
            <Users className="mx-auto mb-2 h-5 w-5 text-muted-foreground" />
            <p className="text-2xl font-bold">{summary.total_intents}</p>
            <p className="text-xs text-muted-foreground">Total</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6 text-center">
            <CheckCircle className="mx-auto mb-2 h-5 w-5 text-green-600" />
            <p className="text-2xl font-bold text-green-600">
              {summary.confirmed_count}
            </p>
            <p className="text-xs text-muted-foreground">Confirmed</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6 text-center">
            <Clock className="mx-auto mb-2 h-5 w-5 text-amber-600" />
            <p className="text-2xl font-bold text-amber-600">
              {summary.pending_count}
            </p>
            <p className="text-xs text-muted-foreground">Pending</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6 text-center">
            <XCircle className="mx-auto mb-2 h-5 w-5 text-red-600" />
            <p className="text-2xl font-bold text-red-600">
              {summary.not_returning_count}
            </p>
            <p className="text-xs text-muted-foreground">Not Returning</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6 text-center">
            <HelpCircle className="mx-auto mb-2 h-5 w-5 text-blue-600" />
            <p className="text-2xl font-bold text-blue-600">
              {summary.undecided_count}
            </p>
            <p className="text-xs text-muted-foreground">Undecided</p>
          </CardContent>
        </Card>
      </div>

      {/* Outstanding fees warning */}
      {summary.total_outstanding_fees > 0 && (
        <Alert>
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>
            Total outstanding fees across returning students:{" "}
            <strong>{formatCurrency(summary.total_outstanding_fees)}</strong>
          </AlertDescription>
        </Alert>
      )}

      {/* By class breakdown */}
      {summary.by_class.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">By Class</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Class</TableHead>
                    <TableHead className="text-center">Confirmed</TableHead>
                    <TableHead className="text-center">Pending</TableHead>
                    <TableHead className="text-center">Not Returning</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {summary.by_class.map((cls, idx) => (
                    <TableRow key={idx}>
                      <TableCell className="font-medium">
                        {cls.class_name}
                      </TableCell>
                      <TableCell className="text-center">
                        {cls.confirmed}
                      </TableCell>
                      <TableCell className="text-center">
                        {cls.pending}
                      </TableCell>
                      <TableCell className="text-center">
                        {cls.not_returning}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Returning intents awaiting confirmation */}
      {returningIntents.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Returning Students Awaiting Confirmation
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Student</TableHead>
                    <TableHead className="hidden sm:table-cell">Class</TableHead>
                    <TableHead>Intent</TableHead>
                    <TableHead className="w-[140px]">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {returningIntents.map((intent) => (
                    <TableRow key={intent.id}>
                      <TableCell className="font-medium">
                        {intent.student_name || "--"}
                      </TableCell>
                      <TableCell className="hidden sm:table-cell">
                        {intent.current_class_name || "--"}
                      </TableCell>
                      <TableCell>
                        <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                          Returning
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Button
                          size="sm"
                          disabled={loadingId === intent.id}
                          onClick={() => setConfirmingId(intent.id)}
                        >
                          {loadingId === intent.id ? (
                            <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                          ) : (
                            <CheckCircle className="mr-1 h-3 w-3" />
                          )}
                          Confirm
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Confirm dialog */}
      <AlertDialog
        open={!!confirmingId}
        onOpenChange={() => setConfirmingId(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirm Re-enrollment</AlertDialogTitle>
            <AlertDialogDescription>
              This will confirm the student&apos;s re-enrollment for the next
              academic year. Outstanding fees will be checked and recorded.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirm}>
              Confirm Re-enrollment
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
