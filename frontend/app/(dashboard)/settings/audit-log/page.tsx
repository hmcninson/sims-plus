"use client";

import { useCallback, useEffect, useState } from "react";
import { Shield, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { Badge } from "@/components/ui/badge";

import { getAuditLogs } from "@/actions/audit.action";
import type { AuditLogFilters } from "@/actions/audit.action";
import type { AuditLogEntry } from "@/types";

const EVENT_TYPES: { value: string; label: string }[] = [
  { value: "all", label: "All Events" },
  { value: "login", label: "Login" },
  { value: "login_failed", label: "Login Failed" },
  { value: "logout", label: "Logout" },
  { value: "password_change", label: "Password Change" },
  { value: "password_reset", label: "Password Reset" },
  { value: "user_created", label: "User Created" },
  { value: "user_updated", label: "User Updated" },
  { value: "student_created", label: "Student Created" },
  { value: "student_updated", label: "Student Updated" },
  { value: "score_entry", label: "Score Entry" },
  { value: "score_updated", label: "Score Updated" },
  { value: "payment_recorded", label: "Payment Recorded" },
  { value: "invoice_created", label: "Invoice Created" },
];

function formatEventType(eventType: string): string {
  return eventType
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function getEventBadgeVariant(
  eventType: string
): "default" | "secondary" | "destructive" | "outline" {
  if (eventType.includes("failed") || eventType.includes("error")) {
    return "destructive";
  }
  if (eventType.includes("login") || eventType.includes("logout")) {
    return "default";
  }
  if (eventType.includes("created") || eventType.includes("updated")) {
    return "secondary";
  }
  return "outline";
}

function formatTimestamp(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatDetails(details: Record<string, unknown> | undefined): string {
  if (!details) return "-";
  const entries = Object.entries(details);
  if (entries.length === 0) return "-";
  return entries
    .filter(([key]) => !["tenant_id", "user_id"].includes(key))
    .map(([key, value]) => `${key}: ${String(value)}`)
    .slice(0, 3)
    .join(", ");
}

export default function AuditLogPage() {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);

  const [eventType, setEventType] = useState<string>("all");
  const [dateFrom, setDateFrom] = useState<string>("");
  const [dateTo, setDateTo] = useState<string>("");

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    const filters: AuditLogFilters = { page, page_size: 25 };
    if (eventType !== "all") filters.event_type = eventType;
    if (dateFrom) filters.date_from = dateFrom;
    if (dateTo) filters.date_to = dateTo;

    const result = await getAuditLogs(filters);
    if (result.success) {
      setLogs(result.data.items);
      setTotal(result.data.total);
      setTotalPages(result.data.total_pages);
    }
    setLoading(false);
  }, [page, eventType, dateFrom, dateTo]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold tracking-tight">Audit Log</h2>
        <p className="text-sm text-muted-foreground">
          View a read-only log of security and system events ({total} entries)
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-4 sm:flex-row">
        <div className="space-y-1">
          <Label htmlFor="event-type-filter" className="text-xs">
            Event Type
          </Label>
          <Select
            value={eventType}
            onValueChange={(v) => {
              setEventType(v);
              setPage(1);
            }}
          >
            <SelectTrigger id="event-type-filter" className="w-full sm:w-[180px]">
              <SelectValue placeholder="Event type" />
            </SelectTrigger>
            <SelectContent>
              {EVENT_TYPES.map((type) => (
                <SelectItem key={type.value} value={type.value}>
                  {type.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <Label htmlFor="audit-date-from" className="text-xs">
            From
          </Label>
          <Input
            id="audit-date-from"
            type="date"
            value={dateFrom}
            onChange={(e) => {
              setDateFrom(e.target.value);
              setPage(1);
            }}
            className="w-full sm:w-[160px]"
          />
        </div>

        <div className="space-y-1">
          <Label htmlFor="audit-date-to" className="text-xs">
            To
          </Label>
          <Input
            id="audit-date-to"
            type="date"
            value={dateTo}
            onChange={(e) => {
              setDateTo(e.target.value);
              setPage(1);
            }}
            className="w-full sm:w-[160px]"
          />
        </div>
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : logs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <Shield className="mb-4 h-12 w-12" />
              <p className="text-lg font-medium">No audit logs found</p>
              <p className="text-sm">
                Try adjusting your filters or check back later
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[180px]">Timestamp</TableHead>
                    <TableHead className="w-[200px]">User</TableHead>
                    <TableHead className="w-[160px]">Event</TableHead>
                    <TableHead className="hidden md:table-cell">Details</TableHead>
                    <TableHead className="hidden lg:table-cell w-[130px]">IP Address</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {logs.map((log) => (
                    <TableRow key={log.id}>
                      <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                        {formatTimestamp(log.created_at)}
                      </TableCell>
                      <TableCell className="text-sm">
                        {log.user_email || "-"}
                      </TableCell>
                      <TableCell>
                        <Badge variant={getEventBadgeVariant(log.event_type)}>
                          {formatEventType(log.event_type)}
                        </Badge>
                      </TableCell>
                      <TableCell className="hidden md:table-cell max-w-[300px] truncate text-xs text-muted-foreground">
                        {formatDetails(log.details)}
                      </TableCell>
                      <TableCell className="hidden lg:table-cell text-xs text-muted-foreground">
                        {log.ip_address || "-"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            Previous
          </Button>
          <span className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
