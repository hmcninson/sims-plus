"use client";

import { useEffect, useState, useTransition } from "react";
import {
  Phone,
  Mail,
  MapPin,
  Briefcase,
  Building,
  IdCard,
  Users,
  Loader2,
} from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";

import { getGuardianStudents } from "@/actions/students.action";
import type { Guardian, StudentListItem } from "@/types";

interface ViewGuardianDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  guardian?: Guardian;
}

export function ViewGuardianDialog({
  open,
  onOpenChange,
  guardian,
}: ViewGuardianDialogProps) {
  const [isPending, startTransition] = useTransition();
  const [linkedStudents, setLinkedStudents] = useState<StudentListItem[]>([]);

  // Fetch linked students when dialog opens
  useEffect(() => {
    if (open && guardian) {
      startTransition(async () => {
        const result = await getGuardianStudents(guardian.id);
        if (result.success && result.data) {
          setLinkedStudents(result.data);
        } else {
          setLinkedStudents([]);
        }
      });
    }
  }, [open, guardian]);

  if (!guardian) return null;

  const getInitials = (firstName: string, lastName: string) => {
    return `${firstName.charAt(0)}${lastName.charAt(0)}`.toUpperCase();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Guardian Details</DialogTitle>
          <DialogDescription>
            View guardian information and linked students.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          {/* Guardian Profile Header */}
          <div className="flex items-center gap-4">
            <Avatar className="h-16 w-16">
              <AvatarImage src={guardian.photo_url || undefined} />
              <AvatarFallback className="text-lg">
                {getInitials(guardian.first_name, guardian.last_name)}
              </AvatarFallback>
            </Avatar>
            <div>
              <h3 className="text-xl font-semibold">
                {guardian.first_name} {guardian.last_name}
              </h3>
              {guardian.occupation && (
                <p className="text-sm text-muted-foreground">{guardian.occupation}</p>
              )}
            </div>
          </div>

          <Separator />

          {/* Contact Information */}
          <div className="space-y-3">
            <h4 className="text-sm font-medium text-muted-foreground">Contact Information</h4>

            <div className="grid gap-3">
              <div className="flex items-center gap-3">
                <Phone className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="text-sm font-medium">{guardian.phone}</p>
                  {guardian.phone_secondary && (
                    <p className="text-xs text-muted-foreground">{guardian.phone_secondary}</p>
                  )}
                </div>
              </div>

              {guardian.email && (
                <div className="flex items-center gap-3">
                  <Mail className="h-4 w-4 text-muted-foreground" />
                  <p className="text-sm">{guardian.email}</p>
                </div>
              )}

              {(guardian.address || guardian.city || guardian.region) && (
                <div className="flex items-start gap-3">
                  <MapPin className="mt-0.5 h-4 w-4 text-muted-foreground" />
                  <div className="text-sm">
                    {guardian.address && <p>{guardian.address}</p>}
                    <p>
                      {guardian.city}
                      {guardian.city && guardian.region && ", "}
                      {guardian.region}
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Work Information */}
          {(guardian.occupation || guardian.workplace || guardian.work_phone) && (
            <>
              <Separator />
              <div className="space-y-3">
                <h4 className="text-sm font-medium text-muted-foreground">Work Information</h4>

                <div className="grid gap-3">
                  {guardian.occupation && (
                    <div className="flex items-center gap-3">
                      <Briefcase className="h-4 w-4 text-muted-foreground" />
                      <p className="text-sm">{guardian.occupation}</p>
                    </div>
                  )}

                  {guardian.workplace && (
                    <div className="flex items-center gap-3">
                      <Building className="h-4 w-4 text-muted-foreground" />
                      <p className="text-sm">{guardian.workplace}</p>
                    </div>
                  )}

                  {guardian.work_phone && (
                    <div className="flex items-center gap-3">
                      <Phone className="h-4 w-4 text-muted-foreground" />
                      <p className="text-sm">{guardian.work_phone} (Work)</p>
                    </div>
                  )}
                </div>
              </div>
            </>
          )}

          {/* Ghana Card */}
          {guardian.ghana_card_number && (
            <>
              <Separator />
              <div className="space-y-3">
                <h4 className="text-sm font-medium text-muted-foreground">Identification</h4>
                <div className="flex items-center gap-3">
                  <IdCard className="h-4 w-4 text-muted-foreground" />
                  <p className="font-mono text-sm">{guardian.ghana_card_number}</p>
                </div>
              </div>
            </>
          )}

          {/* Linked Students */}
          <Separator />
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Users className="h-4 w-4 text-muted-foreground" />
              <h4 className="text-sm font-medium text-muted-foreground">Linked Students</h4>
            </div>

            {isPending ? (
              <div className="flex items-center justify-center py-4">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : linkedStudents.length === 0 ? (
              <p className="py-2 text-sm text-muted-foreground">
                No students linked to this guardian.
              </p>
            ) : (
              <div className="space-y-2">
                {linkedStudents.map((student) => (
                  <div
                    key={student.id}
                    className="flex items-center justify-between rounded-lg border p-3"
                  >
                    <div className="flex items-center gap-3">
                      <Avatar className="h-8 w-8">
                        <AvatarImage src={student.photo_url || undefined} />
                        <AvatarFallback className="text-xs">
                          {getInitials(student.first_name, student.last_name)}
                        </AvatarFallback>
                      </Avatar>
                      <div>
                        <p className="text-sm font-medium">
                          {student.first_name}{" "}
                          {student.middle_name ? `${student.middle_name} ` : ""}
                          {student.last_name}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {student.student_id}
                          {student.class_name && ` - ${student.class_name}`}
                        </p>
                      </div>
                    </div>
                    <Badge
                      variant="secondary"
                      className={
                        student.status === "active"
                          ? "bg-green-500 text-white"
                          : "bg-gray-500 text-white"
                      }
                    >
                      {student.status}
                    </Badge>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Notes */}
          {guardian.notes && (
            <>
              <Separator />
              <div className="space-y-2">
                <h4 className="text-sm font-medium text-muted-foreground">Notes</h4>
                <p className="text-sm">{guardian.notes}</p>
              </div>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
