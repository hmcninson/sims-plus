"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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
import {
  Dialog,
  DialogContent,
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
import { Skeleton } from "@/components/ui/skeleton";
import { CollapsibleFilters } from "@/components/filters/collapsible-filters";
import { EventForm } from "@/components/admissions/event-form";
import {
  Plus,
  CalendarDays,
  Users,
  Eye,
  Pencil,
  XCircle,
  Loader2,
  MapPin,
} from "lucide-react";
import {
  getEvents,
  createEvent,
  updateEvent,
  cancelEvent,
} from "@/actions/events.action";
import { formatDate } from "@/lib/format";
import type {
  SchoolEvent,
  EventType,
  EventStatus,
} from "@/types/admissions.type";

const EVENT_TYPE_LABELS: Record<EventType, string> = {
  open_day: "Open Day",
  tour: "Tour",
  orientation: "Orientation",
};

const EVENT_STATUS_COLORS: Record<EventStatus, string> = {
  upcoming:
    "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  completed:
    "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  cancelled:
    "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
};

export function EventsManagement() {
  const router = useRouter();
  const [events, setEvents] = useState<SchoolEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  // Filters
  const [typeFilter, setTypeFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  // Dialogs
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [editingEvent, setEditingEvent] = useState<SchoolEvent | null>(null);
  const [cancellingEventId, setCancellingEventId] = useState<string | null>(
    null
  );
  const [isSubmitting, setIsSubmitting] = useState(false);

  const loadEvents = useCallback(async () => {
    setLoading(true);
    const result = await getEvents({
      event_type: typeFilter,
      status: statusFilter,
      page,
      page_size: 20,
    });
    if (result.success) {
      setEvents(result.data.items);
      setTotal(result.data.total);
      setTotalPages(result.data.pages);
    } else {
      toast.error(result.error);
    }
    setLoading(false);
  }, [typeFilter, statusFilter, page]);

  useEffect(() => {
    loadEvents();
  }, [loadEvents]);

  // Reset page on filter change
  useEffect(() => {
    setPage(1);
  }, [typeFilter, statusFilter]);

  async function handleCreateEvent(values: Record<string, unknown>) {
    setIsSubmitting(true);
    const result = await createEvent({
      event_type: values.event_type as EventType,
      name: values.name as string,
      description: (values.description as string) || undefined,
      event_date: values.event_date as string,
      start_time: (values.start_time as string) || undefined,
      end_time: (values.end_time as string) || undefined,
      venue: (values.venue as string) || undefined,
      capacity: values.capacity ? Number(values.capacity) : undefined,
      guide_id: (values.guide_id as string) || undefined,
    });
    setIsSubmitting(false);

    if (result.success) {
      toast.success("Event created successfully");
      setShowCreateDialog(false);
      loadEvents();
    } else {
      toast.error(result.error);
    }
  }

  async function handleUpdateEvent(values: Record<string, unknown>) {
    if (!editingEvent) return;
    setIsSubmitting(true);
    const result = await updateEvent(editingEvent.id, {
      name: values.name as string,
      description: (values.description as string) || undefined,
      event_date: values.event_date as string,
      start_time: (values.start_time as string) || undefined,
      end_time: (values.end_time as string) || undefined,
      venue: (values.venue as string) || undefined,
      capacity: values.capacity ? Number(values.capacity) : undefined,
      guide_id: (values.guide_id as string) || undefined,
    });
    setIsSubmitting(false);

    if (result.success) {
      toast.success("Event updated");
      setEditingEvent(null);
      loadEvents();
    } else {
      toast.error(result.error);
    }
  }

  async function handleCancelEvent() {
    if (!cancellingEventId) return;
    setIsSubmitting(true);
    const result = await cancelEvent(cancellingEventId);
    setIsSubmitting(false);
    setCancellingEventId(null);

    if (result.success) {
      toast.success("Event cancelled");
      loadEvents();
    } else {
      toast.error(result.error);
    }
  }

  // Count active filters
  const activeFilterCount =
    (typeFilter !== "all" ? 1 : 0) + (statusFilter !== "all" ? 1 : 0);

  // Stats
  const upcomingCount = events.filter(
    (e) => e.status === "upcoming"
  ).length;
  const totalRegistrations = events.reduce(
    (sum, e) => sum + e.registered_count,
    0
  );

  return (
    <div className="space-y-6 p-4 md:p-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold">School Events</h1>
          <p className="text-sm text-muted-foreground">
            Manage tours, open days, and orientations
          </p>
        </div>
        <Button onClick={() => setShowCreateDialog(true)}>
          <Plus className="mr-2 h-4 w-4" />
          New Event
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Upcoming Events
            </CardTitle>
            <CalendarDays className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{upcomingCount}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Total Registrations
            </CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalRegistrations}</div>
          </CardContent>
        </Card>
        <Card className="hidden md:block">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Events</CardTitle>
            <MapPin className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{total}</div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <CollapsibleFilters activeFilterCount={activeFilterCount}>
        <Select value={typeFilter} onValueChange={setTypeFilter}>
          <SelectTrigger className="w-full md:w-[180px]">
            <SelectValue placeholder="Event Type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Types</SelectItem>
            <SelectItem value="open_day">Open Day</SelectItem>
            <SelectItem value="tour">Tour</SelectItem>
            <SelectItem value="orientation">Orientation</SelectItem>
          </SelectContent>
        </Select>

        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-full md:w-[180px]">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Statuses</SelectItem>
            <SelectItem value="upcoming">Upcoming</SelectItem>
            <SelectItem value="completed">Completed</SelectItem>
            <SelectItem value="cancelled">Cancelled</SelectItem>
          </SelectContent>
        </Select>
      </CollapsibleFilters>

      {/* Table */}
      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead className="hidden sm:table-cell">Type</TableHead>
                <TableHead>Date</TableHead>
                <TableHead className="hidden md:table-cell">Venue</TableHead>
                <TableHead>Registered</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="w-[120px]">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {events.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={7}
                    className="h-24 text-center text-muted-foreground"
                  >
                    No events found. Create your first event to get started.
                  </TableCell>
                </TableRow>
              ) : (
                events.map((event) => (
                  <TableRow key={event.id}>
                    <TableCell className="font-medium">
                      {event.name}
                      <span className="block text-xs text-muted-foreground sm:hidden">
                        {EVENT_TYPE_LABELS[event.event_type]}
                      </span>
                    </TableCell>
                    <TableCell className="hidden sm:table-cell">
                      <Badge variant="secondary">
                        {EVENT_TYPE_LABELS[event.event_type]}
                      </Badge>
                    </TableCell>
                    <TableCell>{formatDate(event.event_date)}</TableCell>
                    <TableCell className="hidden md:table-cell">
                      {event.venue || "--"}
                    </TableCell>
                    <TableCell>
                      {event.registered_count}
                      {event.capacity != null && `/${event.capacity}`}
                    </TableCell>
                    <TableCell>
                      <Badge
                        className={
                          EVENT_STATUS_COLORS[event.status]
                        }
                      >
                        {event.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() =>
                            router.push(`/admissions/events/${event.id}`)
                          }
                          aria-label="View event"
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                        {event.status === "upcoming" && (
                          <>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => setEditingEvent(event)}
                              aria-label="Edit event"
                            >
                              <Pencil className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="text-destructive"
                              onClick={() => setCancellingEventId(event.id)}
                              aria-label="Cancel event"
                            >
                              <XCircle className="h-4 w-4" />
                            </Button>
                          </>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Page {page} of {totalPages} ({total} events)
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
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

      {/* Create dialog */}
      <Dialog
        open={showCreateDialog}
        onOpenChange={setShowCreateDialog}
      >
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Create School Event</DialogTitle>
          </DialogHeader>
          <EventForm onSubmit={handleCreateEvent} isSubmitting={isSubmitting} />
        </DialogContent>
      </Dialog>

      {/* Edit dialog */}
      <Dialog
        open={!!editingEvent}
        onOpenChange={() => setEditingEvent(null)}
      >
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Edit Event</DialogTitle>
          </DialogHeader>
          {editingEvent && (
            <EventForm
              defaultValues={editingEvent}
              onSubmit={handleUpdateEvent}
              isSubmitting={isSubmitting}
            />
          )}
        </DialogContent>
      </Dialog>

      {/* Cancel confirmation */}
      <AlertDialog
        open={!!cancellingEventId}
        onOpenChange={() => setCancellingEventId(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Cancel Event?</AlertDialogTitle>
            <AlertDialogDescription>
              This will cancel the event. Registered attendees will no longer be
              expected. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep Event</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleCancelEvent}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isSubmitting && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Cancel Event
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
