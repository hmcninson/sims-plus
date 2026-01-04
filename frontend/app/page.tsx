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

export default function HomePage() {
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
