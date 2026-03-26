"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";
import {
  ArrowLeft,
  CalendarDays,
  Edit,
  Loader2,
  Mail,
  MapPin,
  Phone,
  RefreshCw,
  Trash2,
  User,
  UserPlus,
  AlertCircle,
} from "lucide-react";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { InquiryStatusBadge } from "@/components/admissions/inquiry-status-badge";
import { InquiryForm } from "@/components/admissions/inquiry-form";
import { CommunicationLog } from "@/components/admissions/communication-log";
import { FollowUpList } from "@/components/admissions/follow-up-list";
import {
  getInquiry,
  getCommunications,
  updateInquiryStatus,
  assignInquiry,
  convertInquiry,
  deleteInquiry,
} from "@/actions/inquiries.action";
import { getAdmissionPeriods } from "@/actions/admissions.action";
import { getUsers } from "@/actions/settings.action";
import type { Inquiry, InquiryStatus, Communication, FollowUp } from "@/types/inquiry.type";

// Valid status transitions map (matches backend)
const VALID_TRANSITIONS: Record<string, string[]> = {
  new: ["contacted", "interested", "lost"],
  contacted: ["interested", "lost"],
  interested: ["applied", "lost"],
  applied: ["enrolled"],
  enrolled: [],
  lost: ["new", "contacted"],
};

interface InquiryDetailProps {
  inquiryId: string;
}

