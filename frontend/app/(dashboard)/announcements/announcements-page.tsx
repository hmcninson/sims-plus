"use client";

import { useEffect, useState, useTransition, useCallback } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { format } from "date-fns";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
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
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
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
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
  FormDescription,
} from "@/components/ui/form";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Calendar } from "@/components/ui/calendar";
import { CollapsibleFilters } from "@/components/filters/collapsible-filters";
import {
  Plus,
  Loader2,
  Megaphone,
  MoreHorizontal,
  Pencil,
  Trash2,
  Send,
  CalendarIcon,
  Pin,
  Search,
} from "lucide-react";

import {
  getAnnouncements,
  createAnnouncement,
  updateAnnouncement,
  publishAnnouncement,
  deleteAnnouncement,
} from "@/actions/announcement.action";
import { getClasses } from "@/actions/academic.action";
import { getHouses } from "@/actions/boarding.action";
import type {
  Announcement,
  AnnouncementTarget,
  AnnouncementPriority,
  AnnouncementStatus,
} from "@/types/parent.type";
import type { Class, House } from "@/types";
import { useToast } from "@/hooks/use-toast";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";

// -------------------------------------------------------------------
// Constants
// -------------------------------------------------------------------

const TARGET_OPTIONS: { value: AnnouncementTarget; label: string }[] = [
  { value: "all_parents", label: "All Parents" },
  { value: "specific_class", label: "Specific Class" },
  { value: "specific_house", label: "Specific House" },
  { value: "boarding_parents", label: "Boarding Parents" },
  { value: "transport_parents", label: "Transport Parents" },
];

const PRIORITY_OPTIONS: { value: AnnouncementPriority; label: string }[] = [
  { value: "normal", label: "Normal" },
  { value: "important", label: "Important" },
  { value: "urgent", label: "Urgent" },
];

// -------------------------------------------------------------------
// Badge helpers
// -------------------------------------------------------------------

function getPriorityBadge(priority: AnnouncementPriority | string) {
  switch (priority) {
    case "normal":
      return <Badge variant="secondary">Normal</Badge>;
    case "important":
      return (
        <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200">
          Important
        </Badge>
      );
    case "urgent":
      return <Badge variant="destructive">Urgent</Badge>;
    default:
      return <Badge variant="secondary">{priority}</Badge>;
  }
}

function getStatusBadge(status: AnnouncementStatus | string) {
  switch (status) {
    case "draft":
      return <Badge variant="outline">Draft</Badge>;
    case "published":
      return (
        <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
          Published
        </Badge>
      );
    default:
      return <Badge variant="secondary">{status}</Badge>;
  }
}

function getTargetLabel(target: AnnouncementTarget | string, announcement?: Announcement) {
  switch (target) {
    case "all_parents":
      return "All Parents";
    case "specific_class":
      return announcement?.target_class_name
        ? `Class: ${announcement.target_class_name}`
        : "Specific Class";
    case "specific_house":
      return announcement?.target_house_name
        ? `House: ${announcement.target_house_name}`
        : "Specific House";
    case "boarding_parents":
      return "Boarding Parents";
    case "transport_parents":
      return "Transport Parents";
    default:
      return target;
  }
}

// -------------------------------------------------------------------
// Zod schemas
// -------------------------------------------------------------------

const announcementFormSchema = z
  .object({
    title: z.string().min(1, "Title is required").max(200, "Title must be under 200 characters"),
    content: z
      .string()
      .min(1, "Content is required")
      .max(5000, "Content must be under 5000 characters"),
    target_audience: z.enum(
      ["all_parents", "specific_class", "specific_house", "boarding_parents", "transport_parents"],
      { message: "Please select a target audience" }
    ),
    target_class_id: z.string().optional(),
    target_house_id: z.string().optional(),
    priority: z.enum(["normal", "important", "urgent"], {
      message: "Please select a priority",
    }),
    expires_at: z.date().optional(),
    is_pinned: z.boolean().optional(),
    attachment_url: z.string().url("Must be a valid URL").or(z.literal("")).optional(),
  })
  .refine(
    (data) => {
      if (data.target_audience === "specific_class" && !data.target_class_id) {
        return false;
      }
      return true;
    },
    { message: "Please select a class", path: ["target_class_id"] }
  )
  .refine(
    (data) => {
      if (data.target_audience === "specific_house" && !data.target_house_id) {
        return false;
      }
      return true;
    },
    { message: "Please select a house", path: ["target_house_id"] }
  );

