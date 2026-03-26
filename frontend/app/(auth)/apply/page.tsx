/**
 * SIMS Plus - Admissions Landing Page
 *
 * Displays open admission periods for prospective parents.
 * Path: {school}.simsplus.io/apply
 *
 * Server Component -- fetches data server-side for fast initial load.
 */

import { cookies } from "next/headers";
import Link from "next/link";
import Image from "next/image";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

import { getPublicPeriods } from "@/actions/admissions.action";

import {
  CalendarDays,
  GraduationCap,
  AlertCircle,
  Phone,
  Mail,
  BookOpen,
  ClipboardCheck,
  Coins,
  LogIn,
  User,
} from "lucide-react";

import { formatGHS, formatGhanaDate } from "@/lib/format";

export default async function ApplyPage() {
  const result = await getPublicPeriods();

  if (!result.success) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardContent className="pt-6 text-center">
            <AlertCircle className="mx-auto mb-4 h-12 w-12 text-muted-foreground" />
            <p className="text-lg font-medium">Unable to Load Admissions</p>
            <p className="mt-2 text-sm text-muted-foreground">
              We could not load admissions information at this time. Please try
              again later.
            </p>
            <Button
              variant="outline"
              className="mt-4"
              asChild
            >
              <Link href="/apply">Try Again</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const { items: periods, school } = result.data;

  const cookieStore = await cookies();
  const isAuthenticated = !!cookieStore.get("applicant_access_token")?.value;

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 md:py-12">
      {/* School Header */}
      <div className="mb-10 text-center">
        {school.logo_url ? (
          <div className="mb-4 flex justify-center">
            <Image
              src={school.logo_url}
              alt={`${school.school_name} logo`}
              width={80}
              height={80}
              className="rounded-full object-cover"
            />
          </div>
        ) : (
          <div className="mb-4 flex justify-center">
            <div
              className="flex h-20 w-20 items-center justify-center rounded-full"
              style={{
                backgroundColor: school.primary_color || "#1B4F72",
              }}
            >
              <GraduationCap className="h-10 w-10 text-white" />
            </div>
          </div>
        )}
        <h1
          className="text-2xl font-bold md:text-3xl"
          style={{ color: school.primary_color || undefined }}
        >
          {school.school_name}
        </h1>
        {school.motto && (
          <p className="mt-1 text-sm italic text-muted-foreground">
            {school.motto}
          </p>
        )}
        <p className="mt-3 text-lg font-medium text-foreground/80">
          Admissions Portal
        </p>
      </div>

      {/* Account links */}
      <div className="mb-6 flex flex-wrap items-center justify-center gap-4 text-sm">
        <span className="text-muted-foreground">
          Have an account?{" "}
          <Link
            href="/apply/login"
            className="font-medium text-primary underline underline-offset-4"
          >
            Sign in
          </Link>
        </span>
        <span className="text-muted-foreground">
          New here?{" "}
          <Link
            href="/apply/register"
            className="font-medium text-primary underline underline-offset-4"
          >
            Create an account
          </Link>
        </span>
      </div>

      {/* Open Periods */}
      {periods.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <GraduationCap className="mx-auto mb-4 h-12 w-12 text-muted-foreground" />
            <p className="text-lg font-medium">No Open Admissions</p>
            <p className="mt-2 text-sm text-muted-foreground">
              There are no admission periods currently open. Please check back
              later.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          <h2 className="text-xl font-semibold">Open Admissions</h2>
          {periods.map((period) => (
            <Card
              key={period.id}
              className="transition-colors hover:border-primary/50"
            >
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BookOpen className="h-5 w-5 text-primary" />
                  {period.name}
                </CardTitle>
                {period.description && (
                  <CardDescription>{period.description}</CardDescription>
                )}
              </CardHeader>
              <CardContent>
                {/* Period metadata */}
                <div className="mb-4 flex flex-wrap gap-3">
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <CalendarDays className="h-4 w-4" />
                    <span>
                      {formatGhanaDate(period.start_date)} &mdash;{" "}
                      {formatGhanaDate(period.end_date)}
                    </span>
                  </div>
                  {period.application_fee_required &&
                    period.application_fee_amount != null && (
                      <Badge variant="secondary" className="gap-1">
                        <Coins className="h-3 w-3" />
                        Application Fee: {formatGHS(period.application_fee_amount)}
                      </Badge>
                    )}
                  {period.entrance_exam_required && (
                    <Badge variant="outline" className="gap-1">
                      <ClipboardCheck className="h-3 w-3" />
                      Entrance Exam Required
                    </Badge>
                  )}
                  {period.require_applicant_account && (
                    <Badge variant="outline" className="gap-1">
                      <User className="h-3 w-3" />
                      Account Required
                    </Badge>
                  )}
                </div>

                {/* Target classes */}
                {period.target_classes.length > 0 && (
                  <div className="mb-4">
                    <p className="mb-2 text-xs font-medium uppercase text-muted-foreground">
                      Available Classes
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {period.target_classes.map((cls) => (
                        <Badge key={cls.id} variant="outline">
                          {cls.name}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}

                {period.require_applicant_account && !isAuthenticated ? (
                  <Button
                    className="w-full sm:w-auto"
                    style={{
                      backgroundColor: school.primary_color || undefined,
                    }}
                    asChild
                  >
                    <Link href={`/apply/login?redirect=/apply/${period.id}`}>
                      <LogIn className="mr-2 h-4 w-4" />
                      Login to Apply
                    </Link>
                  </Button>
                ) : (
                  <Button
                    className="w-full sm:w-auto"
                    style={{
                      backgroundColor: school.primary_color || undefined,
                    }}
                    asChild
                  >
                    <Link href={`/apply/${period.id}`}>Apply Now</Link>
                  </Button>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Status Check Link */}
      <div className="mt-10 text-center">
        <p className="text-sm text-muted-foreground">
          Already applied?{" "}
          <Link
            href="/apply/status"
            className="font-medium text-primary underline underline-offset-4"
          >
            Check your application status
          </Link>
        </p>
      </div>

      {/* School Contact */}
      {(school.phone || school.email) && (
        <div className="mt-4 flex flex-wrap items-center justify-center gap-4 text-sm text-muted-foreground">
          {school.phone && (
            <span className="flex items-center gap-1">
              <Phone className="h-3.5 w-3.5" />
              {school.phone}
            </span>
          )}
          {school.email && (
            <span className="flex items-center gap-1">
              <Mail className="h-3.5 w-3.5" />
              {school.email}
            </span>
          )}
          {school.address && (
            <span className="text-center">{school.address}</span>
          )}
        </div>
      )}
    </div>
  );
}
