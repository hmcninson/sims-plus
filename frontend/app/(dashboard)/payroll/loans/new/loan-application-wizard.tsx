"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Loader2,
  Plus,
  Trash2,
  Search,
  AlertCircle,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import { getLoanTypes, createLoan } from "@/actions/loans.action";
import { getStaff } from "@/actions/staff.action";
import { getCurrentUser } from "@/actions/auth.action";
import { formatGHS } from "@/lib/format";
import type {
  LoanType,
  InterestMethod,
  LoanGuarantorInput,
} from "@/types/loan.type";

interface StaffOption {
  id: string;
  name: string;
  staff_code: string;
}

const STEPS = [
  { label: "Type", description: "Select loan type" },
  { label: "Terms", description: "Amount & repayment" },
  { label: "Guarantors", description: "Add guarantors" },
  { label: "Review", description: "Confirm & submit" },
];

/**
 * Simple flat-rate installment preview for the wizard.
 * The backend does the real calculation; this is just for user preview.
 */
function calculatePreview(
  principal: number,
  annualRate: number,
  method: InterestMethod,
  tenureMonths: number
) {
  if (principal <= 0 || tenureMonths <= 0) {
    return { totalInterest: 0, totalRepayable: 0, monthlyInstallment: 0 };
  }

  const rate = annualRate / 100;

  if (method === "flat") {
    const totalInterest = principal * rate * (tenureMonths / 12);
    const totalRepayable = principal + totalInterest;
    const monthlyInstallment = totalRepayable / tenureMonths;
    return {
      totalInterest: Math.round(totalInterest * 100) / 100,
      totalRepayable: Math.round(totalRepayable * 100) / 100,
      monthlyInstallment: Math.round(monthlyInstallment * 100) / 100,
    };
  }

  // Reducing balance
  const monthlyRate = rate / 12;
  if (monthlyRate === 0) {
    return {
      totalInterest: 0,
      totalRepayable: principal,
      monthlyInstallment: Math.round((principal / tenureMonths) * 100) / 100,
    };
  }
  const monthlyInstallment =
    (principal * monthlyRate * Math.pow(1 + monthlyRate, tenureMonths)) /
    (Math.pow(1 + monthlyRate, tenureMonths) - 1);
  const totalRepayable = monthlyInstallment * tenureMonths;
  const totalInterest = totalRepayable - principal;
  return {
    totalInterest: Math.round(totalInterest * 100) / 100,
    totalRepayable: Math.round(totalRepayable * 100) / 100,
    monthlyInstallment: Math.round(monthlyInstallment * 100) / 100,
  };
}

