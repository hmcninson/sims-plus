"use client";

import { useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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
import { Card, CardContent } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { getPlatformAuditLog } from "@/actions/platform.action";
import type {
  PlatformAuditLogResponse,
  PlatformAuditEntry,
} from "@/types/platform.type";
import {
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  Loader2,
} from "lucide-react";

interface AuditLogPageProps {
  initialData: PlatformAuditLogResponse;
}

const ACTION_OPTIONS = [
  { value: "all", label: "All Actions" },
  { value: "login", label: "Login" },
  { value: "tenant.create", label: "Tenant Create" },
  { value: "tenant.update", label: "Tenant Update" },
  { value: "tenant.suspend", label: "Tenant Suspend" },
  { value: "tenant.activate", label: "Tenant Activate" },
  { value: "impersonate", label: "Impersonate" },
  { value: "user.create", label: "User Create" },
  { value: "user.update", label: "User Update" },
];

function actionBadge(action: string) {
  if (action.includes("suspend")) {
    return <Badge variant="destructive">{action}</Badge>;
  }
  if (action.includes("activate") || action.includes("create")) {
    return (
      <Badge className="bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400">
        {action}
      </Badge>
    );
  }
  if (action.includes("impersonate")) {
    return (
      <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400">
        {action}
      </Badge>
    );
  }
  if (action.includes("login")) {
    return (
      <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400">
        {action}
      </Badge>
    );
  }
  return <Badge variant="secondary">{action}</Badge>;
}

function formatTimestamp(dateStr: string): string {
  try {
    return new Date(dateStr).toLocaleString("en-GB", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return dateStr;
  }
}

function ExpandableRow({ entry }: { entry: PlatformAuditEntry }) {
  const [open, setOpen] = useState(false);
  const hasDetails =
    entry.details && Object.keys(entry.details).length > 0;

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <TableRow className="border-zinc-800 text-zinc-300 hover:bg-zinc-800/50">
        <TableCell className="hidden text-zinc-400 sm:table-cell">
          {formatTimestamp(entry.created_at)}
        </TableCell>
        <TableCell className="text-white">
          {entry.actor_email || entry.actor_user_id.slice(0, 8)}
          <span className="block text-xs text-zinc-500 sm:hidden">
            {formatTimestamp(entry.created_at)}
          </span>
        </TableCell>
        <TableCell>{actionBadge(entry.action)}</TableCell>
        <TableCell className="hidden md:table-cell">
          {entry.target_tenant_name || "--"}
        </TableCell>
        <TableCell>
          {hasDetails ? (
            <CollapsibleTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="text-zinc-400 hover:text-white"
              >
                {open ? (
                  <ChevronUp className="h-4 w-4" />
                ) : (
                  <ChevronDown className="h-4 w-4" />
                )}
              </Button>
            </CollapsibleTrigger>
          ) : (
            <span className="text-zinc-600">--</span>
          )}
        </TableCell>
      </TableRow>
      {hasDetails && (
        <CollapsibleContent asChild>
          <tr className="border-zinc-800">
            <td colSpan={5} className="bg-zinc-800/30 px-6 py-3">
              <pre className="overflow-x-auto whitespace-pre-wrap text-xs text-zinc-400">
                {JSON.stringify(entry.details, null, 2)}
              </pre>
            </td>
          </tr>
        </CollapsibleContent>
      )}
    </Collapsible>
  );
}

export function AuditLogPage({ initialData }: AuditLogPageProps) {
  const [data, setData] = useState<PlatformAuditLogResponse>(initialData);
  const [action, setAction] = useState("all");
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(false);

  const fetchLog = useCallback(
    async (params: { page: number; action: string }) => {
      setIsLoading(true);
      const result = await getPlatformAuditLog({
        page: params.page,
        page_size: 25,
        action: params.action === "all" ? undefined : params.action,
      });
      if (result.success) {
        setData(result.data);
      }
      setIsLoading(false);
    },
    [],
  );

  const handleActionChange = useCallback(
    (value: string) => {
      setAction(value);
      setPage(1);
      fetchLog({ page: 1, action: value });
    },
    [fetchLog],
  );

  const handlePageChange = useCallback(
    (newPage: number) => {
      setPage(newPage);
      fetchLog({ page: newPage, action });
    },
    [action, fetchLog],
  );

  const totalPages = Math.ceil(data.total / (data.page_size || 25));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Audit Log</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Platform admin actions and events ({data.total} total)
        </p>
      </div>

      {/* Filters */}
      <div>
        <Select value={action} onValueChange={handleActionChange}>
          <SelectTrigger className="w-full border-zinc-700 bg-zinc-800 text-white sm:w-[200px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {ACTION_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <Card className="border-zinc-800 bg-zinc-900">
        <CardContent className="p-0">
          {isLoading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-6 w-6 animate-spin text-zinc-500" />
            </div>
          ) : data.items.length === 0 ? (
            <div className="py-16 text-center text-zinc-500">
              No audit log entries found
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="border-zinc-800 hover:bg-transparent">
                    <TableHead className="hidden text-zinc-400 sm:table-cell">
                      Timestamp
                    </TableHead>
                    <TableHead className="text-zinc-400">Actor</TableHead>
                    <TableHead className="text-zinc-400">Action</TableHead>
                    <TableHead className="hidden text-zinc-400 md:table-cell">
                      Target
                    </TableHead>
                    <TableHead className="w-[60px] text-zinc-400">
                      Details
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.items.map((entry: PlatformAuditEntry) => (
                    <ExpandableRow key={entry.id} entry={entry} />
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-zinc-500">
            Page {page} of {totalPages}
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              className="border-zinc-700 text-zinc-400"
              disabled={page <= 1}
              onClick={() => handlePageChange(page - 1)}
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="border-zinc-700 text-zinc-400"
              disabled={page >= totalPages}
              onClick={() => handlePageChange(page + 1)}
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
