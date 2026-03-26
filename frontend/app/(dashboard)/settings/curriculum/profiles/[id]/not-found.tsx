import Link from "next/link";
import { BookOpen } from "lucide-react";

import { Button } from "@/components/ui/button";

export default function ProfileNotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
      <BookOpen className="h-10 w-10 text-muted-foreground" />
      <h2 className="text-lg font-semibold">Profile Not Found</h2>
      <p className="text-sm text-muted-foreground">
        The curriculum profile you are looking for does not exist or has been
        deleted.
      </p>
      <Button asChild variant="outline">
        <Link href="/settings/curriculum/profiles">Back to Profiles</Link>
      </Button>
    </div>
  );
}
