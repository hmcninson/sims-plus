"use client";

import { useState, useCallback, useRef } from "react";
import Image from "next/image";
import {
  Loader2,
  Copy,
  Download,
  Check,
  ShieldCheck,
  QrCode,
  KeyRound,
} from "lucide-react";
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
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { setupMFA, verifyMFASetup } from "@/actions/mfa.action";
import type { MFASetupData } from "@/actions/mfa.action";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface MFASetupDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Called after MFA is successfully enabled */
  onSuccess: () => void;
  /** When true, the dialog cannot be dismissed (MFA enforcement) */
  required?: boolean;
}

type Step = "qr" | "verify" | "backup";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function MFASetupDialog({
  open,
  onOpenChange,
  onSuccess,
  required = false,
}: MFASetupDialogProps) {
  const [step, setStep] = useState<Step>("qr");
  const [setupData, setSetupData] = useState<MFASetupData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [verifyCode, setVerifyCode] = useState("");
  const [verifyError, setVerifyError] = useState<string | null>(null);
  const [isVerifying, setIsVerifying] = useState(false);
  const [secretCopied, setSecretCopied] = useState(false);
  const [codesCopied, setCodesCopied] = useState(false);
  const [savedConfirmed, setSavedConfirmed] = useState(false);
  const codeInputRef = useRef<HTMLInputElement>(null);

  // Start setup when dialog opens
  const handleOpenChange = useCallback(
    (nextOpen: boolean) => {
      if (!nextOpen && required) return; // Cannot dismiss if required
      if (nextOpen && !setupData) {
        setIsLoading(true);
        setupMFA().then((result) => {
          setIsLoading(false);
          if (result.success) {
            setSetupData(result.data);
            setStep("qr");
          } else {
            toast.error(result.error);
            onOpenChange(false);
          }
        });
      }
      if (!nextOpen) {
        // Reset state on close
        setStep("qr");
        setSetupData(null);
        setVerifyCode("");
        setVerifyError(null);
        setSecretCopied(false);
        setCodesCopied(false);
        setSavedConfirmed(false);
      }
      onOpenChange(nextOpen);
    },
    [required, setupData, onOpenChange]
  );

  const handleCopySecret = useCallback(async () => {
    if (!setupData) return;
    await navigator.clipboard.writeText(setupData.secret);
    setSecretCopied(true);
    toast.success("Secret copied to clipboard");
    setTimeout(() => setSecretCopied(false), 2000);
  }, [setupData]);

  const handleVerify = useCallback(async () => {
    if (verifyCode.length !== 6) {
      setVerifyError("Please enter the 6-digit code");
      return;
    }

    setIsVerifying(true);
    setVerifyError(null);

    const result = await verifyMFASetup(verifyCode);

    setIsVerifying(false);

    if (result.success) {
      setStep("backup");
      toast.success("Two-factor authentication enabled");
    } else {
      setVerifyError(result.error);
    }
  }, [verifyCode]);

  const handleCopyCodes = useCallback(async () => {
    if (!setupData) return;
    const text = setupData.backup_codes.join("\n");
    await navigator.clipboard.writeText(text);
    setCodesCopied(true);
    toast.success("Backup codes copied to clipboard");
    setTimeout(() => setCodesCopied(false), 2000);
  }, [setupData]);

  const handleDownloadCodes = useCallback(() => {
    if (!setupData) return;
    const text = [
      "SIMS Plus - MFA Backup Codes",
      "=============================",
      "",
      "Keep these codes safe. Each code can only be used once.",
      "",
      ...setupData.backup_codes.map((code, i) => `${i + 1}. ${code}`),
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
  }, [setupData]);

  const handleDone = useCallback(() => {
    onOpenChange(false);
    onSuccess();
  }, [onOpenChange, onSuccess]);

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        className="sm:max-w-md"
        onInteractOutside={(e) => {
          if (required || step === "backup") e.preventDefault();
        }}
        onEscapeKeyDown={(e) => {
          if (required || step === "backup") e.preventDefault();
        }}
      >
        {/* Loading state */}
        {isLoading && (
          <>
            <DialogHeader>
              <DialogTitle>Setting up 2FA</DialogTitle>
              <DialogDescription>
                Generating your authentication key...
              </DialogDescription>
            </DialogHeader>
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          </>
        )}

        {/* Step 1: QR Code */}
        {!isLoading && setupData && step === "qr" && (
          <>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <QrCode className="h-5 w-5" />
                Scan QR Code
              </DialogTitle>
              <DialogDescription>
                Scan this QR code with your authenticator app (Google
                Authenticator, Authy, etc.)
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4">
              {/* QR Code Image */}
              <div className="flex justify-center rounded-lg border bg-white p-4">
                <Image
                  src={setupData.qr_code_base64}
                  alt="MFA QR Code"
                  width={200}
                  height={200}
                  unoptimized
                />
              </div>

              {/* Manual entry secret */}
              <div className="space-y-2">
                <p className="text-sm font-medium text-muted-foreground">
                  Or enter this code manually:
                </p>
                <div className="flex items-center gap-2">
                  <code className="flex-1 rounded-md bg-muted px-3 py-2 text-sm font-mono break-all select-all">
                    {setupData.secret}
                  </code>
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={handleCopySecret}
                    aria-label="Copy secret"
                  >
                    {secretCopied ? (
                      <Check className="h-4 w-4 text-green-600" />
                    ) : (
                      <Copy className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </div>

              <Button onClick={() => setStep("verify")} className="w-full">
                Next
              </Button>
            </div>
          </>
        )}

        {/* Step 2: Verify */}
        {!isLoading && setupData && step === "verify" && (
          <>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <KeyRound className="h-5 w-5" />
                Verify Code
              </DialogTitle>
              <DialogDescription>
                Enter the 6-digit code from your authenticator app to confirm
                setup.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="mfa-verify-code">Verification Code</Label>
                <Input
                  ref={codeInputRef}
                  id="mfa-verify-code"
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  maxLength={6}
                  placeholder="000000"
                  value={verifyCode}
                  onChange={(e) => {
                    const value = e.target.value.replace(/\D/g, "");
                    setVerifyCode(value);
                    if (verifyError) setVerifyError(null);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && verifyCode.length === 6) {
                      handleVerify();
                    }
                  }}
                  className="text-center text-lg tracking-widest"
                  autoFocus
                  aria-label="6-digit verification code"
                />
                {verifyError && (
                  <p className="text-sm text-destructive">{verifyError}</p>
                )}
              </div>

              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={() => setStep("qr")}
                  className="flex-1"
                >
                  Back
                </Button>
                <Button
                  onClick={handleVerify}
                  disabled={verifyCode.length !== 6 || isVerifying}
                  className="flex-1"
                >
                  {isVerifying ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Verifying...
                    </>
                  ) : (
                    "Verify"
                  )}
                </Button>
              </div>
            </div>
          </>
        )}

        {/* Step 3: Backup Codes */}
        {!isLoading && setupData && step === "backup" && (
          <>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <ShieldCheck className="h-5 w-5 text-green-600" />
                Save Backup Codes
              </DialogTitle>
              <DialogDescription>
                Save these backup codes in a safe place. Each code can only be
                used once if you lose access to your authenticator app.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4">
              {/* Backup codes grid */}
              <div className="grid grid-cols-2 gap-2 rounded-lg border p-4">
                {setupData.backup_codes.map((code) => (
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

              {/* Confirmation checkbox */}
              <div className="flex items-start space-x-2">
                <Checkbox
                  id="saved-codes"
                  checked={savedConfirmed}
                  onCheckedChange={(checked) =>
                    setSavedConfirmed(checked === true)
                  }
                />
                <Label
                  htmlFor="saved-codes"
                  className="text-sm leading-tight cursor-pointer"
                >
                  I have saved these backup codes in a safe place
                </Label>
              </div>

              <Button
                onClick={handleDone}
                disabled={!savedConfirmed}
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
