/**
 * SIMS Plus - Tenant Type Definitions
 */

/**
 * School search result from the public search API.
 * Only contains safe public fields -- no tenant_id, subscription, or features.
 */
export interface SchoolSearchResult {
  name: string;
  subdomain: string;
  logo_url: string | null;
  primary_color: string | null;
}

export interface SchoolSearchResponse {
  results: SchoolSearchResult[];
  count: number;
}
