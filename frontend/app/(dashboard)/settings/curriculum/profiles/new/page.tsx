import Link from "next/link";
import { ChevronLeft } from "lucide-react";

import { Button } from "@/components/ui/button";
import { CurriculumProfileWizard } from "@/components/curriculum/CurriculumProfileWizard";

export const metadata = {
  title: "New Curriculum Profile",
};

export default function NewCurriculumProfilePage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/settings/curriculum/profiles">
            <ChevronLeft className="h-4 w-4" />
            <span className="sr-only">Back to profiles</span>
          </Link>
        </Button>
        <div>
          <h2 className="text-xl font-semibold">Create Curriculum Profile</h2>
          <p className="text-sm text-muted-foreground">
            Set up a new curriculum profile for your school.
          </p>
        </div>
      </div>

      <CurriculumProfileWizard />
    </div>
  );
}
