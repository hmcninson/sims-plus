import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ArrowRight, Phone } from "lucide-react";

export function CTASection() {
  return (
    <section className="bg-primary py-20">
      <div className="container mx-auto px-4">
        <div className="mx-auto max-w-3xl text-center">
          <h2 className="mb-4 text-3xl font-bold text-primary-foreground sm:text-4xl">
            Ready to transform your school?
          </h2>
          <p className="mb-8 text-lg text-primary-foreground/80">
            Join hundreds of schools already using SIMS Plus to streamline
            their operations. Start your free trial today.
          </p>
          <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
            <Button
              size="lg"
              variant="secondary"
              asChild
              className="min-w-[180px]"
            >
              <Link href="/register">
                Start Free Trial
                <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
            <Button
              size="lg"
              variant="outline"
              className="min-w-[180px] border-primary-foreground/30 bg-primary-foreground/10 text-primary-foreground hover:bg-primary-foreground/20"
            >
              <Phone className="mr-2 h-4 w-4" />
              Talk to Sales
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
}
