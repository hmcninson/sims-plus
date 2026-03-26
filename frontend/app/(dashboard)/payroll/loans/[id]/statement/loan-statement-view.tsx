"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { ArrowLeft, Download, Loader2, FileText } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import { getLoanStatement } from "@/actions/loans.action";

interface LoanStatementViewProps {
  loanId: string;
}

export function LoanStatementView({ loanId }: LoanStatementViewProps) {
  const [statementUrl, setStatementUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setIsLoading(true);
      const result = await getLoanStatement(loanId);
      if (result.success && result.data.url) {
        setStatementUrl(result.data.url);
      } else {
        setError(
          result.success ? "No statement URL available" : result.error
        );
      }
      setIsLoading(false);
    }
    load();
  }, [loanId]);

  function handleDownload() {
    if (statementUrl) {
      window.open(statementUrl, "_blank");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link href={`/payroll/loans/${loanId}`}>
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              Loan Statement
            </h1>
            <p className="text-muted-foreground">
              View and download the loan statement PDF
            </p>
          </div>
        </div>
        {statementUrl && (
          <Button onClick={handleDownload}>
            <Download className="h-4 w-4 mr-2" />
            Download PDF
          </Button>
        )}
      </div>

      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-6 space-y-4">
              <Skeleton className="h-[600px] w-full" />
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center py-16 gap-3">
              <FileText className="h-10 w-10 text-muted-foreground" />
              <p className="text-muted-foreground">{error}</p>
              <Button variant="outline" asChild>
                <Link href={`/payroll/loans/${loanId}`}>
                  Back to Loan Detail
                </Link>
              </Button>
            </div>
          ) : statementUrl ? (
            <iframe
              src={statementUrl}
              className="w-full h-[800px] border-0"
              title="Loan Statement"
            />
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
