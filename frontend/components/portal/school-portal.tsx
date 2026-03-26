/**
 * SIMS Plus - School Portal Landing Page
 *
 * Branded landing page shown when users visit {school}.simsplus.io/.
 * Displays school identity, quick links to admissions and parent portal,
 * and contact information.
 *
 * Server Component -- no client-side interactivity needed.
 */

import Link from "next/link";
import Image from "next/image";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

import {
  GraduationCap,
  FileText,
  Users,
  ClipboardCheck,
  Phone,
  Mail,
  MapPin,
  LogIn,
  ArrowRight,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SchoolInfo {
  school_name: string;
  logo_url?: string;
  primary_color?: string;
  motto?: string;
  address?: string;
  phone?: string;
  email?: string;
}

interface SchoolPortalProps {
  schoolInfo: SchoolInfo | null;
  subdomain: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Compute an appropriate foreground color (white or dark) based on a hex
 * background color, using relative luminance (WCAG 2.x formula).
 */
function contrastForeground(hex: string): string {
  const cleaned = hex.replace("#", "");
  if (cleaned.length !== 6) return "#ffffff";

  const r = parseInt(cleaned.substring(0, 2), 16) / 255;
  const g = parseInt(cleaned.substring(2, 4), 16) / 255;
  const b = parseInt(cleaned.substring(4, 6), 16) / 255;

  const toLinear = (c: number) =>
    c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);

  const luminance =
    0.2126 * toLinear(r) + 0.7152 * toLinear(g) + 0.0722 * toLinear(b);

  return luminance > 0.4 ? "#1a1a1a" : "#ffffff";
}

/**
 * Generate a lighter tint of the primary colour for card hover / accent usage.
 */
function lightenHex(hex: string, amount: number): string {
  const cleaned = hex.replace("#", "");
  if (cleaned.length !== 6) return hex;

  const r = Math.min(255, parseInt(cleaned.substring(0, 2), 16) + amount);
  const g = Math.min(255, parseInt(cleaned.substring(2, 4), 16) + amount);
  const b = Math.min(255, parseInt(cleaned.substring(4, 6), 16) + amount);

  return `#${r.toString(16).padStart(2, "0")}${g.toString(16).padStart(2, "0")}${b.toString(16).padStart(2, "0")}`;
}

// ---------------------------------------------------------------------------
// Quick-link data
// ---------------------------------------------------------------------------

interface QuickLink {
  title: string;
  description: string;
  href: string;
  icon: typeof GraduationCap;
}

const QUICK_LINKS: QuickLink[] = [
  {
    title: "Apply for Admission",
    description: "Start your application today",
    href: "/apply",
    icon: GraduationCap,
  },
  {
    title: "Parent Portal",
    description: "View your child's progress",
    href: "/login",
    icon: Users,
  },
  {
    title: "Check Application Status",
    description: "Track your application",
    href: "/apply/status",
    icon: ClipboardCheck,
  },
  {
    title: "Contact Us",
    description: "Get in touch with the school",
    href: "#contact",
    icon: Phone,
  },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SchoolPortal({ schoolInfo, subdomain }: SchoolPortalProps) {
  const schoolName = schoolInfo?.school_name ?? subdomain;
  const primaryColor = schoolInfo?.primary_color ?? "#1B4F72";
  const foreground = contrastForeground(primaryColor);

  return (
    <div className="flex min-h-screen flex-col bg-background">
      {/* ---------------------------------------------------------------- */}
      {/* Header / Navbar                                                  */}
      {/* ---------------------------------------------------------------- */}
      <header className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          {/* Left: Logo + School name */}
          <div className="flex items-center gap-3">
            {schoolInfo?.logo_url ? (
              <Image
                src={schoolInfo.logo_url}
                alt={`${schoolName} logo`}
                width={40}
                height={40}
                className="rounded-full object-cover"
              />
            ) : (
              <div
                className="flex h-10 w-10 items-center justify-center rounded-full"
                style={{ backgroundColor: primaryColor }}
              >
                <GraduationCap
                  className="h-5 w-5"
                  style={{ color: foreground }}
                />
              </div>
            )}
            <div className="hidden sm:block">
              <p className="text-sm font-semibold leading-tight">
                {schoolName}
              </p>
              {schoolInfo?.motto && (
                <p className="text-xs italic text-muted-foreground leading-tight">
                  {schoolInfo.motto}
                </p>
              )}
            </div>
          </div>

          {/* Right: Staff login */}
          <Button variant="ghost" size="sm" asChild>
            <Link href="/login" className="gap-2 text-muted-foreground">
              <LogIn className="h-4 w-4" />
              <span className="hidden sm:inline">Staff Login</span>
              <span className="sm:hidden">Login</span>
            </Link>
          </Button>
        </div>
      </header>

      {/* ---------------------------------------------------------------- */}
      {/* Hero Section                                                     */}
      {/* ---------------------------------------------------------------- */}
      <section
        className="relative overflow-hidden"
        style={{ backgroundColor: primaryColor }}
      >
        {/* Subtle decorative pattern */}
        <div
          className="absolute inset-0 opacity-10"
          style={{
            backgroundImage:
              "radial-gradient(circle at 20% 50%, rgba(255,255,255,0.3) 0%, transparent 50%), radial-gradient(circle at 80% 20%, rgba(255,255,255,0.2) 0%, transparent 40%)",
          }}
        />

        <div className="relative mx-auto max-w-6xl px-4 py-16 sm:px-6 sm:py-20 md:py-28">
          <div className="flex flex-col items-center text-center">
            {/* Logo in hero */}
            {schoolInfo?.logo_url ? (
              <div className="mb-6">
                <Image
                  src={schoolInfo.logo_url}
                  alt={`${schoolName} logo`}
                  width={96}
                  height={96}
                  className="rounded-full border-4 border-white/20 object-cover"
                />
              </div>
            ) : (
              <div
                className="mb-6 flex h-24 w-24 items-center justify-center rounded-full border-4 border-white/20"
                style={{ backgroundColor: lightenHex(primaryColor, 30) }}
              >
                <GraduationCap
                  className="h-12 w-12"
                  style={{ color: foreground }}
                />
              </div>
            )}

            <h1
              className="text-3xl font-bold tracking-tight sm:text-4xl md:text-5xl"
              style={{ color: foreground }}
            >
              Welcome to {schoolName}
            </h1>

            {schoolInfo?.motto && (
              <p
                className="mt-3 text-base italic sm:text-lg"
                style={{ color: foreground, opacity: 0.85 }}
              >
                &ldquo;{schoolInfo.motto}&rdquo;
              </p>
            )}

            <p
              className="mt-4 max-w-2xl text-sm sm:text-base"
              style={{ color: foreground, opacity: 0.75 }}
            >
              Your gateway to academic excellence. Access admissions,
              check student progress, and stay connected with our school community.
            </p>

            <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:gap-4">
              <Button
                size="lg"
                className="gap-2 font-semibold"
                style={{
                  backgroundColor: foreground,
                  color: primaryColor,
                }}
                asChild
              >
                <Link href="/apply">
                  <GraduationCap className="h-5 w-5" />
                  Apply for Admission
                </Link>
              </Button>
              <Button
                size="lg"
                variant="outline"
                className="gap-2 border-2 font-semibold"
                style={{
                  borderColor: `${foreground}50`,
                  color: foreground,
                  backgroundColor: "transparent",
                }}
                asChild
              >
                <Link href="/login">
                  <Users className="h-5 w-5" />
                  Parent / Staff Portal
                </Link>
              </Button>
            </div>
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------------------- */}
      {/* Quick Links Grid                                                 */}
      {/* ---------------------------------------------------------------- */}
      <section className="mx-auto w-full max-w-6xl px-4 py-12 sm:px-6 sm:py-16">
        <h2 className="mb-8 text-center text-xl font-semibold sm:text-2xl">
          Quick Links
        </h2>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {QUICK_LINKS.map((link) => {
            const Icon = link.icon;
            return (
              <Link key={link.href} href={link.href}>
                <Card className="group h-full transition-all duration-200 hover:shadow-md hover:border-primary/40">
                  <CardContent className="flex flex-col items-center p-6 text-center">
                    <div
                      className="mb-4 flex h-14 w-14 items-center justify-center rounded-full transition-colors duration-200"
                      style={{ backgroundColor: `${primaryColor}15` }}
                    >
                      <Icon
                        className="h-7 w-7 transition-colors duration-200"
                        style={{ color: primaryColor }}
                      />
                    </div>
                    <h3 className="mb-1 text-sm font-semibold">{link.title}</h3>
                    <p className="text-xs text-muted-foreground">
                      {link.description}
                    </p>
                    <ArrowRight
                      className="mt-3 h-4 w-4 text-muted-foreground opacity-0 transition-all duration-200 group-hover:translate-x-1 group-hover:opacity-100"
                      style={{ color: primaryColor }}
                    />
                  </CardContent>
                </Card>
              </Link>
            );
          })}
        </div>
      </section>

      {/* ---------------------------------------------------------------- */}
      {/* Admissions CTA Banner                                            */}
      {/* ---------------------------------------------------------------- */}
      <section
        className="mx-4 mb-12 rounded-xl sm:mx-6 md:mx-auto md:max-w-6xl"
        style={{ backgroundColor: `${primaryColor}08` }}
      >
        <div className="flex flex-col items-center gap-6 px-6 py-10 text-center sm:px-12 md:flex-row md:text-left">
          <div className="flex-1">
            <h3 className="text-lg font-semibold sm:text-xl">
              Ready to join {schoolName}?
            </h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Start your admission application online. Our streamlined process
              makes it easy to apply from anywhere.
            </p>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row">
            <Button
              className="gap-2"
              style={{ backgroundColor: primaryColor, color: foreground }}
              asChild
            >
              <Link href="/apply">
                <FileText className="h-4 w-4" />
                Start Application
              </Link>
            </Button>
            <Button variant="outline" className="gap-2" asChild>
              <Link href="/apply/status">
                <ClipboardCheck className="h-4 w-4" />
                Check Status
              </Link>
            </Button>
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------------------- */}
      {/* Contact Section                                                  */}
      {/* ---------------------------------------------------------------- */}
      {(schoolInfo?.address || schoolInfo?.phone || schoolInfo?.email) && (
        <section id="contact" className="border-t bg-muted/30">
          <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
            <h2 className="mb-8 text-center text-xl font-semibold">
              Contact Us
            </h2>
            <div className="flex flex-col items-center gap-6 sm:flex-row sm:justify-center sm:gap-12">
              {schoolInfo?.address && (
                <div className="flex items-start gap-3 text-sm">
                  <MapPin
                    className="mt-0.5 h-5 w-5 shrink-0"
                    style={{ color: primaryColor }}
                  />
                  <span className="text-muted-foreground">
                    {schoolInfo.address}
                  </span>
                </div>
              )}
              {schoolInfo?.phone && (
                <a
                  href={`tel:${schoolInfo.phone}`}
                  className="flex items-center gap-3 text-sm text-muted-foreground transition-colors hover:text-foreground"
                >
                  <Phone
                    className="h-5 w-5 shrink-0"
                    style={{ color: primaryColor }}
                  />
                  <span>{schoolInfo.phone}</span>
                </a>
              )}
              {schoolInfo?.email && (
                <a
                  href={`mailto:${schoolInfo.email}`}
                  className="flex items-center gap-3 text-sm text-muted-foreground transition-colors hover:text-foreground"
                >
                  <Mail
                    className="h-5 w-5 shrink-0"
                    style={{ color: primaryColor }}
                  />
                  <span>{schoolInfo.email}</span>
                </a>
              )}
            </div>
          </div>
        </section>
      )}

      {/* ---------------------------------------------------------------- */}
      {/* Footer                                                           */}
      {/* ---------------------------------------------------------------- */}
      <footer className="border-t">
        <div className="mx-auto flex max-w-6xl flex-col items-center gap-2 px-4 py-6 text-center text-xs text-muted-foreground sm:flex-row sm:justify-between sm:px-6">
          <p>
            &copy; {new Date().getFullYear()} {schoolName}. All rights reserved.
          </p>
          <p>
            Powered by{" "}
            <a
              href="https://simsplus.io"
              className="font-medium underline underline-offset-4 transition-colors hover:text-foreground"
              target="_blank"
              rel="noopener noreferrer"
            >
              SIMS Plus
            </a>
          </p>
        </div>
      </footer>
    </div>
  );
}
