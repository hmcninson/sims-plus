"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useForm , type Resolver} from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
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
  updateTenant,
  suspendTenant,
  activateTenant,
  impersonateTenant,
} from "@/actions/platform.action";
import type { TenantDetail } from "@/types/platform.type";
import {
  ArrowLeft,
  Users,
  UserCog,
  School,
  ExternalLink,
  Loader2,
  Ban,
  CheckCircle,
  Pencil,
} from "lucide-react";

interface TenantDetailPageProps {
  tenant: TenantDetail;
}

const editSchema = z.object({
  subscription_tier: z.enum(["starter", "professional", "enterprise"]),
  max_students: z.coerce.number().min(1, "Must be at least 1"),
  max_staff: z.coerce.number().min(1, "Must be at least 1"),
});

type EditFormData = z.infer<typeof editSchema>;

function statusBadge(status: string) {
  switch (status) {
    case "active":
      return (
        <Badge className="bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400">
          Active
        </Badge>
      );
    case "trial":
      return (
        <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400">
          Trial
        </Badge>
      );
    case "suspended":
      return <Badge variant="destructive">Suspended</Badge>;
    default:
      return <Badge variant="secondary">{status}</Badge>;
  }
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "--";
  try {
    return new Date(dateStr).toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

export function TenantDetailPage({ tenant: initialTenant }: TenantDetailPageProps) {
  const router = useRouter();
  const [tenant, setTenant] = useState<TenantDetail>(initialTenant);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [showSuspendDialog, setShowSuspendDialog] = useState(false);
  const [showActivateDialog, setShowActivateDialog] = useState(false);
  const [showImpersonateDialog, setShowImpersonateDialog] = useState(false);
  const [suspendReason, setSuspendReason] = useState("");
  const [isActioning, setIsActioning] = useState(false);

  const editForm = useForm<EditFormData>({
    resolver: zodResolver(editSchema) as Resolver<EditFormData>,
    defaultValues: {
      subscription_tier: tenant.subscription_tier as "starter" | "professional" | "enterprise",
      max_students: tenant.max_students,
      max_staff: tenant.max_staff,
    },
  });

  const handleEdit = useCallback(
    async (values: EditFormData) => {
      const result = await updateTenant(tenant.id, values);
      if (result.success) {
        setTenant(result.data);
        toast.success("Tenant updated");
        setShowEditDialog(false);
      } else {
        toast.error(result.error);
      }
    },
    [tenant.id],
  );

  const handleSuspend = useCallback(async () => {
    if (!suspendReason.trim()) {
      toast.error("Please provide a reason");
      return;
    }
    setIsActioning(true);
    const result = await suspendTenant(tenant.id, suspendReason);
    setIsActioning(false);
    if (result.success) {
      setTenant((prev) => ({ ...prev, status: "suspended", is_active: false }));
      toast.success("Tenant suspended");
      setShowSuspendDialog(false);
      setSuspendReason("");
    } else {
      toast.error(result.error);
    }
  }, [tenant.id, suspendReason]);

  const handleActivate = useCallback(async () => {
    setIsActioning(true);
    const result = await activateTenant(tenant.id);
    setIsActioning(false);
    if (result.success) {
      setTenant((prev) => ({ ...prev, status: "active", is_active: true }));
      toast.success("Tenant activated");
      setShowActivateDialog(false);
    } else {
      toast.error(result.error);
    }
  }, [tenant.id]);

  const handleImpersonate = useCallback(async () => {
    setIsActioning(true);
    const result = await impersonateTenant(tenant.id);
    setIsActioning(false);
    if (result.success) {
      setShowImpersonateDialog(false);
      // Redirect to school dashboard
      const isDev =
        typeof window !== "undefined" &&
        (window.location.hostname === "localhost" ||
          window.location.hostname === "127.0.0.1");
      if (isDev) {
        window.location.href = `${window.location.protocol}//${window.location.host}/dashboard?subdomain=${result.data.tenant_subdomain}`;
      } else {
        window.location.href = `https://${result.data.tenant_subdomain}.simsplus.io/dashboard`;
      }
    } else {
      toast.error(result.error);
    }
  }, [tenant.id]);

  return (
    <div className="space-y-6">
      {/* Back + Header */}
      <div>
        <Link
          href="/platform/tenants"
          className="mb-4 inline-flex items-center gap-1 text-sm text-zinc-400 hover:text-white"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to tenants
        </Link>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-white">{tenant.name}</h1>
              {statusBadge(tenant.status)}
            </div>
            <p className="mt-1 text-sm text-zinc-400">
              {tenant.subdomain}.simsplus.io
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              size="sm"
              className="border-zinc-700 text-zinc-300"
              onClick={() => setShowEditDialog(true)}
            >
              <Pencil className="mr-2 h-4 w-4" />
              Edit Subscription
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="border-indigo-600 text-indigo-400 hover:bg-indigo-600/10"
              onClick={() => setShowImpersonateDialog(true)}
            >
              <ExternalLink className="mr-2 h-4 w-4" />
              Impersonate
            </Button>
            {tenant.status === "suspended" ? (
              <Button
                variant="outline"
                size="sm"
                className="border-green-600 text-green-400 hover:bg-green-600/10"
                onClick={() => setShowActivateDialog(true)}
              >
                <CheckCircle className="mr-2 h-4 w-4" />
                Activate
              </Button>
            ) : (
              <Button
                variant="outline"
                size="sm"
                className="border-red-600 text-red-400 hover:bg-red-600/10"
                onClick={() => setShowSuspendDialog(true)}
              >
                <Ban className="mr-2 h-4 w-4" />
                Suspend
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card className="border-zinc-800 bg-zinc-900">
          <CardContent className="flex items-center gap-4 p-6">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-600/10">
              <Users className="h-5 w-5 text-blue-400" />
            </div>
            <div>
              <p className="text-sm text-zinc-400">Students</p>
              <p className="text-2xl font-bold text-white">
                {tenant.student_count.toLocaleString()}
              </p>
              <p className="text-xs text-zinc-500">
                / {tenant.max_students === 999999 ? "Unlimited" : tenant.max_students.toLocaleString()}
              </p>
            </div>
          </CardContent>
        </Card>
        <Card className="border-zinc-800 bg-zinc-900">
          <CardContent className="flex items-center gap-4 p-6">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-600/10">
              <UserCog className="h-5 w-5 text-amber-400" />
            </div>
            <div>
              <p className="text-sm text-zinc-400">Staff</p>
              <p className="text-2xl font-bold text-white">
                {tenant.staff_count.toLocaleString()}
              </p>
              <p className="text-xs text-zinc-500">
                / {tenant.max_staff === 999999 ? "Unlimited" : tenant.max_staff.toLocaleString()}
              </p>
            </div>
          </CardContent>
        </Card>
        <Card className="border-zinc-800 bg-zinc-900">
          <CardContent className="flex items-center gap-4 p-6">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-600/10">
              <School className="h-5 w-5 text-green-400" />
            </div>
            <div>
              <p className="text-sm text-zinc-400">Schools</p>
              <p className="text-2xl font-bold text-white">
                {tenant.school_count.toLocaleString()}
              </p>
              <p className="text-xs text-zinc-500">
                {tenant.tenant_type === "school_chain" ? "Chain" : "Single"}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Subscription Details */}
      <Card className="border-zinc-800 bg-zinc-900">
        <CardHeader>
          <CardTitle className="text-white">Subscription Details</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3">
            <div>
              <dt className="text-sm text-zinc-400">Plan</dt>
              <dd className="mt-1 text-sm font-medium capitalize text-white">
                {tenant.subscription_tier}
              </dd>
            </div>
            <div>
              <dt className="text-sm text-zinc-400">Tenant Type</dt>
              <dd className="mt-1 text-sm font-medium capitalize text-white">
                {tenant.tenant_type.replace("_", " ")}
              </dd>
            </div>
            <div>
              <dt className="text-sm text-zinc-400">Created</dt>
              <dd className="mt-1 text-sm font-medium text-white">
                {formatDate(tenant.created_at)}
              </dd>
            </div>
            <div>
              <dt className="text-sm text-zinc-400">Subscription Start</dt>
              <dd className="mt-1 text-sm font-medium text-white">
                {formatDate(tenant.subscription_start)}
              </dd>
            </div>
            <div>
              <dt className="text-sm text-zinc-400">Subscription End</dt>
              <dd className="mt-1 text-sm font-medium text-white">
                {formatDate(tenant.subscription_end)}
              </dd>
            </div>
            <div>
              <dt className="text-sm text-zinc-400">Trial Ends</dt>
              <dd className="mt-1 text-sm font-medium text-white">
                {formatDate(tenant.trial_ends_at)}
              </dd>
            </div>
            {tenant.email && (
              <div>
                <dt className="text-sm text-zinc-400">Contact Email</dt>
                <dd className="mt-1 text-sm font-medium text-white">
                  {tenant.email}
                </dd>
              </div>
            )}
            {tenant.phone && (
              <div>
                <dt className="text-sm text-zinc-400">Contact Phone</dt>
                <dd className="mt-1 text-sm font-medium text-white">
                  {tenant.phone}
                </dd>
              </div>
            )}
          </dl>
        </CardContent>
      </Card>

      {/* Features */}
      {tenant.features && Object.keys(tenant.features).length > 0 && (
        <Card className="border-zinc-800 bg-zinc-900">
          <CardHeader>
            <CardTitle className="text-white">Features</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {Object.entries(tenant.features).map(([key, value]) => (
                <Badge
                  key={key}
                  variant={value ? "default" : "secondary"}
                  className={
                    value
                      ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
                      : "bg-zinc-800 text-zinc-500"
                  }
                >
                  {key.replace(/_/g, " ")}
                  {typeof value === "boolean" ? (value ? " (on)" : " (off)") : `: ${String(value)}`}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Edit Dialog */}
      <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
        <DialogContent className="border-zinc-800 bg-zinc-900 text-white">
          <DialogHeader>
            <DialogTitle>Edit Subscription</DialogTitle>
            <DialogDescription className="text-zinc-400">
              Update subscription tier and limits for {tenant.name}
            </DialogDescription>
          </DialogHeader>
          <Form {...editForm}>
            <form
              onSubmit={editForm.handleSubmit(handleEdit)}
              className="space-y-4"
            >
              <FormField
                control={editForm.control}
                name="subscription_tier"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-zinc-300">Plan</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      defaultValue={field.value}
                    >
                      <FormControl>
                        <SelectTrigger className="border-zinc-700 bg-zinc-800 text-white">
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="starter">Starter</SelectItem>
                        <SelectItem value="professional">
                          Professional
                        </SelectItem>
                        <SelectItem value="enterprise">Enterprise</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={editForm.control}
                name="max_students"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-zinc-300">
                      Max Students
                    </FormLabel>
                    <FormControl>
                      <Input
                        {...field}
                        type="number"
                        className="border-zinc-700 bg-zinc-800 text-white"
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={editForm.control}
                name="max_staff"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-zinc-300">Max Staff</FormLabel>
                    <FormControl>
                      <Input
                        {...field}
                        type="number"
                        className="border-zinc-700 bg-zinc-800 text-white"
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <DialogFooter>
                <Button
                  type="button"
                  variant="ghost"
                  className="text-zinc-400"
                  onClick={() => setShowEditDialog(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  className="bg-indigo-600 hover:bg-indigo-700"
                  disabled={editForm.formState.isSubmitting}
                >
                  {editForm.formState.isSubmitting ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    "Save Changes"
                  )}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* Suspend Dialog */}
      <AlertDialog open={showSuspendDialog} onOpenChange={setShowSuspendDialog}>
        <AlertDialogContent className="border-zinc-800 bg-zinc-900 text-white">
          <AlertDialogHeader>
            <AlertDialogTitle>Suspend {tenant.name}?</AlertDialogTitle>
            <AlertDialogDescription className="text-zinc-400">
              This will immediately block all users from accessing the school
              portal. The school&apos;s data will be preserved.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="py-2">
            <label className="text-sm font-medium text-zinc-300">
              Reason for suspension
            </label>
            <Input
              value={suspendReason}
              onChange={(e) => setSuspendReason(e.target.value)}
              placeholder="e.g., Non-payment, Policy violation"
              className="mt-1 border-zinc-700 bg-zinc-800 text-white placeholder:text-zinc-500"
            />
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel className="border-zinc-700 text-zinc-300">
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 hover:bg-red-700"
              onClick={handleSuspend}
              disabled={isActioning}
            >
              {isActioning ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              Suspend
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Activate Dialog */}
      <AlertDialog
        open={showActivateDialog}
        onOpenChange={setShowActivateDialog}
      >
        <AlertDialogContent className="border-zinc-800 bg-zinc-900 text-white">
          <AlertDialogHeader>
            <AlertDialogTitle>Activate {tenant.name}?</AlertDialogTitle>
            <AlertDialogDescription className="text-zinc-400">
              This will restore access for all users of this school.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="border-zinc-700 text-zinc-300">
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              className="bg-green-600 hover:bg-green-700"
              onClick={handleActivate}
              disabled={isActioning}
            >
              {isActioning ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              Activate
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Impersonate Dialog */}
      <AlertDialog
        open={showImpersonateDialog}
        onOpenChange={setShowImpersonateDialog}
      >
        <AlertDialogContent className="border-zinc-800 bg-zinc-900 text-white">
          <AlertDialogHeader>
            <AlertDialogTitle>
              Enter {tenant.name} dashboard as admin?
            </AlertDialogTitle>
            <AlertDialogDescription className="text-zinc-400">
              You will be redirected to {tenant.subdomain}.simsplus.io with
              platform admin privileges. A banner will indicate you are
              impersonating.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="border-zinc-700 text-zinc-300">
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              className="bg-indigo-600 hover:bg-indigo-700"
              onClick={handleImpersonate}
              disabled={isActioning}
            >
              {isActioning ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              Enter Dashboard
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