type AnnouncementFormData = z.infer<typeof announcementFormSchema>;

// -------------------------------------------------------------------
// Main component
// -------------------------------------------------------------------

export function AnnouncementsPage() {
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();

  // List state
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  // Filter state
  const [searchQuery, setSearchQuery] = useState("");
  const [priorityFilter, setPriorityFilter] = useState<string>("");
  const [targetFilter, setTargetFilter] = useState<string>("");

  // Dialog state
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingAnnouncement, setEditingAnnouncement] = useState<Announcement | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Announcement | null>(null);
  const [publishTarget, setPublishTarget] = useState<Announcement | null>(null);

  // Lookup data
  const [classes, setClasses] = useState<Class[]>([]);
  const [houses, setHouses] = useState<House[]>([]);
  const [isLoadingLookups, setIsLoadingLookups] = useState(false);

  // Submitting state
  const [isSubmitting, setIsSubmitting] = useState(false);

  // -------------------------------------------------------------------
  // Form setup
  // -------------------------------------------------------------------

  const form = useForm<AnnouncementFormData>({
    resolver: zodResolver(announcementFormSchema),
    defaultValues: {
      title: "",
      content: "",
      target_audience: "all_parents",
      target_class_id: "",
      target_house_id: "",
      priority: "normal",
      is_pinned: false,
      attachment_url: "",
    },
  });

  const watchedTarget = form.watch("target_audience");

  // -------------------------------------------------------------------
  // Data loading
  // -------------------------------------------------------------------

  const loadAnnouncements = useCallback(() => {
    startTransition(async () => {
      const result = await getAnnouncements({
        search: searchQuery || undefined,
        priority: priorityFilter || undefined,
        target: targetFilter || undefined,
        page,
        pageSize: 20,
      });
      if (result.success && result.data) {
        const data = result.data;
        const items = Array.isArray(data) ? data : (data.items ?? []);
        const count = Array.isArray(data) ? data.length : (data.total ?? 0);
        const pages = Array.isArray(data) ? 1 : (data.total_pages ?? 1);
        setAnnouncements(items);
        setTotal(count);
        setTotalPages(pages);
      }
    });
  }, [searchQuery, priorityFilter, targetFilter, page]);

  useEffect(() => {
    loadAnnouncements();
  }, [loadAnnouncements]);

  const loadLookups = useCallback(async () => {
    if (classes.length > 0 && houses.length > 0) return;
    setIsLoadingLookups(true);
    try {
      const [classResult, houseResult] = await Promise.all([
        getClasses(),
        getHouses({ pageSize: 100 }),
      ]);
      if (classResult.success && classResult.data) {
        setClasses(Array.isArray(classResult.data) ? classResult.data : []);
      }
      if (houseResult.success && houseResult.data) {
        const houseData = houseResult.data;
        setHouses(
          Array.isArray(houseData)
            ? houseData
            : (houseData.items ?? [])
        );
      }
    } finally {
      setIsLoadingLookups(false);
    }
  }, [classes.length, houses.length]);

  // -------------------------------------------------------------------
  // Handlers
  // -------------------------------------------------------------------

  const handleOpenCreate = () => {
    setEditingAnnouncement(null);
    form.reset({
      title: "",
      content: "",
      target_audience: "all_parents",
      target_class_id: "",
      target_house_id: "",
      priority: "normal",
      is_pinned: false,
      attachment_url: "",
    });
    loadLookups();
    setIsFormOpen(true);
  };

  const handleOpenEdit = (announcement: Announcement) => {
    setEditingAnnouncement(announcement);
    form.reset({
      title: announcement.title,
      content: announcement.content,
      target_audience: announcement.target_audience,
      target_class_id: announcement.target_class_id || "",
      target_house_id: announcement.target_house_id || "",
      priority: announcement.priority,
      is_pinned: announcement.is_pinned,
      attachment_url: announcement.attachment_url || "",
      expires_at: announcement.expires_at ? new Date(announcement.expires_at) : undefined,
    });
    loadLookups();
    setIsFormOpen(true);
  };

  const handleSubmit = async (data: AnnouncementFormData) => {
    setIsSubmitting(true);
    try {
      const payload = {
        title: data.title,
        content: data.content,
        target_audience: data.target_audience,
        target_class_id:
          data.target_audience === "specific_class" ? data.target_class_id : undefined,
        target_house_id:
          data.target_audience === "specific_house" ? data.target_house_id : undefined,
        priority: data.priority,
        is_pinned: data.is_pinned || false,
        attachment_url: data.attachment_url || undefined,
        expires_at: data.expires_at ? format(data.expires_at, "yyyy-MM-dd") : undefined,
      };

      const result = editingAnnouncement
        ? await updateAnnouncement(editingAnnouncement.id, payload)
        : await createAnnouncement(payload);

      if (result.success) {
        toast({
          title: editingAnnouncement
            ? "Announcement updated"
            : "Announcement created",
        });
        setIsFormOpen(false);
        setEditingAnnouncement(null);
        form.reset();
        loadAnnouncements();
      } else {
        toast({ title: "Error", description: result.error, variant: "destructive" });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handlePublish = async () => {
    if (!publishTarget) return;
    setIsSubmitting(true);
    try {
      const result = await publishAnnouncement(publishTarget.id);
      if (result.success) {
        toast({ title: "Announcement published" });
        loadAnnouncements();
      } else {
        toast({ title: "Error", description: result.error, variant: "destructive" });
      }
    } finally {
      setIsSubmitting(false);
      setPublishTarget(null);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setIsSubmitting(true);
    try {
      const result = await deleteAnnouncement(deleteTarget.id);
      if (result.success) {
        toast({ title: "Announcement deleted" });
        loadAnnouncements();
      } else {
        toast({ title: "Error", description: result.error, variant: "destructive" });
      }
    } finally {
      setIsSubmitting(false);
      setDeleteTarget(null);
    }
  };

  // -------------------------------------------------------------------
  // Filter helpers
  // -------------------------------------------------------------------

  const activeFilterCount =
    (priorityFilter ? 1 : 0) + (targetFilter ? 1 : 0);

  const handleSearchChange = (value: string) => {
    setSearchQuery(value);
    setPage(1);
  };

  // -------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Announcements</h1>
          <p className="text-muted-foreground">
            Create and manage school announcements for parents
          </p>
        </div>
        <Button onClick={handleOpenCreate}>
          <Plus className="mr-2 h-4 w-4" />
          Create Announcement
        </Button>
      </div>

      {/* Search and filters */}
      <div className="flex flex-col gap-3 md:flex-row md:items-center">
        <div className="relative w-full md:w-[300px]">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search announcements..."
            value={searchQuery}
            onChange={(e) => handleSearchChange(e.target.value)}
            className="pl-9"
          />
        </div>
        <CollapsibleFilters activeFilterCount={activeFilterCount}>
          <Select
            value={priorityFilter}
            onValueChange={(v) => {
              setPriorityFilter(v === "all" ? "" : v);
              setPage(1);
            }}
          >
            <SelectTrigger className="w-full md:w-[160px]">
              <SelectValue placeholder="Priority" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Priorities</SelectItem>
              {PRIORITY_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={targetFilter}
            onValueChange={(v) => {
              setTargetFilter(v === "all" ? "" : v);
              setPage(1);
            }}
          >
            <SelectTrigger className="w-full md:w-[180px]">
              <SelectValue placeholder="Target Audience" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Audiences</SelectItem>
              {TARGET_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CollapsibleFilters>
      </div>

      {/* Data table */}
      <Card>
        <CardHeader>
          <CardTitle>Announcements</CardTitle>
          <CardDescription>
            {total} announcement{total !== 1 ? "s" : ""} found
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isPending ? (
            <div className="flex h-[200px] items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : announcements.length > 0 ? (
            <>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Title</TableHead>
                      <TableHead className="hidden sm:table-cell">Target</TableHead>
                      <TableHead>Priority</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="hidden md:table-cell">Published</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {announcements.map((announcement) => (
                      <TableRow key={announcement.id}>
                        <TableCell className="font-medium">
                          <div className="flex items-center gap-2">
                            {announcement.is_pinned && (
                              <Pin className="h-3 w-3 text-muted-foreground shrink-0" />
                            )}
                            <span className="max-w-[200px] truncate sm:max-w-[300px]">
                              {announcement.title}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell className="hidden sm:table-cell">
                          <Badge variant="outline" className="whitespace-nowrap">
                            {getTargetLabel(announcement.target_audience, announcement)}
                          </Badge>
                        </TableCell>
                        <TableCell>{getPriorityBadge(announcement.priority)}</TableCell>
                        <TableCell>{getStatusBadge(announcement.status)}</TableCell>
                        <TableCell className="hidden whitespace-nowrap md:table-cell">
                          {announcement.published_at
                            ? formatDate(announcement.published_at)
                            : "--"}
                        </TableCell>
                        <TableCell className="text-right">
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8"
                                aria-label="Row actions"
                              >
                                <MoreHorizontal className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem onClick={() => handleOpenEdit(announcement)}>
                                <Pencil className="mr-2 h-4 w-4" />
                                Edit
                              </DropdownMenuItem>
                              {announcement.status === "draft" && (
                                <DropdownMenuItem
                                  onClick={() => setPublishTarget(announcement)}
                                >
                                  <Send className="mr-2 h-4 w-4" />
                                  Publish
                                </DropdownMenuItem>
                              )}
                              <DropdownMenuSeparator />
                              <DropdownMenuItem
                                className="text-destructive focus:text-destructive"
                                onClick={() => setDeleteTarget(announcement)}
                              >
                                <Trash2 className="mr-2 h-4 w-4" />
                                Delete
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between border-t pt-4 mt-4">
                  <p className="text-sm text-muted-foreground">
                    Page {page} of {totalPages}
                  </p>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={page <= 1}
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                    >
                      Previous
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={page >= totalPages}
                      onClick={() => setPage((p) => p + 1)}
                    >
                      Next
                    </Button>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="flex h-[200px] flex-col items-center justify-center gap-2 text-muted-foreground">
              <Megaphone className="h-12 w-12" />
              <p className="font-medium">No announcements found</p>
              <p className="text-sm">
                {searchQuery || priorityFilter || targetFilter
                  ? "Try adjusting your search or filters."
                  : "Create your first announcement to notify parents."}
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ============================================================= */}
      {/* Create / Edit Dialog                                           */}
      {/* ============================================================= */}
      <Dialog
        open={isFormOpen}
        onOpenChange={(open) => {
          if (!open) {
            form.reset();
            setEditingAnnouncement(null);
          }
          setIsFormOpen(open);
        }}
      >
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle>
              {editingAnnouncement ? "Edit Announcement" : "Create Announcement"}
            </DialogTitle>
            <DialogDescription>
              {editingAnnouncement
                ? "Update the announcement details below."
                : "Create a new announcement. It will be saved as a draft until published."}
            </DialogDescription>
          </DialogHeader>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
              {/* Title */}
              <FormField
                control={form.control}
                name="title"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Title *</FormLabel>
                    <FormControl>
                      <Input placeholder="Announcement title" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Content */}
              <FormField
                control={form.control}
                name="content"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Content *</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Write the announcement content here..."
                        rows={5}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Target Audience + Priority row */}
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <FormField
                  control={form.control}
                  name="target_audience"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Target Audience *</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder="Select audience" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {TARGET_OPTIONS.map((opt) => (
                            <SelectItem key={opt.value} value={opt.value}>
                              {opt.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="priority"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Priority *</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder="Select priority" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {PRIORITY_OPTIONS.map((opt) => (
                            <SelectItem key={opt.value} value={opt.value}>
                              {opt.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              {/* Conditional: Target Class */}
              {watchedTarget === "specific_class" && (
                <FormField
                  control={form.control}
                  name="target_class_id"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Class *</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value || ""}>
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder={isLoadingLookups ? "Loading classes..." : "Select class"} />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {classes.map((cls) => (
                            <SelectItem key={cls.id} value={cls.id}>
                              {cls.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              )}

              {/* Conditional: Target House */}
              {watchedTarget === "specific_house" && (
                <FormField
                  control={form.control}
                  name="target_house_id"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>House *</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value || ""}>
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder={isLoadingLookups ? "Loading houses..." : "Select house"} />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {houses.map((house) => (
                            <SelectItem key={house.id} value={house.id}>
                              {house.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              )}

              {/* Expires At */}
              <FormField
                control={form.control}
                name="expires_at"
                render={({ field }) => (
                  <FormItem className="flex flex-col">
                    <FormLabel>Expires At</FormLabel>
                    <Popover>
                      <PopoverTrigger asChild>
                        <FormControl>
                          <Button
                            variant="outline"
                            className={cn(
                              "w-full pl-3 text-left font-normal",
                              !field.value && "text-muted-foreground"
                            )}
                          >
                            {field.value
                              ? format(field.value, "dd/MM/yyyy")
                              : "No expiry date (optional)"}
                            <CalendarIcon className="ml-auto h-4 w-4 opacity-50" />
                          </Button>
                        </FormControl>
                      </PopoverTrigger>
                      <PopoverContent className="w-auto p-0" align="start">
                        <Calendar
                          mode="single"
                          selected={field.value}
                          onSelect={field.onChange}
                          disabled={(date) =>
                            date < new Date(new Date().setHours(0, 0, 0, 0))
                          }
                        />
                      </PopoverContent>
                    </Popover>
                    <FormDescription>
                      Leave empty if the announcement should not expire.
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Attachment URL */}
              <FormField
                control={form.control}
                name="attachment_url"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Attachment URL</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="https://example.com/file.pdf"
                        {...field}
                      />
                    </FormControl>
                    <FormDescription>
                      Link to an attachment (optional).
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Is Pinned */}
              <FormField
                control={form.control}
                name="is_pinned"
                render={({ field }) => (
                  <FormItem className="flex flex-row items-start space-x-3 space-y-0">
                    <FormControl>
                      <Checkbox
                        checked={field.value}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                    <div className="space-y-1 leading-none">
                      <FormLabel>Pin this announcement</FormLabel>
                      <FormDescription>
                        Pinned announcements appear at the top of the list for parents.
                      </FormDescription>
                    </div>
                  </FormItem>
                )}
              />

              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsFormOpen(false)}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  {editingAnnouncement ? "Update" : "Create Draft"}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* ============================================================= */}
      {/* Publish Confirmation Dialog                                     */}
      {/* ============================================================= */}
      <AlertDialog
        open={!!publishTarget}
        onOpenChange={(open) => {
          if (!open) setPublishTarget(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Publish Announcement</AlertDialogTitle>
            <AlertDialogDescription>
              This will publish{" "}
              <span className="font-medium">&quot;{publishTarget?.title}&quot;</span> and make it
              visible to{" "}
              <span className="font-medium">
                {publishTarget
                  ? getTargetLabel(publishTarget.target_audience, publishTarget).toLowerCase()
                  : ""}
              </span>
              . This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isSubmitting}>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handlePublish} disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Publish
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* ============================================================= */}
      {/* Delete Confirmation Dialog                                      */}
      {/* ============================================================= */}
      <AlertDialog
        open={!!deleteTarget}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Announcement</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete{" "}
              <span className="font-medium">&quot;{deleteTarget?.title}&quot;</span>? This action
              cannot be undone.
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
