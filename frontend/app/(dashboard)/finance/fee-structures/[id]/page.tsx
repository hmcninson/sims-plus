"use client";

import { useEffect, useState, useTransition } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  ArrowLeft,
  Edit,
  Copy,
  FileText,
  AlertCircle,
  Receipt,
} from "lucide-react";
import { getFeeStructure } from "@/actions/finance.action";
import type { FeeStructureWithItems } from "@/types";
import { formatCurrency } from "@/lib/format";

const LEVEL_CATEGORIES: Record<string, string> = {
  preschool: "Preschool",
  primary: "Primary",
  jhs: "JHS",
  shs: "SHS",
};

const STUDENT_TYPES: Record<string, string> = {
  all: "All Students",
  boarding: "Boarding Students",
  day: "Day Students",
};

export default function FeeStructureDetailPage() {
  const params = useParams();
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [feeStructure, setFeeStructure] = useState<FeeStructureWithItems | null>(null);
  const [error, setError] = useState<string | null>(null);

  const feeStructureId = params.id as string;

  useEffect(() => {
    startTransition(async () => {
      const result = await getFeeStructure(feeStructureId);
      if (result.success && result.data) {
        setFeeStructure(result.data);
      } else {
        setError(result.error || "Failed to load fee structure");
      }
    });
  }, [feeStructureId]);

  if (isPending && !feeStructure) {
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
        <Button onClick={() => router.push("/finance/fee-structures")}>
          Back to Fee Structures
        </Button>
      </div>
    );
  }

  if (!feeStructure) return null;

  const requiredTotal =
    feeStructure.items
      ?.filter((item) => !item.is_optional)
      .reduce((sum, item) => sum + Number(item.amount), 0) || 0;

  const optionalTotal =
    feeStructure.items
      ?.filter((item) => item.is_optional)
      .reduce((sum, item) => sum + Number(item.amount), 0) || 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link href="/finance/fee-structures">
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight">
                {feeStructure.name}
              </h1>
              <Badge variant={feeStructure.is_active ? "default" : "secondary"}>
                {feeStructure.is_active ? "Active" : "Inactive"}
              </Badge>
            </div>
            <p className="text-muted-foreground">
              {feeStructure.class_name ||
               (feeStructure.level_category && LEVEL_CATEGORIES[feeStructure.level_category]) ||
               (feeStructure.level && LEVEL_CATEGORIES[feeStructure.level]) ||
               "All Classes"} -{" "}
              {feeStructure.term_name || "All Terms"}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" asChild>
            <Link href={`/finance/fee-structures/new?copy=${feeStructureId}`}>
              <Copy className="mr-2 h-4 w-4" />
              Duplicate
            </Link>
          </Button>
          <Button variant="outline" asChild>
            <Link href={`/finance/fee-structures/${feeStructureId}/edit`}>
              <Edit className="mr-2 h-4 w-4" />
              Edit
            </Link>
          </Button>
          <Button asChild>
            <Link
              href={`/finance/invoices/generate?fee_structure_id=${feeStructureId}`}
            >
              <FileText className="mr-2 h-4 w-4" />
              Generate Invoices
            </Link>
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Required Fees</CardTitle>
            <Receipt className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatCurrency(requiredTotal)}
            </div>
            <p className="text-xs text-muted-foreground">
              {feeStructure.items?.filter((i) => !i.is_optional).length || 0}{" "}
              items
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Optional Fees</CardTitle>
            <Receipt className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-muted-foreground">
              {formatCurrency(optionalTotal)}
            </div>
            <p className="text-xs text-muted-foreground">
              {feeStructure.items?.filter((i) => i.is_optional).length || 0}{" "}
              items
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              Total (All Items)
            </CardTitle>
            <Receipt className="h-4 w-4 text-green-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {formatCurrency(feeStructure.total_amount || 0)}
            </div>
            <p className="text-xs text-muted-foreground">
              {feeStructure.items?.length || 0} total items
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Fee Items */}
      <Card>
        <CardHeader>
          <CardTitle>Fee Items</CardTitle>
          <CardDescription>
            Individual fee components in this structure
          </CardDescription>
        </CardHeader>
        <CardContent>
          {feeStructure.items && feeStructure.items.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[50px]">#</TableHead>
                  <TableHead>Item Name</TableHead>
                  <TableHead className="text-right">Amount (GHS)</TableHead>
                  <TableHead className="text-center">Type</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {feeStructure.items
                  .sort((a, b) => a.sequence - b.sequence)
                  .map((item, index) => (
                    <TableRow key={item.id}>
                      <TableCell className="text-muted-foreground">
                        {index + 1}
                      </TableCell>
                      <TableCell className="font-medium">{item.name}</TableCell>
                      <TableCell className="text-right font-mono">
                        {Number(item.amount).toLocaleString("en-GH", {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2,
                        })}
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge
                          variant={item.is_optional ? "secondary" : "default"}
                        >
                          {item.is_optional ? "Optional" : "Required"}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
              </TableBody>
            </Table>
          ) : (
            <div className="flex h-[200px] flex-col items-center justify-center gap-2 text-muted-foreground">
              <Receipt className="h-12 w-12" />
              <p>No fee items defined</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Details */}
      <Card>
        <CardHeader>
          <CardTitle>Details</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            <div>
              <dt className="text-sm font-medium text-muted-foreground">
                Academic Year
              </dt>
              <dd className="mt-1">
                {feeStructure.academic_year_name || "All Years"}
              </dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-muted-foreground">
                Term
              </dt>
              <dd className="mt-1">{feeStructure.term_name || "All Terms"}</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-muted-foreground">
                Class
              </dt>
              <dd className="mt-1">
                {feeStructure.class_name || "All Classes"}
              </dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-muted-foreground">
                Level Category
              </dt>
              <dd className="mt-1">
                {(feeStructure.level_category && LEVEL_CATEGORIES[feeStructure.level_category]) ||
                 (feeStructure.level && LEVEL_CATEGORIES[feeStructure.level]) ||
                 "All Levels"}
              </dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-muted-foreground">
                Student Type
              </dt>
              <dd className="mt-1">
                {STUDENT_TYPES[feeStructure.student_type || "all"]}
              </dd>
            </div>
          </dl>
        </CardContent>
      </Card>
    </div>
  );
}
