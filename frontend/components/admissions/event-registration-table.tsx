"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Loader2, Trash2, UserCheck, UserX } from "lucide-react";
import {
  markAttendance,
  cancelRegistration,
} from "@/actions/events.action";
import { formatDate, formatGhanaPhone } from "@/lib/format";
import type { EventRegistration } from "@/types/admissions.type";

interface EventRegistrationTableProps {
  eventId: string;
  registrations: EventRegistration[];
  eventStatus: string;
  onRefresh: () => void;
}

export function EventRegistrationTable({
  eventId,
  registrations,
  eventStatus,
  onRefresh,
}: EventRegistrationTableProps) {
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [loadingIds, setLoadingIds] = useState<Set<string>>(new Set());

  async function handleToggleAttendance(
    registration: EventRegistration
  ) {
    setLoadingIds((prev) => new Set(prev).add(registration.id));
    const result = await markAttendance(
      eventId,
      registration.id,
      !registration.attended
    );
    setLoadingIds((prev) => {
      const next = new Set(prev);
      next.delete(registration.id);
      return next;
    });

    if (result.success) {
      toast.success(
        registration.attended ? "Attendance unmarked" : "Marked as attended"
      );
      onRefresh();
    } else {
      toast.error(result.error);
    }
  }

  async function handleDelete() {
    if (!deletingId) return;
    setLoadingIds((prev) => new Set(prev).add(deletingId));
    const result = await cancelRegistration(eventId, deletingId);
    setLoadingIds((prev) => {
      const next = new Set(prev);
      next.delete(deletingId);
      return next;
    });
    setDeletingId(null);

    if (result.success) {
      toast.success("Registration cancelled");
      onRefresh();
    } else {
      toast.error(result.error);
    }
  }

  return (
    <>
      <div className="overflow-x-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead className="hidden sm:table-cell">Phone</TableHead>
              <TableHead className="hidden md:table-cell">Email</TableHead>
              <TableHead className="hidden md:table-cell">Student</TableHead>
              <TableHead>Attended</TableHead>
              <TableHead className="w-[100px]">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {registrations.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={6}
                  className="h-24 text-center text-muted-foreground"
                >
                  No registrations yet.
                </TableCell>
              </TableRow>
            ) : (
              registrations.map((reg) => (
                <TableRow key={reg.id}>
                  <TableCell className="font-medium">
                    {reg.registrant_name}
                    <span className="block text-xs text-muted-foreground sm:hidden">
                      {reg.registrant_phone}
                    </span>
                  </TableCell>
                  <TableCell className="hidden sm:table-cell">
                    {formatGhanaPhone(reg.registrant_phone)}
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    {reg.registrant_email || "--"}
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    {reg.student_name || "--"}
                  </TableCell>
                  <TableCell>
                    {reg.attended ? (
                      <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                        <UserCheck className="mr-1 h-3 w-3" />
                        Yes
                      </Badge>
                    ) : (
                      <Badge variant="secondary">
                        <UserX className="mr-1 h-3 w-3" />
                        No
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      {(eventStatus === "upcoming" ||
                        eventStatus === "completed") && (
                        <Button
                          variant="ghost"
                          size="icon"
                          disabled={loadingIds.has(reg.id)}
                          onClick={() => handleToggleAttendance(reg)}
                          aria-label={
                            reg.attended
                              ? "Unmark attendance"
                              : "Mark as attended"
                          }
                        >
                          {loadingIds.has(reg.id) ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Checkbox
                              checked={reg.attended}
                              className="pointer-events-none"
                            />
                          )}
                        </Button>
                      )}
                      {eventStatus === "upcoming" && (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="text-destructive"
                          onClick={() => setDeletingId(reg.id)}
                          aria-label="Cancel registration"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <AlertDialog
        open={!!deletingId}
        onOpenChange={() => setDeletingId(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Cancel Registration?</AlertDialogTitle>
            <AlertDialogDescription>
              This will remove the registration and free up an event slot. This
              action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Cancel Registration
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
