"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Download,
  Loader2,
  AlertCircle,
  FileSpreadsheet,
  Banknote,
  Users,
  CreditCard,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import {
  getPayrollRun,
  getPayrollRunSummary,
  getBankFileConfigs,
  generateBankFile,
} from "@/actions/payroll.action";
import { formatGHS } from "@/lib/format";
import type {
  PayrollRun,
  PayrollRunSummary,
  BankFileConfig,
  BankFileResult,
} from "@/types/payroll.type";

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

interface BankFileGenerationProps {
  runId: string;
}

export function BankFileGeneration({ runId }: BankFileGenerationProps) {
  const [run, setRun] = useState<PayrollRun | null>(null);
  const [summary, setSummary] = useState<PayrollRunSummary | null>(null);
  const [configs, setConfigs] = useState<BankFileConfig[]>([]);
  const [selectedConfig, setSelectedConfig] = useState<string>("");
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [result, setResult] = useState<BankFileResult | null>(null);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    const [runResult, summaryResult, configsResult] = await Promise.all([
      getPayrollRun(runId),
      getPayrollRunSummary(runId),
      getBankFileConfigs(),
    ]);

    if (runResult.success) setRun(runResult.data);
    else toast.error(runResult.error);

    if (summaryResult.success) setSummary(summaryResult.data);
    if (configsResult.success) {
      setConfigs(configsResult.data);
      const defaultConfig = configsResult.data.find((c) => c.is_default);
      if (defaultConfig) setSelectedConfig(defaultConfig.id);
      else if (configsResult.data.length > 0) setSelectedConfig(configsResult.data[0].id);
    }

    setIsLoading(false);
  }, [runId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  async function handleGenerate() {
    const config = configs.find((c) => c.id === selectedConfig);
    if (!config) {
      toast.error("Please select a bank configuration");
      return;
    }

    setIsGenerating(true);
    const genResult = await generateBankFile(runId, config.bank_name);
    setIsGenerating(false);

    if (genResult.success) {
      setResult(genResult.data);
      toast.success("Bank file generated successfully");
    } else {
      toast.error(genResult.error);
    }
  }

  function handleDownload() {
    if (result?.url) {
      window.open(result.url, "_blank");
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <Skeleton className="h-10 w-10" />
          <div className="space-y-2">
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-4 w-40" />
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="p-4 space-y-2">
                <Skeleton className="h-4 w-20" />
                <Skeleton className="h-8 w-32" />
              </CardContent>
            </Card>
          ))}
        </div>
        <Skeleton className="h-[300px] w-full" />
      </div>
    );
  }

  if (!run) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
        <AlertCircle className="h-10 w-10 text-destructive" />
        <h2 className="text-lg font-semibold">Payroll run not found</h2>
        <Button variant="outline" asChild>
          <Link href="/payroll/runs">Back to Runs</Link>
        </Button>
      </div>
    );
  }

  const runTitle = `${MONTH_NAMES[run.month - 1]} ${run.year}`;
  const canGenerate = run.status === "approved" || run.status === "paid";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" asChild>
          <Link href={`/payroll/runs/${runId}`}>
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Bank File - {runTitle}</h1>
          <p className="text-sm text-muted-foreground">
            Generate payment file for bank processing
          </p>
        </div>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Card>
            <CardContent className="p-4 flex items-center gap-3">
              <div className="rounded-lg bg-emerald-50 dark:bg-emerald-950 p-2">
                <Banknote className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Total Net Pay</p>
                <p className="text-lg font-bold">{formatGHS(summary.run.total_net)}</p>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4 flex items-center gap-3">
              <div className="rounded-lg bg-blue-50 dark:bg-blue-950 p-2">
                <Users className="h-5 w-5 text-blue-600 dark:text-blue-400" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Staff Count</p>
                <p className="text-lg font-bold">{summary.run.staff_count}</p>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4 flex items-center gap-3">
              <div className="rounded-lg bg-purple-50 dark:bg-purple-950 p-2">
                <CreditCard className="h-5 w-5 text-purple-600 dark:text-purple-400" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Payment Methods</p>
                <div className="flex flex-wrap gap-1 mt-0.5">
                  {summary.by_payment_method.map((pm) => (
                    <span key={pm.payment_method} className="text-xs">
                      {pm.payment_method.replace("_", " ")} ({pm.staff_count})
                    </span>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Bank File Generation */}
      <Card>
        <CardHeader>
          <CardTitle>Generate Bank File</CardTitle>
          <CardDescription>
            Select a bank configuration and generate a payment file for upload to your bank portal.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {!canGenerate && (
            <div className="rounded-lg bg-amber-50 dark:bg-amber-950 border border-amber-200 dark:border-amber-900 p-4 text-sm text-amber-700 dark:text-amber-300">
              Bank files can only be generated for approved or paid payroll runs.
              Current status: <span className="font-medium capitalize">{run.status.replace("_", " ")}</span>
            </div>
          )}

          {configs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <FileSpreadsheet className="h-10 w-10 text-muted-foreground mb-3" />
              <h3 className="text-sm font-medium">No bank configurations found</h3>
              <p className="text-xs text-muted-foreground mt-1 mb-3">
                Set up bank file configurations in payroll settings first.
              </p>
              <Button variant="outline" size="sm" asChild>
                <Link href="/payroll/settings">Go to Settings</Link>
              </Button>
            </div>
          ) : (
            <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
              <div className="space-y-2 flex-1">
                <label className="text-sm font-medium">Bank Configuration</label>
                <Select value={selectedConfig} onValueChange={setSelectedConfig}>
                  <SelectTrigger className="w-full sm:w-[300px]">
                    <SelectValue placeholder="Select a bank" />
                  </SelectTrigger>
                  <SelectContent>
                    {configs.map((config) => (
                      <SelectItem key={config.id} value={config.id}>
                        {config.bank_name}
                        {config.is_default && " (Default)"}
                        {" - "}
                        {config.file_format.toUpperCase()}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Button
                onClick={handleGenerate}
                disabled={isGenerating || !canGenerate || !selectedConfig}
                className="gap-2"
              >
                {isGenerating ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <FileSpreadsheet className="h-4 w-4" />
                )}
                {isGenerating ? "Generating..." : "Generate File"}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Result */}
      {result && (
        <Card className="border-green-200 dark:border-green-900">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-green-700 dark:text-green-400">
              <FileSpreadsheet className="h-5 w-5" />
              File Generated Successfully
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
              <div>
                <p className="text-muted-foreground">File Name</p>
                <p className="font-medium">{result.file_name}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Total Amount</p>
                <p className="font-medium">{formatGHS(result.total_amount)}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Staff Count</p>
                <p className="font-medium">{result.staff_count}</p>
              </div>
            </div>

            {result.by_payment_method.length > 0 && (
              <div className="text-sm">
                <p className="text-muted-foreground mb-1">By Payment Method</p>
                <div className="flex flex-wrap gap-2">
                  {result.by_payment_method.map((pm) => (
                    <span
                      key={pm.payment_method}
                      className="inline-flex items-center gap-1 rounded-md bg-muted px-2 py-1 text-xs"
                    >
                      {pm.payment_method.replace("_", " ")}: {pm.staff_count} staff ({formatGHS(pm.total_net)})
                    </span>
                  ))}
                </div>
              </div>
            )}

            <Button onClick={handleDownload} className="gap-2">
              <Download className="h-4 w-4" />
              Download File
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
