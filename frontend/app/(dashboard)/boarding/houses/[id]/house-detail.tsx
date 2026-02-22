"use client";

import { useCallback, useState, useTransition } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
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
import {
  ArrowLeft,
  BedDouble,
  Building2,
  ChevronDown,
  ChevronRight,
  Loader2,
  Pencil,
  Plus,
  Trash2,
  Users,
} from "lucide-react";
import {
  updateHouse,
  getDormitories,
  createDormitory,
  updateDormitory,
  deleteDormitory,
  getBeds,
  createBedsBulk,
  updateBed,
} from "@/actions/boarding.action";
import { useToast } from "@/hooks/use-toast";
import type {
  HouseDetail,
  HouseGender,
  Dormitory,
  DormitoryType,
  Bed,
  BedStatus,
  BedType,
} from "@/types";

// ===========================
// Schemas
// ===========================

const editHouseSchema = z.object({
  name: z.string().min(1, "Name is required").max(100),
  house_code: z.string().min(1, "House code is required").max(20),
  gender: z.enum(["male", "female", "mixed"]),
  capacity: z.coerce.number().int().positive("Capacity must be positive"),
  description: z.string().optional(),
});

type EditHouseFormData = z.infer<typeof editHouseSchema>;

const dormitorySchema = z.object({
  name: z.string().min(1, "Name is required").max(100),
  floor: z.string().optional(),
  capacity: z.coerce.number().int().positive("Capacity must be positive"),
  dormitory_type: z.enum(["room", "hall", "cubicle"]),
});

type DormFormData = z.infer<typeof dormitorySchema>;

const bulkBedSchema = z.object({
  dormitory_id: z.string().min(1, "Dormitory is required"),
  bed_type: z.enum(["single", "bunk_upper", "bunk_lower"]),
  count: z.coerce.number().int().min(1, "At least 1 bed required").max(100, "Maximum 100 beds at once"),
  prefix: z.string().optional(),
});

type BulkBedFormData = z.infer<typeof bulkBedSchema>;

const editBedSchema = z.object({
  bed_number: z.string().min(1, "Bed number is required"),
  bed_type: z.enum(["single", "bunk_upper", "bunk_lower"]),
  status: z.enum(["available", "occupied", "maintenance"]),
});

type EditBedFormData = z.infer<typeof editBedSchema>;

// ===========================
// Constants
// ===========================

const GENDER_OPTIONS: { value: HouseGender; label: string }[] = [
  { value: "male", label: "Male" },
  { value: "female", label: "Female" },
  { value: "mixed", label: "Mixed" },
];

const DORM_TYPES: { value: DormitoryType; label: string }[] = [
  { value: "room", label: "Room" },
  { value: "hall", label: "Hall" },
  { value: "cubicle", label: "Cubicle" },
];

const BED_TYPES: { value: BedType; label: string }[] = [
  { value: "single", label: "Single" },
  { value: "bunk_upper", label: "Bunk (Upper)" },
  { value: "bunk_lower", label: "Bunk (Lower)" },
];

const BED_STATUS_OPTIONS: { value: BedStatus; label: string }[] = [
  { value: "available", label: "Available" },
  { value: "occupied", label: "Occupied" },
  { value: "maintenance", label: "Maintenance" },
];

// ===========================
// Helpers
// ===========================

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

function getBedStatusBadge(status: BedStatus) {
  switch (status) {
    case "available":
      return <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">Available</Badge>;
    case "occupied":
      return <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">Occupied</Badge>;
    case "maintenance":
      return <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200">Maintenance</Badge>;
    default:
      return <Badge variant="secondary">{status}</Badge>;
  }
}

function getBedTypeLabel(type: BedType) {
  switch (type) {
    case "single":
      return "Single";
    case "bunk_upper":
      return "Bunk (Upper)";
    case "bunk_lower":
      return "Bunk (Lower)";
    default:
      return type;
  }
}

// ===========================
// Props
// ===========================

interface Props {
  house: HouseDetail;
  initialDormitories: Dormitory[];
}

// ===========================
// Main Component
// ===========================

