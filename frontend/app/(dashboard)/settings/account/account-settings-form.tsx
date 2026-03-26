"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Eye, EyeOff, Key, Loader2, Shield, Smartphone, AlertTriangle, Phone, CheckCircle2, Monitor, Globe, Clock } from "lucide-react";
import { toast } from "sonner";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
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
import { changePassword } from "@/actions/user.action";
import { logout, getActiveSessions, terminateSession, terminateAllOtherSessions } from "@/actions/auth.action";
import { sendPhoneOTP, verifyPhone } from "@/actions/otp.action";
import { clearOfflineData } from "@/lib/offline/db";
import { MFASetupDialog } from "@/components/mfa/mfa-setup-dialog";
import { MFADisableDialog } from "@/components/mfa/mfa-disable-dialog";
import { BackupCodesDialog } from "@/components/mfa/backup-codes-dialog";

import type { UserSession } from "@/types";

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

interface AccountSettingsFormProps {
  user: {
    email: string;
    phone: string | null;
    phone_verified: boolean;
    mfa_enabled: boolean;
    created_at: string;
  };
}

export function AccountSettingsForm({ user }: AccountSettingsFormProps) {
  const router = useRouter();
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [passwordForm, setPasswordForm] = useState({
    currentPassword: "",
    newPassword: "",
    confirmPassword: "",
  });
  const [passwordErrors, setPasswordErrors] = useState<string[]>([]);

  // MFA dialog state
  const [mfaSetupOpen, setMfaSetupOpen] = useState(false);
  const [mfaDisableOpen, setMfaDisableOpen] = useState(false);
  const [backupCodesOpen, setBackupCodesOpen] = useState(false);
  const [mfaEnabled, setMfaEnabled] = useState(user.mfa_enabled);

  // Auto-open MFA setup when enforcement redirect is detected
  const searchParams = useSearchParams();
  const mfaRequired = searchParams.get("setup_mfa") === "required";

  useEffect(() => {
    if (mfaRequired && !mfaEnabled) {
      setMfaSetupOpen(true);
    }
  }, [mfaRequired, mfaEnabled]);

  // Phone verification state
  const [showOTPInput, setShowOTPInput] = useState(false);
  const [otpCode, setOtpCode] = useState("");
  const [otpCooldown, setOtpCooldown] = useState(0);
  const [isSendingOTP, setIsSendingOTP] = useState(false);
  const [isVerifyingPhone, setIsVerifyingPhone] = useState(false);

  // Session management state
  const [sessions, setSessions] = useState<UserSession[]>([]);
  const [isLoadingSessions, setIsLoadingSessions] = useState(true);
  const [terminatingSessionId, setTerminatingSessionId] = useState<string | null>(null);
  const [isTerminatingAll, setIsTerminatingAll] = useState(false);

  // Cooldown timer effect
  useEffect(() => {
    if (otpCooldown > 0) {
      const timer = setTimeout(() => setOtpCooldown(otpCooldown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [otpCooldown]);

  // Fetch active sessions on mount
  const fetchSessions = useCallback(async () => {
    setIsLoadingSessions(true);
    const result = await getActiveSessions();
    if (result.success && result.data) {
      setSessions(result.data.sessions);
    }
    setIsLoadingSessions(false);
  }, []);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const handleSendPhoneOTP = useCallback(async () => {
    setIsSendingOTP(true);
    const result = await sendPhoneOTP();
    setIsSendingOTP(false);

    if (result.success) {
      setShowOTPInput(true);
      setOtpCooldown(60);
      toast.success("Verification code sent to your phone");
    } else {
      toast.error(result.error || "Failed to send verification code");
    }
  }, []);

  const handleVerifyPhone = useCallback(async () => {
    if (otpCode.length !== 6) {
      toast.error("Please enter the 6-digit code");
      return;
    }

    setIsVerifyingPhone(true);
    const result = await verifyPhone(otpCode);
    setIsVerifyingPhone(false);

    if (result.success) {
      toast.success("Phone number verified successfully");
      setShowOTPInput(false);
      setOtpCode("");
      // Refresh the page to get updated user data
      router.refresh();
    } else {
      toast.error(result.error || "Verification failed");
    }
  }, [otpCode, router]);

  const validatePassword = (password: string): string[] => {
    const errors: string[] = [];
    if (password.length < 8) {
      errors.push("At least 8 characters");
    }
    if (!/[A-Z]/.test(password)) {
      errors.push("One uppercase letter");
    }
    if (!/[a-z]/.test(password)) {
      errors.push("One lowercase letter");
    }
    if (!/\d/.test(password)) {
      errors.push("One number");
    }
    if (!/[!@#$%^&*(),.?":{}|<>]/.test(password)) {
      errors.push("One special character");
    }
    return errors;
  };

  const handlePasswordChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setPasswordForm((prev) => ({ ...prev, [name]: value }));

    if (name === "newPassword") {
      setPasswordErrors(validatePassword(value));
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validate
    if (!passwordForm.currentPassword) {
      toast.error("Current password required");
      return;
    }

    const errors = validatePassword(passwordForm.newPassword);
    if (errors.length > 0) {
      toast.error("Password requirements not met", {
        description: errors.join(", "),
      });
      return;
    }

    if (passwordForm.newPassword !== passwordForm.confirmPassword) {
      toast.error("Passwords do not match");
      return;
    }

    setIsChangingPassword(true);

    try {
      const result = await changePassword({
        current_password: passwordForm.currentPassword,
        new_password: passwordForm.newPassword,
      });

      if (result.success) {
        toast.success("Password changed", {
          description: "Your password has been updated. Please log in again.",
        });
        // Clear form
        setPasswordForm({
          currentPassword: "",
          newPassword: "",
          confirmPassword: "",
        });
        // Logout user since tokens are invalidated
        setTimeout(async () => {
          try { await clearOfflineData(); } catch { /* ignore */ }
          await logout();
        }, 2000);
      } else {
        toast.error("Failed to change password", {
          description: result.error || "Please check your current password.",
        });
      }
    } catch {
      toast.error("Error", {
        description: "An unexpected error occurred.",
      });
    } finally {
      setIsChangingPassword(false);
    }
  };

  const handleLogoutAllSessions = async () => {
    toast.info("Logging out from all sessions...");
    try { await clearOfflineData(); } catch { /* ignore */ }
    await logout();
  };

  const handleTerminateSession = async (sessionId: string) => {
    setTerminatingSessionId(sessionId);
    const result = await terminateSession(sessionId);

    if (result.success) {
      toast.success("Session terminated");
      await fetchSessions();
    } else {
      toast.error(result.error || "Failed to terminate session");
    }
    setTerminatingSessionId(null);
  };

  const handleTerminateAllOtherSessions = async () => {
    setIsTerminatingAll(true);
    const result = await terminateAllOtherSessions();

    if (result.success) {
      const count = result.data?.terminated ?? 0;
      toast.success(`Terminated ${count} session(s)`);
      await fetchSessions();
    } else {
      toast.error(result.error || "Failed to terminate sessions");
    }
    setIsTerminatingAll(false);
  };

  const otherSessions = sessions.filter((s) => !s.is_current);

  const memberSince = new Date(user.created_at).toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  return (
    <div className="space-y-6">
      {/* Change Password */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Key className="h-5 w-5" />
            Change Password
          </CardTitle>
          <CardDescription>
            Update your password to keep your account secure.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleChangePassword} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="currentPassword">Current Password</Label>
              <div className="relative">
                <Input
                  id="currentPassword"
                  name="currentPassword"
                  type={showCurrentPassword ? "text" : "password"}
                  placeholder="Enter current password"
                  value={passwordForm.currentPassword}
                  onChange={handlePasswordChange}
                  className="pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowCurrentPassword(!showCurrentPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showCurrentPassword ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="newPassword">New Password</Label>
              <div className="relative">
                <Input
                  id="newPassword"
                  name="newPassword"
                  type={showNewPassword ? "text" : "password"}
                  placeholder="Enter new password"
                  value={passwordForm.newPassword}
                  onChange={handlePasswordChange}
                  className="pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowNewPassword(!showNewPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showNewPassword ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              </div>
              {passwordForm.newPassword && (
                <div className="mt-2 space-y-1">
                  <p className="text-xs text-muted-foreground">Password requirements:</p>
                  <div className="flex flex-wrap gap-1">
                    {[
                      { test: passwordForm.newPassword.length >= 8, label: "8+ chars" },
                      { test: /[A-Z]/.test(passwordForm.newPassword), label: "Uppercase" },
                      { test: /[a-z]/.test(passwordForm.newPassword), label: "Lowercase" },
                      { test: /\d/.test(passwordForm.newPassword), label: "Number" },
                      { test: /[!@#$%^&*(),.?":{}|<>]/.test(passwordForm.newPassword), label: "Special" },
                    ].map(({ test, label }) => (
                      <span
                        key={label}
                        className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs ${
                          test
                            ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
                            : "bg-muted text-muted-foreground"
                        }`}
                      >
                        {label}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="confirmPassword">Confirm New Password</Label>
              <div className="relative">
                <Input
                  id="confirmPassword"
                  name="confirmPassword"
                  type={showConfirmPassword ? "text" : "password"}
                  placeholder="Confirm new password"
                  value={passwordForm.confirmPassword}
                  onChange={handlePasswordChange}
                  className="pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showConfirmPassword ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              </div>
              {passwordForm.confirmPassword && passwordForm.newPassword !== passwordForm.confirmPassword && (
                <p className="text-xs text-destructive">Passwords do not match</p>
              )}
            </div>

            <div className="flex justify-end pt-2">
              <Button type="submit" disabled={isChangingPassword}>
                {isChangingPassword ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Updating...
                  </>
                ) : (
                  "Update Password"
                )}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Phone Verification */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Phone className="h-5 w-5" />
            Phone Verification
          </CardTitle>
          <CardDescription>
            Verify your phone number to receive SMS notifications and enable SMS-based password recovery.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {user.phone ? (
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <span className="text-sm font-medium">{user.phone}</span>
                {user.phone_verified ? (
                  <Badge variant="default" className="bg-green-600">
                    <CheckCircle2 className="mr-1 h-3 w-3" />
                    Verified
                  </Badge>
                ) : (
                  <Badge variant="secondary">Unverified</Badge>
                )}
              </div>

              {!user.phone_verified && (
                <>
                  {!showOTPInput ? (
                    <Button
                      onClick={handleSendPhoneOTP}
                      disabled={otpCooldown > 0 || isSendingOTP}
                      variant="outline"
                      size="sm"
                    >
                      {isSendingOTP ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Sending...
                        </>
                      ) : otpCooldown > 0 ? (
                        `Resend in ${otpCooldown}s`
                      ) : (
                        "Send Verification Code"
                      )}
                    </Button>
                  ) : (
                    <div className="space-y-3">
                      <p className="text-sm text-muted-foreground">
                        Enter the 6-digit code sent to {user.phone}
                      </p>
                      <div className="flex items-center gap-3">
                        <Input
                          type="text"
                          inputMode="numeric"
                          pattern="[0-9]*"
                          maxLength={6}
                          placeholder="000000"
                          value={otpCode}
                          onChange={(e) => {
                            const value = e.target.value.replace(/\D/g, "");
                            setOtpCode(value);
                          }}
                          className="w-32 text-center text-lg tracking-widest"
                          aria-label="Verification code"
                        />
                      </div>
                      <div className="flex gap-2">
                        <Button
                          onClick={handleVerifyPhone}
                          size="sm"
                          disabled={otpCode.length !== 6 || isVerifyingPhone}
                        >
                          {isVerifyingPhone ? (
                            <>
                              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                              Verifying...
                            </>
                          ) : (
                            "Verify"
                          )}
                        </Button>
                        <Button
                          onClick={handleSendPhoneOTP}
                          variant="ghost"
                          size="sm"
                          disabled={otpCooldown > 0 || isSendingOTP}
                        >
                          {otpCooldown > 0
                            ? `Resend in ${otpCooldown}s`
                            : "Resend Code"}
                        </Button>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              No phone number on your profile. Add one in your profile settings to enable phone verification.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Two-Factor Authentication */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Shield className="h-5 w-5" />
                Two-Factor Authentication
              </CardTitle>
              <CardDescription className="mt-1">
                Add an extra layer of security to your account using an
                authenticator app.
              </CardDescription>
            </div>
            {mfaEnabled && (
              <Badge variant="default" className="bg-green-600 shrink-0">
                Enabled
              </Badge>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {mfaEnabled ? (
            <div className="space-y-3">
              <div className="flex items-center gap-4 rounded-lg border p-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-muted">
                  <Smartphone className="h-5 w-5" />
                </div>
                <div className="flex-1">
                  <p className="font-medium">Authenticator App</p>
                  <p className="text-sm text-muted-foreground">
                    Your account is secured with two-factor authentication.
                  </p>
                </div>
              </div>
              <div className="flex flex-col gap-2 sm:flex-row">
                <Button
                  variant="outline"
                  onClick={() => setBackupCodesOpen(true)}
                >
                  Regenerate Backup Codes
                </Button>
                <Button
                  variant="destructive"
                  onClick={() => setMfaDisableOpen(true)}
                >
                  Disable 2FA
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-between rounded-lg border p-4">
              <div className="flex items-center gap-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-muted">
                  <Smartphone className="h-5 w-5" />
                </div>
                <div>
                  <p className="font-medium">Authenticator App</p>
                  <p className="text-sm text-muted-foreground">
                    Use an app like Google Authenticator or Authy.
                  </p>
                </div>
              </div>
              <Button onClick={() => setMfaSetupOpen(true)}>
                Enable 2FA
              </Button>
            </div>
          )}

          {mfaRequired && !mfaEnabled && (
            <p className="mt-3 text-sm font-medium text-amber-700 dark:text-amber-400">
              Your administrator requires two-factor authentication for your
              role. Please enable 2FA to continue.
            </p>
          )}
        </CardContent>
      </Card>

      {/* MFA Dialogs */}
      <MFASetupDialog
        open={mfaSetupOpen}
        onOpenChange={setMfaSetupOpen}
        onSuccess={() => {
          setMfaEnabled(true);
          router.refresh();
        }}
        required={mfaRequired}
      />
      <MFADisableDialog
        open={mfaDisableOpen}
        onOpenChange={setMfaDisableOpen}
        onSuccess={() => {
          setMfaEnabled(false);
          router.refresh();
        }}
      />
      <BackupCodesDialog
        open={backupCodesOpen}
        onOpenChange={setBackupCodesOpen}
      />

      {/* Active Sessions */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Monitor className="h-5 w-5" />
                Active Sessions
              </CardTitle>
              <CardDescription>
                Manage devices where you&apos;re currently logged in.
              </CardDescription>
            </div>
            {otherSessions.length > 0 && (
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={isTerminatingAll}
                  >
                    {isTerminatingAll ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Terminating...
                      </>
                    ) : (
                      "Terminate All Others"
                    )}
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Terminate all other sessions?</AlertDialogTitle>
                    <AlertDialogDescription>
                      This will sign you out of all other devices. Only your
                      current session will remain active.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction onClick={handleTerminateAllOtherSessions}>
                      Terminate All
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {isLoadingSessions ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : sessions.length === 0 ? (
            <p className="py-4 text-center text-sm text-muted-foreground">
              No active sessions found.
            </p>
          ) : (
            sessions.map((session) => (
              <div
                key={session.id}
                className="flex items-center justify-between rounded-lg border p-4"
              >
                <div className="flex items-start gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-muted">
                    <Monitor className="h-5 w-5" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="font-medium text-sm">
                        {session.device_info || "Unknown device"}
                      </p>
                      {session.is_current && (
                        <Badge variant="outline" className="text-green-600 border-green-600 shrink-0">
                          Current
                        </Badge>
                      )}
                    </div>
                    <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                      {session.ip_address && (
                        <span className="flex items-center gap-1">
                          <Globe className="h-3 w-3" />
                          {session.ip_address}
                        </span>
                      )}
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {formatRelativeTime(session.last_activity_at)}
                      </span>
                    </div>
                  </div>
                </div>
                {!session.is_current && (
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="shrink-0 text-destructive hover:text-destructive"
                        disabled={terminatingSessionId === session.id}
                      >
                        {terminatingSessionId === session.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          "Terminate"
                        )}
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>Terminate this session?</AlertDialogTitle>
                        <AlertDialogDescription>
                          This will sign out the device running{" "}
                          <strong>{session.device_info || "this session"}</strong>.
                          They will need to log in again.
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction
                          onClick={() => handleTerminateSession(session.id)}
                        >
                          Terminate
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                )}
              </div>
            ))
          )}
        </CardContent>
      </Card>

      {/* Account Info */}
      <Card>
        <CardHeader>
          <CardTitle>Account Information</CardTitle>
          <CardDescription>
            Your account details and membership information.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-lg border p-4">
              <p className="text-sm text-muted-foreground">Email Address</p>
              <p className="font-medium">{user.email}</p>
            </div>
            <div className="rounded-lg border p-4">
              <p className="text-sm text-muted-foreground">Member Since</p>
              <p className="font-medium">{memberSince}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Danger Zone */}
      <Card className="border-destructive/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-5 w-5" />
            Danger Zone
          </CardTitle>
          <CardDescription>
            Irreversible actions that affect your account.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between rounded-lg border border-destructive/30 p-4">
            <div>
              <p className="font-medium">Delete Account</p>
              <p className="text-sm text-muted-foreground">
                Permanently delete your account and all associated data.
              </p>
            </div>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="destructive" size="sm">
                  Delete Account
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Are you absolutely sure?</AlertDialogTitle>
                  <AlertDialogDescription>
                    This action cannot be undone. This will permanently delete your
                    account and remove all your data from our servers. Please contact
                    your administrator if you need to delete your account.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction
                    className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                    onClick={() => {
                      toast.info("Account deletion", {
                        description: "Please contact your administrator to delete your account.",
                      });
                    }}
                  >
                    I understand
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
