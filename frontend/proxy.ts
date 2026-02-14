/**
 * SIMS Plus - Proxy (Next.js 16)
 *
 * Handles subdomain detection and tenant routing.
 * In Next.js 16, proxy.ts replaces middleware.ts and runs on Node.js runtime.
 *
 * This proxy:
 * 1. Extracts subdomain from hostname (e.g., presec.simsplus.io -> presec)
 * 2. Sets x-subdomain header for server components
 * 3. Sets x-subdomain cookie for client components
 * 4. Supports development mode subdomain override
 */

import { NextRequest, NextResponse } from "next/server";

// Reserved subdomains that should not be treated as tenant subdomains
const RESERVED_SUBDOMAINS = new Set([
  "www",
  "app",
  "api",
  "admin",
  "mail",
  "ftp",
  "status",
  "blog",
  "help",
  "support",
  "docs",
  "cdn",
  "assets",
  "staging",
  "dev",
  "test",
  "demo",
  "sandbox",
]);

/**
 * Validate subdomain format.
 * Rules: 4-63 chars, lowercase alphanumeric and hyphens, no leading/trailing hyphens.
 */
function isValidSubdomainFormat(subdomain: string): boolean {
  if (subdomain.length < 4 || subdomain.length > 63) {
    return false;
  }
  const pattern = /^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]+$/;
  return pattern.test(subdomain);
}

/**
 * Get subdomain from cookie.
 */
function getSubdomainFromCookie(request: NextRequest): string | null {
  const cookieValue = request.cookies.get("x-subdomain")?.value;
  if (cookieValue && !RESERVED_SUBDOMAINS.has(cookieValue) && isValidSubdomainFormat(cookieValue)) {
    return cookieValue;
  }
  return null;
}

/**
 * Extract subdomain from hostname.
 *
 * @param hostname - Full hostname (e.g., "presec.simsplus.io")
 * @param searchParams - URL search params for dev mode override
 * @param request - NextRequest for cookie access
 * @returns Subdomain or null if none
 */
function extractSubdomain(hostname: string, searchParams?: URLSearchParams, request?: NextRequest): string | null {
  // Remove port if present
  const hostWithoutPort = hostname.split(":")[0];

  // Development mode: support presec.localhost:3000 format
  if (hostWithoutPort.endsWith(".localhost")) {
    const subdomain = hostWithoutPort.replace(".localhost", "").toLowerCase();
    if (subdomain && !RESERVED_SUBDOMAINS.has(subdomain) && isValidSubdomainFormat(subdomain)) {
      return subdomain;
    }
    return null;
  }

  // Development mode: support ?subdomain=presec query param OR cookie
  if (hostWithoutPort === "localhost" || hostWithoutPort === "127.0.0.1") {
    // First check query param (allows switching tenants)
    const devSubdomain = searchParams?.get("subdomain")?.toLowerCase();
    if (devSubdomain && !RESERVED_SUBDOMAINS.has(devSubdomain) && isValidSubdomainFormat(devSubdomain)) {
      return devSubdomain;
    }
    // Fallback to cookie (persists across navigation)
    if (request) {
      return getSubdomainFromCookie(request);
    }
    return null;
  }

  // Split hostname into parts
  const parts = hostWithoutPort.split(".");

  // Need at least 3 parts for subdomain (e.g., presec.simsplus.io)
  if (parts.length < 3) {
    return null;
  }

  // First part is the subdomain
  const subdomain = parts[0].toLowerCase();

  // Check if it's a reserved subdomain
  if (RESERVED_SUBDOMAINS.has(subdomain)) {
    return null;
  }

  // Validate format
  if (!isValidSubdomainFormat(subdomain)) {
    return null;
  }

  return subdomain;
}

/**
 * Check if the current path is a public route that doesn't require tenant context.
 */
function isPublicRoute(pathname: string): boolean {
  const publicPaths = [
    "/",
    "/login",
    "/register",
    "/register/success",
    "/forgot-password",
    "/reset-password",
    "/verify-email",
    "/pricing",
    "/features",
    "/about",
    "/contact",
    "/terms",
    "/privacy",
    "/api",
    "/_next",
    "/favicon.ico",
  ];

  return publicPaths.some(
    (path) => pathname === path || pathname.startsWith(path + "/") || pathname.startsWith("/_next")
  );
}

/**
 * Next.js 16 Proxy function.
 *
 * Handles subdomain detection and sets tenant context headers.
 */
export default function proxy(request: NextRequest): NextResponse {
  const hostname = request.headers.get("host") || "";
  const pathname = request.nextUrl.pathname;
  const searchParams = request.nextUrl.searchParams;

  // Extract subdomain from hostname (with dev mode support via query param or cookie)
  const subdomain = extractSubdomain(hostname, searchParams, request);

  // Create response headers with subdomain info
  const requestHeaders = new Headers(request.headers);

  if (subdomain) {
    // Set subdomain header for downstream use (server components)
    requestHeaders.set("x-subdomain", subdomain);
    requestHeaders.set("x-tenant-subdomain", subdomain);
  }

  // For API routes, pass through with subdomain header
  if (pathname.startsWith("/api")) {
    return NextResponse.next({
      request: {
        headers: requestHeaders,
      },
    });
  }

  // For public routes on main domain (no subdomain), allow access
  if (!subdomain && isPublicRoute(pathname)) {
    return NextResponse.next({
      request: {
        headers: requestHeaders,
      },
    });
  }

  // For tenant subdomains, validate and proceed
  if (subdomain) {
    // Set subdomain in headers for server components to access
    const response = NextResponse.next({
      request: {
        headers: requestHeaders,
      },
    });

    // Set response header for debugging
    response.headers.set("x-subdomain", subdomain);

    // Set cookie for client-side access (TenantProvider can read this)
    response.cookies.set("x-subdomain", subdomain, {
      httpOnly: false, // Accessible by client JS
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 60 * 60 * 24, // 24 hours
    });

    return response;
  }

  // For non-public routes without subdomain, redirect to login with error
  if (!subdomain && !isPublicRoute(pathname)) {
    const url = new URL("/login", request.url);
    url.searchParams.set("error", "no_school");
    url.searchParams.set("message", "Please access your school portal directly");
    return NextResponse.redirect(url);
  }

  return NextResponse.next({
    request: {
      headers: requestHeaders,
    },
  });
}

/**
 * Proxy configuration.
 *
 * Define which paths the proxy should run on.
 */
export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public folder files
     */
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
