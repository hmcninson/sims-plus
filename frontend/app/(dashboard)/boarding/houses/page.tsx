"use client";

import { useEffect, useState, useTransition } from "react";
import Link from "next/link";
import { useForm , type Resolver} from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
import { Textarea } from "@/components/ui/textarea";
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
  Plus,
  Pencil,
  Trash2,
  Search,
  Loader2,
  Building2,
  Eye,
} from "lucide-react";
import {
  getHouses,
  createHouse,
  updateHouse,
  deleteHouse,
} from "@/actions/boarding.action";
import type { House, HouseGender } from "@/types";
import { useToast } from "@/hooks/use-toast";

const houseSchema = z.object({
  name: z.string().min(1, "House name is required").max(100),
  house_code: z.string().min(1, "House code is required").max(20),
  gender: z.enum(["male", "female", "mixed"]),
  capacity: z.coerce.number().int().positive("Capacity must be positive"),
  description: z.string().optional(),
});

type HouseFormData = z.infer<typeof houseSchema>;

const GENDER_OPTIONS: { value: HouseGender; label: string }[] = [
  { value: "male", label: "Male" },
  { value: "female", label: "Female" },
  { value: "mixed", label: "Mixed" },
];

function getGenderBadge(gender: string) {
  switch (gender) {
    case "male":
      return <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">Male</Badge>;
    case "female":
      return <Badge className="bg-pink-100 text-pink-800 dark:bg-pink-900 dark:text-pink-200">Female</Badge>;
    case "mixed":
      return <Badge className="bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200">Mixed</Badge>;
    default:
      return <Badge variant="secondary">{gender}</Badge>;
  }
}

export default function HousesPage() {
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();
  const [houses, setHouses] = useState<House[]>([]);
  const [total, setTotal] = useState(0);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterGender, setFilterGender] = useState<string>("all");

  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingHouse, setEditingHouse] = useState<House | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const form = useForm<HouseFormData>({
    resolver: zodResolver(houseSchema) as Resolver<HouseFormData>,
    defaultValues: {
      name: "",
      house_code: "",
      gender: "male",
      capacity: 50,
      description: "",
    },
  });

  const loadHouses = () => {
    startTransition(async () => {
      const result = await getHouses({
        search: searchQuery || undefined,
        gender: filterGender !== "all" ? filterGender : undefined,
      });
      if (result.success && result.data) {
        const data = result.data;
        const items = Array.isArray(data) ? data : (data.items ?? []);
        const count = Array.isArray(data) ? data.length : (data.total ?? 0);
        setHouses(items);
        setTotal(count);
      }
    });
  };

  useEffect(() => {
    const timer = setTimeout(loadHouses, 300);
    return () => clearTimeout(timer);
  }, [searchQuery, filterGender]);

  const handleOpenDialog = (house?: House) => {
    if (house) {
      setEditingHouse(house);
      form.reset({
        name: house.name,
        house_code: house.house_code,
        gender: house.gender,
        capacity: house.capacity,
        description: house.description || "",
      });
    } else {
      setEditingHouse(null);
      form.reset({
        name: "",
        house_code: "",
        gender: "male",
        capacity: 50,
        description: "",
      });
    }
    setIsDialogOpen(true);
  };

  const onSubmit = async (formData: HouseFormData) => {
    setIsSubmitting(true);
    try {
      const data = {
        name: formData.name.trim(),
        house_code: formData.house_code.trim(),
        gender: formData.gender,
        capacity: formData.capacity,
        description: formData.description?.trim() || undefined,
      };

      if (editingHouse) {
        const result = await updateHouse(editingHouse.id, data);
        if (result.success) {
          toast({ title: "House updated", description: `${formData.name} has been updated.` });
          setIsDialogOpen(false);
          loadHouses();
        } else {
          toast({ title: "Error", description: result.error, variant: "destructive" });
        }
      } else {
        const result = await createHouse(data);
        if (result.success) {
          toast({ title: "House created", description: `${formData.name} has been created.` });
          setIsDialogOpen(false);
          loadHouses();
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
      const result = await deleteHouse(deleteId);
      if (result.success) {
        toast({ title: "House deleted" });
        loadHouses();
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
          <h1 className="text-2xl font-bold tracking-tight">Houses</h1>
          <p className="text-muted-foreground">Manage boarding houses</p>
        </div>
        <Button onClick={() => handleOpenDialog()}>
          <Plus className="mr-2 h-4 w-4" />
          Add House
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Filters</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-4 sm:flex-row">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search houses..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select value={filterGender} onValueChange={setFilterGender}>
              <SelectTrigger className="w-full sm:w-[150px]">
                <SelectValue placeholder="Gender" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Genders</SelectItem>
                {GENDER_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Houses</CardTitle>
          <CardDescription>{total} house{total !== 1 ? "s" : ""} found</CardDescription>
        </CardHeader>
        <CardContent>
          {isPending ? (
            <div className="flex h-[200px] items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : houses.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead className="hidden sm:table-cell">Code</TableHead>
                  <TableHead className="hidden sm:table-cell">Gender</TableHead>
                  <TableHead className="hidden md:table-cell text-right">Capacity</TableHead>
                  <TableHead className="hidden md:table-cell">Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {houses.map((house) => (
                  <TableRow key={house.id}>
                    <TableCell className="font-medium">{house.name}</TableCell>
                    <TableCell className="hidden sm:table-cell font-mono text-sm">{house.house_code}</TableCell>
                    <TableCell className="hidden sm:table-cell">{getGenderBadge(house.gender)}</TableCell>
                    <TableCell className="hidden md:table-cell text-right">{house.capacity}</TableCell>
                    <TableCell className="hidden md:table-cell">
                      <Badge variant={house.is_active ? "default" : "secondary"}>
                        {house.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="icon" asChild>
                          <Link href={`/boarding/houses/${house.id}`}>
                            <Eye className="h-4 w-4" />
                          </Link>
                        </Button>
                        <Button variant="ghost" size="icon" onClick={() => handleOpenDialog(house)}>
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="icon" onClick={() => setDeleteId(house.id)}>
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
              <Building2 className="h-12 w-12" />
              <p>No houses found</p>
              <p className="text-sm text-center max-w-md">
                Create boarding houses to manage dormitories and student assignments.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingHouse ? "Edit House" : "Create House"}</DialogTitle>
            <DialogDescription>
              {editingHouse ? "Update house details." : "Add a new boarding house."}
            </DialogDescription>
          </DialogHeader>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <FormField control={form.control} name="name" render={({ field }) => (
                <FormItem>
                  <FormLabel>Name *</FormLabel>
                  <FormControl><Input placeholder="e.g., Eagle House" {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="house_code" render={({ field }) => (
                <FormItem>
                  <FormLabel>House Code *</FormLabel>
                  <FormControl><Input placeholder="e.g., EGL" {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField control={form.control} name="gender" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Gender *</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {GENDER_OPTIONS.map((opt) => (
                          <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
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
              <FormField control={form.control} name="description" render={({ field }) => (
                <FormItem>
                  <FormLabel>Description</FormLabel>
                  <FormControl><Textarea rows={3} {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setIsDialogOpen(false)} disabled={isSubmitting}>
                  Cancel
                </Button>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  {editingHouse ? "Save Changes" : "Create House"}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!deleteId} onOpenChange={() => setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete House?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete this house and all its dormitories and beds.
              Students assigned to this house will need to be reassigned.
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