export function LoanApplicationWizard() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  // Data
  const [loanTypes, setLoanTypes] = useState<LoanType[]>([]);
  const [staffList, setStaffList] = useState<StaffOption[]>([]);
  const [currentUserId, setCurrentUserId] = useState("");

  // Form state
  const [selectedTypeId, setSelectedTypeId] = useState("");
  const [principal, setPrincipal] = useState<number>(0);
  const [interestRate, setInterestRate] = useState<number>(0);
  const [interestMethod, setInterestMethod] = useState<InterestMethod>("flat");
  const [tenureMonths, setTenureMonths] = useState<number>(12);
  const [firstDeductionDate, setFirstDeductionDate] = useState("");
  const [purpose, setPurpose] = useState("");
  const [guarantors, setGuarantors] = useState<
    (LoanGuarantorInput & { name?: string })[]
  >([]);
  const [guarantorSearchOpen, setGuarantorSearchOpen] = useState(false);

  const selectedType = loanTypes.find((lt) => lt.id === selectedTypeId);

  const preview = useMemo(
    () => calculatePreview(principal, interestRate, interestMethod, tenureMonths),
    [principal, interestRate, interestMethod, tenureMonths]
  );

  const loadData = useCallback(async () => {
    setIsLoading(true);
    const [typesResult, staffResult, userResult] = await Promise.all([
      getLoanTypes(true),
      getStaff(),
      getCurrentUser(),
    ]);

    if (typesResult.success) setLoanTypes(typesResult.data);
    if (staffResult.success && staffResult.data) {
      const data = staffResult.data;
      const items = "items" in data ? data.items : [];
      setStaffList(
        items.map((s) => ({
          id: s.id,
          name: `${s.first_name} ${s.last_name}`.trim(),
          staff_code: s.staff_id || "",
        }))
      );
    }
    if (userResult) setCurrentUserId(userResult.id);
    setIsLoading(false);
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  function handleSelectType(typeId: string) {
    setSelectedTypeId(typeId);
    const lt = loanTypes.find((t) => t.id === typeId);
    if (lt) {
      setInterestRate(lt.default_interest_rate);
      setInterestMethod(lt.default_interest_method);
    }
  }

  function addGuarantor(staffId: string) {
    if (guarantors.some((g) => g.guarantor_staff_id === staffId)) {
      toast.error("This staff member is already a guarantor");
      return;
    }
    const staff = staffList.find((s) => s.id === staffId);
    setGuarantors((prev) => [
      ...prev,
      {
        guarantor_staff_id: staffId,
        name: staff?.name,
      },
    ]);
    setGuarantorSearchOpen(false);
  }

  function removeGuarantor(staffId: string) {
    setGuarantors((prev) =>
      prev.filter((g) => g.guarantor_staff_id !== staffId)
    );
  }

  function canProceed(): boolean {
    switch (step) {
      case 0:
        return !!selectedTypeId;
      case 1:
        return principal > 0 && tenureMonths > 0;
      case 2:
        if (selectedType?.requires_guarantor && guarantors.length === 0) {
          return false;
        }
        return true;
      default:
        return true;
    }
  }

  async function handleSubmit() {
    setIsSubmitting(true);

    const result = await createLoan({
      staff_id: currentUserId,
      loan_type_id: selectedTypeId,
      principal_amount: principal,
      interest_rate: interestRate,
      interest_method: interestMethod,
      tenure_months: tenureMonths,
      first_deduction_date: firstDeductionDate || undefined,
      purpose: purpose.trim() || undefined,
      guarantor_staff_ids:
        guarantors.length > 0
          ? guarantors.map((g) => g.guarantor_staff_id)
          : undefined,
    });

    if (result.success) {
      toast.success("Loan application created successfully");
      router.push(`/payroll/loans/${result.data.id}`);
    } else {
      toast.error(result.error);
    }
    setIsSubmitting(false);
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-72" />
        <Card>
          <CardContent className="p-6 space-y-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/payroll/loans">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            New Loan Application
          </h1>
          <p className="text-muted-foreground">
            Step {step + 1} of {STEPS.length}: {STEPS[step].description}
          </p>
        </div>
      </div>

      {/* Stepper */}
      <div className="hidden md:flex items-center gap-2">
        {STEPS.map((s, i) => (
          <div key={i} className="flex items-center gap-2">
            <div
              className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium ${
                i < step
                  ? "bg-primary text-primary-foreground"
                  : i === step
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground"
              }`}
            >
              {i < step ? <Check className="h-4 w-4" /> : i + 1}
            </div>
            <span
              className={`text-sm ${
                i <= step ? "font-medium" : "text-muted-foreground"
              }`}
            >
              {s.label}
            </span>
            {i < STEPS.length - 1 && (
              <div
                className={`h-px w-8 ${
                  i < step ? "bg-primary" : "bg-muted"
                }`}
              />
            )}
          </div>
        ))}
      </div>

      {/* Mobile stepper */}
      <div className="md:hidden flex items-center justify-center gap-1">
        {STEPS.map((s, i) => (
          <div key={i} className="flex flex-col items-center gap-1">
            <div
              className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-medium ${
                i < step
                  ? "bg-primary text-primary-foreground"
                  : i === step
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground"
              }`}
            >
              {i < step ? <Check className="h-3 w-3" /> : i + 1}
            </div>
            <span className="text-[10px] max-w-[60px] text-center truncate">
              {s.label}
            </span>
          </div>
        ))}
      </div>

      {/* Step Content */}
      <Card>
        <CardContent className="p-6">
          {/* Step 0: Select Loan Type */}
          {step === 0 && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">Select Loan Type</h3>
              {loanTypes.length === 0 ? (
                <div className="flex flex-col items-center py-8 gap-2">
                  <AlertCircle className="h-8 w-8 text-muted-foreground" />
                  <p className="text-muted-foreground">
                    No loan types configured.{" "}
                    <Link
                      href="/payroll/loans/settings"
                      className="text-primary underline"
                    >
                      Configure loan types
                    </Link>{" "}
                    first.
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {loanTypes.map((lt) => (
                    <button
                      key={lt.id}
                      type="button"
                      onClick={() => handleSelectType(lt.id)}
                      className={`text-left rounded-lg border-2 p-4 transition-colors ${
                        selectedTypeId === lt.id
                          ? "border-primary bg-primary/5"
                          : "border-border hover:border-primary/50"
                      }`}
                    >
                      <div className="font-semibold">{lt.name}</div>
                      <div className="text-sm text-muted-foreground mt-1">
                        {lt.description || lt.code}
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2 text-xs">
                        <Badge variant="secondary">
                          {lt.default_interest_rate}%{" "}
                          {lt.default_interest_method === "flat"
                            ? "Flat"
                            : "Reducing"}
                        </Badge>
                        {lt.max_amount && (
                          <Badge variant="outline">
                            Max {formatGHS(lt.max_amount)}
                          </Badge>
                        )}
                        {lt.max_tenure_months && (
                          <Badge variant="outline">
                            Max {lt.max_tenure_months} months
                          </Badge>
                        )}
                        {lt.requires_guarantor && (
                          <Badge variant="outline">Guarantor required</Badge>
                        )}
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Step 1: Amount & Terms */}
          {step === 1 && (
            <div className="space-y-6">
              <h3 className="text-lg font-semibold">Amount & Terms</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Principal Amount (GHS)</Label>
                  <Input
                    type="number"
                    step="0.01"
                    min="0"
                    max={selectedType?.max_amount || undefined}
                    value={principal || ""}
                    onChange={(e) => setPrincipal(parseFloat(e.target.value) || 0)}
                    placeholder="Enter loan amount"
                  />
                  {selectedType?.max_amount && (
                    <p className="text-xs text-muted-foreground">
                      Maximum: {formatGHS(selectedType.max_amount)}
                    </p>
                  )}
                </div>

                <div className="space-y-2">
                  <Label>Interest Rate (% per annum)</Label>
                  <Input
                    type="number"
                    step="0.01"
                    min="0"
                    max="100"
                    value={interestRate}
                    onChange={(e) =>
                      setInterestRate(parseFloat(e.target.value) || 0)
                    }
                  />
                </div>

                <div className="space-y-2">
                  <Label>Interest Method</Label>
                  <Select
                    value={interestMethod}
                    onValueChange={(v) =>
                      setInterestMethod(v as InterestMethod)
                    }
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="flat">Flat Rate</SelectItem>
                      <SelectItem value="reducing_balance">
                        Reducing Balance
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Tenure (months)</Label>
                  <Input
                    type="number"
                    min="1"
                    max={selectedType?.max_tenure_months || 120}
                    value={tenureMonths}
                    onChange={(e) =>
                      setTenureMonths(parseInt(e.target.value) || 1)
                    }
                  />
                  {selectedType?.max_tenure_months && (
                    <p className="text-xs text-muted-foreground">
                      Maximum: {selectedType.max_tenure_months} months
                    </p>
                  )}
                </div>

                <div className="space-y-2">
                  <Label>First Deduction Date (optional)</Label>
                  <Input
                    type="date"
                    value={firstDeductionDate}
                    onChange={(e) => setFirstDeductionDate(e.target.value)}
                  />
                  <p className="text-xs text-muted-foreground">
                    Must be the 1st of a month
                  </p>
                </div>

                <div className="space-y-2">
                  <Label>Purpose (optional)</Label>
                  <Textarea
                    value={purpose}
                    onChange={(e) => setPurpose(e.target.value)}
                    placeholder="Brief purpose description"
                    rows={2}
                  />
                </div>
              </div>

              {/* Installment Preview */}
              {principal > 0 && tenureMonths > 0 && (
                <Card className="bg-muted/50">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium">
                      Installment Preview
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
                      <div>
                        <p className="text-muted-foreground">Total Interest</p>
                        <p className="text-lg font-semibold">
                          {formatGHS(preview.totalInterest)}
                        </p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">
                          Total Repayable
                        </p>
                        <p className="text-lg font-semibold">
                          {formatGHS(preview.totalRepayable)}
                        </p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">
                          Monthly Installment
                        </p>
                        <p className="text-lg font-semibold text-primary">
                          {formatGHS(preview.monthlyInstallment)}
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          )}

          {/* Step 2: Guarantors */}
          {step === 2 && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-semibold">Guarantors</h3>
                  {selectedType?.requires_guarantor && (
                    <p className="text-sm text-amber-600 dark:text-amber-400">
                      At least one guarantor is required for this loan type
                    </p>
                  )}
                </div>

                <Popover
                  open={guarantorSearchOpen}
                  onOpenChange={setGuarantorSearchOpen}
                >
                  <PopoverTrigger asChild>
                    <Button variant="outline" size="sm">
                      <Plus className="h-4 w-4 mr-1" />
                      Add Guarantor
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-[300px] p-0" align="end">
                    <Command>
                      <CommandInput placeholder="Search staff..." />
                      <CommandList>
                        <CommandEmpty>No staff found</CommandEmpty>
                        <CommandGroup>
                          {staffList
                            .filter(
                              (s) =>
                                !guarantors.some(
                                  (g) => g.guarantor_staff_id === s.id
                                )
                            )
                            .map((s) => (
                              <CommandItem
                                key={s.id}
                                value={`${s.name} ${s.staff_code}`}
                                onSelect={() => addGuarantor(s.id)}
                              >
                                <div>
                                  <div className="font-medium">{s.name}</div>
                                  <div className="text-xs text-muted-foreground">
                                    {s.staff_code}
                                  </div>
                                </div>
                              </CommandItem>
                            ))}
                        </CommandGroup>
                      </CommandList>
                    </Command>
                  </PopoverContent>
                </Popover>
              </div>

              {guarantors.length === 0 ? (
                <div className="flex flex-col items-center py-8 gap-2 text-muted-foreground">
                  <Search className="h-8 w-8" />
                  <p>No guarantors added yet</p>
                  {!selectedType?.requires_guarantor && (
                    <p className="text-xs">
                      Guarantors are optional for this loan type
                    </p>
                  )}
                </div>
              ) : (
                <div className="space-y-2">
                  {guarantors.map((g) => (
                    <div
                      key={g.guarantor_staff_id}
                      className="flex items-center justify-between rounded-lg border p-3"
                    >
                      <div>
                        <p className="font-medium">{g.name || "Staff"}</p>
                        {g.relationship && (
                          <p className="text-sm text-muted-foreground">
                            {g.relationship}
                          </p>
                        )}
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() =>
                          removeGuarantor(g.guarantor_staff_id)
                        }
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Step 3: Review */}
          {step === 3 && (
            <div className="space-y-6">
              <h3 className="text-lg font-semibold">Review & Submit</h3>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                <div className="space-y-3">
                  <h4 className="font-medium text-muted-foreground">
                    Loan Type
                  </h4>
                  <p className="font-semibold">{selectedType?.name}</p>
                </div>

                <div className="space-y-3">
                  <h4 className="font-medium text-muted-foreground">
                    Principal Amount
                  </h4>
                  <p className="font-semibold">
                    {formatGHS(principal)}
                  </p>
                </div>

                <div className="space-y-3">
                  <h4 className="font-medium text-muted-foreground">
                    Interest Rate
                  </h4>
                  <p className="font-semibold">
                    {interestRate}% ({interestMethod === "flat" ? "Flat" : "Reducing Balance"})
                  </p>
                </div>

                <div className="space-y-3">
                  <h4 className="font-medium text-muted-foreground">
                    Tenure
                  </h4>
                  <p className="font-semibold">{tenureMonths} months</p>
                </div>

                <div className="space-y-3">
                  <h4 className="font-medium text-muted-foreground">
                    Total Interest
                  </h4>
                  <p className="font-semibold">
                    {formatGHS(preview.totalInterest)}
                  </p>
                </div>

                <div className="space-y-3">
                  <h4 className="font-medium text-muted-foreground">
                    Total Repayable
                  </h4>
                  <p className="font-semibold">
                    {formatGHS(preview.totalRepayable)}
                  </p>
                </div>

                <div className="space-y-3">
                  <h4 className="font-medium text-muted-foreground">
                    Monthly Installment
                  </h4>
                  <p className="text-lg font-bold text-primary">
                    {formatGHS(preview.monthlyInstallment)}
                  </p>
                </div>

                {firstDeductionDate && (
                  <div className="space-y-3">
                    <h4 className="font-medium text-muted-foreground">
                      First Deduction
                    </h4>
                    <p className="font-semibold">{firstDeductionDate}</p>
                  </div>
                )}

                {purpose && (
                  <div className="space-y-3 md:col-span-2">
                    <h4 className="font-medium text-muted-foreground">
                      Purpose
                    </h4>
                    <p>{purpose}</p>
                  </div>
                )}
              </div>

              {guarantors.length > 0 && (
                <div>
                  <h4 className="font-medium text-muted-foreground mb-2">
                    Guarantors
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {guarantors.map((g) => (
                      <Badge key={g.guarantor_staff_id} variant="secondary">
                        {g.name || "Staff"}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Navigation */}
      <div className="flex justify-between">
        <Button
          variant="outline"
          onClick={() => (step > 0 ? setStep(step - 1) : router.push("/payroll/loans"))}
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          {step > 0 ? "Back" : "Cancel"}
        </Button>

        {step < STEPS.length - 1 ? (
          <Button onClick={() => setStep(step + 1)} disabled={!canProceed()}>
            Next
            <ArrowRight className="h-4 w-4 ml-2" />
          </Button>
        ) : (
          <Button onClick={handleSubmit} disabled={isSubmitting}>
            {isSubmitting && (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            )}
            Create Loan Application
          </Button>
        )}
      </div>
    </div>
  );
}
