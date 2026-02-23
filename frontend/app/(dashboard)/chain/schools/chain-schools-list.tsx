"use client";

/**
 * Chain Schools List
 *
 * Displays all schools in the chain with search and pagination.
 * Allows navigating to school details or adding a new school.
 */

import { useState, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { School, Plus, Search, AlertCircle } from "lucide-react";
import { getChainSchools } from "@/actions/chain.action";
import type { ChainSchool } from "@/types/chain.type";

interface ChainSchoolsListProps {
  initialData: {
    items: ChainSchool[];
    total: number;
  };
  error?: string;
}

export function ChainSchoolsList({ initialData, error }: ChainSchoolsListProps) {
  const router = useRouter();
  const [data, setData] = useState(initialData);
  const [search, setSearch] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const fetchSchools = useCallback(async (page: number, searchTerm: string) => {
    setIsLoading(true);
    try {
      const result = await getChainSchools(page, 20, searchTerm || undefined);
      if (result.success && result.data) {
        setData(result.data);
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  const handleSearch = useCallback(() => {
    fetchSchools(1, search);
  }, [search, fetchSchools]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") {
        handleSearch();
      }
    },
    [handleSearch]
  );

  if (error) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold tracking-tight">Schools</h1>
        <Alert variant="destructive">
          <AlertCircle className="size-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Schools</h1>
          <p className="text-muted-foreground">
            Manage schools in your chain ({data.total} total).
          </p>
        </div>
        <Button asChild>
          <Link href="/chain/schools/new">
            <Plus className="mr-2 size-4" />
            Add School
          </Link>
        </Button>
      </div>

      {/* Search */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search schools by name or code..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                onKeyDown={handleKeyDown}
                className="pl-9"
              />
            </div>
            <Button variant="secondary" onClick={handleSearch} disabled={isLoading}>
              Search
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Schools Table */}
      <Card>
        <CardHeader>
          <CardTitle>All Schools</CardTitle>
          <CardDescription>
            Click on a school to view details and manage settings.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {data.items.length === 0 ? (
            <div className="py-8 text-center text-muted-foreground">
              <School className="mx-auto mb-2 size-8" />
              <p>No schools found.</p>
              {!search && (
                <Button asChild variant="outline" className="mt-4">
                  <Link href="/chain/schools/new">Add Your First School</Link>
                </Button>
              )}
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>School</TableHead>
                      <TableHead className="hidden sm:table-cell">Code</TableHead>
                      <TableHead className="hidden sm:table-cell text-right">Students</TableHead>
                      <TableHead className="hidden sm:table-cell text-right">Staff</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.items.map((school) => (
                      <TableRow
                        key={school.id}
                        className="cursor-pointer"
                        onClick={() => router.push(`/chain/schools/${school.id}`)}
                      >
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <div className="flex size-8 items-center justify-center rounded bg-muted">
                              <School className="size-4 text-muted-foreground" />
                            </div>
                            <span className="font-medium">{school.name}</span>
                          </div>
                        </TableCell>
                        <TableCell className="hidden sm:table-cell">
                          <span className="text-muted-foreground">{school.code ?? "-"}</span>
                        </TableCell>
                        <TableCell className="hidden sm:table-cell text-right">
                          {school.student_count.toLocaleString()}
                        </TableCell>
                        <TableCell className="hidden sm:table-cell text-right">
                          {school.staff_count.toLocaleString()}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
