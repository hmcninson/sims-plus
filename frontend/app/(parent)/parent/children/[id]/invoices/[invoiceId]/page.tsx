import { Suspense } from "react";
import { getChildInvoiceDetail } from "@/actions/parent.action";
import { InvoiceDetailView } from "./invoice-detail";
import InvoiceDetailLoading from "./loading";

export const metadata = {
  title: "Invoice Details",
};

interface InvoiceDetailPageProps {
  params: Promise<{ id: string; invoiceId: string }>;
}

export default async function InvoiceDetailPage({
  params,
}: InvoiceDetailPageProps) {
  const { id: studentId, invoiceId } = await params;

  const result = await getChildInvoiceDetail(studentId, invoiceId);
  const invoice = result.success ? result.data : null;

  return (
    <Suspense fallback={<InvoiceDetailLoading />}>
      <InvoiceDetailView
        studentId={studentId}
        invoice={invoice}
      />
    </Suspense>
  );
}
