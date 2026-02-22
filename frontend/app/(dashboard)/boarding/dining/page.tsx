"use client";

import { useEffect, useState, useTransition } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Plus, Pencil, Trash2, Loader2, UtensilsCrossed } from "lucide-react";
import { getMeals, logMeal, updateMeal, deleteMeal } from "@/actions/boarding.action";
import type { DiningMeal, DiningMealType } from "@/types";
import { useToast } from "@/hooks/use-toast";

const MEAL_TYPES: { value: DiningMealType; label: string }[] = [
  { value: "breakfast", label: "Breakfast" },
  { value: "lunch", label: "Lunch" },
  { value: "dinner", label: "Dinner" },
  { value: "snack", label: "Snack" },
];

function getMealTypeBadge(type: string) {
  switch (type) {
    case "breakfast":
      return <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200">Breakfast</Badge>;
    case "lunch":
      return <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">Lunch</Badge>;
    case "dinner":
      return <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">Dinner</Badge>;
    case "snack":
      return <Badge className="bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200">Snack</Badge>;
    default:
      return <Badge variant="outline" className="capitalize">{type}</Badge>;
  }
}

const mealSchema = z.object({
  date: z.string().min(1, "Date is required"),
  meal_type: z.enum(["breakfast", "lunch", "dinner", "snack"]),
  menu_description: z.string().optional(),
  head_count: z.coerce.number().int().nonnegative("Head count cannot be negative").optional(),
  prepared_by: z.string().optional(),
  notes: z.string().optional(),
});

type MealFormData = z.infer<typeof mealSchema>;

