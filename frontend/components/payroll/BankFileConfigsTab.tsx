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
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, Plus, Pencil, Trash2, Building2, X } from "lucide-react";

import {
  getBankFileConfigs,
  createBankFileConfig,
  updateBankFileConfig,
  deleteBankFileConfig,
} from "@/actions/payroll.action";
import type { BankFileConfig, ColumnMappingEntry } from "@/types/payroll.type";
import { useToast } from "@/hooks/use-toast";

const COLUMN_SOURCES = [
  { value: "staff_name", label: "Staff Name" },
  { value: "staff_code", label: "Staff Code" },
  { value: "account_number", label: "Account Number" },
  { value: "bank_name", label: "Bank Name" },
  { value: "bank_branch", label: "Bank Branch" },
  { value: "net_salary", label: "Net Salary" },
  { value: "gross_salary", label: "Gross Salary" },
  { value: "basic_salary", label: "Basic Salary" },
  { value: "ssnit_number", label: "SSNIT Number" },
  { value: "tin_number", label: "TIN" },
  { value: "department_name", label: "Department" },
  { value: "template", label: "Template (custom text)" },
];

const bankFileConfigSchema = z.object({
  bank_name: z.string().min(1, "Bank name is required").max(100),
  file_format: z.string().min(1, "Format is required"),
  delimiter: z.string().min(1, "Delimiter is required"),
  include_header_row: z.boolean(),
  is_default: z.boolean(),
  date_format: z.string().optional(),
  amount_format: z.string().optional(),
  encoding: z.string().optional(),
});

type BankFileConfigFormValues = z.infer<typeof bankFileConfigSchema>;

