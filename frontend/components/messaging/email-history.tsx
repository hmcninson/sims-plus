"use client";

import { useTransition } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ChevronLeft, ChevronRight, Loader2 } from "lucide-react";
import { getEmailHistory } from "@/actions/messaging.action";
import { formatRelativeTime } from "@/lib/format";
import type { EmailHistoryResponse, EmailLogEntry } from "@/types/messaging.type";

interface EmailHistoryProps {
  data: EmailHistoryResponse | undefined;
  onDataChange: (data: EmailHistoryResponse) => void;
}

const STATUS_BADGE_STYLES: Record<string, string> = {
  sent: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
  delivered: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
  failed: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
  bounced: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
  pending: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400",
};

/**
 * Displays a paginated table of email history with status badges,
 * status filter, and pagination controls.
 */
export function EmailHistory({ data, onDataChange }: EmailHistoryProps) {
  const [isPending, startTransition] = useTransition();

  function fetchPage(page: number, statusFilter?: string) {
    startTransition(async () => {
      const result = await getEmailHistory(page, 20, statusFilter);
      if (result.success && result.data) {
        onDataChange(result.data);
      }
    });
  }

  function handleStatusFilter(value: string) {
    const filterValue = value === "all" ? undefined : value;
    fetchPage(1, filterValue);
  }

  function handlePreviousPage() {
    if (data && data.page > 1) {
      fetchPage(data.page - 1);
    }
  }

  function handleNextPage() {
    if (data && data.page < data.total_pages) {
      fetchPage(data.page + 1);
    }
  }

  if (!data) {
    return (
      <div className="flex h-[200px] items-center justify-center text-muted-foreground">
        No email history available
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Toolbar: status filter */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Select defaultValue="all" onValueChange={handleStatusFilter}>
            <SelectTrigger className="w-[140px]">
              <SelectValue placeholder="All statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Statuses</SelectItem>
              <SelectItem value="sent">Sent</SelectItem>
              <SelectItem value="delivered">Delivered</SelectItem>
              <SelectItem value="pending">Pending</SelectItem>
              <SelectItem value="failed">Failed</SelectItem>
              <SelectItem value="bounced">Bounced</SelectItem>
            </SelectContent>
          </Select>
          {isPending && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
        </div>
        <p className="text-sm text-muted-foreground">
          {data.total} email{data.total !== 1 ? "s" : ""} total
        </p>
      </div>

      {/* Table */}
      {data.items.length === 0 ? (
        <div className="flex h-[200px] items-center justify-center text-muted-foreground">
          No emails found
        </div>
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Recipient</TableHead>
                <TableHead className="hidden sm:table-cell">Subject</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="hidden md:table-cell">Sent</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.map((entry: EmailLogEntry) => (
                <TableRow key={entry.id}>
                  <TableCell>
                    <div>
                      {entry.recipient_name && (
                        <div className="font-medium text-sm">{entry.recipient_name}</div>
                      )}
                      <div className="text-sm text-muted-foreground truncate max-w-[200px]">
                        {entry.recipient_email}
                      </div>
                      {/* Show subject on mobile where the column is hidden */}
                      <div className="text-xs text-muted-foreground truncate max-w-[200px] sm:hidden mt-0.5">
                        {entry.subject}
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="hidden sm:table-cell">
                    <span className="truncate block max-w-[250px]" title={entry.subject}>
                      {entry.subject}
                    </span>
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant="outline"
                      className={STATUS_BADGE_STYLES[entry.status] || ""}
                    >
                      {entry.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="hidden md:table-cell text-sm text-muted-foreground">
                    {entry.sent_at
                      ? formatRelativeTime(entry.sent_at)
                      : formatRelativeTime(entry.created_at)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Pagination */}
      {data.total_pages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Page {data.page} of {data.total_pages}
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handlePreviousPage}
              disabled={data.page <= 1 || isPending}
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleNextPage}
              disabled={data.page >= data.total_pages || isPending}
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
