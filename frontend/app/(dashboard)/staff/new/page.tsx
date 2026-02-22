import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { Button } from "@/components/ui/button";
import { NewStaffForm } from "./new-staff-form";

export const metadata = {
  title: "Add Staff",
};

export default function NewStaffPage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/staff">
            <ArrowLeft className="h-5 w-5" />
          </Link>
        </Button>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Add New Staff Member</h1>
          <p className="text-muted-foreground">
            Enter staff details to create a new record
          </p>
        </div>
      </div>

      {/* Form */}
      <NewStaffForm />
    </div>
  );
}
