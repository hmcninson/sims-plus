import { Card, CardContent } from "@/components/ui/card";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Quote } from "lucide-react";

const testimonials = [
  {
    quote:
      "SIMS Plus has transformed how we manage our school. The fee collection through Mobile Money alone has saved us countless hours every term.",
    name: "Ama Mensah",
    role: "Headmistress",
    school: "Blessed Academy, Kumasi",
    initials: "AM",
  },
  {
    quote:
      "As a school chain with 5 branches, the multi-school management feature is invaluable. We can now see all our schools from one dashboard.",
    name: "Kwame Asante",
    role: "Director",
    school: "Excellence Schools Group, Accra",
    initials: "KA",
  },
  {
    quote:
      "The report card generation used to take us a whole week. Now it's done in minutes. Parents love receiving updates via SMS too.",
    name: "Grace Osei",
    role: "Academic Head",
    school: "St. Mary's SHS, Cape Coast",
    initials: "GO",
  },
];

export function Testimonials() {
  return (
    <section id="testimonials" className="py-20">
      <div className="container mx-auto px-4">
        {/* Section Header */}
        <div className="mx-auto mb-16 max-w-2xl text-center">
          <h2 className="mb-4 text-3xl font-bold text-foreground sm:text-4xl">
            Loved by schools across Ghana
          </h2>
          <p className="text-lg text-muted-foreground">
            See what educators are saying about SIMS Plus
          </p>
        </div>

        {/* Testimonials Grid */}
        <div className="grid gap-6 md:grid-cols-3">
          {testimonials.map((testimonial) => (
            <Card key={testimonial.name} className="relative">
              <CardContent className="p-6">
                <Quote className="mb-4 h-8 w-8 text-primary/20" />
                <blockquote className="mb-6 text-muted-foreground">
                  &ldquo;{testimonial.quote}&rdquo;
                </blockquote>
                <div className="flex items-center gap-3">
                  <Avatar>
                    <AvatarFallback className="bg-primary/10 text-primary">
                      {testimonial.initials}
                    </AvatarFallback>
                  </Avatar>
                  <div>
                    <div className="font-semibold text-foreground">
                      {testimonial.name}
                    </div>
                    <div className="text-sm text-muted-foreground">
                      {testimonial.role}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {testimonial.school}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
}
