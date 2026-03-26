"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
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
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { EventRegistrationTable } from "@/components/admissions/event-registration-table";
import {
  ArrowLeft,
  CalendarDays,
  Clock,
  MapPin,
  Users,
  UserCheck,
  Percent,
  Plus,
  Loader2,
} from "lucide-react";
import {
  getEvent,
  getRegistrations,
  getEventStats,
  registerForEvent,
} from "@/actions/events.action";
import { formatDate } from "@/lib/format";
import type {
  SchoolEvent,
  EventRegistration,
  EventStatsResponse,
  EventType,
} from "@/types/admissions.type";

const EVENT_TYPE_LABELS: Record<EventType, string> = {
  open_day: "Open Day",
  tour: "Tour",
  orientation: "Orientation",
};

const registrationSchema = z.object({
  registrant_name: z.string().min(1, "Name is required").max(200),
  registrant_phone: z.string().min(1, "Phone is required").max(20),
  registrant_email: z.string().email("Invalid email").optional().or(z.literal("")),
  student_name: z.string().max(200).optional(),
  notes: z.string().optional(),
});

type RegistrationFormValues = z.infer<typeof registrationSchema>;

interface EventDetailProps {
  eventId: string;
}

export function EventDetail({ eventId }: EventDetailProps) {
  const router = useRouter();
  const [event, setEvent] = useState<SchoolEvent | null>(null);
  const [registrations, setRegistrations] = useState<EventRegistration[]>([]);
  const [stats, setStats] = useState<EventStatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [showRegisterDialog, setShowRegisterDialog] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const form = useForm<RegistrationFormValues>({
    resolver: zodResolver(registrationSchema),
    defaultValues: {
      registrant_name: "",
      registrant_phone: "",
      registrant_email: "",
      student_name: "",
      notes: "",
    },
  });

  const loadData = useCallback(async () => {
    setLoading(true);
    const [eventResult, regsResult, statsResult] = await Promise.all([
      getEvent(eventId),
      getRegistrations(eventId),
      getEventStats(eventId),
    ]);

    if (eventResult.success) {
      setEvent(eventResult.data);
    } else {
      toast.error(eventResult.error);
    }

    if (regsResult.success) {
      setRegistrations(regsResult.data);
    }

    if (statsResult.success) {
      setStats(statsResult.data);
    }

    setLoading(false);
  }, [eventId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  async function handleRegister(values: RegistrationFormValues) {
    setIsSubmitting(true);
    const result = await registerForEvent(eventId, {
      registrant_name: values.registrant_name,
      registrant_phone: values.registrant_phone,
      registrant_email: values.registrant_email || undefined,
      student_name: values.student_name || undefined,
      notes: values.notes || undefined,
    });
    setIsSubmitting(false);

    if (result.success) {
      toast.success("Registration added");
      setShowRegisterDialog(false);
      form.reset();
      loadData();
    } else {
      toast.error(result.error);
    }
  }

  if (loading) {
    return (
      <div className="space-y-6 p-4 md:p-6">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-20" />
          ))}
        </div>
        <Skeleton className="h-[300px]" />
      </div>
    );
  }

  if (!event) {
    return (
      <div className="flex h-[400px] items-center justify-center">
        <p className="text-muted-foreground">Event not found.</p>
      </div>
    );
  }

  const statusColors: Record<string, string> = {
    upcoming: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
    completed:
      "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
    cancelled: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  };

  return (
    <div className="space-y-6 p-4 md:p-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <Button
            variant="ghost"
            size="sm"
            className="mb-2"
            onClick={() => router.push("/admissions/events")}
          >
            <ArrowLeft className="mr-1 h-4 w-4" />
            Back to Events
          </Button>
          <h1 className="text-2xl font-bold">{event.name}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <Badge variant="secondary">
              {EVENT_TYPE_LABELS[event.event_type]}
            </Badge>
            <Badge className={statusColors[event.status] ?? ""}>
              {event.status}
            </Badge>
          </div>
        </div>
        {event.status === "upcoming" && (
          <Button onClick={() => setShowRegisterDialog(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Register Attendee
          </Button>
        )}
      </div>

      {/* Event info */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="flex items-center gap-3 pt-6">
            <CalendarDays className="h-5 w-5 text-muted-foreground" />
            <div>
              <p className="text-sm font-medium">
                {formatDate(event.event_date)}
              </p>
              <p className="text-xs text-muted-foreground">Date</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 pt-6">
            <Clock className="h-5 w-5 text-muted-foreground" />
            <div>
              <p className="text-sm font-medium">
                {event.start_time
                  ? `${event.start_time}${event.end_time ? ` - ${event.end_time}` : ""}`
                  : "--"}
              </p>
              <p className="text-xs text-muted-foreground">Time</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 pt-6">
            <MapPin className="h-5 w-5 text-muted-foreground" />
            <div>
              <p className="text-sm font-medium">{event.venue || "--"}</p>
              <p className="text-xs text-muted-foreground">Venue</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 pt-6">
            <Users className="h-5 w-5 text-muted-foreground" />
            <div>
              <p className="text-sm font-medium">
                {event.registered_count}
                {event.capacity != null ? ` / ${event.capacity}` : ""}
              </p>
              <p className="text-xs text-muted-foreground">Registered</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Stats row */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Registered</CardTitle>
              <Users className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {stats.total_registered}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Attended</CardTitle>
              <UserCheck className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.total_attended}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                Attendance Rate
              </CardTitle>
              <Percent className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {stats.attendance_rate.toFixed(1)}%
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Fill Rate</CardTitle>
              <Percent className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {stats.fill_rate != null
                  ? `${stats.fill_rate.toFixed(1)}%`
                  : "--"}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Description */}
      {event.description && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Description</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground whitespace-pre-wrap">
              {event.description}
            </p>
          </CardContent>
        </Card>
      )}

      {/* Registrations */}
      <div>
        <h2 className="mb-4 text-lg font-semibold">Registrations</h2>
        <EventRegistrationTable
          eventId={eventId}
          registrations={registrations}
          eventStatus={event.status}
          onRefresh={loadData}
        />
      </div>

      {/* Register dialog */}
      <Dialog
        open={showRegisterDialog}
        onOpenChange={setShowRegisterDialog}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Register Attendee</DialogTitle>
          </DialogHeader>
          <Form {...form}>
            <form
              onSubmit={form.handleSubmit(handleRegister)}
              className="space-y-4"
            >
              <FormField
                control={form.control}
                name="registrant_name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Parent/Guardian Name</FormLabel>
                    <FormControl>
                      <Input placeholder="Full name" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="registrant_phone"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Phone</FormLabel>
                      <FormControl>
                        <Input placeholder="+233 XX XXX XXXX" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="registrant_email"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Email (Optional)</FormLabel>
                      <FormControl>
                        <Input
                          type="email"
                          placeholder="email@example.com"
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <FormField
                control={form.control}
                name="student_name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Student Name (Optional)</FormLabel>
                    <FormControl>
                      <Input placeholder="Prospective student" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="notes"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Notes (Optional)</FormLabel>
                    <FormControl>
                      <Textarea rows={2} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <Button
                type="submit"
                disabled={isSubmitting}
                className="w-full sm:w-auto"
              >
                {isSubmitting && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                Register
              </Button>
            </form>
          </Form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
