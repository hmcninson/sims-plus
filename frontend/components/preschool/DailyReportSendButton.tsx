"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Loader2, Send, SendHorizonal } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { sendDailyLogToParents, bulkSendDailyLogs } from "@/actions/preschool.action";

// Single student send button
interface DailyReportSendButtonProps {
  logId: string;
  studentName: string;
  onSent?: () => void;
}

export function DailyReportSendButton({
  logId,
  studentName,
  onSent,
}: DailyReportSendButtonProps) {
  const [sending, setSending] = useState(false);

  async function handleSend() {
    setSending(true);
    try {
      const result = await sendDailyLogToParents(logId);
      if (result.success && result.data) {
        toast.success(`Report sent to ${result.data.sent_count} guardian(s)`);
        onSent?.();
      } else {
        toast.error(result.error || "Failed to send report");
      }
    } catch {
      toast.error("Failed to send report");
    } finally {
      setSending(false);
    }
  }

  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="outline" size="sm" disabled={sending}>
          {sending ? (
            <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
          ) : (
            <Send className="mr-1.5 h-3.5 w-3.5" />
          )}
          Send to Parents
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Send Daily Report</AlertDialogTitle>
          <AlertDialogDescription>
            Send the daily activity report for <strong>{studentName}</strong> to their
            guardians? They will receive a notification with today&apos;s log details.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction onClick={handleSend} disabled={sending}>
            {sending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Send Report
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

// Bulk send button for a whole class
interface BulkSendButtonProps {
  classId: string;
  logDate: string;
  onSent?: () => void;
}

export function BulkSendButton({
  classId,
  logDate,
  onSent,
}: BulkSendButtonProps) {
  const [sending, setSending] = useState(false);

  async function handleSend() {
    setSending(true);
    try {
      const result = await bulkSendDailyLogs(classId, logDate);
      if (result.success && result.data) {
        toast.success(
          `Sent ${result.data.sent} of ${result.data.total} daily reports to parents`
        );
        onSent?.();
      } else {
        toast.error(result.error || "Failed to send reports");
      }
    } catch {
      toast.error("Failed to send reports");
    } finally {
      setSending(false);
    }
  }

  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="default" size="sm" disabled={sending}>
          {sending ? (
            <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
          ) : (
            <SendHorizonal className="mr-1.5 h-3.5 w-3.5" />
          )}
          Send All to Parents
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Send All Daily Reports</AlertDialogTitle>
          <AlertDialogDescription>
            Send daily activity reports for <strong>all students</strong> in this class
            to their guardians? Each guardian will receive their child&apos;s log.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction onClick={handleSend} disabled={sending}>
            {sending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Send All Reports
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
