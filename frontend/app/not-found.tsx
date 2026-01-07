import Link from "next/link";
import { FileQuestion, Home, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4">
      <div className="w-full max-w-md space-y-8 text-center">
        {/* 404 Icon */}
        <div className="mx-auto flex h-24 w-24 items-center justify-center rounded-full bg-muted">
          <FileQuestion className="h-12 w-12 text-muted-foreground" />
        </div>

        {/* Error Code */}
        <div className="space-y-2">
          <h1 className="text-6xl font-bold tracking-tighter text-primary">404</h1>
          <h2 className="text-xl font-semibold text-foreground">Page Not Found</h2>
          <p className="text-muted-foreground">
            Sorry, we couldn&apos;t find the page you&apos;re looking for. It might have
            been moved, deleted, or never existed.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-col gap-3 sm:flex-row sm:justify-center">
          <Button asChild>
            <Link href="/dashboard">
              <Home className="mr-2 h-4 w-4" />
              Go to Dashboard
            </Link>
          </Button>
          <Button variant="outline" asChild>
            <Link href="javascript:history.back()">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Go Back
            </Link>
          </Button>
        </div>

        {/* Help Text */}
        <div className="space-y-2 text-sm text-muted-foreground">
          <p>Here are some helpful links:</p>
          <div className="flex flex-wrap justify-center gap-4">
            <Link href="/dashboard" className="text-primary hover:underline">
              Dashboard
            </Link>
            <Link href="/students" className="text-primary hover:underline">
              Students
            </Link>
            <Link href="/settings" className="text-primary hover:underline">
              Settings
            </Link>
            <Link href="/help" className="text-primary hover:underline">
              Help Center
            </Link>
          </div>
        </div>
      </div>

      {/* SIMS Plus Branding */}
      <div className="absolute bottom-8">
        <p className="text-sm text-muted-foreground">
          SIMS Plus - School Information Management System
        </p>
      </div>
    </div>
  );
}
