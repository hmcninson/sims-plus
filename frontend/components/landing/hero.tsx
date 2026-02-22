import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ArrowRight, PlayCircle } from "lucide-react";

export function Hero() {
  return (
    <section className="relative overflow-hidden bg-gradient-to-b from-primary/5 to-background py-20 sm:py-32">
      {/* Background Pattern */}
      <div className="absolute inset-0 -z-10 bg-[linear-gradient(to_right,#8080800a_1px,transparent_1px),linear-gradient(to_bottom,#8080800a_1px,transparent_1px)] bg-[size:24px_24px]" />

      <div className="container mx-auto px-4">
        <div className="mx-auto max-w-3xl text-center">
          {/* Badge */}
          <Badge variant="secondary" className="mb-6">
            Trusted by 100+ schools in Ghana
          </Badge>

          {/* Headline */}
          <h1 className="mb-6 text-4xl font-bold tracking-tight text-foreground sm:text-5xl lg:text-6xl">
            Modern School Management{" "}
            <span className="text-primary">for Ghana</span>
          </h1>

          {/* Subheadline */}
          <p className="mx-auto mb-10 max-w-2xl text-lg text-muted-foreground sm:text-xl">
            The all-in-one platform to manage students, academics, finances, and
            operations. Built specifically for Ghanaian schools from preschools
            to Senior High Schools.
          </p>

          {/* CTA Buttons */}
          <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
            <Button size="lg" asChild className="min-w-[180px]">
              <Link href="/register">
                Start Free Trial
                <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
            <Button size="lg" variant="outline" className="min-w-[180px]">
              <PlayCircle className="mr-2 h-4 w-4" />
              Watch Demo
            </Button>
          </div>

          {/* Trust Indicators */}
          <p className="mt-8 text-sm text-muted-foreground">
            No credit card required. 14-day free trial.
          </p>
        </div>

        {/* Hero Image Placeholder - Dashboard Preview */}
        <div className="mx-auto mt-16 max-w-5xl">
          <div className="relative rounded-xl border bg-background p-2 shadow-2xl">
            <div className="aspect-[16/9] overflow-hidden rounded-lg bg-gradient-to-br from-primary/20 via-primary/10 to-secondary/20">
              {/* Fake Dashboard UI */}
              <div className="flex h-full flex-col">
                {/* Top Bar */}
                <div className="flex items-center gap-2 border-b bg-background/80 px-4 py-2">
                  <div className="h-3 w-3 rounded-full bg-red-400" />
                  <div className="h-3 w-3 rounded-full bg-yellow-400" />
                  <div className="h-3 w-3 rounded-full bg-green-400" />
                  <div className="ml-4 h-4 w-48 rounded bg-muted" />
                </div>
                {/* Content */}
                <div className="flex flex-1">
                  {/* Sidebar */}
                  <div className="hidden w-48 border-r bg-primary/5 p-4 sm:block">
                    <div className="space-y-3">
                      <div className="h-4 w-24 rounded bg-primary/20" />
                      <div className="h-4 w-32 rounded bg-muted" />
                      <div className="h-4 w-28 rounded bg-muted" />
                      <div className="h-4 w-24 rounded bg-muted" />
                      <div className="h-4 w-30 rounded bg-muted" />
                    </div>
                  </div>
                  {/* Main Content */}
                  <div className="flex-1 p-4">
                    <div className="mb-4 h-6 w-48 rounded bg-muted" />
                    <div className="grid gap-4 sm:grid-cols-3">
                      <div className="h-24 rounded-lg bg-primary/10" />
                      <div className="h-24 rounded-lg bg-secondary/30" />
                      <div className="h-24 rounded-lg bg-green-500/10" />
                    </div>
                    <div className="mt-4 h-32 rounded-lg bg-muted/50" />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
