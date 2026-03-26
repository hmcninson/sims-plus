"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Search, School, ExternalLink, Clock, X, Loader2 } from "lucide-react";
import { searchSchools } from "@/actions/tenant.action";
import type { SchoolSearchResult } from "@/types/tenant.type";

// --- Recent schools persistence (localStorage) ---

const RECENT_SCHOOLS_KEY = "sims_recent_schools";
const MAX_RECENT_SCHOOLS = 5;

interface RecentSchool {
  subdomain: string;
  name: string;
  logo_url: string | null;
  timestamp: number;
}

function getRecentSchools(): RecentSchool[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(RECENT_SCHOOLS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.slice(0, MAX_RECENT_SCHOOLS);
  } catch {
    return [];
  }
}

function saveRecentSchool(school: {
  subdomain: string;
  name: string;
  logo_url: string | null;
}): void {
  if (typeof window === "undefined") return;
  try {
    const existing = getRecentSchools();
    // Remove any prior entry for this subdomain to avoid duplicates
    const filtered = existing.filter((s) => s.subdomain !== school.subdomain);
    const updated: RecentSchool[] = [
      {
        subdomain: school.subdomain,
        name: school.name,
        logo_url: school.logo_url,
        timestamp: Date.now(),
      },
      ...filtered,
    ].slice(0, MAX_RECENT_SCHOOLS);
    localStorage.setItem(RECENT_SCHOOLS_KEY, JSON.stringify(updated));
  } catch {
    // localStorage unavailable — silently ignore
  }
}

function clearRecentSchools(): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.removeItem(RECENT_SCHOOLS_KEY);
  } catch {
    // Silently ignore
  }
}

// --- Component ---

export function SchoolFinder() {
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SchoolSearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [recentSchools, setRecentSchools] = useState<RecentSchool[]>([]);

  // Debounce timer ref
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Generation counter to discard stale responses from out-of-order arrivals
  const searchGenerationRef = useRef(0);

  // Load recent schools on mount
  useEffect(() => {
    setRecentSchools(getRecentSchools());
  }, []);

  // Debounced search function with stale-response protection
  const debouncedSearch = useCallback((query: string) => {
    // Clear any pending debounce
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    if (query.trim().length < 2) {
      // Bump generation so any in-flight request is discarded
      searchGenerationRef.current += 1;
      setSearchResults([]);
      setHasSearched(false);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);

    debounceRef.current = setTimeout(async () => {
      // Capture the generation at dispatch time
      const generation = ++searchGenerationRef.current;

      const result = await searchSchools(query);

      // Discard if a newer search was initiated while this one was in-flight
      if (generation !== searchGenerationRef.current) return;

      if (result.success) {
        setSearchResults(result.data.results);
      } else {
        setSearchResults([]);
      }
      setHasSearched(true);
      setIsLoading(false);
    }, 300);
  }, []);

  // Clean up debounce on unmount
  useEffect(() => {
    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
      // Ensure any in-flight request is discarded on unmount
      searchGenerationRef.current += 1;
    };
  }, []);

  const handleInputChange = (value: string) => {
    setSearchQuery(value);
    debouncedSearch(value);
  };

  const appDomain = process.env.NEXT_PUBLIC_APP_DOMAIN || "simsplus.io";
  const protocol = process.env.NODE_ENV === "development" ? "http" : "https";

  const handleSchoolClick = (school: {
    subdomain: string;
    name: string;
    logo_url: string | null;
  }) => {
    // Save to recent schools before navigating
    saveRecentSchool(school);
    window.location.href = `${protocol}://${school.subdomain}.${appDomain}`;
  };

  const handleClearRecent = () => {
    clearRecentSchools();
    setRecentSchools([]);
  };

  const showSearchResults = searchQuery.trim().length >= 2;

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

          {/* Recently visited schools */}
          {recentSchools.length > 0 && !showSearchResults && (
            <div className="mb-6">
              <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                  <Clock className="h-4 w-4" />
                  Recently visited
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleClearRecent}
                  className="h-auto px-2 py-1 text-xs text-muted-foreground hover:text-foreground"
                >
                  <X className="mr-1 h-3 w-3" />
                  Clear history
                </Button>
              </div>
              <div className="grid gap-2 sm:grid-cols-2">
                {recentSchools.map((school) => (
                  <button
                    key={school.subdomain}
                    onClick={() => handleSchoolClick(school)}
                    className="flex items-center gap-3 rounded-lg border bg-background p-3 text-left transition-colors hover:bg-muted"
                  >
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                      {school.logo_url ? (
                        <img
                          src={school.logo_url}
                          alt=""
                          className="h-6 w-6 rounded object-contain"
                        />
                      ) : (
                        <School className="h-4 w-4 text-primary" />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium text-foreground">
                        {school.name}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {school.subdomain}.{appDomain}
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Search Input */}
          <div className="relative mb-6">
            <Search className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
            <Input
              type="text"
              placeholder="Search for your school..."
              value={searchQuery}
              onChange={(e) => handleInputChange(e.target.value)}
              className="h-14 pl-12 pr-4 text-lg"
            />
            {isLoading && (
              <Loader2 className="absolute right-4 top-1/2 h-5 w-5 -translate-y-1/2 animate-spin text-muted-foreground" />
            )}
          </div>

          {/* Search Results */}
          {showSearchResults && !isLoading && searchResults.length > 0 && (
            <Card className="mb-6">
              <CardContent className="p-2">
                {searchResults.map((school) => (
                  <button
                    key={school.subdomain}
                    onClick={() => handleSchoolClick(school)}
                    className="flex w-full items-center gap-4 rounded-lg p-3 text-left transition-colors hover:bg-muted"
                  >
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                      {school.logo_url ? (
                        <img
                          src={school.logo_url}
                          alt=""
                          className="h-7 w-7 rounded object-contain"
                        />
                      ) : (
                        <School className="h-5 w-5 text-primary" />
                      )}
                    </div>
                    <div className="flex-1">
                      <div className="font-medium text-foreground">
                        {school.name}
                      </div>
                      <div className="text-sm text-muted-foreground">
                        {school.subdomain}.{appDomain}
                      </div>
                    </div>
                    <ExternalLink className="h-4 w-4 text-muted-foreground" />
                  </button>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Loading state while searching */}
          {showSearchResults && isLoading && (
            <Card className="mb-6">
              <CardContent className="p-6 text-center">
                <Loader2 className="mx-auto mb-2 h-5 w-5 animate-spin text-muted-foreground" />
                <p className="text-sm text-muted-foreground">
                  Searching schools...
                </p>
              </CardContent>
            </Card>
          )}

          {/* No Results */}
          {showSearchResults &&
            hasSearched &&
            !isLoading &&
            searchResults.length === 0 && (
              <Card className="mb-6">
                <CardContent className="p-6 text-center">
                  <p className="text-muted-foreground">
                    No schools found matching &quot;{searchQuery}&quot;
                  </p>
                  <p className="mt-2 text-sm text-muted-foreground">
                    Is your school not registered yet?{" "}
                    <a
                      href="/register"
                      className="text-primary hover:underline"
                    >
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
                yourschool.{appDomain}
              </code>
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
