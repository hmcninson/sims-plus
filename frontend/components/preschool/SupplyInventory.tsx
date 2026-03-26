"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Package,
  Plus,
  Minus,
  Pencil,
  RotateCcw,
  Loader2,
  PackageOpen,
  AlertTriangle,
} from "lucide-react";
import { useForm , type Resolver} from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

import {
  listSupplies,
  addSupply,
  updateSupply,
  useSupply,
  restockSupply,
} from "@/actions/preschool.action";
import type { PreschoolSupply } from "@/types";

// ===========================
// Schemas
// ===========================

const addSupplySchema = z.object({
  item_name: z.string().min(1, "Item name is required").max(100),
  quantity_remaining: z.coerce.number().int().min(0, "Cannot be negative"),
  low_stock_threshold: z.coerce.number().int().min(0, "Cannot be negative"),
  notes: z.string().max(500).optional(),
});

type AddSupplyValues = z.infer<typeof addSupplySchema>;

const editSupplySchema = z.object({
  item_name: z.string().min(1, "Item name is required").max(100),
  low_stock_threshold: z.coerce.number().int().min(0, "Cannot be negative"),
  notes: z.string().max(500).optional(),
});

type EditSupplyValues = z.infer<typeof editSupplySchema>;

const restockSchema = z.object({
  quantity: z.coerce.number().int().min(1, "Must restock at least 1"),
});

type RestockValues = z.infer<typeof restockSchema>;

// ===========================
// Presets
// ===========================

const SUPPLY_PRESETS = [
  "Diapers",
  "Wipes",
  "Spare Clothes",
  "Water Bottle",
  "Blanket",
];

// ===========================
// Helpers
// ===========================

function getQuantityBadge(supply: PreschoolSupply) {
  const { quantity_remaining, low_stock_threshold, is_low_stock } = supply;

  if (is_low_stock || quantity_remaining <= low_stock_threshold) {
    return {
      variant: "destructive" as const,
      className: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300 hover:bg-red-100",
    };
  }

  if (quantity_remaining <= low_stock_threshold + 2) {
    return {
      variant: "secondary" as const,
      className: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-300 hover:bg-amber-100",
    };
  }

  return {
    variant: "secondary" as const,
    className: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300 hover:bg-green-100",
  };
}

// ===========================
// Props
// ===========================

interface SupplyInventoryProps {
  studentId: string;
}

// ===========================
// Component
// ===========================