export function InquiryDetail({ inquiryId }: InquiryDetailProps) {
  const router = useRouter();
  const [inquiry, setInquiry] = useState<Inquiry | null>(null);
  const [communications, setCommunications] = useState<Communication[]>([]);
  const [followUps, setFollowUps] = useState<FollowUp[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Lookups
  const [staffMembers, setStaffMembers] = useState<Array<{ id: string; name: string }>>([]);
  const [periods, setPeriods] = useState<Array<{ id: string; name: string }>>([]);

  // Dialogs
  const [showEditForm, setShowEditForm] = useState(false);
  const [showConvertDialog, setShowConvertDialog] = useState(false);
  const [selectedPeriodId, setSelectedPeriodId] = useState("");
  const [convertLoading, setConvertLoading] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const loadInquiry = useCallback(async () => {
    const result = await getInquiry(inquiryId);
    if (result.success && result.data) {
      setInquiry(result.data);
    } else {
      setError(result.error || "Failed to load inquiry");
    }
  }, [inquiryId]);

  const loadCommunications = useCallback(async () => {
    const result = await getCommunications(inquiryId);
    if (result.success && result.data) {
      setCommunications(result.data);
    }
  }, [inquiryId]);

  const loadAll = useCallback(async () => {
    setLoading(true);
    await Promise.all([loadInquiry(), loadCommunications()]);
    setLoading(false);
  }, [loadInquiry, loadCommunications]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  useEffect(() => {
    async function loadLookups() {
      const [usersResult, periodsResult] = await Promise.all([
        getUsers(1, 100),
        getAdmissionPeriods({ page_size: 50 }),
      ]);

      if (usersResult.success && usersResult.data) {
        setStaffMembers(
          usersResult.data.items.map((u) => ({
            id: u.id,
            name: `${u.first_name} ${u.last_name}`,
          }))
        );
      }
      if (periodsResult.success && periodsResult.data) {
        setPeriods(
          periodsResult.data.items
            .filter((p) => p.status === "open")
            .map((p) => ({ id: p.id, name: p.name }))
        );
      }
    }
    loadLookups();
  }, []);

  async function handleStatusChange(newStatus: string) {
    const result = await updateInquiryStatus(inquiryId, newStatus);
    if (result.success) {
      toast.success(`Status updated to ${newStatus}`);
      loadInquiry();
    } else {
      toast.error(result.error);
    }
  }

  async function handleAssign(userId: string) {
    const result = await assignInquiry(inquiryId, userId);
    if (result.success) {
      toast.success("Inquiry assigned");
      loadInquiry();
    } else {
      toast.error(result.error);
    }
  }

  async function handleConvert() {
    if (!selectedPeriodId) {
      toast.error("Please select an admission period");
      return;
    }
    setConvertLoading(true);
    const result = await convertInquiry(inquiryId, {
      period_id: selectedPeriodId,
    });
    if (result.success) {
      toast.success("Inquiry converted to application");
      loadInquiry();
      setShowConvertDialog(false);
    } else {
      toast.error(result.error);
    }
    setConvertLoading(false);
  }

  async function handleDelete() {
    setDeleting(true);
    const result = await deleteInquiry(inquiryId);
    if (result.success) {
      toast.success("Inquiry deleted");
      router.push("/admissions/inquiries");
    } else {
      toast.error(result.error);
      setDeleting(false);
    }
  }

  if (loading) {
    return (
      <div className="p-4 md:p-6 space-y-6">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-4">
            <Skeleton className="h-[200px]" />
            <Skeleton className="h-[300px]" />
          </div>
          <Skeleton className="h-[300px]" />
        </div>
      </div>
    );
  }

  if (error || !inquiry) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4 p-6">
        <AlertCircle className="h-10 w-10 text-destructive" />
        <h2 className="text-lg font-semibold">Inquiry not found</h2>
        <p className="text-sm text-muted-foreground">{error}</p>
        <Button variant="outline" asChild>
          <Link href="/admissions/inquiries">Back to Inquiries</Link>
        </Button>
      </div>
    );
  }

  const validTransitions = VALID_TRANSITIONS[inquiry.status] || [];
  const isConverted = !!inquiry.converted_application_id;
  const isTerminal = inquiry.status === "enrolled";

  return (
    <div className="p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" asChild>
            <Link href="/admissions/inquiries">
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold">
                {inquiry.first_name} {inquiry.last_name}
              </h1>
              <InquiryStatusBadge status={inquiry.status as InquiryStatus} />
            </div>
            <p className="text-sm text-muted-foreground">
              Added{" "}
              {new Date(inquiry.created_at).toLocaleDateString("en-GB", {
                day: "2-digit",
                month: "long",
                year: "numeric",
              })}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowEditForm(true)}
          >
            <Edit className="mr-2 h-4 w-4" />
            Edit
          </Button>
          {!isConverted && !isTerminal && (
            <Button
              size="sm"
              onClick={() => setShowConvertDialog(true)}
            >
              <UserPlus className="mr-2 h-4 w-4" />
              Convert to Application
            </Button>
          )}
          {isConverted && (
            <Button variant="outline" size="sm" asChild>
              <Link
                href={`/admissions/applications/${inquiry.converted_application_id}`}
              >
                View Application
              </Link>
            </Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Info Card */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Student Information</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-muted-foreground">Name</span>
                  <p className="font-medium">
                    {inquiry.first_name} {inquiry.last_name}
                  </p>
                </div>
                {inquiry.date_of_birth && (
                  <div>
                    <span className="text-muted-foreground">Date of Birth</span>
                    <p className="font-medium">
                      {new Date(inquiry.date_of_birth).toLocaleDateString("en-GB", {
                        day: "2-digit",
                        month: "long",
                        year: "numeric",
                      })}
                    </p>
                  </div>
                )}
                {inquiry.gender && (
                  <div>
                    <span className="text-muted-foreground">Gender</span>
                    <p className="font-medium capitalize">{inquiry.gender}</p>
                  </div>
                )}
                <div>
                  <span className="text-muted-foreground">Source</span>
                  <p className="font-medium capitalize">
                    {inquiry.source.replace(/_/g, " ")}
                  </p>
                </div>
                {inquiry.referred_by && (
                  <div>
                    <span className="text-muted-foreground">Referred By</span>
                    <p className="font-medium">{inquiry.referred_by}</p>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Guardian Card */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Guardian Information</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3 text-sm">
                <div className="flex items-center gap-2">
                  <User className="h-4 w-4 text-muted-foreground" />
                  <span className="font-medium">{inquiry.guardian_name}</span>
                </div>
                <div className="flex items-center gap-2">
                  <Phone className="h-4 w-4 text-muted-foreground" />
                  <span>{inquiry.guardian_phone}</span>
                </div>
                {inquiry.guardian_email && (
                  <div className="flex items-center gap-2">
                    <Mail className="h-4 w-4 text-muted-foreground" />
                    <span>{inquiry.guardian_email}</span>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Tabs */}
          <Tabs defaultValue="communications">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="communications">Communications</TabsTrigger>
              <TabsTrigger value="followups">Follow-ups</TabsTrigger>
            </TabsList>
            <TabsContent value="communications" className="mt-4">
              <CommunicationLog
                inquiryId={inquiryId}
                communications={communications}
                onRefresh={loadCommunications}
              />
            </TabsContent>
            <TabsContent value="followups" className="mt-4">
              <FollowUpList
                inquiryId={inquiryId}
                followUps={followUps}
                staffMembers={staffMembers}
                onRefresh={loadAll}
              />
            </TabsContent>
          </Tabs>

          {/* Notes */}
          {inquiry.notes && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Notes</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm whitespace-pre-wrap">{inquiry.notes}</p>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          {/* Status Change */}
          {validTransitions.length > 0 && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">Change Status</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {validTransitions.map((status) => (
                  <Button
                    key={status}
                    variant="outline"
                    size="sm"
                    className="w-full justify-start"
                    onClick={() => handleStatusChange(status)}
                  >
                    <InquiryStatusBadge
                      status={status as InquiryStatus}
                      className="mr-2"
                    />
                    Mark as {status.charAt(0).toUpperCase() + status.slice(1)}
                  </Button>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Assign Staff */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Assigned To</CardTitle>
            </CardHeader>
            <CardContent>
              <Select
                value={inquiry.assigned_to || ""}
                onValueChange={handleAssign}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Assign staff member" />
                </SelectTrigger>
                <SelectContent>
                  {staffMembers.map((s) => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </CardContent>
          </Card>

          {/* Danger Zone */}
          <Card className="border-destructive/30">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm text-destructive">
                Danger Zone
              </CardTitle>
            </CardHeader>
            <CardContent>
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button
                    variant="destructive"
                    size="sm"
                    className="w-full"
                    disabled={deleting}
                  >
                    {deleting ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Trash2 className="mr-2 h-4 w-4" />
                    )}
                    Delete Inquiry
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Delete Inquiry</AlertDialogTitle>
                    <AlertDialogDescription>
                      This will permanently delete this inquiry and all associated
                      communications and follow-up tasks. This action cannot be
                      undone.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction
                      onClick={handleDelete}
                      className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                    >
                      Delete
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Edit Form Dialog */}
      <InquiryForm
        open={showEditForm}
        onOpenChange={setShowEditForm}
        editingInquiry={inquiry}
        onSuccess={loadInquiry}
      />

      {/* Convert Dialog */}
      <AlertDialog open={showConvertDialog} onOpenChange={setShowConvertDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Convert to Application</AlertDialogTitle>
            <AlertDialogDescription>
              This will create a formal application from this inquiry. The
              guardian information will be pre-filled. Select an admission
              period to proceed.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="py-4">
            <Select
              value={selectedPeriodId}
              onValueChange={setSelectedPeriodId}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select admission period" />
              </SelectTrigger>
              <SelectContent>
                {periods.length === 0 ? (
                  <SelectItem value="none" disabled>
                    No open periods available
                  </SelectItem>
                ) : (
                  periods.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name}
                    </SelectItem>
                  ))
                )}
              </SelectContent>
            </Select>
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConvert}
              disabled={!selectedPeriodId || convertLoading}
            >
              {convertLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Converting...
                </>
              ) : (
                "Convert"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
