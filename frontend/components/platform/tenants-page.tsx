"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import { listTenants } from "@/actions/platform.action";
import type { TenantListResponse, TenantSummary } from "@/types/platform.type";
import { Search, ChevronLeft, ChevronRight, Loader2 } from "lucide-react";

interface TenantsPageProps {
  initialData: TenantListResponse;
}

const STATUS_OPTIONS = [
  { value: "all", label: "All Statuses" },
  { value: "active", label: "Active" },
  { value: "trial", label: "Trial" },
  { value: "suspended", label: "Suspended" },
];

const TIER_OPTIONS = [
  { value: "all", label: "All Plans" },
  { value: "starter", label: "Starter" },
  { value: "professional", label: "Professional" },
  { value: "enterprise", label: "Enterprise" },
];

function statusBadge(status: string) {
  switch (status) {
    case "active":
      return (
        <Badge className="bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400">
          Active
        </Badge>
      );
    case "trial":
      return (
        <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400">
          Trial
        </Badge>
      );
    case "suspended":
      return (
        <Badge variant="destructive">Suspended</Badge>
      );
    default:
      return <Badge variant="secondary">{status}</Badge>;
  }
}

function tierBadge(tier: string) {
  switch (tier) {
    case "enterprise":
      return (
        <Badge className="bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400">
          Enterprise
        </Badge>
      );
    case "professional":
      return (
        <Badge className="bg-indigo-100 text-indigo-800 dark:bg-indigo-900/30 dark:text-indigo-400">
          Professional
        </Badge>
      );
    default:
      return <Badge variant="outline">{tier || "Starter"}</Badge>;
  }
}

function formatDate(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

export function TenantsPage({ initialData }: TenantsPageProps) {
  const router = useRouter();
  const [data, setData] = useState<TenantListResponse>(initialData);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [tier, setTier] = useState("all");
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const fetchTenants = useCallback(
    async (params: {
      page: number;
      search: string;
      status: string;
      tier: string;
    }) => {
      setIsLoading(true);
      const result = await listTenants({
        page: params.page,
        page_size: 20,
        search: params.search || undefined,
        status: params.status === "all" ? undefined : params.status,
        tier: params.tier === "all" ? undefined : params.tier,
      });
      if (result.success) {
        setData(result.data);
      }
      setIsLoading(false);
    },
    [],
  );

  // Debounced search
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setPage(1);
      fetchTenants({ page: 1, search, status, tier });
    }, 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [search, status, tier, fetchTenants]);

  const handlePageChange = useCallback(
    (newPage: number) => {
      setPage(newPage);
      fetchTenants({ page: newPage, search, status, tier });
    },
    [search, status, tier, fetchTenants],
  );

  const totalPages = Math.ceil(data.total / (data.page_size || 20));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Tenants</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Manage all schools on the platform ({data.total} total)
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
          <Input
            placeholder="Search by name or subdomain..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="border-zinc-700 bg-zinc-800 pl-9 text-white placeholder:text-zinc-500"
          />
        </div>
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="w-full border-zinc-700 bg-zinc-800 text-white sm:w-[160px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {STATUS_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={tier} onValueChange={setTier}>
          <SelectTrigger className="w-full border-zinc-700 bg-zinc-800 text-white sm:w-[160px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {TIER_OPTIONS.map((opt) => (
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
              No tenants found
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="border-zinc-800 hover:bg-transparent">
                    <TableHead className="text-zinc-400">Name</TableHead>
                    <TableHead className="hidden text-zinc-400 sm:table-cell">
                      Subdomain
                    </TableHead>
                    <TableHead className="text-zinc-400">Plan</TableHead>
                    <TableHead className="text-zinc-400">Status</TableHead>
                    <TableHead className="hidden text-zinc-400 md:table-cell">
                      Students
                    </TableHead>
                    <TableHead className="hidden text-zinc-400 md:table-cell">
                      Staff
                    </TableHead>
                    <TableHead className="hidden text-zinc-400 lg:table-cell">
                      Created
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.items.map((tenant: TenantSummary) => (
                    <TableRow
                      key={tenant.id}
                      className="cursor-pointer border-zinc-800 text-zinc-300 hover:bg-zinc-800/50"
                      onClick={() =>
                        router.push(`/platform/tenants/${tenant.id}`)
                      }
                    >
                      <TableCell className="font-medium text-white">
                        {tenant.name}
                        <span className="block text-xs text-zinc-500 sm:hidden">
                          {tenant.subdomain}
                        </span>
                      </TableCell>
                      <TableCell className="hidden text-zinc-400 sm:table-cell">
                        {tenant.subdomain}
                      </TableCell>
                      <TableCell>{tierBadge(tenant.subscription_tier)}</TableCell>
                      <TableCell>{statusBadge(tenant.status)}</TableCell>
                      <TableCell className="hidden md:table-cell">
                        {tenant.student_count.toLocaleString()}
                      </TableCell>
                      <TableCell className="hidden md:table-cell">
                        {tenant.staff_count.toLocaleString()}
                      </TableCell>
                      <TableCell className="hidden lg:table-cell">
                        {formatDate(tenant.created_at)}
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
