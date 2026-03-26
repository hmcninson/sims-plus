"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Send,
  CheckCircle,
  XCircle,
  Banknote,
  CreditCard,
  RefreshCw,
  AlertTriangle,
  Download,
  Pencil,
  Trash2,
  Loader2,
  Calendar,
  FileText,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import { LoanStatusBadge } from "@/components/payroll/LoanStatusBadge";
import { LoanApprovalDialog } from "@/components/payroll/LoanApprovalDialog";
import { LoanDisbursementDialog } from "@/components/payroll/LoanDisbursementDialog";
import { EarlyRepaymentDialog } from "@/components/payroll/EarlyRepaymentDialog";
import { LoanRestructureDialog } from "@/components/payroll/LoanRestructureDialog";
import { LoanWriteOffDialog } from "@/components/payroll/LoanWriteOffDialog";
import {
  getLoan,
  getLoanInstallments,
  getLoanPayments,
  submitLoan,
  deleteLoan,
  getLoanStatement,
} from "@/actions/loans.action";
import { formatGHS, formatGhanaDate } from "@/lib/format";
import type { StaffLoan, LoanInstallment, LoanPayment } from "@/types/loan.type";

interface LoanDetailProps {
  loanId: string;
}

export function LoanDetail({ loanId }: LoanDetailProps) {
  const router = useRouter();
  const [loan, setLoan] = useState<StaffLoan | null>(null);
  const [installments, setInstallments] = useState<LoanInstallment[]>([]);
  const [payments, setPayments] = useState<LoanPayment[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isActionLoading, setIsActionLoading] = useState(false);

  // Dialog states
  const [approveAction, setApproveAction] = useState<"approve" | "reject" | null>(null);
  const [showDisbursement, setShowDisbursement] = useState(false);
  const [showEarlyRepayment, setShowEarlyRepayment] = useState(false);
  const [showRestructure, setShowRestructure] = useState(false);
  const [showWriteOff, setShowWriteOff] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    const [loanResult, installmentsResult, paymentsResult] = await Promise.all([
      getLoan(loanId),
      getLoanInstallments(loanId),
      getLoanPayments(loanId),
    ]);

    if (loanResult.success) {
      setLoan(loanResult.data);
    } else {
      toast.error(loanResult.error);
    }
    if (installmentsResult.success) {
      setInstallments(installmentsResult.data);
    }
    if (paymentsResult.success) {
      setPayments(paymentsResult.data);
    }
    setIsLoading(false);
  }, [loanId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  async function handleSubmit() {
    setIsActionLoading(true);
    const result = await submitLoan(loanId);
    if (result.success) {
      toast.success("Loan submitted for approval");
      loadData();
    } else {
      toast.error(result.error);
    }
    setIsActionLoading(false);
  }

  async function handleDelete() {
    setIsActionLoading(true);
    const result = await deleteLoan(loanId);
    if (result.success) {
      toast.success("Loan deleted");
      router.push("/payroll/loans");
    } else {
      toast.error(result.error);
    }
    setIsActionLoading(false);
  }

  async function handleDownloadStatement() {
    const result = await getLoanStatement(loanId);
    if (result.success && result.data.url) {
      window.open(result.data.url, "_blank");
    } else {
      toast.error(result.success ? "No statement available" : result.error);
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Skeleton className="h-10 w-10" />
          <div className="space-y-2">
            <Skeleton className="h-8 w-48" />
            <Skeleton className="h-4 w-32" />
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="p-4 space-y-2">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-6 w-32" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  if (!loan) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
        <AlertTriangle className="h-10 w-10 text-destructive" />
        <h2 className="text-lg font-semibold">Loan not found</h2>
        <Button variant="outline" asChild>
          <Link href="/payroll/loans">Back to Loans</Link>
        </Button>
      </div>
    );
  }

  const repaymentPercent =
    loan.total_repayable > 0
      ? Math.round((loan.total_paid / loan.total_repayable) * 100)
      : 0;

  const today = new Date().toISOString().split("T")[0];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link href="/payroll/loans">
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight">
                {loan.loan_number}
              </h1>
              <LoanStatusBadge status={loan.status} />
            </div>
            <p className="text-muted-foreground">
              {loan.staff_name} &middot; {loan.loan_type.name}
            </p>
          </div>
        </div>

        {/* Action buttons based on status */}
        <div className="flex flex-wrap gap-2">
          {loan.status === "draft" && (
            <>
              <Button
                variant="outline"
                size="sm"
                asChild
              >
                <Link href={`/payroll/loans/${loan.id}`}>
                  <Pencil className="h-4 w-4 mr-1" />
                  Edit
                </Link>
              </Button>
              <Button
                size="sm"
                onClick={handleSubmit}
                disabled={isActionLoading}
              >
                {isActionLoading ? (
                  <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                ) : (
                  <Send className="h-4 w-4 mr-1" />
                )}
                Submit
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => setShowDeleteConfirm(true)}
              >
                <Trash2 className="h-4 w-4 mr-1" />
                Delete
              </Button>
            </>
          )}

          {loan.status === "pending_approval" && (
            <>
              <Button
                size="sm"
                onClick={() => setApproveAction("approve")}
              >
                <CheckCircle className="h-4 w-4 mr-1" />
                Approve
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => setApproveAction("reject")}
              >
                <XCircle className="h-4 w-4 mr-1" />
                Reject
              </Button>
            </>
          )}

          {loan.status === "approved" && (
            <Button size="sm" onClick={() => setShowDisbursement(true)}>
              <Banknote className="h-4 w-4 mr-1" />
              Disburse
            </Button>
          )}

          {loan.status === "active" && (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowEarlyRepayment(true)}
              >
                <CreditCard className="h-4 w-4 mr-1" />
                Early Repayment
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowRestructure(true)}
              >
                <RefreshCw className="h-4 w-4 mr-1" />
                Restructure
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowWriteOff(true)}
              >
                <AlertTriangle className="h-4 w-4 mr-1" />
                Write Off
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleDownloadStatement}
              >
                <Download className="h-4 w-4 mr-1" />
                Statement
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <Card>
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground">Principal</p>
            <p className="text-lg font-bold">{formatGHS(loan.principal_amount)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground">Interest</p>
            <p className="text-lg font-bold">{formatGHS(loan.total_interest)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground">Total Repayable</p>
            <p className="text-lg font-bold">{formatGHS(loan.total_repayable)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground">Monthly</p>
            <p className="text-lg font-bold text-primary">
              {formatGHS(loan.monthly_installment)}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground">Paid</p>
            <p className="text-lg font-bold text-green-600 dark:text-green-400">
              {formatGHS(loan.total_paid)}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-xs text-muted-foreground">Outstanding</p>
            <p className="text-lg font-bold text-amber-600 dark:text-amber-400">
              {formatGHS(loan.outstanding_balance)}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Progress Bar */}
      {(loan.status === "active" || loan.status === "completed") && (
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-medium">Repayment Progress</p>
              <p className="text-sm text-muted-foreground">
                {repaymentPercent}% ({loan.installments_paid} of{" "}
                {loan.installments_paid + loan.installments_remaining}{" "}
                installments)
              </p>
            </div>
            <Progress value={repaymentPercent} className="h-3" />
          </CardContent>
        </Card>
      )}

      {/* Loan Info */}
      <Card>
        <CardContent className="p-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
            <div>
              <p className="text-muted-foreground">Interest Rate</p>
              <p className="font-medium">
                {loan.interest_rate}%{" "}
                ({loan.interest_method === "flat" ? "Flat" : "Reducing Balance"})
              </p>
            </div>
            <div>
              <p className="text-muted-foreground">Tenure</p>
              <p className="font-medium">{loan.tenure_months} months</p>
            </div>
            <div>
              <p className="text-muted-foreground">Application Date</p>
              <p className="font-medium">
                {formatGhanaDate(loan.application_date)}
              </p>
            </div>
            {loan.approval_date && (
              <div>
                <p className="text-muted-foreground">Approval Date</p>
                <p className="font-medium">
                  {formatGhanaDate(loan.approval_date)}
                </p>
              </div>
            )}
            {loan.disbursement_date && (
              <div>
                <p className="text-muted-foreground">Disbursement Date</p>
                <p className="font-medium">
                  {formatGhanaDate(loan.disbursement_date)}
                </p>
              </div>
            )}
            {loan.first_deduction_date && (
              <div>
                <p className="text-muted-foreground">First Deduction</p>
                <p className="font-medium">
                  {formatGhanaDate(loan.first_deduction_date)}
                </p>
              </div>
            )}
            {loan.expected_completion_date && (
              <div>
                <p className="text-muted-foreground">Expected Completion</p>
                <p className="font-medium">
                  {formatGhanaDate(loan.expected_completion_date)}
                </p>
              </div>
            )}
            {loan.purpose && (
              <div className="md:col-span-2 lg:col-span-4">
                <p className="text-muted-foreground">Purpose</p>
                <p className="font-medium">{loan.purpose}</p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Tabs: Schedule, Payments, Guarantors */}
      <Tabs defaultValue="schedule" className="space-y-4">
        <TabsList>
          <TabsTrigger value="schedule" className="flex items-center gap-1.5">
            <Calendar className="h-4 w-4" />
            <span className="hidden sm:inline">Schedule</span>
          </TabsTrigger>
          <TabsTrigger value="payments" className="flex items-center gap-1.5">
            <CreditCard className="h-4 w-4" />
            <span className="hidden sm:inline">Payments</span>
          </TabsTrigger>
          <TabsTrigger value="guarantors" className="flex items-center gap-1.5">
            <FileText className="h-4 w-4" />
            <span className="hidden sm:inline">Guarantors</span>
          </TabsTrigger>
        </TabsList>

        {/* Schedule Tab */}
        <TabsContent value="schedule">
          <Card>
            <CardContent className="p-0">
              {installments.length === 0 ? (
                <div className="flex flex-col items-center py-12 gap-2">
                  <Calendar className="h-8 w-8 text-muted-foreground" />
                  <p className="text-muted-foreground">
                    {loan.status === "active" || loan.status === "completed"
                      ? "No installment schedule available"
                      : "Installment schedule will be generated after disbursement"}
                  </p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-[60px]">#</TableHead>
                        <TableHead>Due Date</TableHead>
                        <TableHead className="text-right hidden sm:table-cell">
                          Principal
                        </TableHead>
                        <TableHead className="text-right hidden sm:table-cell">
                          Interest
                        </TableHead>
                        <TableHead className="text-right">Amount</TableHead>
                        <TableHead className="text-right hidden md:table-cell">
                          Balance
                        </TableHead>
                        <TableHead>Status</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {installments.map((inst) => {
                        const isOverdue =
                          !inst.is_paid && inst.due_date < today;
                        const rowClass = inst.is_paid
                          ? "bg-green-50 dark:bg-green-950/20"
                          : isOverdue
                          ? "bg-red-50 dark:bg-red-950/20"
                          : "";

                        return (
                          <TableRow key={inst.id} className={rowClass}>
                            <TableCell className="font-mono">
                              {inst.installment_number}
                            </TableCell>
                            <TableCell>
                              {formatGhanaDate(inst.due_date)}
                            </TableCell>
                            <TableCell className="text-right hidden sm:table-cell">
                              {formatGHS(inst.principal_component)}
                            </TableCell>
                            <TableCell className="text-right hidden sm:table-cell">
                              {formatGHS(inst.interest_component)}
                            </TableCell>
                            <TableCell className="text-right font-medium">
                              {formatGHS(inst.installment_amount)}
                            </TableCell>
                            <TableCell className="text-right hidden md:table-cell">
                              {formatGHS(inst.closing_balance)}
                            </TableCell>
                            <TableCell>
                              {inst.is_paid ? (
                                <Badge className="bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300">
                                  Paid
                                </Badge>
                              ) : isOverdue ? (
                                <Badge className="bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300">
                                  Overdue
                                </Badge>
                              ) : (
                                <Badge variant="secondary">Pending</Badge>
                              )}
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
        </TabsContent>

        {/* Payments Tab */}
        <TabsContent value="payments">
          <Card>
            <CardContent className="p-0">
              {payments.length === 0 ? (
                <div className="flex flex-col items-center py-12 gap-2">
                  <CreditCard className="h-8 w-8 text-muted-foreground" />
                  <p className="text-muted-foreground">No payments recorded yet</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Payment #</TableHead>
                        <TableHead>Date</TableHead>
                        <TableHead className="text-right">Amount</TableHead>
                        <TableHead className="hidden sm:table-cell">
                          Method
                        </TableHead>
                        <TableHead className="hidden md:table-cell">
                          Reference
                        </TableHead>
                        <TableHead className="hidden lg:table-cell">
                          Type
                        </TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {payments.map((pay) => (
                        <TableRow key={pay.id}>
                          <TableCell className="font-mono text-sm">
                            {pay.payment_number}
                          </TableCell>
                          <TableCell>
                            {formatGhanaDate(pay.payment_date)}
                          </TableCell>
                          <TableCell className="text-right font-medium">
                            {formatGHS(pay.amount)}
                          </TableCell>
                          <TableCell className="hidden sm:table-cell capitalize">
                            {pay.payment_method.replace("_", " ")}
                          </TableCell>
                          <TableCell className="hidden md:table-cell">
                            {pay.reference || "—"}
                          </TableCell>
                          <TableCell className="hidden lg:table-cell">
                            {pay.is_early_repayment ? (
                              <Badge variant="outline">Early</Badge>
                            ) : (
                              <Badge variant="secondary">Regular</Badge>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Guarantors Tab */}
        <TabsContent value="guarantors">
          <Card>
            <CardContent className="p-0">
              {loan.guarantors.length === 0 ? (
                <div className="flex flex-col items-center py-12 gap-2">
                  <FileText className="h-8 w-8 text-muted-foreground" />
                  <p className="text-muted-foreground">No guarantors for this loan</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Staff</TableHead>
                        <TableHead className="hidden sm:table-cell">
                          Relationship
                        </TableHead>
                        <TableHead className="text-right hidden md:table-cell">
                          Guaranteed Amount
                        </TableHead>
                        <TableHead>Consent</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {loan.guarantors.map((g) => (
                        <TableRow key={g.id}>
                          <TableCell className="font-medium">
                            {g.guarantor_staff_name || "—"}
                          </TableCell>
                          <TableCell className="hidden sm:table-cell">
                            {g.relationship || "—"}
                          </TableCell>
                          <TableCell className="text-right hidden md:table-cell">
                            {g.guaranteed_amount
                              ? formatGHS(g.guaranteed_amount)
                              : "Full amount"}
                          </TableCell>
                          <TableCell>
                            {g.consent_given ? (
                              <Badge className="bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300">
                                Consented
                                {g.consent_date &&
                                  ` (${formatGhanaDate(g.consent_date)})`}
                              </Badge>
                            ) : (
                              <Badge variant="outline">Pending</Badge>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Dialogs */}
      {approveAction && (
        <LoanApprovalDialog
          loanId={loanId}
          loanNumber={loan.loan_number}
          action={approveAction}
          open={!!approveAction}
          onOpenChange={(open) => !open && setApproveAction(null)}
          onSuccess={loadData}
        />
      )}

      <LoanDisbursementDialog
        loanId={loanId}
        loanNumber={loan.loan_number}
        principalAmount={loan.principal_amount}
        open={showDisbursement}
        onOpenChange={setShowDisbursement}
        onSuccess={loadData}
      />

      <EarlyRepaymentDialog
        loanId={loanId}
        loanNumber={loan.loan_number}
        outstandingBalance={loan.outstanding_balance}
        open={showEarlyRepayment}
        onOpenChange={setShowEarlyRepayment}
        onSuccess={loadData}
      />

      <LoanRestructureDialog
        loanId={loanId}
        loanNumber={loan.loan_number}
        currentRate={loan.interest_rate}
        currentMethod={loan.interest_method}
        currentTenure={loan.tenure_months}
        open={showRestructure}
        onOpenChange={setShowRestructure}
        onSuccess={loadData}
      />

      <LoanWriteOffDialog
        loanId={loanId}
        loanNumber={loan.loan_number}
        outstandingBalance={loan.outstanding_balance}
        open={showWriteOff}
        onOpenChange={setShowWriteOff}
        onSuccess={loadData}
      />

      {/* Delete Confirmation */}
      <AlertDialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Loan</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete loan {loan.loan_number}? This
              action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isActionLoading && (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              )}
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