export function SupplyInventory({ studentId }: SupplyInventoryProps) {
  const [supplies, setSupplies] = useState<PreschoolSupply[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<Record<string, boolean>>({});

  // Dialogs
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [restockDialogOpen, setRestockDialogOpen] = useState(false);
  const [editingSupply, setEditingSupply] = useState<PreschoolSupply | null>(null);
  const [restockingSupply, setRestockingSupply] = useState<PreschoolSupply | null>(null);

  // Forms
  const addForm = useForm<AddSupplyValues>({
    resolver: zodResolver(addSupplySchema) as Resolver<AddSupplyValues>,
    defaultValues: {
      item_name: "",
      quantity_remaining: 0,
      low_stock_threshold: 3,
      notes: "",
    },
  });

  const editForm = useForm<EditSupplyValues>({
    resolver: zodResolver(editSupplySchema) as Resolver<EditSupplyValues>,
    defaultValues: {
      item_name: "",
      low_stock_threshold: 3,
      notes: "",
    },
  });

  const restockForm = useForm<RestockValues>({
    resolver: zodResolver(restockSchema) as Resolver<RestockValues>,
    defaultValues: { quantity: 1 },
  });

  // Fetch
  const fetchSupplies = useCallback(async () => {
    setLoading(true);
    const result = await listSupplies(studentId);
    if (result.success && result.data) {
      setSupplies(result.data);
    } else {
      toast.error(result.error || "Failed to load supplies");
    }
    setLoading(false);
  }, [studentId]);

  useEffect(() => {
    fetchSupplies();
  }, [fetchSupplies]);

  // Handlers
  const setItemLoading = (id: string, val: boolean) => {
    setActionLoading((prev) => ({ ...prev, [id]: val }));
  };

  const handleQuickUse = async (supply: PreschoolSupply) => {
    if (supply.quantity_remaining <= 0) {
      toast.error("No items remaining");
      return;
    }
    setItemLoading(supply.id, true);
    const result = await useSupply(supply.id, 1);
    if (result.success && result.data) {
      setSupplies((prev) =>
        prev.map((s) => (s.id === supply.id ? result.data! : s))
      );
      if (result.data.is_low_stock) {
        toast.warning(`${supply.item_name} is running low (${result.data.quantity_remaining} left)`);
      } else {
        toast.success(`Used 1 ${supply.item_name}`);
      }
    } else {
      toast.error(result.error || "Failed to use supply");
    }
    setItemLoading(supply.id, false);
  };

  const handleQuickRestock = async (supply: PreschoolSupply) => {
    setItemLoading(supply.id, true);
    const result = await restockSupply(supply.id, 1);
    if (result.success && result.data) {
      setSupplies((prev) =>
        prev.map((s) => (s.id === supply.id ? result.data! : s))
      );
      toast.success(`Restocked 1 ${supply.item_name}`);
    } else {
      toast.error(result.error || "Failed to restock supply");
    }
    setItemLoading(supply.id, false);
  };

  const handleAddSupply = async (values: AddSupplyValues) => {
    const result = await addSupply(studentId, {
      item_name: values.item_name,
      quantity_remaining: values.quantity_remaining,
      low_stock_threshold: values.low_stock_threshold,
      notes: values.notes || undefined,
    });
    if (result.success && result.data) {
      setSupplies((prev) => [...prev, result.data!]);
      toast.success(`Added ${values.item_name}`);
      setAddDialogOpen(false);
      addForm.reset();
    } else {
      toast.error(result.error || "Failed to add supply");
    }
  };

  const handleEditSupply = async (values: EditSupplyValues) => {
    if (!editingSupply) return;
    const result = await updateSupply(editingSupply.id, {
      item_name: values.item_name,
      low_stock_threshold: values.low_stock_threshold,
      notes: values.notes || undefined,
    });
    if (result.success && result.data) {
      setSupplies((prev) =>
        prev.map((s) => (s.id === editingSupply.id ? result.data! : s))
      );
      toast.success(`Updated ${values.item_name}`);
      setEditDialogOpen(false);
      setEditingSupply(null);
    } else {
      toast.error(result.error || "Failed to update supply");
    }
  };

  const handleRestock = async (values: RestockValues) => {
    if (!restockingSupply) return;
    const result = await restockSupply(restockingSupply.id, values.quantity);
    if (result.success && result.data) {
      setSupplies((prev) =>
        prev.map((s) => (s.id === restockingSupply.id ? result.data! : s))
      );
      toast.success(`Restocked ${values.quantity} ${restockingSupply.item_name}`);
      setRestockDialogOpen(false);
      setRestockingSupply(null);
      restockForm.reset();
    } else {
      toast.error(result.error || "Failed to restock supply");
    }
  };

  const openEditDialog = (supply: PreschoolSupply) => {
    setEditingSupply(supply);
    editForm.reset({
      item_name: supply.item_name,
      low_stock_threshold: supply.low_stock_threshold,
      notes: supply.notes || "",
    });
    setEditDialogOpen(true);
  };

  const openRestockDialog = (supply: PreschoolSupply) => {
    setRestockingSupply(supply);
    restockForm.reset({ quantity: 1 });
    setRestockDialogOpen(true);
  };

  const applyPreset = (preset: string) => {
    addForm.setValue("item_name", preset, { shouldValidate: true });
  };

  // Low stock count
  const lowStockCount = supplies.filter((s) => s.is_low_stock).length;

  // ===========================
  // Render
  // ===========================

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-40" />
          <Skeleton className="h-4 w-60" />
        </CardHeader>
        <CardContent className="space-y-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-16 w-full rounded-lg" />
          ))}
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <Card>
        <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-3">
          <div className="space-y-1">
            <CardTitle className="text-base flex items-center gap-2">
              <Package className="h-4 w-4" />
              Supplies
              {lowStockCount > 0 && (
                <Badge variant="destructive" className="ml-1">
                  {lowStockCount} low
                </Badge>
              )}
            </CardTitle>
            <CardDescription>
              Track parent-provided supplies for this student
            </CardDescription>
          </div>
          <Button
            size="sm"
            onClick={() => {
              addForm.reset();
              setAddDialogOpen(true);
            }}
          >
            <Plus className="h-4 w-4 mr-1" />
            Add
          </Button>
        </CardHeader>
        <CardContent>
          {supplies.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <PackageOpen className="h-10 w-10 text-muted-foreground mb-3" />
              <p className="text-sm font-medium">No supplies tracked</p>
              <p className="text-xs text-muted-foreground mt-1">
                Add items like diapers, wipes, or spare clothes to track inventory.
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {supplies.map((supply) => {
                const badge = getQuantityBadge(supply);
                const isLoading = actionLoading[supply.id] || false;

                return (
                  <div
                    key={supply.id}
                    className="flex items-center gap-3 rounded-lg border p-3 transition-colors hover:bg-muted/50"
                  >
                    {/* Item info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-medium truncate">
                          {supply.item_name}
                        </span>
                        <Badge variant={badge.variant} className={badge.className}>
                          {supply.quantity_remaining}
                        </Badge>
                        {supply.is_low_stock && (
                          <AlertTriangle className="h-3.5 w-3.5 text-red-500 shrink-0" />
                        )}
                      </div>
                      {supply.notes && (
                        <p className="text-xs text-muted-foreground mt-0.5 truncate">
                          {supply.notes}
                        </p>
                      )}
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-1 shrink-0">
                      <TooltipProvider delayDuration={300}>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              variant="outline"
                              size="icon"
                              className="h-8 w-8"
                              disabled={isLoading || supply.quantity_remaining <= 0}
                              onClick={() => handleQuickUse(supply)}
                            >
                              {isLoading ? (
                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              ) : (
                                <Minus className="h-3.5 w-3.5" />
                              )}
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>Use 1</TooltipContent>
                        </Tooltip>

                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              variant="outline"
                              size="icon"
                              className="h-8 w-8"
                              disabled={isLoading}
                              onClick={() => handleQuickRestock(supply)}
                            >
                              <Plus className="h-3.5 w-3.5" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>Add 1</TooltipContent>
                        </Tooltip>

                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8"
                              onClick={() => openRestockDialog(supply)}
                            >
                              <RotateCcw className="h-3.5 w-3.5" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>Bulk restock</TooltipContent>
                        </Tooltip>

                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8"
                              onClick={() => openEditDialog(supply)}
                            >
                              <Pencil className="h-3.5 w-3.5" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>Edit</TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Add Supply Dialog */}
      <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Add Supply Item</DialogTitle>
            <DialogDescription>
              Track a new supply item for this student.
            </DialogDescription>
          </DialogHeader>
          <Form {...addForm}>
            <form
              onSubmit={addForm.handleSubmit(handleAddSupply)}
              className="space-y-4"
            >
              {/* Presets */}
              <div>
                <p className="text-xs text-muted-foreground mb-2">Quick presets</p>
                <div className="flex flex-wrap gap-1.5">
                  {SUPPLY_PRESETS.map((preset) => (
                    <Button
                      key={preset}
                      type="button"
                      variant="outline"
                      size="sm"
                      className="h-7 text-xs"
                      onClick={() => applyPreset(preset)}
                    >
                      {preset}
                    </Button>
                  ))}
                </div>
              </div>

              <FormField
                control={addForm.control}
                name="item_name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Item Name</FormLabel>
                    <FormControl>
                      <Input placeholder="e.g., Diapers" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <FormField
                  control={addForm.control}
                  name="quantity_remaining"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Initial Quantity</FormLabel>
                      <FormControl>
                        <Input type="number" min={0} {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={addForm.control}
                  name="low_stock_threshold"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Low Stock Threshold</FormLabel>
                      <FormControl>
                        <Input type="number" min={0} {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <FormField
                control={addForm.control}
                name="notes"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Notes (optional)</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Brand preference, size, etc."
                        className="resize-none"
                        rows={2}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setAddDialogOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={addForm.formState.isSubmitting}
                >
                  {addForm.formState.isSubmitting ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                      Adding...
                    </>
                  ) : (
                    "Add Supply"
                  )}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* Edit Supply Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Edit Supply</DialogTitle>
            <DialogDescription>
              Update supply item details.
            </DialogDescription>
          </DialogHeader>
          <Form {...editForm}>
            <form
              onSubmit={editForm.handleSubmit(handleEditSupply)}
              className="space-y-4"
            >
              <FormField
                control={editForm.control}
                name="item_name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Item Name</FormLabel>
                    <FormControl>
                      <Input {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={editForm.control}
                name="low_stock_threshold"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Low Stock Threshold</FormLabel>
                    <FormControl>
                      <Input type="number" min={0} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={editForm.control}
                name="notes"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Notes (optional)</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Brand preference, size, etc."
                        className="resize-none"
                        rows={2}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setEditDialogOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={editForm.formState.isSubmitting}
                >
                  {editForm.formState.isSubmitting ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    "Save Changes"
                  )}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* Restock Dialog */}
      <Dialog open={restockDialogOpen} onOpenChange={setRestockDialogOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Restock {restockingSupply?.item_name}</DialogTitle>
            <DialogDescription>
              Enter the quantity to add to the current stock
              {restockingSupply && (
                <> (currently {restockingSupply.quantity_remaining})</>
              )}
              .
            </DialogDescription>
          </DialogHeader>
          <Form {...restockForm}>
            <form
              onSubmit={restockForm.handleSubmit(handleRestock)}
              className="space-y-4"
            >
              <FormField
                control={restockForm.control}
                name="quantity"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Quantity to Add</FormLabel>
                    <FormControl>
                      <Input type="number" min={1} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setRestockDialogOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={restockForm.formState.isSubmitting}
                >
                  {restockForm.formState.isSubmitting ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                      Restocking...
                    </>
                  ) : (
                    "Restock"
                  )}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>
    </>
  );
}
