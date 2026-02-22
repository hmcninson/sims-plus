"use client";

import { useEffect, useState, useTransition } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Plus, Pencil, Trash2, Loader2, BedDouble } from "lucide-react";
import { getDormitories, createDormitory, updateDormitory, deleteDormitory, getHouses } from "@/actions/boarding.action";
import type { Dormitory, House, DormitoryType } from "@/types";
import { useToast } from "@/hooks/use-toast";

const dormitorySchema = z.object({
  house_id: z.string().min(1, "House is required"),
  name: z.string().min(1, "Name is required").max(100),
  floor: z.string().optional(),
  capacity: z.coerce.number().int().positive("Capacity must be positive"),
  dormitory_type: z.enum(["room", "hall", "cubicle"]),
});

type DormFormData = z.infer<typeof dormitorySchema>;

const DORM_TYPES: { value: DormitoryType; label: string }[] = [
  { value: "room", label: "Room" },
  { value: "hall", label: "Hall" },
  { value: "cubicle", label: "Cubicle" },
];

export default function DormitoriesPage() {
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();
  const [dormitories, setDormitories] = useState<Dormitory[]>([]);
  const [houses, setHouses] = useState<House[]>([]);
  const [total, setTotal] = useState(0);
  const [filterHouse, setFilterHouse] = useState("all");

  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingDorm, setEditingDorm] = useState<Dormitory | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const form = useForm<DormFormData>({
    resolver: zodResolver(dormitorySchema),
    defaultValues: { house_id: "", name: "", floor: "", capacity: 20, dormitory_type: "room" },
  });

  useEffect(() => {
    startTransition(async () => {
      const housesResult = await getHouses({ pageSize: 100 });
      if (housesResult.success && housesResult.data) {
        setHouses(Array.isArray(housesResult.data) ? housesResult.data : (housesResult.data.items ?? []));
      }
    });
  }, []);

  const loadDormitories = () => {
    startTransition(async () => {
      const result = await getDormitories({
        houseId: filterHouse !== "all" ? filterHouse : undefined,
      });
      if (result.success && result.data) {
        const data = result.data;
        const items = Array.isArray(data) ? data : (data.items ?? []);
        const count = Array.isArray(data) ? data.length : (data.total ?? 0);
        setDormitories(items);
        setTotal(count);
      }
    });
  };

  useEffect(() => {
    loadDormitories();
  }, [filterHouse]);

  const handleOpenDialog = (dorm?: Dormitory) => {
    if (dorm) {
      setEditingDorm(dorm);
      form.reset({
        house_id: dorm.house_id,
        name: dorm.name,
        floor: dorm.floor || "",
        capacity: dorm.capacity,
        dormitory_type: dorm.dormitory_type as DormitoryType,
      });
    } else {
      setEditingDorm(null);
      form.reset({ house_id: "", name: "", floor: "", capacity: 20, dormitory_type: "room" });
    }
    setIsDialogOpen(true);
  };

  const onSubmit = async (formData: DormFormData) => {
    setIsSubmitting(true);
    try {
      const data = {
        house_id: formData.house_id,
        name: formData.name.trim(),
        floor: formData.floor?.trim() || undefined,
        capacity: formData.capacity,
        dormitory_type: formData.dormitory_type,
      };

      if (editingDorm) {
        const result = await updateDormitory(editingDorm.id, data);
        if (result.success) {
          toast({ title: "Dormitory updated" });
          setIsDialogOpen(false);
          loadDormitories();
        } else {
          toast({ title: "Error", description: result.error, variant: "destructive" });
        }
      } else {
        const result = await createDormitory(data);
        if (result.success) {
          toast({ title: "Dormitory created" });
          setIsDialogOpen(false);
          loadDormitories();
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
      const result = await deleteDormitory(deleteId);
      if (result.success) {
        toast({ title: "Dormitory deleted" });
        loadDormitories();
      } else {
        toast({ title: "Error", description: result.error, variant: "destructive" });
      }
    } finally {
      setIsSubmitting(false);
      setDeleteId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Dormitories</h1>
          <p className="text-muted-foreground">Manage dormitories across all houses</p>
        </div>
        <Button onClick={() => handleOpenDialog()}>
          <Plus className="mr-2 h-4 w-4" />
          Add Dormitory
        </Button>
      </div>

      <Card>
        <CardHeader><CardTitle className="text-base">Filter by House</CardTitle></CardHeader>
        <CardContent>
          <Select value={filterHouse} onValueChange={setFilterHouse}>
            <SelectTrigger className="w-full sm:w-[250px]">
              <SelectValue placeholder="All Houses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Houses</SelectItem>
              {houses.map((h) => (
                <SelectItem key={h.id} value={h.id}>{h.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Dormitories</CardTitle>
          <CardDescription>{total} dormitor{total !== 1 ? "ies" : "y"}</CardDescription>
        </CardHeader>
        <CardContent>
          {isPending ? (
            <div className="flex h-[200px] items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : dormitories.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Floor</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead className="text-right">Capacity</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {dormitories.map((dorm) => (
                  <TableRow key={dorm.id}>
                    <TableCell className="font-medium">{dorm.name}</TableCell>
                    <TableCell>{dorm.floor || "--"}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className="capitalize">{dorm.dormitory_type}</Badge>
                    </TableCell>
                    <TableCell className="text-right">{dorm.capacity}</TableCell>
                    <TableCell>
                      <Badge variant={dorm.is_active ? "default" : "secondary"}>
                        {dorm.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="icon" onClick={() => handleOpenDialog(dorm)}>
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="icon" onClick={() => setDeleteId(dorm.id)}>
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="flex h-[200px] flex-col items-center justify-center gap-2 text-muted-foreground">
              <BedDouble className="h-12 w-12" />
              <p>No dormitories found</p>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingDorm ? "Edit Dormitory" : "Create Dormitory"}</DialogTitle>
            <DialogDescription>{editingDorm ? "Update dormitory details." : "Add a new dormitory to a house."}</DialogDescription>
          </DialogHeader>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <FormField control={form.control} name="house_id" render={({ field }) => (
                <FormItem>
                  <FormLabel>House *</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl>
                      <SelectTrigger className="w-full"><SelectValue placeholder="Select house" /></SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {houses.map((h) => (
                        <SelectItem key={h.id} value={h.id}>{h.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="name" render={({ field }) => (
                <FormItem>
                  <FormLabel>Name *</FormLabel>
                  <FormControl><Input placeholder="e.g., Room A1" {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField control={form.control} name="floor" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Floor</FormLabel>
                    <FormControl><Input placeholder="e.g., Ground" {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )} />
                <FormField control={form.control} name="capacity" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Capacity *</FormLabel>
                    <FormControl><Input type="number" min={1} {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )} />
              </div>
              <FormField control={form.control} name="dormitory_type" render={({ field }) => (
                <FormItem>
                  <FormLabel>Type *</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl>
                      <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {DORM_TYPES.map((t) => (
                        <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )} />
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setIsDialogOpen(false)} disabled={isSubmitting}>Cancel</Button>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  {editingDorm ? "Save Changes" : "Create Dormitory"}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!deleteId} onOpenChange={() => setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Dormitory?</AlertDialogTitle>
            <AlertDialogDescription>This will permanently delete this dormitory and its beds.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isSubmitting}>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} disabled={isSubmitting} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
