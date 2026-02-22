import { Suspense } from "react";
import { PaymentCallbackView } from "./payment-callback";
import PaymentCallbackLoading from "./loading";

export const metadata = {
  title: "Payment Status",
};

interface PaymentCallbackPageProps {
  searchParams: Promise<{ reference?: string }>;
}

export default async function PaymentCallbackPage({
  searchParams,
}: PaymentCallbackPageProps) {
  const { reference } = await searchParams;

  return (
    <Suspense fallback={<PaymentCallbackLoading />}>
      <PaymentCallbackView reference={reference || null} />
    </Suspense>
  );
}
