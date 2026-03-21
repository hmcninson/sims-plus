import { headers } from "next/headers";

import {
  Navbar,
  Hero,
  Stats,
  SchoolFinder,
  Features,
  Pricing,
  Testimonials,
  CTASection,
  Footer,
} from "@/components/landing";

import { SchoolPortal } from "@/components/portal/school-portal";

import { apiGet } from "@/lib/api";

import type { PublicSchoolInfo } from "@/types/admissions.type";

export default async function HomePage() {
  const headersList = await headers();
  const subdomain = headersList.get("x-subdomain");

  if (subdomain) {
    // School-specific portal: fetch branding directly using the subdomain
    // from headers rather than cookies, since on the very first request the
    // x-subdomain cookie may not yet be set in the request.
    let schoolInfo: PublicSchoolInfo | null = null;
    try {
      schoolInfo = await apiGet<PublicSchoolInfo>(
        "/admissions/public/school-info",
        { subdomain }
      );
    } catch {
      // If the school-info endpoint fails (e.g. admissions module not enabled,
      // or backend unreachable), we still show the portal with fallback data.
      schoolInfo = null;
    }

    return <SchoolPortal schoolInfo={schoolInfo} subdomain={subdomain} />;
  }

  // Marketing page (no subdomain) -- unchanged
  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />
      <main className="flex-1">
        <Hero />
        <Stats />
        <SchoolFinder />
        <Features />
        <Pricing />
        <Testimonials />
        <CTASection />
      </main>
      <Footer />
    </div>
  );
}