export function HouseDetailView({ house, initialDormitories }: Props) {
  const router = useRouter();
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();
  const [isSubmitting, setIsSubmitting] = useState(false);

  // House state
  const [houseData, setHouseData] = useState<HouseDetail>(house);
  const [isEditHouseOpen, setIsEditHouseOpen] = useState(false);

  // Dormitory state
  const [dormitories, setDormitories] = useState<Dormitory[]>(initialDormitories);
  const [isDormDialogOpen, setIsDormDialogOpen] = useState(false);
  const [editingDorm, setEditingDorm] = useState<Dormitory | null>(null);
  const [deleteDormId, setDeleteDormId] = useState<string | null>(null);

  // Beds state
  const [expandedDormId, setExpandedDormId] = useState<string | null>(null);
  const [bedsByDorm, setBedsByDorm] = useState<Record<string, Bed[]>>({});
  const [loadingBeds, setLoadingBeds] = useState<string | null>(null);
  const [isBulkBedOpen, setIsBulkBedOpen] = useState(false);
  const [isEditBedOpen, setIsEditBedOpen] = useState(false);
  const [editingBed, setEditingBed] = useState<Bed | null>(null);

  // ===========================
  // Forms
  // ===========================

  const editHouseForm = useForm<EditHouseFormData>({
    resolver: zodResolver(editHouseSchema),
    defaultValues: {
      name: house.name,
      house_code: house.house_code,
      gender: house.gender,
      capacity: house.capacity,
      description: house.description || "",
    },
  });

  const dormForm = useForm<DormFormData>({
    resolver: zodResolver(dormitorySchema),
    defaultValues: { name: "", floor: "", capacity: 20, dormitory_type: "room" },
  });

  const bulkBedForm = useForm<BulkBedFormData>({
    resolver: zodResolver(bulkBedSchema),
    defaultValues: { dormitory_id: "", bed_type: "single", count: 10, prefix: "" },
  });

  const editBedForm = useForm<EditBedFormData>({
    resolver: zodResolver(editBedSchema),
    defaultValues: { bed_number: "", bed_type: "single", status: "available" },
  });

  // ===========================
  // Data Loading
  // ===========================

  const loadDormitories = useCallback(() => {
    startTransition(async () => {
      const result = await getDormitories({ houseId: house.id });
      if (result.success && result.data) {
        const items = Array.isArray(result.data) ? result.data : (result.data.items ?? []);
        setDormitories(items);
      }
    });
  }, [house.id]);

  const loadBeds = useCallback(async (dormitoryId: string) => {
    setLoadingBeds(dormitoryId);
    try {
      const result = await getBeds({ dormitoryId, pageSize: 200 });
      if (result.success && result.data) {
        const items = Array.isArray(result.data) ? result.data : (result.data.items ?? []);
        setBedsByDorm((prev) => ({ ...prev, [dormitoryId]: items }));
      }
    } finally {
      setLoadingBeds(null);
    }
  }, []);

  const handleToggleDorm = useCallback((dormId: string) => {
    if (expandedDormId === dormId) {
      setExpandedDormId(null);
    } else {
      setExpandedDormId(dormId);
      if (!bedsByDorm[dormId]) {
        loadBeds(dormId);
      }
    }
  }, [expandedDormId, bedsByDorm, loadBeds]);

  // ===========================
  // House Edit
  // ===========================

  const handleOpenEditHouse = () => {
    editHouseForm.reset({
      name: houseData.name,
      house_code: houseData.house_code,
      gender: houseData.gender,
      capacity: houseData.capacity,
      description: houseData.description || "",
    });
    setIsEditHouseOpen(true);
  };

  const onEditHouseSubmit = async (data: EditHouseFormData) => {
    setIsSubmitting(true);
    try {
      const payload = {
        name: data.name.trim(),
        house_code: data.house_code.trim(),
        gender: data.gender,
        capacity: data.capacity,
        description: data.description?.trim() || undefined,
      };
      const result = await updateHouse(house.id, payload);
      if (result.success) {
        toast({ title: "House updated", description: `${data.name} has been updated.` });
        setIsEditHouseOpen(false);
        // Update local state to reflect changes without full refresh
        setHouseData((prev) => ({
          ...prev,
          ...payload,
          description: payload.description || undefined,
        }));
        router.refresh();
      } else {
        toast({ title: "Error", description: result.error, variant: "destructive" });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  // ===========================
  // Dormitory CRUD
  // ===========================

  const handleOpenDormDialog = (dorm?: Dormitory) => {
    if (dorm) {
      setEditingDorm(dorm);
      dormForm.reset({
        name: dorm.name,
        floor: dorm.floor || "",
        capacity: dorm.capacity,
        dormitory_type: dorm.dormitory_type as DormitoryType,
      });
    } else {
      setEditingDorm(null);
      dormForm.reset({ name: "", floor: "", capacity: 20, dormitory_type: "room" });
    }
    setIsDormDialogOpen(true);
  };

  const onDormSubmit = async (formData: DormFormData) => {
    setIsSubmitting(true);
    try {
      if (editingDorm) {
        const result = await updateDormitory(editingDorm.id, {
          name: formData.name.trim(),
          floor: formData.floor?.trim() || undefined,
          capacity: formData.capacity,
          dormitory_type: formData.dormitory_type,
        });
        if (result.success) {
          toast({ title: "Dormitory updated" });
          setIsDormDialogOpen(false);
          loadDormitories();
        } else {
          toast({ title: "Error", description: result.error, variant: "destructive" });
        }
      } else {
        const result = await createDormitory({
          house_id: house.id,
          name: formData.name.trim(),
          floor: formData.floor?.trim() || undefined,
          capacity: formData.capacity,
          dormitory_type: formData.dormitory_type,
        });
        if (result.success) {
          toast({ title: "Dormitory created" });
          setIsDormDialogOpen(false);
          loadDormitories();
        } else {
          toast({ title: "Error", description: result.error, variant: "destructive" });
        }
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteDorm = async () => {
    if (!deleteDormId) return;
    setIsSubmitting(true);
    try {
      const result = await deleteDormitory(deleteDormId);
      if (result.success) {
        toast({ title: "Dormitory deleted" });
        // Clean up expanded beds for deleted dorm
        if (expandedDormId === deleteDormId) {
          setExpandedDormId(null);
        }
        setBedsByDorm((prev) => {
          const updated = { ...prev };
          delete updated[deleteDormId];
          return updated;
        });
        loadDormitories();
      } else {
        toast({ title: "Error", description: result.error, variant: "destructive" });
      }
    } finally {
      setIsSubmitting(false);
      setDeleteDormId(null);
    }
  };

  // ===========================
  // Beds CRUD
  // ===========================

  const handleOpenBulkBed = (dormitoryId?: string) => {
    bulkBedForm.reset({
      dormitory_id: dormitoryId || (dormitories.length === 1 ? dormitories[0].id : ""),
      bed_type: "single",
      count: 10,
      prefix: "",
    });
    setIsBulkBedOpen(true);
  };

  const onBulkBedSubmit = async (formData: BulkBedFormData) => {
    setIsSubmitting(true);
    try {
      const result = await createBedsBulk({
        dormitory_id: formData.dormitory_id,
        bed_type: formData.bed_type,
        count: formData.count,
        prefix: formData.prefix?.trim() || undefined,
      });
      if (result.success) {
        const createdCount = Array.isArray(result.data) ? result.data.length : formData.count;
        toast({
          title: "Beds created",
          description: `${createdCount} bed${createdCount !== 1 ? "s" : ""} added successfully.`,
        });
        setIsBulkBedOpen(false);
        // Refresh beds for the target dormitory
        loadBeds(formData.dormitory_id);
        loadDormitories();
      } else {
        toast({ title: "Error", description: result.error, variant: "destructive" });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleOpenEditBed = (bed: Bed) => {
    setEditingBed(bed);
    editBedForm.reset({
      bed_number: bed.bed_number,
      bed_type: bed.bed_type,
      status: bed.status,
    });
    setIsEditBedOpen(true);
  };

  const onEditBedSubmit = async (formData: EditBedFormData) => {
    if (!editingBed) return;
    setIsSubmitting(true);
    try {
      const result = await updateBed(editingBed.id, {
        bed_number: formData.bed_number.trim(),
        bed_type: formData.bed_type,
        status: formData.status,
      });
      if (result.success) {
        toast({ title: "Bed updated" });
        setIsEditBedOpen(false);
        // Refresh beds for this dormitory
        loadBeds(editingBed.dormitory_id);
      } else {
        toast({ title: "Error", description: result.error, variant: "destructive" });
      }
    } finally {
      setIsSubmitting(false);
      setEditingBed(null);
    }
  };

  // ===========================
  // Bed stats per dormitory
  // ===========================

  function getDormBedStats(dormId: string) {
    const beds = bedsByDorm[dormId];
    if (!beds) return null;
    const total = beds.length;
    const available = beds.filter((b) => b.status === "available").length;
    const occupied = beds.filter((b) => b.status === "occupied").length;
    const maintenance = beds.filter((b) => b.status === "maintenance").length;
    return { total, available, occupied, maintenance };
  }

  // ===========================
  // Derived values
  // ===========================

  const occupancyPercent = houseData.capacity > 0
    ? Math.round((houseData.current_occupancy / houseData.capacity) * 100)
    : 0;

  // ===========================
  // Render
  // ===========================

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link href="/boarding/houses">
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">{houseData.name}</h1>
            <p className="text-muted-foreground">House Code: {houseData.house_code}</p>
          </div>
        </div>
        <Button variant="outline" onClick={handleOpenEditHouse}>
          <Pencil className="mr-2 h-4 w-4" />
          Edit House
        </Button>
      </div>

      {/* House Info Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Gender</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {getGenderBadge(houseData.gender)}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Capacity</CardTitle>
            <Building2 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{houseData.capacity}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Occupancy</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{houseData.current_occupancy}</div>
            <p className="text-xs text-muted-foreground">{occupancyPercent}% filled</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Dormitories</CardTitle>
            <BedDouble className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{houseData.dormitory_count}</div>
          </CardContent>
        </Card>
      </div>

      {/* Description */}
      {houseData.description && (
        <Card>
          <CardHeader>
            <CardTitle>Description</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">{houseData.description}</p>
          </CardContent>
        </Card>
      )}

      {/* House Parent */}
      {houseData.house_parent_name && (
        <Card>
          <CardHeader>
            <CardTitle>House Parent</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm">{houseData.house_parent_name}</p>
          </CardContent>
        </Card>
      )}

      {/* Dormitories & Beds Section */}
      <Card>
        <CardHeader>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle>Dormitories & Beds</CardTitle>
              <CardDescription>
                {dormitories.length} dormitor{dormitories.length !== 1 ? "ies" : "y"} in this house.
                Click a dormitory to view and manage its beds.
              </CardDescription>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => handleOpenBulkBed()}>
                <Plus className="mr-2 h-4 w-4" />
                Add Beds
              </Button>
              <Button size="sm" onClick={() => handleOpenDormDialog()}>
                <Plus className="mr-2 h-4 w-4" />
                Add Dormitory
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isPending ? (
            <div className="flex h-[200px] items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : dormitories.length > 0 ? (
            <div className="space-y-3">
              {dormitories.map((dorm) => {
                const isExpanded = expandedDormId === dorm.id;
                const beds = bedsByDorm[dorm.id];
                const stats = getDormBedStats(dorm.id);
                const isLoadingThisDorm = loadingBeds === dorm.id;

                return (
                  <div key={dorm.id} className="rounded-lg border">
                    {/* Dormitory Row */}
                    <div
                      className="flex cursor-pointer items-center gap-3 p-4 hover:bg-muted/50 transition-colors"
                      onClick={() => handleToggleDorm(dorm.id)}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          handleToggleDorm(dorm.id);
                        }
                      }}
                      aria-expanded={isExpanded}
                      aria-label={`${dorm.name} dormitory, click to ${isExpanded ? "collapse" : "expand"} beds`}
                    >
                      <div className="flex-shrink-0">
                        {isExpanded ? (
                          <ChevronDown className="h-4 w-4 text-muted-foreground" />
                        ) : (
                          <ChevronRight className="h-4 w-4 text-muted-foreground" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-medium truncate">{dorm.name}</span>
                          <Badge variant="outline" className="capitalize text-xs">
                            {dorm.dormitory_type}
                          </Badge>
                          <Badge variant={dorm.is_active ? "default" : "secondary"} className="text-xs">
                            {dorm.is_active ? "Active" : "Inactive"}
                          </Badge>
                        </div>
                        <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                          {dorm.floor && <span>Floor: {dorm.floor}</span>}
                          <span>Capacity: {dorm.capacity}</span>
                          {stats && (
                            <>
                              <span className="text-green-600 dark:text-green-400">
                                {stats.available} available
                              </span>
                              <span className="text-blue-600 dark:text-blue-400">
                                {stats.occupied} occupied
                              </span>
                              {stats.maintenance > 0 && (
                                <span className="text-amber-600 dark:text-amber-400">
                                  {stats.maintenance} maintenance
                                </span>
                              )}
                              <span>{stats.total} total beds</span>
                            </>
                          )}
                        </div>
                      </div>
                      <div className="flex-shrink-0 flex gap-1" onClick={(e) => e.stopPropagation()}>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleOpenBulkBed(dorm.id);
                          }}
                          aria-label={`Add beds to ${dorm.name}`}
                        >
                          <Plus className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleOpenDormDialog(dorm);
                          }}
                          aria-label={`Edit ${dorm.name}`}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={(e) => {
                            e.stopPropagation();
                            setDeleteDormId(dorm.id);
                          }}
                          aria-label={`Delete ${dorm.name}`}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </div>

                    {/* Expanded Beds Section */}
                    {isExpanded && (
                      <div className="border-t bg-muted/20 p-4">
                        {isLoadingThisDorm ? (
                          <div className="flex h-[100px] items-center justify-center">
                            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                          </div>
                        ) : beds && beds.length > 0 ? (
                          <div className="overflow-x-auto">
                            <Table>
                              <TableHeader>
                                <TableRow>
                                  <TableHead>Bed Number</TableHead>
                                  <TableHead>Type</TableHead>
                                  <TableHead>Status</TableHead>
                                  <TableHead className="text-right">Actions</TableHead>
                                </TableRow>
                              </TableHeader>
                              <TableBody>
                                {beds.map((bed) => (
                                  <TableRow key={bed.id}>
                                    <TableCell className="font-mono text-sm font-medium">
                                      {bed.bed_number}
                                    </TableCell>
                                    <TableCell className="text-sm">
                                      {getBedTypeLabel(bed.bed_type)}
                                    </TableCell>
                                    <TableCell>
                                      {getBedStatusBadge(bed.status)}
                                    </TableCell>
                                    <TableCell className="text-right">
                                      <Button
                                        variant="ghost"
                                        size="icon"
                                        className="h-8 w-8"
                                        onClick={() => handleOpenEditBed(bed)}
                                        aria-label={`Edit bed ${bed.bed_number}`}
                                      >
                                        <Pencil className="h-4 w-4" />
                                      </Button>
                                    </TableCell>
                                  </TableRow>
                                ))}
                              </TableBody>
                            </Table>
                          </div>
                        ) : (
                          <div className="flex flex-col items-center justify-center gap-2 py-6 text-muted-foreground">
                            <BedDouble className="h-8 w-8" />
                            <p className="text-sm">No beds in this dormitory yet</p>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleOpenBulkBed(dorm.id)}
                            >
                              <Plus className="mr-2 h-4 w-4" />
                              Add Beds
                            </Button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="flex h-[200px] flex-col items-center justify-center gap-2 text-muted-foreground">
              <BedDouble className="h-12 w-12" />
              <p className="text-sm font-medium">No dormitories in this house yet</p>
              <p className="text-xs text-center max-w-sm">
                Add dormitories to organize rooms and beds within this house.
              </p>
              <Button variant="outline" size="sm" onClick={() => handleOpenDormDialog()}>
                <Plus className="mr-2 h-4 w-4" />
                Add Dormitory
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ===========================
          DIALOGS
          =========================== */}

      {/* Edit House Dialog */}
      <Dialog open={isEditHouseOpen} onOpenChange={setIsEditHouseOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit House</DialogTitle>
            <DialogDescription>Update house details.</DialogDescription>
          </DialogHeader>
          <Form {...editHouseForm}>
            <form onSubmit={editHouseForm.handleSubmit(onEditHouseSubmit)} className="space-y-4">
              <FormField control={editHouseForm.control} name="name" render={({ field }) => (
                <FormItem>
                  <FormLabel>Name *</FormLabel>
                  <FormControl><Input placeholder="e.g., Eagle House" {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={editHouseForm.control} name="house_code" render={({ field }) => (
                <FormItem>
                  <FormLabel>House Code *</FormLabel>
                  <FormControl><Input placeholder="e.g., EGL" {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField control={editHouseForm.control} name="gender" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Gender *</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
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
                <FormField control={editHouseForm.control} name="capacity" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Capacity *</FormLabel>
                    <FormControl><Input type="number" min={1} {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )} />
              </div>
              <FormField control={editHouseForm.control} name="description" render={({ field }) => (
                <FormItem>
                  <FormLabel>Description</FormLabel>
                  <FormControl><Textarea rows={3} {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setIsEditHouseOpen(false)} disabled={isSubmitting}>
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

      {/* Create/Edit Dormitory Dialog */}
      <Dialog open={isDormDialogOpen} onOpenChange={setIsDormDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingDorm ? "Edit Dormitory" : "Add Dormitory"}</DialogTitle>
            <DialogDescription>
              {editingDorm
                ? "Update dormitory details."
                : `Add a new dormitory to ${houseData.name}.`}
            </DialogDescription>
          </DialogHeader>
          <Form {...dormForm}>
            <form onSubmit={dormForm.handleSubmit(onDormSubmit)} className="space-y-4">
              <FormField control={dormForm.control} name="name" render={({ field }) => (
                <FormItem>
                  <FormLabel>Name *</FormLabel>
                  <FormControl><Input placeholder="e.g., Room A1" {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField control={dormForm.control} name="floor" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Floor</FormLabel>
                    <FormControl><Input placeholder="e.g., Ground" {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )} />
                <FormField control={dormForm.control} name="capacity" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Capacity *</FormLabel>
                    <FormControl><Input type="number" min={1} {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )} />
              </div>
              <FormField control={dormForm.control} name="dormitory_type" render={({ field }) => (
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
                <Button type="button" variant="outline" onClick={() => setIsDormDialogOpen(false)} disabled={isSubmitting}>
                  Cancel
                </Button>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  {editingDorm ? "Save Changes" : "Add Dormitory"}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* Bulk Add Beds Dialog */}
      <Dialog open={isBulkBedOpen} onOpenChange={setIsBulkBedOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Beds</DialogTitle>
            <DialogDescription>
              Bulk create beds in a dormitory. Beds will be numbered automatically.
            </DialogDescription>
          </DialogHeader>
          <Form {...bulkBedForm}>
            <form onSubmit={bulkBedForm.handleSubmit(onBulkBedSubmit)} className="space-y-4">
              <FormField control={bulkBedForm.control} name="dormitory_id" render={({ field }) => (
                <FormItem>
                  <FormLabel>Dormitory *</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl>
                      <SelectTrigger className="w-full"><SelectValue placeholder="Select dormitory" /></SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {dormitories.filter((d) => d.is_active).map((d) => (
                        <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )} />
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField control={bulkBedForm.control} name="count" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Number of Beds *</FormLabel>
                    <FormControl><Input type="number" min={1} max={100} {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )} />
                <FormField control={bulkBedForm.control} name="bed_type" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Bed Type *</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {BED_TYPES.map((t) => (
                          <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )} />
              </div>
              <FormField control={bulkBedForm.control} name="prefix" render={({ field }) => (
                <FormItem>
                  <FormLabel>Bed Number Prefix</FormLabel>
                  <FormControl>
                    <Input placeholder="e.g., A- (produces A-1, A-2, ...)" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setIsBulkBedOpen(false)} disabled={isSubmitting}>
                  Cancel
                </Button>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Create Beds
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* Edit Bed Dialog */}
      <Dialog open={isEditBedOpen} onOpenChange={(open) => {
        setIsEditBedOpen(open);
        if (!open) setEditingBed(null);
      }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Bed</DialogTitle>
            <DialogDescription>
              Update bed details and status.
            </DialogDescription>
          </DialogHeader>
          <Form {...editBedForm}>
            <form onSubmit={editBedForm.handleSubmit(onEditBedSubmit)} className="space-y-4">
              <FormField control={editBedForm.control} name="bed_number" render={({ field }) => (
                <FormItem>
                  <FormLabel>Bed Number *</FormLabel>
                  <FormControl><Input {...field} /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField control={editBedForm.control} name="bed_type" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Bed Type *</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {BED_TYPES.map((t) => (
                          <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )} />
                <FormField control={editBedForm.control} name="status" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Status *</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {BED_STATUS_OPTIONS.map((s) => (
                          <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )} />
              </div>
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setIsEditBedOpen(false)} disabled={isSubmitting}>
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

      {/* Delete Dormitory Confirmation */}
      <AlertDialog open={!!deleteDormId} onOpenChange={() => setDeleteDormId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Dormitory?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete this dormitory and all its beds.
              Any students assigned to beds in this dormitory will need to be reassigned.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isSubmitting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteDorm}
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
