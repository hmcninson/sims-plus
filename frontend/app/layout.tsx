import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Toaster } from "@/components/ui/sonner";
import { ThemeProvider } from "@/components/providers/ThemeProvider";
import { TenantProvider } from "@/components/providers/TenantProvider";
import { SwRegister } from "@/components/pwa/sw-register";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: "SIMS Plus",
    template: "%s | SIMS Plus",
  },
  description:
    "School Information Management System Plus - Manage students, staff, academics, and finances in one platform.",
  keywords: [
    "school management",
    "education",
    "student management",
    "school software",
    "SIMS",
    "SaaS",
  ],
  authors: [{ name: "Harry McNinson" }],
  creator: "SIMS Plus",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "SIMS Plus",
  },
  other: {
    "mobile-web-app-capable": "yes",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <meta name="theme-color" content="#0969da" />
        <link rel="apple-touch-icon" href="/icons/icon-192.png" />
      </head>
      <body
        className={`${geistSans.variable} ${geistMono.variable} font-sans antialiased`}
      >
        <ThemeProvider>
          <TenantProvider>
            {children}
            <Toaster position="top-right" richColors />
            <SwRegister />
          </TenantProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