export function BankFileConfigsTab() {
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();
  const [configs, setConfigs] = useState<BankFileConfig[]>([]);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingConfig, setEditingConfig] = useState<BankFileConfig | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [columnMapping, setColumnMapping] = useState<ColumnMappingEntry[]>([]);

  const form = useForm<BankFileConfigFormValues>({
    resolver: zodResolver(bankFileConfigSchema) as Resolver<BankFileConfigFormValues>,
    defaultValues: {
      bank_name: "",
      file_format: "csv",
      delimiter: ",",
      include_header_row: true,
      is_default: false,
      date_format: "YYYY-MM-DD",
      amount_format: "decimal",
      encoding: "utf-8",
    },
  });

  const loadConfigs = () => {
    startTransition(async () => {
      const result = await getBankFileConfigs();
      if (result.success && result.data) {
        setConfigs(result.data);
      }
    });
  };

  useEffect(() => {
    loadConfigs();
  }, []);

  const handleAddColumn = () => {
    setColumnMapping([
      ...columnMapping,
      { header: "", source: "staff_name", template: undefined, width: null },
    ]);
  };

  const handleRemoveColumn = (index: number) => {
    setColumnMapping(columnMapping.filter((_, i) => i !== index));
  };

  const handleUpdateColumn = (index: number, field: keyof ColumnMappingEntry, value: string | number | null) => {
    const updated = [...columnMapping];
    updated[index] = { ...updated[index], [field]: value };
    setColumnMapping(updated);
  };

  const handleOpenDialog = (config?: BankFileConfig) => {
    if (config) {
      setEditingConfig(config);
      form.reset({
        bank_name: config.bank_name,
        file_format: config.file_format,
        delimiter: config.delimiter,
        include_header_row: config.include_header_row,
        is_default: config.is_default,
        date_format: config.date_format || "YYYY-MM-DD",
        amount_format: config.amount_format || "decimal",
        encoding: config.encoding || "utf-8",
      });
      setColumnMapping(config.column_mapping || []);
    } else {
      setEditingConfig(null);
      form.reset({
        bank_name: "",
        file_format: "csv",
        delimiter: ",",
        include_header_row: true,
        is_default: false,
        date_format: "YYYY-MM-DD",
        amount_format: "decimal",
        encoding: "utf-8",
      });
      setColumnMapping([
        { header: "Beneficiary Name", source: "staff_name", width: null },
        { header: "Account Number", source: "account_number", width: null },
        { header: "Amount", source: "net_salary", format: "decimal_2", width: null },
      ]);
    }
    setIsDialogOpen(true);
  };

  const onSubmit = async (formData: BankFileConfigFormValues) => {
    if (columnMapping.length === 0) {
      toast({ title: "Error", description: "Add at least one column mapping.", variant: "destructive" });
      return;
    }

    const hasEmptyHeaders = columnMapping.some((c) => !c.header.trim());
    if (hasEmptyHeaders) {
      toast({ title: "Error", description: "All column headers must be filled.", variant: "destructive" });
      return;
    }

    setIsSubmitting(true);
    try {
      const data = {
        bank_name: formData.bank_name.trim(),
        file_format: formData.file_format,
        delimiter: formData.delimiter,
        column_mapping: columnMapping.map((c) => ({
          ...c,
          header: c.header.trim(),
        })),
        include_header_row: formData.include_header_row,
        is_default: formData.is_default,
        date_format: formData.date_format || undefined,
        amount_format: formData.amount_format || undefined,
        encoding: formData.encoding || undefined,
      };

      if (editingConfig) {
        const result = await updateBankFileConfig(editingConfig.id, data);
        if (result.success) {
          toast({ title: "Bank config updated", description: `${formData.bank_name} has been updated.` });
          setIsDialogOpen(false);
          loadConfigs();
        } else {
          toast({ title: "Error", description: result.error, variant: "destructive" });
        }
      } else {
        const result = await createBankFileConfig(data);
        if (result.success) {
          toast({ title: "Bank config created", description: `${formData.bank_name} has been created.` });
          setIsDialogOpen(false);
          loadConfigs();
        } else {
          toast({ title: "Error", description: result.error, variant: "destructive" });
        }
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    setIsSubmitting(true);
    try {
      const result = await deleteBankFileConfig(deleteId);
      if (result.success) {
        toast({ title: "Bank config deleted" });
        loadConfigs();
      } else {
        toast({ title: "Error", description: result.error, variant: "destructive" });
      }
    } finally {
      setIsSubmitting(false);
      setDeleteId(null);
    }
  };

  return (
    <>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold">Bank File Configurations</h2>
          <p className="text-sm text-muted-foreground">
            Configure bank payment file formats for salary transfers
          </p>
        </div>
        <Button onClick={() => handleOpenDialog()}>
          <Plus className="mr-2 h-4 w-4" />
          Add Bank Config
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>All Bank Configurations</CardTitle>
          <CardDescription>
            {configs.length} configuration{configs.length !== 1 ? "s" : ""} set up
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isPending ? (
            <div className="flex h-[200px] items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : configs.length > 0 ? (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Bank Name</TableHead>
                    <TableHead className="hidden sm:table-cell">Format</TableHead>
                    <TableHead className="hidden md:table-cell">Delimiter</TableHead>
                    <TableHead className="hidden md:table-cell text-right">Columns</TableHead>
                    <TableHead>Default</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {configs.map((config) => (
                    <TableRow key={config.id}>
                      <TableCell className="font-medium">{config.bank_name}</TableCell>
                      <TableCell className="hidden sm:table-cell font-mono text-sm uppercase">
                        {config.file_format}
                      </TableCell>
                      <TableCell className="hidden md:table-cell font-mono text-sm">
                        {config.delimiter === "," ? "Comma" : config.delimiter === "|" ? "Pipe" : config.delimiter === "\t" ? "Tab" : config.delimiter}
                      </TableCell>
                      <TableCell className="hidden md:table-cell text-right">
                        {config.column_mapping.length}
                      </TableCell>
                      <TableCell>
                        {config.is_default ? (
                          <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                            Default
                          </Badge>
                        ) : (
                          <span className="text-sm text-muted-foreground">-</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          <Button variant="ghost" size="icon" onClick={() => handleOpenDialog(config)}>
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="icon" onClick={() => setDeleteId(config.id)}>
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <div className="flex h-[200px] flex-col items-center justify-center gap-2 text-muted-foreground">
              <Building2 className="h-12 w-12" />
              <p>No bank file configurations</p>
              <p className="text-sm text-center max-w-md">
                Create configurations for each bank to generate payment files for salary transfers.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create/Edit Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {editingConfig ? "Edit Bank Configuration" : "Create Bank Configuration"}
            </DialogTitle>
            <DialogDescription>
              {editingConfig
                ? "Update bank file format and column mapping."
                : "Configure how salary payment files are generated for this bank."}
            </DialogDescription>
          </DialogHeader>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="bank_name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Bank Name *</FormLabel>
                      <FormControl>
                        <Input placeholder="e.g., GCB Bank" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="file_format"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>File Format *</FormLabel>
                      <Select onValueChange={field.onChange} defaultValue={field.value}>
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value="csv">CSV</SelectItem>
                          <SelectItem value="txt">TXT</SelectItem>
                          <SelectItem value="xlsx">Excel (XLSX)</SelectItem>
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <FormField
                  control={form.control}
                  name="delimiter"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Delimiter *</FormLabel>
                      <Select onValueChange={field.onChange} defaultValue={field.value}>
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value=",">Comma (,)</SelectItem>
                          <SelectItem value="|">Pipe (|)</SelectItem>
                          <SelectItem value="\t">Tab</SelectItem>
                          <SelectItem value=";">Semicolon (;)</SelectItem>
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="include_header_row"
                  render={({ field }) => (
                    <FormItem className="flex items-center justify-between rounded-lg border p-3">
                      <FormLabel className="text-sm font-medium">Header Row</FormLabel>
                      <FormControl>
                        <Switch checked={field.value} onCheckedChange={field.onChange} />
                      </FormControl>
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="is_default"
                  render={({ field }) => (
                    <FormItem className="flex items-center justify-between rounded-lg border p-3">
                      <FormLabel className="text-sm font-medium">Default</FormLabel>
                      <FormControl>
                        <Switch checked={field.value} onCheckedChange={field.onChange} />
                      </FormControl>
                    </FormItem>
                  )}
                />
              </div>

              {/* Column Mapping Editor */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <FormLabel className="text-sm font-medium">
                    Column Mapping ({columnMapping.length} columns)
                  </FormLabel>
                  <Button type="button" variant="outline" size="sm" onClick={handleAddColumn}>
                    <Plus className="mr-1 h-3 w-3" />
                    Add Column
                  </Button>
                </div>
                {columnMapping.length === 0 ? (
                  <p className="text-sm text-muted-foreground py-4 text-center border rounded-lg">
                    No columns defined. Add at least one column.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {columnMapping.map((col, index) => (
                      <div key={index} className="flex items-center gap-2 rounded-lg border p-2">
                        <Input
                          value={col.header}
                          onChange={(e) => handleUpdateColumn(index, "header", e.target.value)}
                          placeholder="Column header"
                          className="flex-1"
                        />
                        <Select
                          value={col.source}
                          onValueChange={(v) => handleUpdateColumn(index, "source", v)}
                        >
                          <SelectTrigger className="w-full sm:w-[160px]">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {COLUMN_SOURCES.map((s) => (
                              <SelectItem key={s.value} value={s.value}>
                                {s.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        {col.source === "template" && (
                          <Input
                            value={col.template || ""}
                            onChange={(e) => handleUpdateColumn(index, "template", e.target.value)}
                            placeholder="{month_name} {year} Salary"
                            className="flex-1"
                          />
                        )}
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          onClick={() => handleRemoveColumn(index)}
                          className="shrink-0"
                        >
                          <X className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsDialogOpen(false)}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  {editingConfig ? "Save Changes" : "Create Config"}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog open={!!deleteId} onOpenChange={() => setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Bank Configuration?</AlertDialogTitle>
            <AlertDialogDescription>
              This will remove this bank file configuration. Previously generated files will not be affected.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isSubmitting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={isSubmitting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
