"use client";

import { useEffect, useState, useTransition } from "react";
import { useForm, type Resolver } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, Pencil, Download, Receipt, AlertTriangle } from "lucide-react";

import {
  getTaxBrackets,
  seedTaxBrackets,
  updateTaxBracket,
} from "@/actions/payroll.action";
import type { TaxBracket } from "@/types/payroll.type";
import { useToast } from "@/hooks/use-toast";

const currentYear = new Date().getFullYear();
const YEAR_OPTIONS = Array.from({ length: 5 }, (_, i) => currentYear - 2 + i);

const taxBracketEditSchema = z.object({
  lower_limit: z.coerce.number().min(0, "Must be 0 or more"),
  upper_limit: z.coerce.number().min(0).optional().or(z.literal("")),
  rate: z.coerce.number().min(0, "Must be 0 or more").max(1, "Rate must be 0-1 (e.g. 0.175 for 17.5%)"),
  cumulative_tax: z.coerce.number().min(0, "Must be 0 or more"),
});

type TaxBracketEditFormValues = z.infer<typeof taxBracketEditSchema>;

function formatGHS(amount: number): string {
  return `GHS ${amount.toLocaleString("en-GH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatRate(rate: number): string {
  return `${(rate * 100).toFixed(1)}%`;
}

export function TaxBracketsTab() {
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();
  const [brackets, setBrackets] = useState<TaxBracket[]>([]);
  const [selectedYear, setSelectedYear] = useState<number>(currentYear);
  const [editingBracket, setEditingBracket] = useState<TaxBracket | null>(null);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [isSeedDialogOpen, setIsSeedDialogOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const form = useForm<TaxBracketEditFormValues>({
    resolver: zodResolver(taxBracketEditSchema) as Resolver<TaxBracketEditFormValues>,
    defaultValues: {
      lower_limit: 0,
      upper_limit: "",
      rate: 0,
      cumulative_tax: 0,
    },
  });

  const loadBrackets = () => {
    startTransition(async () => {
      const result = await getTaxBrackets(selectedYear);
      if (result.success && result.data) {
        setBrackets(result.data.sort((a, b) => a.band_number - b.band_number));
      }
    });
  };

  useEffect(() => {
    loadBrackets();
  }, [selectedYear]);

  const handleEditBracket = (bracket: TaxBracket) => {
    setEditingBracket(bracket);
    form.reset({
      lower_limit: bracket.lower_limit,
      upper_limit: bracket.upper_limit ?? "",
      rate: bracket.rate,
      cumulative_tax: bracket.cumulative_tax,
    });
    setIsEditDialogOpen(true);
  };

  const onSubmitEdit = async (formData: TaxBracketEditFormValues) => {
    if (!editingBracket) return;
    setIsSubmitting(true);
    try {
      const data = {
        lower_limit: formData.lower_limit,
        upper_limit: formData.upper_limit !== "" ? Number(formData.upper_limit) : null,
        rate: formData.rate,
        cumulative_tax: formData.cumulative_tax,
      };

      const result = await updateTaxBracket(editingBracket.id, data);
      if (result.success) {
        toast({ title: "Tax bracket updated", description: `Band ${editingBracket.band_number} has been updated.` });
        setIsEditDialogOpen(false);
        loadBrackets();
      } else {
        toast({ title: "Error", description: result.error, variant: "destructive" });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSeedBrackets = async () => {
    setIsSubmitting(true);
    try {
      const result = await seedTaxBrackets({ effective_year: selectedYear });
      if (result.success) {
        toast({
          title: "Tax brackets seeded",
          description: `${selectedYear} GRA tax brackets have been loaded.`,
        });
        setIsSeedDialogOpen(false);
        loadBrackets();
      } else {
        toast({ title: "Error", description: result.error, variant: "destructive" });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold">Ghana PAYE Tax Brackets</h2>
          <p className="text-sm text-muted-foreground">
            GRA monthly income tax bands used for PAYE calculation
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Select
            value={String(selectedYear)}
            onValueChange={(v) => setSelectedYear(Number(v))}
          >
            <SelectTrigger className="w-full sm:w-[120px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {YEAR_OPTIONS.map((y) => (
                <SelectItem key={y} value={String(y)}>
                  {y}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            variant="outline"
            onClick={() => setIsSeedDialogOpen(true)}
          >
            <Download className="mr-2 h-4 w-4" />
            <span className="hidden sm:inline">Seed GRA Brackets</span>
            <span className="sm:hidden">Seed</span>
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Tax Bands for {selectedYear}</CardTitle>
          <CardDescription>
            {brackets.length} band{brackets.length !== 1 ? "s" : ""} configured
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isPending ? (
            <div className="flex h-[200px] items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : brackets.length > 0 ? (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Band</TableHead>
                    <TableHead className="text-right">Lower Limit</TableHead>
                    <TableHead className="text-right">Upper Limit</TableHead>
                    <TableHead className="text-right">Rate</TableHead>
                    <TableHead className="hidden sm:table-cell text-right">Cumulative Tax</TableHead>
                    <TableHead className="hidden sm:table-cell text-right">Band Width</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {brackets.map((bracket) => {
                    const bandWidth = bracket.upper_limit != null
                      ? bracket.upper_limit - bracket.lower_limit
                      : null;
                    return (
                      <TableRow key={bracket.id}>
                        <TableCell className="font-medium">Band {bracket.band_number}</TableCell>
                        <TableCell className="text-right">{formatGHS(bracket.lower_limit)}</TableCell>
                        <TableCell className="text-right">
                          {bracket.upper_limit != null ? formatGHS(bracket.upper_limit) : (
                            <Badge variant="secondary">No limit</Badge>
                          )}
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          {formatRate(bracket.rate)}
                        </TableCell>
                        <TableCell className="hidden sm:table-cell text-right">
                          {formatGHS(bracket.cumulative_tax)}
                        </TableCell>
                        <TableCell className="hidden sm:table-cell text-right text-muted-foreground">
                          {bandWidth != null ? formatGHS(bandWidth) : "-"}
                        </TableCell>
                        <TableCell className="text-right">
                          <Button variant="ghost" size="icon" onClick={() => handleEditBracket(bracket)}>
                            <Pencil className="h-4 w-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          ) : (
            <div className="flex h-[200px] flex-col items-center justify-center gap-2 text-muted-foreground">
              <Receipt className="h-12 w-12" />
              <p>No tax brackets for {selectedYear}</p>
              <p className="text-sm text-center max-w-md">
                Use the &quot;Seed GRA Brackets&quot; button to load the standard Ghana Revenue Authority tax bands.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Edit Bracket Dialog */}
      <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Edit Tax Band {editingBracket?.band_number}
            </DialogTitle>
            <DialogDescription>
              Update tax bracket values. Ensure brackets remain contiguous.
            </DialogDescription>
          </DialogHeader>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmitEdit)} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="lower_limit"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Lower Limit (GHS) *</FormLabel>
                      <FormControl>
                        <Input type="number" min={0} step={0.01} {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="upper_limit"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Upper Limit (GHS)</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          min={0}
                          step={0.01}
                          placeholder="Leave empty for top band"
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="rate"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Rate (decimal) *</FormLabel>
                      <FormControl>
                        <Input type="number" min={0} max={1} step={0.0001} {...field} />
                      </FormControl>
                      <p className="text-xs text-muted-foreground">
                        e.g., 0.175 for 17.5%
                      </p>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="cumulative_tax"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Cumulative Tax (GHS) *</FormLabel>
                      <FormControl>
                        <Input type="number" min={0} step={0.01} {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-900 dark:bg-amber-950">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="h-4 w-4 text-amber-600 mt-0.5" />
                  <p className="text-xs text-amber-700 dark:text-amber-300">
                    Tax brackets must be contiguous: each band&apos;s lower limit must equal the previous
                    band&apos;s upper limit. The backend will reject non-contiguous brackets.
                  </p>
                </div>
              </div>
              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsEditDialogOpen(false)}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Save Changes
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* Seed Confirmation */}
      <AlertDialog open={isSeedDialogOpen} onOpenChange={setIsSeedDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Seed GRA Tax Brackets?</AlertDialogTitle>
            <AlertDialogDescription>
              This will load the standard Ghana Revenue Authority PAYE tax bands for {selectedYear}.
              If brackets already exist for this year, they will be overwritten.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isSubmitting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleSeedBrackets}
              disabled={isSubmitting}
            >
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Seed Brackets
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
