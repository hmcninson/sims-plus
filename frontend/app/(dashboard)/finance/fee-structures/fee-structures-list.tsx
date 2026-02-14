"use client";

import { useEffect, useState, useTransition, useMemo } from "react";
import Link from "next/link";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Receipt,
  Plus,
  Search,
  MoreHorizontal,
  Eye,
  Edit,
  Copy,
  Trash,
  AlertCircle,
  Loader2,
} from "lucide-react";
import { getFeeStructures, deleteFeeStructure } from "@/actions/finance.action";
import { getAcademicYears, getTerms } from "@/actions/academic.action";
import type { FeeStructure, FeeStructureWithItems, AcademicYear, Term } from "@/types";
import { formatCurrency } from "@/lib/format";
import { useToast } from "@/hooks/use-toast";

const LEVEL_CATEGORIES: Record<string, string> = {
  preschool: "Preschool",
  primary: "Primary",
  jhs: "JHS",
  shs: "SHS",
};

export function FeeStructuresList() {
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();
  const [isInitialLoad, setIsInitialLoad] = useState(true);
  const [isDeleting, setIsDeleting] = useState(false);
  const [feeStructures, setFeeStructures] = useState<FeeStructureWithItems[]>([]);
  const [academicYears, setAcademicYears] = useState<AcademicYear[]>([]);
  const [terms, setTerms] = useState<Term[]>([]);
  const [selectedYear, setSelectedYear] = useState<string>("all");
  const [selectedTerm, setSelectedTerm] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [deleteDialog, setDeleteDialog] = useState<{
    open: boolean;
    feeStructure: FeeStructureWithItems | null;
  }>({ open: false, feeStructure: null });

  const fetchFeeStructures = () => {
    startTransition(async () => {
      const result = await getFeeStructures({
        academicYearId: selectedYear !== "all" ? selectedYear : undefined,
        termId: selectedTerm !== "all" ? selectedTerm : undefined,
      });
      if (result.success && result.data) {
        setFeeStructures(result.data.items);
      } else {
        setError(result.error || "Failed to load fee structures");
      }
      setIsInitialLoad(false);
    });
  };

  useEffect(() => {
    startTransition(async () => {
      const [yearsResult, termsResult] = await Promise.all([
        getAcademicYears(),
        getTerms(),
      ]);

      if (yearsResult.success && yearsResult.data) {
        setAcademicYears(yearsResult.data);
        const currentYear = yearsResult.data.find((y) => y.is_current);
        if (currentYear) {
          setSelectedYear(currentYear.id);
        }
      }

      if (termsResult.success && termsResult.data) {
        setTerms(termsResult.data);
      }
    });
  }, []);

  useEffect(() => {
    fetchFeeStructures();
  }, [selectedYear, selectedTerm]);

  const handleDeleteClick = (feeStructure: FeeStructureWithItems) => {
    setDeleteDialog({ open: true, feeStructure });
  };

  const handleDeleteConfirm = async () => {
    if (!deleteDialog.feeStructure) return;

    setIsDeleting(true);
    const result = await deleteFeeStructure(deleteDialog.feeStructure.id);
    setIsDeleting(false);

    if (result.success) {
      // Update local state directly instead of refetching
      setFeeStructures((prev) =>
        prev.filter((fs) => fs.id !== deleteDialog.feeStructure!.id)
      );
      toast({
        title: "Fee structure deleted",
        description: "The fee structure has been deleted successfully.",
      });
      setDeleteDialog({ open: false, feeStructure: null });
    } else {
      toast({
        title: "Error",
        description: result.error || "Failed to delete fee structure",
        variant: "destructive",
      });
    }
  };

  // Memoize filtered results and calculations
  const filteredFeeStructures = useMemo(
    () =>
      feeStructures.filter((fs) =>
        fs.name.toLowerCase().includes(searchQuery.toLowerCase())
      ),
    [feeStructures, searchQuery]
  );

  const { totalExpectedRevenue, activeCount, withOptionalCount } = useMemo(() => {
    let total = 0;
    let active = 0;
    let withOptional = 0;

    for (const fs of feeStructures) {
      total += Number(fs.total_amount) || 0;
      if (fs.is_active) active++;
      if (fs.items?.some((item) => item.is_optional)) withOptional++;
    }

    return {
      totalExpectedRevenue: total,
      activeCount: active,
      withOptionalCount: withOptional,
    };
  }, [feeStructures]);

  // Memoize filtered terms
  const filteredTerms = useMemo(
    () =>
      terms.filter(
        (t) => selectedYear === "all" || t.academic_year_id === selectedYear
      ),
    [terms, selectedYear]
  );

  if (isInitialLoad && isPending) {
    return (
      <div className="flex h-[400px] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-[400px] flex-col items-center justify-center gap-4">
        <AlertCircle className="h-12 w-12 text-destructive" />
        <p className="text-muted-foreground">{error}</p>
        <Button onClick={() => window.location.reload()}>Retry</Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Fee Structures</h1>
          <p className="text-muted-foreground">
            Manage fee templates for different classes and terms
          </p>
        </div>
        <Button asChild>
          <Link href="/finance/fee-structures/new">
            <Plus className="mr-2 h-4 w-4" />
            New Fee Structure
          </Link>
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              Total Structures
            </CardTitle>
            <Receipt className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{feeStructures.length}</div>
            <p className="text-xs text-muted-foreground">
              {activeCount} active
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              Average Fee Amount
            </CardTitle>
            <Receipt className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {feeStructures.length > 0
                ? formatCurrency(totalExpectedRevenue / feeStructures.length)
                : formatCurrency(0)}
            </div>
            <p className="text-xs text-muted-foreground">per structure</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              With Optional Items
            </CardTitle>
            <Receipt className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{withOptionalCount}</div>
            <p className="text-xs text-muted-foreground">structures</p>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle>Fee Structures</CardTitle>
          <CardDescription>
            View and manage all fee structure templates
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="mb-4 flex flex-col gap-4 sm:flex-row sm:items-center">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search fee structures..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            {isPending && !isInitialLoad && (
              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
            )}
            <Select value={selectedYear} onValueChange={setSelectedYear}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Academic Year" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Years</SelectItem>
                {academicYears.map((year) => (
                  <SelectItem key={year.id} value={year.id}>
                    {year.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={selectedTerm} onValueChange={setSelectedTerm}>
              <SelectTrigger className="w-[150px]">
                <SelectValue placeholder="Term" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Terms</SelectItem>
                {filteredTerms.map((term) => (
                  <SelectItem key={term.id} value={term.id}>
                    {term.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {filteredFeeStructures.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Class/Level</TableHead>
                  <TableHead>Term</TableHead>
                  <TableHead className="text-right">Items</TableHead>
                  <TableHead className="text-right">Total Amount</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-[70px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredFeeStructures.map((fs) => (
                  <TableRow key={fs.id}>
                    <TableCell className="font-medium">
                      <Link
                        href={`/finance/fee-structures/${fs.id}`}
                        className="hover:underline"
                      >
                        {fs.name}
                      </Link>
                    </TableCell>
                    <TableCell>
                      {fs.class_name ||
                       (fs.level_category && LEVEL_CATEGORIES[fs.level_category]) ||
                       (fs.level && LEVEL_CATEGORIES[fs.level]) ||
                       "All"}
                    </TableCell>
                    <TableCell>{fs.term_name || "All Terms"}</TableCell>
                    <TableCell className="text-right">
                      {fs.items?.length || 0}
                    </TableCell>
                    <TableCell className="text-right font-medium">
                      {formatCurrency(fs.total_amount || 0)}
                    </TableCell>
                    <TableCell>
                      <Badge variant={fs.is_active ? "default" : "secondary"}>
                        {fs.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem asChild>
                            <Link href={`/finance/fee-structures/${fs.id}`}>
                              <Eye className="mr-2 h-4 w-4" />
                              View Details
                            </Link>
                          </DropdownMenuItem>
                          <DropdownMenuItem asChild>
                            <Link href={`/finance/fee-structures/${fs.id}/edit`}>
                              <Edit className="mr-2 h-4 w-4" />
                              Edit
                            </Link>
                          </DropdownMenuItem>
                          <DropdownMenuItem asChild>
                            <Link
                              href={`/finance/fee-structures/new?copy=${fs.id}`}
                            >
                              <Copy className="mr-2 h-4 w-4" />
                              Duplicate
                            </Link>
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() => handleDeleteClick(fs)}
                            className="text-destructive"
                          >
                            <Trash className="mr-2 h-4 w-4" />
                            Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="flex h-[200px] flex-col items-center justify-center gap-2 text-muted-foreground">
              <Receipt className="h-12 w-12" />
              <p>No fee structures found</p>
              <Button asChild variant="outline" size="sm">
                <Link href="/finance/fee-structures/new">
                  Create your first fee structure
                </Link>
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Delete Confirmation Dialog */}
      <AlertDialog
        open={deleteDialog.open}
        onOpenChange={(open) =>
          setDeleteDialog((prev) => ({ ...prev, open }))
        }
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Fee Structure</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete{" "}
              <span className="font-medium text-foreground">
                {deleteDialog.feeStructure?.name}
              </span>
              ? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteConfirm}
              disabled={isDeleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isDeleting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
