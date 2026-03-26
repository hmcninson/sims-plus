import { Metadata } from "next";
import { CreatePayrollRunForm } from "./create-payroll-run-form";

export const metadata: Metadata = {
  title: "Create Payroll Run",
  description: "Create a new payroll processing run",
};

export default function CreatePayrollRunPage() {
  return <CreatePayrollRunForm />;
}
