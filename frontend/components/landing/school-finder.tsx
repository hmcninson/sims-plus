"use client";

import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Search, School, ExternalLink } from "lucide-react";

// Mock data - in production this would come from an API
const mockSchools = [
  {
    id: "1",
    name: "Presbyterian Boys' Secondary School",
    subdomain: "presec",
    location: "Legon, Accra",
    type: "SHS",
  },
  {
    id: "2",
    name: "Achimota School",
    subdomain: "achimota",
    location: "Achimota, Accra",
    type: "SHS",
  },
  {
    id: "3",
    name: "Wesley Girls' High School",
    subdomain: "wesleyg",
    location: "Cape Coast",
    type: "SHS",
  },
  {
    id: "4",
    name: "Mfantsipim School",
    subdomain: "mfantsipim",
    location: "Cape Coast",
    type: "SHS",
  },
  {
    id: "5",
    name: "St. Augustine's College",
    subdomain: "augusco",
    location: "Cape Coast",
    type: "SHS",
  },
  {
    id: "6",
    name: "Accra Academy",
    subdomain: "accraacademy",
    location: "Accra",
    type: "SHS",
  },
];

export function SchoolFinder() {
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<typeof mockSchools>([]);
  const [isSearching, setIsSearching] = useState(false);

  const handleSearch = (query: string) => {
    setSearchQuery(query);

    if (query.length < 2) {
      setSearchResults([]);
      setIsSearching(false);
      return;
    }

    setIsSearching(true);

    // Simulate API search - in production this would be an API call
    const results = mockSchools.filter(
      (school) =>
        school.name.toLowerCase().includes(query.toLowerCase()) ||
        school.subdomain.toLowerCase().includes(query.toLowerCase()) ||
        school.location.toLowerCase().includes(query.toLowerCase())
    );

    setSearchResults(results);
  };

  const handleSchoolClick = (subdomain: string) => {
    // In production, this would redirect to the school's subdomain
    window.open(`https://${subdomain}.simsplus.io`, "_blank");
  };

  return (
    <section className="border-y bg-muted/50 py-16">
      <div className="container mx-auto px-4">
        <div className="mx-auto max-w-2xl">
          {/* Header */}
          <div className="mb-8 text-center">
            <h2 className="mb-2 text-2xl font-bold text-foreground">
              Already have an account?
            </h2>
            <p className="text-muted-foreground">
              Find your school and login to your portal
            </p>
          </div>

          {/* Search Input */}
          <div className="relative mb-6">
            <Search className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
            <Input
              type="text"
              placeholder="Search for your school..."
              value={searchQuery}
              onChange={(e) => handleSearch(e.target.value)}
              className="h-14 pl-12 pr-4 text-lg"
            />
          </div>

          {/* Search Results */}
          {isSearching && searchResults.length > 0 && (
            <Card className="mb-6">
              <CardContent className="p-2">
                {searchResults.map((school) => (
                  <button
                    key={school.id}
                    onClick={() => handleSchoolClick(school.subdomain)}
                    className="flex w-full items-center gap-4 rounded-lg p-3 text-left transition-colors hover:bg-muted"
                  >
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                      <School className="h-5 w-5 text-primary" />
                    </div>
                    <div className="flex-1">
                      <div className="font-medium text-foreground">
                        {school.name}
                      </div>
                      <div className="text-sm text-muted-foreground">
                        {school.subdomain}.simsplus.io • {school.location}
                      </div>
                    </div>
                    <ExternalLink className="h-4 w-4 text-muted-foreground" />
                  </button>
                ))}
              </CardContent>
            </Card>
          )}

          {/* No Results */}
          {isSearching && searchQuery.length >= 2 && searchResults.length === 0 && (
            <Card className="mb-6">
              <CardContent className="p-6 text-center">
                <p className="text-muted-foreground">
                  No schools found matching &quot;{searchQuery}&quot;
                </p>
                <p className="mt-2 text-sm text-muted-foreground">
                  Is your school not registered yet?{" "}
                  <a href="/register" className="text-primary hover:underline">
                    Register now
                  </a>
                </p>
              </CardContent>
            </Card>
          )}

          {/* Direct Access */}
          <div className="mt-8 text-center">
            <p className="text-sm text-muted-foreground">
              Know your school code? Go directly to{" "}
              <code className="rounded bg-muted px-2 py-1 text-xs">
                yourschool.simsplus.io
              </code>
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
