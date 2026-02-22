import { Loader2 } from "lucide-react";

export default function PaymentCallbackLoading() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
      <Loader2 className="h-10 w-10 animate-spin text-primary" />
      <h2 className="text-lg font-semibold">Verifying your payment...</h2>
      <p className="text-sm text-muted-foreground text-center max-w-md">
        Please wait while we confirm your payment with the provider.
      </p>
    </div>
  );
}
