import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { Button } from "@/components/ui/button";

import { getClasses } from "@/actions/academic.action";
import { NewStudentForm } from "./new-student-form";

export default async function NewStudentPage() {
  // Fetch classes server-side
  const classesResult = await getClasses(true);
  const classes = classesResult.success && classesResult.data ? classesResult.data : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/students">
            <ArrowLeft className="h-5 w-5" />
          </Link>
        </Button>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Add New Student</h1>
          <p className="text-muted-foreground">
            Enter student details to create a new record
          </p>
        </div>
      </div>

      {/* Form */}
      <NewStudentForm classes={classes} />
    </div>
  );
}
