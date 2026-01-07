import Link from "next/link";
import { ArrowLeft, Pencil, Mail, Phone, MapPin, Briefcase, Calendar, CreditCard, BadgeCheck, User } from "lucide-react";
import { notFound } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Separator } from "@/components/ui/separator";

import { getStaffMember } from "@/actions/staff.action";
import type { StaffStatus, StaffType } from "@/types";

export const metadata = {
  title: "Staff Profile",
};

const STATUS_CONFIG: Record<StaffStatus, { label: string; color: string }> = {
  active: { label: "Active", color: "bg-green-500" },
  on_leave: { label: "On Leave", color: "bg-yellow-500" },
  suspended: { label: "Suspended", color: "bg-red-500" },
  terminated: { label: "Terminated", color: "bg-gray-500" },
  retired: { label: "Retired", color: "bg-blue-500" },
};

const TYPE_CONFIG: Record<StaffType, { label: string; color: string }> = {
  teaching: { label: "Teaching", color: "bg-purple-500" },
  non_teaching: { label: "Non-Teaching", color: "bg-blue-500" },
  administrative: { label: "Administrative", color: "bg-indigo-500" },
};

interface StaffProfilePageProps {
  params: Promise<{ id: string }>;
}

export default async function StaffProfilePage({ params }: StaffProfilePageProps) {
  const { id } = await params;
  const result = await getStaffMember(id);

  if (!result.success || !result.data) {
    notFound();
  }

  const staff = result.data;

  const getInitials = (firstName: string, lastName: string) => {
    return `${firstName.charAt(0)}${lastName.charAt(0)}`.toUpperCase();
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link href="/staff">
              <ArrowLeft className="h-5 w-5" />
            </Link>
          </Button>
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Staff Profile</h1>
            <p className="text-muted-foreground">
              View and manage staff member details
            </p>
          </div>
        </div>
        <Button asChild>
          <Link href={`/staff/${staff.id}/edit`}>
            <Pencil className="mr-2 h-4 w-4" />
            Edit Profile
          </Link>
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left Column - Profile Overview */}
        <div className="space-y-6">
          {/* Profile Card */}
          <Card>
            <CardContent className="pt-6">
              <div className="flex flex-col items-center text-center">
                <Avatar className="h-24 w-24">
                  <AvatarImage src={staff.photo_url || undefined} />
                  <AvatarFallback className="text-2xl">
                    {getInitials(staff.first_name, staff.last_name)}
                  </AvatarFallback>
                </Avatar>
                <h2 className="mt-4 text-xl font-semibold">
                  {staff.first_name} {staff.middle_name ? `${staff.middle_name} ` : ""}{staff.last_name}
                </h2>
                <p className="text-muted-foreground">{staff.job_title}</p>
                <div className="mt-2 flex gap-2">
                  <Badge
                    variant="secondary"
                    className={`${STATUS_CONFIG[staff.status]?.color || "bg-gray-500"} text-white`}
                  >
                    {STATUS_CONFIG[staff.status]?.label || staff.status}
                  </Badge>
                  <Badge
                    variant="outline"
                    className={`${TYPE_CONFIG[staff.staff_type]?.color || "bg-gray-500"} text-white border-0`}
                  >
                    {TYPE_CONFIG[staff.staff_type]?.label || staff.staff_type}
                  </Badge>
                </div>
                <p className="mt-4 font-mono text-sm text-muted-foreground">
                  {staff.staff_id}
                </p>
              </div>

              <Separator className="my-6" />

              {/* Contact Quick View */}
              <div className="space-y-4">
                <div className="flex items-center gap-3">
                  <Mail className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm">{staff.email}</span>
                </div>
                <div className="flex items-center gap-3">
                  <Phone className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm">{staff.phone}</span>
                </div>
                {(staff.address || staff.city || staff.region) && (
                  <div className="flex items-center gap-3">
                    <MapPin className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm">
                      {[staff.address, staff.city, staff.region].filter(Boolean).join(", ")}
                    </span>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Quick Stats */}
          {staff.assignments && staff.assignments.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium">Class Assignments</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {staff.assignments.map((assignment) => (
                    <div
                      key={assignment.id}
                      className="flex items-center justify-between rounded-lg border p-3"
                    >
                      <div>
                        <p className="font-medium">
                          {assignment.class_name} - {assignment.section_name}
                        </p>
                        {assignment.is_class_teacher && (
                          <Badge variant="secondary" className="mt-1">
                            Class Teacher
                          </Badge>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Right Column - Details */}
        <div className="lg:col-span-2 space-y-6">
          {/* Personal Information */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <User className="h-5 w-5" />
                Personal Information
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <p className="text-sm text-muted-foreground">Full Name</p>
                  <p className="font-medium">
                    {staff.first_name} {staff.middle_name} {staff.last_name}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Gender</p>
                  <p className="font-medium capitalize">{staff.gender}</p>
                </div>
                {staff.date_of_birth && (
                  <div>
                    <p className="text-sm text-muted-foreground">Date of Birth</p>
                    <p className="font-medium">{formatDate(staff.date_of_birth)}</p>
                  </div>
                )}
                {staff.phone_secondary && (
                  <div>
                    <p className="text-sm text-muted-foreground">Secondary Phone</p>
                    <p className="font-medium">{staff.phone_secondary}</p>
                  </div>
                )}
              </div>

              {/* Emergency Contact */}
              {staff.emergency_contact_name && (
                <>
                  <Separator className="my-4" />
                  <h4 className="text-sm font-medium mb-3">Emergency Contact</h4>
                  <div className="grid gap-4 sm:grid-cols-3">
                    <div>
                      <p className="text-sm text-muted-foreground">Name</p>
                      <p className="font-medium">{staff.emergency_contact_name}</p>
                    </div>
                    {staff.emergency_contact_phone && (
                      <div>
                        <p className="text-sm text-muted-foreground">Phone</p>
                        <p className="font-medium">{staff.emergency_contact_phone}</p>
                      </div>
                    )}
                    {staff.emergency_contact_relationship && (
                      <div>
                        <p className="text-sm text-muted-foreground">Relationship</p>
                        <p className="font-medium">{staff.emergency_contact_relationship}</p>
                      </div>
                    )}
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          {/* Employment Information */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Briefcase className="h-5 w-5" />
                Employment Information
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <p className="text-sm text-muted-foreground">Staff Type</p>
                  <p className="font-medium">{TYPE_CONFIG[staff.staff_type]?.label || staff.staff_type}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Job Title</p>
                  <p className="font-medium">{staff.job_title}</p>
                </div>
                {staff.department && (
                  <div>
                    <p className="text-sm text-muted-foreground">Department</p>
                    <p className="font-medium">{staff.department}</p>
                  </div>
                )}
                <div>
                  <p className="text-sm text-muted-foreground">Employment Date</p>
                  <p className="font-medium">{formatDate(staff.employment_date)}</p>
                </div>
                {staff.termination_date && (
                  <div>
                    <p className="text-sm text-muted-foreground">Termination Date</p>
                    <p className="font-medium">{formatDate(staff.termination_date)}</p>
                  </div>
                )}
                {staff.school_name && (
                  <div>
                    <p className="text-sm text-muted-foreground">School</p>
                    <p className="font-medium">{staff.school_name}</p>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Identification */}
          {(staff.ghana_card_number || staff.ssnit_number || staff.teacher_license_number) && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BadgeCheck className="h-5 w-5" />
                  Identification
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4 sm:grid-cols-3">
                  {staff.ghana_card_number && (
                    <div>
                      <p className="text-sm text-muted-foreground">Ghana Card</p>
                      <p className="font-medium font-mono">{staff.ghana_card_number}</p>
                    </div>
                  )}
                  {staff.ssnit_number && (
                    <div>
                      <p className="text-sm text-muted-foreground">SSNIT Number</p>
                      <p className="font-medium">{staff.ssnit_number}</p>
                    </div>
                  )}
                  {staff.teacher_license_number && (
                    <div>
                      <p className="text-sm text-muted-foreground">Teacher License</p>
                      <p className="font-medium">{staff.teacher_license_number}</p>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Banking Information */}
          {(staff.bank_name || staff.account_number) && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <CreditCard className="h-5 w-5" />
                  Banking Information
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4 sm:grid-cols-3">
                  {staff.bank_name && (
                    <div>
                      <p className="text-sm text-muted-foreground">Bank Name</p>
                      <p className="font-medium">{staff.bank_name}</p>
                    </div>
                  )}
                  {staff.bank_branch && (
                    <div>
                      <p className="text-sm text-muted-foreground">Branch</p>
                      <p className="font-medium">{staff.bank_branch}</p>
                    </div>
                  )}
                  {staff.account_number && (
                    <div>
                      <p className="text-sm text-muted-foreground">Account Number</p>
                      <p className="font-medium font-mono">{staff.account_number}</p>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Notes */}
          {staff.notes && (
            <Card>
              <CardHeader>
                <CardTitle>Notes</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm whitespace-pre-wrap">{staff.notes}</p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
