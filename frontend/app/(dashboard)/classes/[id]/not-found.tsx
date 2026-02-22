import Link from "next/link";
import { GraduationCap, ArrowLeft } from "lucide-react";

import { Button } from "@/components/ui/button";

export default function ClassNotFound() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center px-4">
      <div className="w-full max-w-md space-y-6 text-center">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-muted">
          <GraduationCap className="h-8 w-8 text-muted-foreground" />
        </div>

        <div className="space-y-2">
          <h2 className="text-xl font-semibold text-foreground">
            Class not found
          </h2>
          <p className="text-sm text-muted-foreground">
            The class you are looking for does not exist or may have been removed.
          </p>
        </div>

        <Button variant="outline" asChild>
          <Link href="/classes">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Classes
          </Link>
        </Button>
      </div>
    </div>
  );
}
