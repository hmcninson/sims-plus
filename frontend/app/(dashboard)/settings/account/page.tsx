import { Suspense } from "react";
import { getCurrentUser } from "@/actions/auth.action";
import { AccountSettingsForm } from "./account-settings-form";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Account",
};

function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-4 w-64" />
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-4 w-56" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-20 w-full" />
        </CardContent>
      </Card>
    </div>
  );
}

async function AccountSettingsContent() {
  const user = await getCurrentUser();

  if (!user) {
    return (
      <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4">
        <p className="text-destructive">Failed to load account settings</p>
      </div>
    );
  }

  return (
    <AccountSettingsForm
      user={{
        email: user.email,
        mfa_enabled: user.mfa_enabled,
        created_at: user.created_at,
      }}
    />
  );
}

export default function AccountSettingsPage() {
  return (
    <Suspense fallback={<LoadingSkeleton />}>
      <AccountSettingsContent />
    </Suspense>
  );
}