export default function DiningPage() {
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();
  const [meals, setMeals] = useState<DiningMeal[]>([]);
  const [total, setTotal] = useState(0);
  const [filterMealType, setFilterMealType] = useState("all");

  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingMeal, setEditingMeal] = useState<DiningMeal | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const form = useForm<MealFormData>({
    resolver: zodResolver(mealSchema),
    defaultValues: {
      date: new Date().toISOString().split("T")[0],
      meal_type: "lunch",
      menu_description: "",
      head_count: undefined,
      prepared_by: "",
      notes: "",
    },
  });

  const loadMeals = () => {
    startTransition(async () => {
      const result = await getMeals({
        mealType: filterMealType !== "all" ? filterMealType : undefined,
        pageSize: 50,
      });
      if (result.success && result.data) {
        const data = result.data;
        const items = Array.isArray(data) ? data : (data.items ?? []);
        const count = Array.isArray(data) ? data.length : (data.total ?? 0);
        setMeals(items);
        setTotal(count);
      }
    });
  };

  useEffect(() => {
    loadMeals();
  }, [filterMealType]);

  const handleOpenDialog = (meal?: DiningMeal) => {
    if (meal) {
      setEditingMeal(meal);
      form.reset({
        date: meal.date,
        meal_type: meal.meal_type,
        menu_description: meal.menu_description || "",
        head_count: meal.head_count ?? undefined,
        prepared_by: meal.prepared_by || "",
        notes: meal.notes || "",
      });
    } else {
      setEditingMeal(null);
      form.reset({
        date: new Date().toISOString().split("T")[0],
        meal_type: "lunch",
        menu_description: "",
        head_count: undefined,
        prepared_by: "",
        notes: "",
      });
    }
    setIsDialogOpen(true);
  };

  const onSubmit = async (data: MealFormData) => {
    setIsSubmitting(true);
    try {
      const payload = {
        date: data.date,
        meal_type: data.meal_type,
        menu_description: data.menu_description?.trim() || undefined,
        head_count: data.head_count || undefined,
        prepared_by: data.prepared_by?.trim() || undefined,
        notes: data.notes?.trim() || undefined,
      };

      if (editingMeal) {
        const result = await updateMeal(editingMeal.id, {
          meal_type: payload.meal_type,
          menu_description: payload.menu_description,
          head_count: payload.head_count,
          prepared_by: payload.prepared_by,
          notes: payload.notes,
        });
        if (result.success) {
          toast({ title: "Meal updated" });
          setIsDialogOpen(false);
          loadMeals();
        } else {
          toast({ title: "Error", description: result.error, variant: "destructive" });
        }
      } else {
        const result = await logMeal(payload);
        if (result.success) {
          toast({ title: "Meal logged" });
          setIsDialogOpen(false);
          loadMeals();
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
      const result = await deleteMeal(deleteId);
      if (result.success) {
        toast({ title: "Meal record deleted" });
        loadMeals();
      } else {
        toast({ title: "Error", description: result.error, variant: "destructive" });
      }
    } finally {
      setIsSubmitting(false);
      setDeleteId(null);
    }
  };

  // Calculate weekly stats from loaded meals
  const now = new Date();
  const weekStart = new Date(now);
  weekStart.setDate(now.getDate() - now.getDay());
  const weekStartStr = weekStart.toISOString().split("T")[0];
  const thisWeekMeals = meals.filter((m) => m.date >= weekStartStr);
  const totalHeadCount = thisWeekMeals.reduce((sum, m) => sum + (m.head_count || 0), 0);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Dining Management</h1>
          <p className="text-muted-foreground">Log and manage boarding house meals</p>
        </div>
        <Button onClick={() => handleOpenDialog()}>
          <Plus className="mr-2 h-4 w-4" />
          Log Meal
        </Button>
      </div>

      {/* Weekly Summary */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">This Week</CardTitle>
            <UtensilsCrossed className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{thisWeekMeals.length}</div>
            <p className="text-xs text-muted-foreground">meals logged</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Servings</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalHeadCount}</div>
            <p className="text-xs text-muted-foreground">head count this week</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">All Records</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{total}</div>
            <p className="text-xs text-muted-foreground">total meal entries</p>
          </CardContent>
        </Card>
      </div>

      {/* Filter */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Filter by Meal Type</CardTitle>
        </CardHeader>
        <CardContent>
          <Select value={filterMealType} onValueChange={setFilterMealType}>
            <SelectTrigger className="w-full sm:w-[200px]">
              <SelectValue placeholder="Meal Type" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Types</SelectItem>
              {MEAL_TYPES.map((t) => (
                <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CardContent>
      </Card>

      {/* Meals Table */}
      <Card>
        <CardHeader>
          <CardTitle>Meal Log</CardTitle>
          <CardDescription>{total} meal{total !== 1 ? "s" : ""}</CardDescription>
        </CardHeader>
        <CardContent>
          {isPending ? (
            <div className="flex h-[200px] items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : meals.length > 0 ? (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Meal</TableHead>
                    <TableHead className="hidden sm:table-cell">Menu</TableHead>
                    <TableHead className="hidden md:table-cell text-right">Head Count</TableHead>
                    <TableHead className="hidden md:table-cell">Prepared By</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {meals.map((meal) => (
                    <TableRow key={meal.id}>
                      <TableCell className="whitespace-nowrap">
                        {new Date(meal.date + "T00:00:00").toLocaleDateString("en-GB")}
                      </TableCell>
                      <TableCell>{getMealTypeBadge(meal.meal_type)}</TableCell>
                      <TableCell className="hidden sm:table-cell max-w-[250px] truncate">
                        {meal.menu_description || "--"}
                      </TableCell>
                      <TableCell className="hidden md:table-cell text-right">{meal.head_count ?? "--"}</TableCell>
                      <TableCell className="hidden md:table-cell">{meal.prepared_by || "--"}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          <Button variant="ghost" size="icon" onClick={() => handleOpenDialog(meal)}>
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="icon" onClick={() => setDeleteId(meal.id)}>
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
              <UtensilsCrossed className="h-12 w-12" />
              <p>No meals logged yet</p>
              <p className="text-sm text-center max-w-md">
                Start logging daily meals to track dining operations.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create/Edit Meal Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>{editingMeal ? "Edit Meal" : "Log Meal"}</DialogTitle>
            <DialogDescription>
              {editingMeal ? "Update meal details." : "Record a meal for boarding students."}
            </DialogDescription>
          </DialogHeader>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="date"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Date *</FormLabel>
                      <FormControl>
                        <Input type="date" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="meal_type"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Meal Type *</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {MEAL_TYPES.map((t) => (
                            <SelectItem key={t.value} value={t.value}>
                              {t.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <FormField
                control={form.control}
                name="menu_description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Menu Description</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="e.g., Jollof rice with chicken, salad, and juice"
                        rows={2}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="head_count"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Head Count</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          min={0}
                          placeholder="e.g., 150"
                          {...field}
                          value={field.value ?? ""}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="prepared_by"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Prepared By</FormLabel>
                      <FormControl>
                        <Input placeholder="e.g., Kitchen Staff" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <FormField
                control={form.control}
                name="notes"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Notes</FormLabel>
                    <FormControl>
                      <Textarea placeholder="Any additional notes..." rows={2} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
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
                  {editingMeal ? "Save Changes" : "Log Meal"}
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
            <AlertDialogTitle>Delete Meal Record?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete this meal record. This action cannot be undone.
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
    </div>
  );
}
