"use client";

import { useState, useCallback } from "react";
import { Loader2, Copy, Download, Check, KeyRound } from "lucide-react";
import { toast } from "sonner";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { regenerateBackupCodes } from "@/actions/mfa.action";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface BackupCodesDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

type Phase = "confirm" | "codes";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function BackupCodesDialog({
  open,
  onOpenChange,
}: BackupCodesDialogProps) {
  const [phase, setPhase] = useState<Phase>("confirm");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [backupCodes, setBackupCodes] = useState<string[]>([]);
  const [codesCopied, setCodesCopied] = useState(false);

  const handleRegenerate = useCallback(async () => {
    if (!password) {
      setError("Password is required");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    const result = await regenerateBackupCodes(password);

    setIsSubmitting(false);

    if (result.success) {
      setBackupCodes(result.data.backup_codes);
      setPhase("codes");
      toast.success("New backup codes generated");
    } else {
      setError(result.error);
    }
  }, [password]);

  const handleCopyCodes = useCallback(async () => {
    const text = backupCodes.join("\n");
    await navigator.clipboard.writeText(text);
    setCodesCopied(true);
    toast.success("Backup codes copied to clipboard");
    setTimeout(() => setCodesCopied(false), 2000);
  }, [backupCodes]);

  const handleDownloadCodes = useCallback(() => {
    const text = [
      "SIMS Plus - MFA Backup Codes",
      "=============================",
      "",
      "Keep these codes safe. Each code can only be used once.",
      "Your previous backup codes have been invalidated.",
      "",
      ...backupCodes.map((code, i) => `${i + 1}. ${code}`),
      "",
      `Generated: ${new Date().toLocaleDateString("en-GB")}`,
    ].join("\n");

    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "sims-plus-backup-codes.txt";
    a.click();
    URL.revokeObjectURL(url);
    toast.success("Backup codes downloaded");
  }, [backupCodes]);

  const handleOpenChange = useCallback(
    (nextOpen: boolean) => {
      if (!nextOpen) {
        setPhase("confirm");
        setPassword("");
        setError(null);
        setBackupCodes([]);
        setCodesCopied(false);
      }
      onOpenChange(nextOpen);
    },
    [onOpenChange]
  );

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        {/* Phase 1: Password confirmation */}
        {phase === "confirm" && (
          <>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <KeyRound className="h-5 w-5" />
                Regenerate Backup Codes
              </DialogTitle>
              <DialogDescription>
                This will generate new backup codes and invalidate all existing
                ones. Enter your password to confirm.
              </DialogDescription>
            </DialogHeader>

            <Alert className="border-amber-500/50 bg-amber-50 text-amber-900 dark:border-amber-500/30 dark:bg-amber-950/50 dark:text-amber-200">
              <AlertDescription>
                Your existing backup codes will stop working immediately after
                new codes are generated.
              </AlertDescription>
            </Alert>

            <div className="space-y-2">
              <Label htmlFor="regen-password">Password</Label>
              <Input
                id="regen-password"
                type="password"
                placeholder="Enter your password"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  if (error) setError(null);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && password) {
                    handleRegenerate();
                  }
                }}
                autoFocus
                autoComplete="current-password"
              />
              {error && <p className="text-sm text-destructive">{error}</p>}
            </div>

            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => handleOpenChange(false)}
                disabled={isSubmitting}
              >
                Cancel
              </Button>
              <Button
                onClick={handleRegenerate}
                disabled={!password || isSubmitting}
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Generating...
                  </>
                ) : (
                  "Generate New Codes"
                )}
              </Button>
            </div>
          </>
        )}

        {/* Phase 2: Display new codes */}
        {phase === "codes" && (
          <>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <KeyRound className="h-5 w-5 text-green-600" />
                New Backup Codes
              </DialogTitle>
              <DialogDescription>
                Save these codes in a safe place. Each code can only be used
                once if you lose access to your authenticator app.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4">
              {/* Backup codes grid */}
              <div className="grid grid-cols-2 gap-2 rounded-lg border p-4">
                {backupCodes.map((code) => (
                  <code
                    key={code}
                    className="rounded bg-muted px-2 py-1 text-center text-sm font-mono"
                  >
                    {code}
                  </code>
                ))}
              </div>

              {/* Action buttons */}
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={handleDownloadCodes}
                  className="flex-1"
                >
                  <Download className="mr-2 h-4 w-4" />
                  Download
                </Button>
                <Button
                  variant="outline"
                  onClick={handleCopyCodes}
                  className="flex-1"
                >
                  {codesCopied ? (
                    <>
                      <Check className="mr-2 h-4 w-4 text-green-600" />
                      Copied
                    </>
                  ) : (
                    <>
                      <Copy className="mr-2 h-4 w-4" />
                      Copy
                    </>
                  )}
                </Button>
              </div>

              <Button
                onClick={() => handleOpenChange(false)}
                className="w-full"
              >
                Done
              </Button>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
