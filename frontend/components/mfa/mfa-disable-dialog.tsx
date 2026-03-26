"use client";

import { useState, useCallback } from "react";
import { Loader2, ShieldOff } from "lucide-react";
import { toast } from "sonner";

import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { disableMFA } from "@/actions/mfa.action";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface MFADisableDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Called after MFA is successfully disabled */
  onSuccess: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function MFADisableDialog({
  open,
  onOpenChange,
  onSuccess,
}: MFADisableDialogProps) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleDisable = useCallback(async () => {
    if (!password) {
      setError("Password is required");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    const result = await disableMFA(password);

    setIsSubmitting(false);

    if (result.success) {
      toast.success("Two-factor authentication disabled");
      setPassword("");
      setError(null);
      onOpenChange(false);
      onSuccess();
    } else {
      setError(result.error);
    }
  }, [password, onOpenChange, onSuccess]);

  const handleOpenChange = useCallback(
    (nextOpen: boolean) => {
      if (!nextOpen) {
        setPassword("");
        setError(null);
      }
      onOpenChange(nextOpen);
    },
    [onOpenChange]
  );

  return (
    <AlertDialog open={open} onOpenChange={handleOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center gap-2">
            <ShieldOff className="h-5 w-5 text-destructive" />
            Disable Two-Factor Authentication
          </AlertDialogTitle>
          <AlertDialogDescription>
            This will remove the extra security layer from your account. You
            will only need your password to sign in. Enter your password to
            confirm.
          </AlertDialogDescription>
        </AlertDialogHeader>

        <div className="space-y-2 py-2">
          <Label htmlFor="disable-mfa-password">Password</Label>
          <Input
            id="disable-mfa-password"
            type="password"
            placeholder="Enter your password"
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              if (error) setError(null);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && password) {
                handleDisable();
              }
            }}
            autoFocus
            autoComplete="current-password"
          />
          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>

        <AlertDialogFooter>
          <AlertDialogCancel disabled={isSubmitting}>Cancel</AlertDialogCancel>
          <Button
            variant="destructive"
            onClick={handleDisable}
            disabled={!password || isSubmitting}
          >
            {isSubmitting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Disabling...
              </>
            ) : (
              "Disable 2FA"
            )}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
