"use client";

import { useState, useTransition, useCallback } from "react";
import {
  MessageSquare,
  Send,
  AlertCircle,
  Clock,
  CreditCard,
  Loader2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

import { SMSCompose } from "@/components/messaging/sms-compose";
import { SMSHistory } from "@/components/messaging/sms-history";
import { getSMSStats, getSMSHistory } from "@/actions/messaging.action";
import type { SMSStats, SMSHistoryResponse } from "@/types/messaging.type";

interface SMSPageContentProps {
  initialStats?: SMSStats;
  initialHistory?: SMSHistoryResponse;
}

export function SMSPageContent({ initialStats, initialHistory }: SMSPageContentProps) {
  const [stats, setStats] = useState(initialStats);
  const [history, setHistory] = useState(initialHistory);
  const [composeOpen, setComposeOpen] = useState(false);
  const [isRefreshing, startRefresh] = useTransition();

  const handleSent = useCallback(() => {
    // Refresh both stats and history after a message is sent
    startRefresh(async () => {
      const [statsResult, historyResult] = await Promise.all([
        getSMSStats(),
        getSMSHistory(),
      ]);
      if (statsResult.success) setStats(statsResult.data);
      if (historyResult.success) setHistory(historyResult.data);
    });
  }, []);

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">SMS Messages</h1>
          <p className="text-sm text-muted-foreground">
            Send SMS messages to parents, staff, and other contacts.
          </p>
        </div>
        <Button onClick={() => setComposeOpen(true)}>
          <Send className="size-4" />
          Compose SMS
        </Button>
      </div>

      {/* Stats cards */}
      <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Sent</CardTitle>
            <MessageSquare className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats ? stats.total_sent.toLocaleString() : "--"}
            </div>
            <p className="text-xs text-muted-foreground">
              Messages delivered successfully
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Failed</CardTitle>
            <AlertCircle className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-destructive">
              {stats ? stats.total_failed.toLocaleString() : "--"}
            </div>
            <p className="text-xs text-muted-foreground">
              Messages that could not be sent
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Pending</CardTitle>
            <Clock className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats ? stats.total_pending.toLocaleString() : "--"}
            </div>
            <p className="text-xs text-muted-foreground">
              Messages awaiting delivery
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Credits Used</CardTitle>
            <CreditCard className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats ? stats.credits_used.toLocaleString() : "--"}
            </div>
            <p className="text-xs text-muted-foreground">
              SMS credits consumed this period
            </p>
          </CardContent>
        </Card>
      </div>

      {/* History section */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Message History</CardTitle>
          {isRefreshing && (
            <Loader2 className="size-4 animate-spin text-muted-foreground" />
          )}
        </CardHeader>
        <CardContent>
          <SMSHistory initialData={history} />
        </CardContent>
      </Card>

      {/* Compose dialog */}
      <SMSCompose
        open={composeOpen}
        onOpenChange={setComposeOpen}
        onSent={handleSent}
      />
    </div>
  );
}
