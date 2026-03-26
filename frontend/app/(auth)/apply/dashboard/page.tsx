"use client";

/**
 * SIMS Plus - Applicant Dashboard
 *
 * Lists all of the applicant's applications (drafts, submitted, decisions).
 * Provides: New Application, Claim Application, Profile menu.
 * Path: {school}.simsplus.io/apply/dashboard
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";

import {
  getMyApplications,
  getApplicantProfile,
  claimApplication,
  createDraftApplication,
  logoutApplicant,
} from "@/actions/applicant.action";
import { getPublicPeriods } from "@/actions/admissions.action";
import { ApplicationStatusBadge } from "@/components/admissions/application-status-badge";
import { useTenant } from "@/components/providers/TenantProvider";

import {
  Plus,
  LinkIcon,
  User,
  LogOut,
  KeyRound,
  GraduationCap,
  FileText,
  Loader2,
  ArrowRight,
} from "lucide-react";

import type { MyApplicationListItem } from "@/types/applicant.type";
import type { ApplicantProfile } from "@/types/applicant.type";
import type { PublicPeriod } from "@/types/admissions.type";

import { formatGhanaDate } from "@/lib/format";

export default function ApplicantDashboardPage() {
  const router = useRouter();
  const { tenant } = useTenant();

  const [profile, setProfile] = useState<ApplicantProfile | null>(null);
  const [applications, setApplications] = useState<MyApplicationListItem[]>(
    []
  );
  const [loading, setLoading] = useState(true);

  // Claim dialog state
  const [claimOpen, setClaimOpen] = useState(false);
  const [claimCode, setClaimCode] = useState("");
  const [claiming, setClaiming] = useState(false);

  // New application dialog state
  const [newAppOpen, setNewAppOpen] = useState(false);
  const [periods, setPeriods] = useState<PublicPeriod[]>([]);
  const [selectedPeriodId, setSelectedPeriodId] = useState("");
  const [childFirstName, setChildFirstName] = useState("");
  const [childLastName, setChildLastName] = useState("");
  const [creatingDraft, setCreatingDraft] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    const [profileResult, appsResult] = await Promise.all([
      getApplicantProfile(),
      getMyApplications({ page_size: 50 }),
    ]);

    if (profileResult.success) setProfile(profileResult.data);
    if (appsResult.success) setApplications(appsResult.data.items);
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Fetch periods when new-app dialog opens
  useEffect(() => {
    if (newAppOpen && periods.length === 0) {
      getPublicPeriods().then((result) => {
        if (result.success) setPeriods(result.data.items);
      });
    }
  }, [newAppOpen, periods.length]);

  async function handleClaim() {
    if (!claimCode.trim()) return;
    setClaiming(true);

    const result = await claimApplication(claimCode.trim());

    if (result.success) {
      toast.success("Application claimed successfully");
      setClaimOpen(false);
      setClaimCode("");
      fetchData();
    } else {
      toast.error(result.error || "Failed to claim application");
    }

    setClaiming(false);
  }

  async function handleNewApplication() {
    if (!selectedPeriodId || !childFirstName.trim() || !childLastName.trim()) return;
    setCreatingDraft(true);

    // Create a draft with the child's name -- user will complete details in the form wizard
    const result = await createDraftApplication({
      admission_period_id: selectedPeriodId,
      applicant_first_name: childFirstName.trim(),
      applicant_last_name: childLastName.trim(),
    });

    if (result.success) {
      // Navigate to the form wizard with the draft ID for editing
      // (capture periodId before resetting state)
      const periodId = selectedPeriodId;
      setNewAppOpen(false);
      setChildFirstName("");
      setChildLastName("");
      setSelectedPeriodId("");
      router.push(`/apply/${periodId}?draft=${result.data.id}`);
    } else {
      toast.error(result.error || "Failed to create application");
    }

    setCreatingDraft(false);
  }

  async function handleLogout() {
    try {
      await logoutApplicant();
    } catch {
      // logoutApplicant() calls redirect() which throws a NEXT_REDIRECT
      // error. In some contexts (onClick handler vs form action) the
      // framework may not intercept it. Catch and navigate client-side.
    }
    // Fallback: if the server-side redirect didn't fire, navigate manually
    router.push("/apply/login");
  }

  // ---------- Loading Skeleton ----------
  if (loading) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-8">
        <div className="mb-8 flex items-center justify-between">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-10 w-10 rounded-full" />
        </div>
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-28 w-full rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      {/* Header */}
      <div className="mb-8 flex items-center justify-between">
        <div className="flex items-center gap-3">
          {tenant?.branding?.logo_url ? (
            <Image
              src={tenant.branding.logo_url}
              alt={`${tenant.name} logo`}
              width={40}
              height={40}
              className="rounded-lg"
            />
          ) : (
            <div
              className="flex h-10 w-10 items-center justify-center rounded-lg"
              style={{
                backgroundColor:
                  tenant?.branding?.primary_color || "#1B4F72",
              }}
            >
              <GraduationCap className="h-5 w-5 text-white" />
            </div>
          )}
          <span className="text-lg font-semibold">
            {tenant?.name || "SIMS Plus"}
          </span>
        </div>

        {/* Profile dropdown */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="sm" className="gap-2">
              <User className="h-4 w-4" />
              {profile?.first_name}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem asChild>
              <Link href="/apply/dashboard/profile">
                <User className="mr-2 h-4 w-4" />
                Profile Settings
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link href="/apply/dashboard/change-password">
                <KeyRound className="mr-2 h-4 w-4" />
                Change Password
              </Link>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={handleLogout}>
              <LogOut className="mr-2 h-4 w-4" />
              Sign Out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Welcome */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold">
          Welcome, {profile?.first_name || "Applicant"}
        </h1>
        <p className="text-sm text-muted-foreground">
          Manage your admission applications
        </p>
      </div>

      {/* Action Buttons */}
      <div className="mb-6 flex flex-wrap gap-3">
        {/* New Application */}
        <Dialog open={newAppOpen} onOpenChange={setNewAppOpen}>
          <DialogTrigger asChild>
            <Button
              style={{
                backgroundColor:
                  tenant?.branding?.primary_color || undefined,
              }}
            >
              <Plus className="mr-2 h-4 w-4" />
              New Application
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Start New Application</DialogTitle>
              <DialogDescription>
                Select the admission period and enter the child&apos;s name to
                begin. You will complete the full application in the next step.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label>Admission Period</Label>
                <Select
                  value={selectedPeriodId}
                  onValueChange={setSelectedPeriodId}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select a period" />
                  </SelectTrigger>
                  <SelectContent>
                    {periods.map((period) => (
                      <SelectItem key={period.id} value={period.id}>
                        {period.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="child-first-name">Child&apos;s First Name</Label>
                  <Input
                    id="child-first-name"
                    value={childFirstName}
                    onChange={(e) => setChildFirstName(e.target.value)}
                    placeholder="e.g. Kofi"
                    disabled={creatingDraft}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="child-last-name">Child&apos;s Last Name</Label>
                  <Input
                    id="child-last-name"
                    value={childLastName}
                    onChange={(e) => setChildLastName(e.target.value)}
                    placeholder="e.g. Mensah"
                    disabled={creatingDraft}
                  />
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setNewAppOpen(false)}
              >
                Cancel
              </Button>
              <Button
                onClick={handleNewApplication}
                disabled={!selectedPeriodId || !childFirstName.trim() || !childLastName.trim() || creatingDraft}
              >
                {creatingDraft ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Creating...
                  </>
                ) : (
                  "Start Application"
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Claim Application */}
        <Dialog open={claimOpen} onOpenChange={setClaimOpen}>
          <DialogTrigger asChild>
            <Button variant="outline">
              <LinkIcon className="mr-2 h-4 w-4" />
              Claim Application
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Claim Application</DialogTitle>
              <DialogDescription>
                If you previously submitted an application without an account,
                enter your tracking code to link it to your account. Your
                account email must match a guardian email on the application.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="tracking-code">Tracking Code</Label>
                <Input
                  id="tracking-code"
                  value={claimCode}
                  onChange={(e) => setClaimCode(e.target.value)}
                  placeholder="e.g. APP-A1B2C3D4"
                  disabled={claiming}
                />
              </div>
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setClaimOpen(false)}
              >
                Cancel
              </Button>
              <Button
                onClick={handleClaim}
                disabled={!claimCode.trim() || claiming}
              >
                {claiming ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Claiming...
                  </>
                ) : (
                  "Claim"
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* Applications List */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold">
          My Applications ({applications.length})
        </h2>

        {applications.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center">
              <FileText className="mx-auto mb-4 h-12 w-12 text-muted-foreground" />
              <p className="text-lg font-medium">No applications yet</p>
              <p className="mt-2 text-sm text-muted-foreground">
                Start a new application or claim an existing one using your
                tracking code.
              </p>
            </CardContent>
          </Card>
        ) : (
          applications.map((app) => (
            <Card key={app.id} className="transition-colors hover:bg-muted/30">
              <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold">
                      {app.applicant_first_name} {app.applicant_last_name}
                    </span>
                    <ApplicationStatusBadge status={app.status} />
                  </div>
                  <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
                    {app.target_class_name && (
                      <span>{app.target_class_name}</span>
                    )}
                    {app.admission_period_name && (
                      <span>{app.admission_period_name}</span>
                    )}
                    <span>
                      {app.submitted_at
                        ? `Submitted ${formatGhanaDate(app.submitted_at)}`
                        : `Created ${formatGhanaDate(app.created_at)}`}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {app.tracking_code}
                  </div>
                </div>

                <div className="flex-shrink-0">
                  {app.status === "draft" ? (
                    <Button size="sm" asChild>
                      <Link
                        href={`/apply/${app.admission_period_id}?draft=${app.id}`}
                      >
                        Continue
                        <ArrowRight className="ml-1 h-3.5 w-3.5" />
                      </Link>
                    </Button>
                  ) : app.status === "offered" ? (
                    <Button
                      size="sm"
                      asChild
                      className="bg-green-600 hover:bg-green-700 text-white"
                    >
                      <Link href={`/apply/dashboard/${app.id}`}>
                        Respond to Offer
                        <ArrowRight className="ml-1 h-3.5 w-3.5" />
                      </Link>
                    </Button>
                  ) : (
                    <Button size="sm" variant="outline" asChild>
                      <Link href={`/apply/dashboard/${app.id}`}>
                        View Details
                      </Link>
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>
    </div>
  );
}
