"use client";

import { useState, useTransition, useCallback } from "react";
import { Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import { getSMSHistory } from "@/actions/messaging.action";
import type { SMSHistoryResponse } from "@/types/messaging.type";

interface SMSHistoryProps {
  initialData?: SMSHistoryResponse;
}

const STATUS_STYLES: Record<string, { variant: "default" | "secondary" | "destructive" | "outline"; className?: string }> = {
  sent: { variant: "default", className: "bg-green-600 hover:bg-green-600/90" },
  delivered: { variant: "default", className: "bg-blue-600 hover:bg-blue-600/90" },
  failed: { variant: "destructive" },
  pending: { variant: "secondary" },
  queued: { variant: "outline" },
};

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "--";
  try {
    return new Date(dateStr).toLocaleString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return dateStr;
  }
}

function truncateMessage(msg: string, maxLen: number = 60): string {
  if (msg.length <= maxLen) return msg;
  return msg.slice(0, maxLen) + "...";
}

export function SMSHistory({ initialData }: SMSHistoryProps) {
  const [data, setData] = useState(initialData);
  const [page, setPage] = useState(initialData?.page ?? 1);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [isPending, startTransition] = useTransition();

  const fetchHistory = useCallback(
    (newPage: number, status: string) => {
      startTransition(async () => {
        const result = await getSMSHistory(
          newPage,
          20,
          status === "all" ? undefined : status
        );
        if (result.success) {
          setData(result.data);
          setPage(newPage);
        }
      });
    },
    []
  );

  function handleStatusChange(value: string) {
    setStatusFilter(value);
    fetchHistory(1, value);
  }

  function handlePrevPage() {
    if (page > 1) {
      fetchHistory(page - 1, statusFilter);
    }
  }

  function handleNextPage() {
    if (data && page < data.total_pages) {
      fetchHistory(page + 1, statusFilter);
    }
  }

  /** Allow parent components to trigger a refresh */
  const refresh = useCallback(() => {
    fetchHistory(page, statusFilter);
  }, [page, statusFilter, fetchHistory]);

  // Expose refresh via a stable ref-accessible method on the component
  // Parent components can call this via the onSent callback pattern instead
  void refresh;

  return (
    <div className="space-y-4">
      {/* Filter controls */}
      <div className="flex items-center gap-3">
        <Select value={statusFilter} onValueChange={handleStatusChange}>
          <SelectTrigger className="w-full sm:w-[160px]">
            <SelectValue placeholder="Filter by status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Statuses</SelectItem>
            <SelectItem value="sent">Sent</SelectItem>
            <SelectItem value="delivered">Delivered</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="failed">Failed</SelectItem>
          </SelectContent>
        </Select>

        {isPending && <Loader2 className="size-4 animate-spin text-muted-foreground" />}
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Recipient</TableHead>
              <TableHead className="hidden sm:table-cell">Message</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="hidden md:table-cell">Sent At</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {!data || data.items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} className="h-24 text-center text-muted-foreground">
                  No SMS messages found.
                </TableCell>
              </TableRow>
            ) : (
              data.items.map((entry) => {
                const style = STATUS_STYLES[entry.status] ?? { variant: "outline" as const };
                return (
                  <TableRow key={entry.id}>
                    <TableCell className="font-mono text-sm">
                      {entry.recipient_phone}
                    </TableCell>
                    <TableCell className="hidden sm:table-cell max-w-[200px]">
                      <span className="text-sm text-muted-foreground" title={entry.message}>
                        {truncateMessage(entry.message)}
                      </span>
                    </TableCell>
                    <TableCell>
                      <Badge variant={style.variant} className={style.className}>
                        {entry.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="hidden md:table-cell text-sm text-muted-foreground">
                      {formatDate(entry.sent_at ?? entry.created_at)}
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      {data && data.total_pages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Page {data.page} of {data.total_pages} ({data.total} total)
          </p>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handlePrevPage}
              disabled={page <= 1 || isPending}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleNextPage}
              disabled={page >= data.total_pages || isPending}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
