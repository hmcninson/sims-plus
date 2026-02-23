"use client";

import { useState, useTransition } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Mail,
  CheckCircle2,
  XCircle,
  Clock,
  Plus,
  Loader2,
} from "lucide-react";
import { EmailCompose } from "@/components/messaging/email-compose";
import { EmailHistory } from "@/components/messaging/email-history";
import { getEmailStats, getEmailHistory } from "@/actions/messaging.action";
import type { EmailStats, EmailHistoryResponse } from "@/types/messaging.type";

interface EmailPageContentProps {
  initialStats?: EmailStats;
  initialHistory?: EmailHistoryResponse;
}

/**
 * Client-side page content for the Email Messages page.
 * Renders stats cards, a compose dialog, and the email history table.
 * Data is initially loaded server-side and passed via props; subsequent
 * refreshes happen client-side after sending an email.
 */
export function EmailPageContent({
  initialStats,
  initialHistory,
}: EmailPageContentProps) {
  const [stats, setStats] = useState<EmailStats | undefined>(initialStats);
  const [history, setHistory] = useState<EmailHistoryResponse | undefined>(initialHistory);
  const [composeOpen, setComposeOpen] = useState(false);
  const [isRefreshing, startRefresh] = useTransition();

  function refreshData() {
    startRefresh(async () => {
      const [statsResult, historyResult] = await Promise.all([
        getEmailStats(),
        getEmailHistory(),
      ]);
      if (statsResult.success && statsResult.data) {
        setStats(statsResult.data);
      }
      if (historyResult.success && historyResult.data) {
        setHistory(historyResult.data);
      }
    });
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Email Messages</h1>
          <p className="text-muted-foreground">
            Send and track email communications
          </p>
        </div>
        <Button onClick={() => setComposeOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Compose Email
        </Button>
      </div>

      {/* Stats cards */}
      <div className="grid gap-4 grid-cols-1 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Sent</CardTitle>
            <CheckCircle2 className="h-4 w-4 text-green-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {stats?.total_sent ?? 0}
            </div>
            <p className="text-xs text-muted-foreground">
              Emails delivered successfully
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Failed</CardTitle>
            <XCircle className="h-4 w-4 text-red-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">
              {stats?.total_failed ?? 0}
            </div>
            <p className="text-xs text-muted-foreground">
              Emails that could not be sent
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Pending</CardTitle>
            <Clock className="h-4 w-4 text-yellow-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-yellow-600">
              {stats?.total_pending ?? 0}
            </div>
            <p className="text-xs text-muted-foreground">
              Emails awaiting delivery
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Email history */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Email History</CardTitle>
            <CardDescription>
              Recent email messages sent from this school
            </CardDescription>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={refreshData}
            disabled={isRefreshing}
          >
            {isRefreshing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Mail className="h-4 w-4" />
            )}
            Refresh
          </Button>
        </CardHeader>
        <CardContent>
          <EmailHistory data={history} onDataChange={setHistory} />
        </CardContent>
      </Card>

      {/* Compose dialog */}
      <EmailCompose
        open={composeOpen}
        onOpenChange={setComposeOpen}
        onSent={refreshData}
      />
    </div>
  );
}
