"use client";

import { useState, useCallback, useEffect } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  platformLogin,
  platformMfaVerify,
  platformMfaGenerate,
  platformMfaSetup,
} from "@/actions/platform.action";
import type {
  PlatformMFASetupRequiredResponse,
  MFAGenerateResponse,
} from "@/types/platform.type";
import {
  Loader2,
  AlertCircle,
  Shield,
  ShieldCheck,
  Clock,
  ArrowLeft,
  Copy,
  Check,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Schemas
// ---------------------------------------------------------------------------

const loginSchema = z.object({
  email: z.string().email("Please enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});

type LoginFormData = z.infer<typeof loginSchema>;

// ---------------------------------------------------------------------------
// Login Steps
// ---------------------------------------------------------------------------

type LoginStep =
  | "credentials"
  | "mfa_verify"
  | "mfa_setup_generate"
  | "mfa_setup_confirm";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function PlatformLoginPage() {
  const router = useRouter();

  const [step, setStep] = useState<LoginStep>("credentials");
  const [error, setError] = useState<string | null>(null);

  // MFA verify state
  const [mfaPendingToken, setMfaPendingToken] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [isMfaSubmitting, setIsMfaSubmitting] = useState(false);

  // MFA setup state
  const [setupToken, setSetupToken] = useState("");
  const [mfaSetupData, setMfaSetupData] = useState<MFAGenerateResponse | null>(
    null,
  );
  const [setupCode, setSetupCode] = useState("");
  const [isSetupSubmitting, setIsSetupSubmitting] = useState(false);
  const [secretCopied, setSecretCopied] = useState(false);

  const form = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  const { isSubmitting } = form.formState;

  // Clear error when user types
  useEffect(() => {
    const subscription = form.watch(() => {
      if (error) setError(null);
    });
    return () => subscription.unsubscribe();
  }, [form, error]);

  // ---- Credential submission ----
  async function onSubmit(values: LoginFormData) {
    setError(null);
    const result = await platformLogin(values.email, values.password);

    if (!result.success) {
      if (result.code === 429) {
        setError("Too many login attempts. Please try again later.");
      } else {
        setError(result.error || "Invalid credentials");
      }
      return;
    }

    const data = result.data;

    // MFA required
    if ("mfa_required" in data && data.mfa_required) {
      setMfaPendingToken(data.mfa_pending_token);
      setStep("mfa_verify");
      return;
    }

    // MFA setup required
    if ("mfa_setup_required" in data && data.mfa_setup_required) {
      const setupData = data as PlatformMFASetupRequiredResponse;
      setSetupToken(setupData.setup_token);
      // Generate QR code
      const genResult = await platformMfaGenerate(setupData.setup_token);
      if (genResult.success) {
        setMfaSetupData(genResult.data);
        setStep("mfa_setup_generate");
      } else {
        setError(genResult.error || "Failed to generate MFA setup");
      }
      return;
    }

    // Success -- redirect to platform dashboard
    router.push("/platform/tenants");
  }

  // ---- MFA verify ----
  const handleMfaVerify = useCallback(async () => {
    if (!mfaCode || mfaCode.length !== 6) {
      setError("Please enter the full 6-digit code");
      return;
    }

    setIsMfaSubmitting(true);
    setError(null);

    const result = await platformMfaVerify(mfaPendingToken, mfaCode);
    setIsMfaSubmitting(false);

    if (result.success) {
      router.push("/platform/tenants");
      return;
    }

    if (result.code === 429) {
      setError("Too many failed attempts. Please log in again.");
    } else {
      setError(result.error || "Invalid code. Please try again.");
    }
  }, [mfaCode, mfaPendingToken, router]);

  // ---- MFA setup confirm ----
  const handleMfaSetupConfirm = useCallback(async () => {
    if (!setupCode || setupCode.length !== 6) {
      setError("Please enter the full 6-digit code");
      return;
    }

    if (!mfaSetupData) return;

    setIsSetupSubmitting(true);
    setError(null);

    const result = await platformMfaSetup(
      setupToken,
      setupCode,
      mfaSetupData.secret,
    );
    setIsSetupSubmitting(false);

    if (result.success) {
      router.push("/platform/tenants");
      return;
    }

    setError(result.error || "Invalid code. Please try again.");
  }, [setupCode, setupToken, mfaSetupData, router]);

  const handleCopySecret = useCallback(() => {
    if (mfaSetupData?.secret) {
      navigator.clipboard.writeText(mfaSetupData.secret);
      setSecretCopied(true);
      setTimeout(() => setSecretCopied(false), 2000);
    }
  }, [mfaSetupData]);

  const handleBackToLogin = useCallback(() => {
    setStep("credentials");
    setError(null);
    setMfaPendingToken("");
    setMfaCode("");
    setSetupToken("");
    setMfaSetupData(null);
    setSetupCode("");
  }, []);

  // ---- Render ----
  return (
    <main className="flex min-h-screen items-center justify-center bg-zinc-950 p-4">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="mb-8 text-center">
          <div className="mb-4 flex justify-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-xl bg-indigo-600">
              <ShieldCheck className="h-8 w-8 text-white" />
            </div>
          </div>
          <h1 className="text-2xl font-bold text-white">SIMS Plus</h1>
          <p className="mt-1 text-sm text-zinc-400">
            Platform Administration
          </p>
        </div>

        {/* Error alert */}
        {error && (
          <Alert variant="destructive" className="mb-4">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* ========== CREDENTIALS STEP ========== */}
        {step === "credentials" && (
          <Card className="border-zinc-800 bg-zinc-900">
            <CardHeader>
              <CardTitle className="text-white">Sign In</CardTitle>
              <CardDescription className="text-zinc-400">
                Enter your platform admin credentials
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Form {...form}>
                <form
                  onSubmit={form.handleSubmit(onSubmit)}
                  noValidate
                  className="space-y-4"
                >
                  <FormField
                    control={form.control}
                    name="email"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-zinc-300">
                          Email Address
                        </FormLabel>
                        <FormControl>
                          <Input
                            {...field}
                            type="email"
                            placeholder="admin@simsplus.io"
                            autoComplete="email"
                            disabled={isSubmitting}
                            className="border-zinc-700 bg-zinc-800 text-white placeholder:text-zinc-500"
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="password"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-zinc-300">
                          Password
                        </FormLabel>
                        <FormControl>
                          <Input
                            {...field}
                            type="password"
                            placeholder="Enter your password"
                            autoComplete="current-password"
                            disabled={isSubmitting}
                            className="border-zinc-700 bg-zinc-800 text-white placeholder:text-zinc-500"
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <Button
                    type="submit"
                    className="w-full bg-indigo-600 hover:bg-indigo-700"
                    disabled={isSubmitting}
                  >
                    {isSubmitting ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Signing in...
                      </>
                    ) : (
                      "Sign In"
                    )}
                  </Button>
                </form>
              </Form>
            </CardContent>
          </Card>
        )}

        {/* ========== MFA VERIFY STEP ========== */}
        {step === "mfa_verify" && (
          <Card className="border-zinc-800 bg-zinc-900">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-white">
                <Shield className="h-5 w-5" />
                Two-Factor Authentication
              </CardTitle>
              <CardDescription className="text-zinc-400">
                Enter the 6-digit code from your authenticator app
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <label
                  htmlFor="mfa-code"
                  className="text-sm font-medium text-zinc-300"
                >
                  Verification Code
                </label>
                <Input
                  id="mfa-code"
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  maxLength={6}
                  placeholder="000000"
                  value={mfaCode}
                  onChange={(e) => {
                    const value = e.target.value.replace(/\D/g, "");
                    setMfaCode(value);
                    if (error) setError(null);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && mfaCode.length === 6) {
                      handleMfaVerify();
                    }
                  }}
                  className="border-zinc-700 bg-zinc-800 text-center text-lg tracking-widest text-white"
                  autoFocus
                  autoComplete="one-time-code"
                  aria-label="6-digit verification code"
                />
              </div>

              <Button
                onClick={handleMfaVerify}
                className="w-full bg-indigo-600 hover:bg-indigo-700"
                disabled={isMfaSubmitting}
              >
                {isMfaSubmitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Verifying...
                  </>
                ) : (
                  "Verify"
                )}
              </Button>

              <p className="text-center text-xs text-zinc-500">
                <Clock className="mr-1 inline h-3 w-3" />
                Token expires in 5 minutes
              </p>

              <Button
                variant="ghost"
                className="w-full text-zinc-400 hover:text-white"
                onClick={handleBackToLogin}
              >
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to login
              </Button>
            </CardContent>
          </Card>
        )}

        {/* ========== MFA SETUP STEP ========== */}
        {step === "mfa_setup_generate" && mfaSetupData && (
          <Card className="border-zinc-800 bg-zinc-900">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-white">
                <Shield className="h-5 w-5" />
                Set Up Two-Factor Authentication
              </CardTitle>
              <CardDescription className="text-zinc-400">
                MFA is required for platform administrators. Scan the QR code
                with your authenticator app.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* QR Code */}
              <div className="flex justify-center rounded-lg bg-white p-4">
                <Image
                  src={`data:image/png;base64,${mfaSetupData.qr_code_base64}`}
                  alt="MFA QR Code"
                  width={200}
                  height={200}
                />
              </div>

              {/* Manual entry secret */}
              <div className="space-y-1">
                <p className="text-xs text-zinc-400">
                  Or enter this secret manually:
                </p>
                <div className="flex items-center gap-2">
                  <code className="flex-1 rounded bg-zinc-800 px-3 py-2 font-mono text-xs text-zinc-300">
                    {mfaSetupData.secret}
                  </code>
                  <Button
                    variant="outline"
                    size="icon"
                    className="shrink-0 border-zinc-700"
                    onClick={handleCopySecret}
                  >
                    {secretCopied ? (
                      <Check className="h-4 w-4 text-green-500" />
                    ) : (
                      <Copy className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </div>

              {/* Verification code */}
              <div className="space-y-2">
                <label
                  htmlFor="setup-code"
                  className="text-sm font-medium text-zinc-300"
                >
                  Enter code from your app to verify
                </label>
                <Input
                  id="setup-code"
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  maxLength={6}
                  placeholder="000000"
                  value={setupCode}
                  onChange={(e) => {
                    const value = e.target.value.replace(/\D/g, "");
                    setSetupCode(value);
                    if (error) setError(null);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && setupCode.length === 6) {
                      handleMfaSetupConfirm();
                    }
                  }}
                  className="border-zinc-700 bg-zinc-800 text-center text-lg tracking-widest text-white"
                  autoComplete="one-time-code"
                  aria-label="6-digit setup verification code"
                />
              </div>

              <Button
                onClick={handleMfaSetupConfirm}
                className="w-full bg-indigo-600 hover:bg-indigo-700"
                disabled={isSetupSubmitting}
              >
                {isSetupSubmitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Verifying...
                  </>
                ) : (
                  "Verify & Complete Setup"
                )}
              </Button>

              <Button
                variant="ghost"
                className="w-full text-zinc-400 hover:text-white"
                onClick={handleBackToLogin}
              >
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to login
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Footer */}
        <p className="mt-6 text-center text-xs text-zinc-600">
          SIMS Plus Platform Administration
        </p>
      </div>
    </main>
  );
}
