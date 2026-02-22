# SIMS Plus (School Information Management System Plus) - Infrastructure Overview

**Version:** 1.0  
**Date:** January 2026  
**Author:** Harry McNinson  
**Purpose:** Clear explanation of shared infrastructure multi-tenant architecture

---

## The Big Picture

**All schools share ONE infrastructure. Subdomains are just identifiers, not separate systems.**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│   🏫 PRESEC        🏫 ACHIMOTA       🏫 WESLEY GIRLS      🏫 NEW SCHOOL    │
│      │                 │                  │                   │            │
│      │                 │                  │                   │            │
│      ▼                 ▼                  ▼                   ▼            │
│   presec.          achimota.          wesleyg.          newschool.        │
│   simsplus.io    simsplus.io      simsplus.io     simsplus.io     │
│      │                 │                  │                   │            │
│      └─────────────────┴──────────────────┴───────────────────┘            │
│                                 │                                           │
│                                 │  ALL go to the SAME place                │
│                                 ▼                                           │
│                    ┌───────────────────────┐                               │
│                    │                       │                               │
│                    │    YOUR ONE SERVER    │◄─── Just ONE server           │
│                    │                       │     (or cluster)              │
│                    └───────────┬───────────┘                               │
│                                │                                           │
│                                ▼                                           │
│                    ┌───────────────────────┐                               │
│                    │                       │                               │
│                    │   YOUR ONE DATABASE   │◄─── Just ONE database         │
│                    │                       │                               │
│                    │  ┌─────────────────┐  │                               │
│                    │  │ tenant_id = X   │  │◄─── Data separated by         │
│                    │  │ tenant_id = Y   │  │     tenant_id column          │
│                    │  │ tenant_id = Z   │  │                               │
│                    │  └─────────────────┘  │                               │
│                    │                       │                               │
│                    └───────────────────────┘                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## What You Deploy (Total)

| Component | Quantity | Serves |
|-----------|----------|--------|
| **Servers** | 1 cluster | ALL schools |
| **Database** | 1 instance | ALL schools |
| **Redis Cache** | 1 instance | ALL schools |
| **DNS Record** | 1 wildcard | ALL schools |
| **SSL Certificate** | 1 wildcard | ALL schools |
| **S3 Bucket** | 1 bucket | ALL schools |
| **Codebase** | 1 codebase | ALL schools |

**Total monthly cost: ~$300-500 (regardless of number of schools)**

---

## Common Questions

### Q: Does each school need its own server?

**NO.** All schools share the same servers.

```
❌ Wrong:
   Presec → Server 1
   Achimota → Server 2
   Wesley → Server 3
   
✅ Correct:
   Presec    ──┐
   Achimota  ──┼──► Same Server(s)
   Wesley    ──┘
```

### Q: Does each school need its own database?

**NO.** All schools share one database. Data is separated by `tenant_id`.

```
❌ Wrong:
   Presec → Database 1
   Achimota → Database 2
   
✅ Correct:
   ONE Database containing:
   ┌─────────────────────────────────────────┐
   │ students table                          │
   ├──────────┬──────────────┬───────────────┤
   │ id       │ tenant_id    │ name          │
   │ 1        │ presec       │ Kwame         │
   │ 2        │ presec       │ Ama           │
   │ 3        │ achimota     │ Kofi          │
   │ 4        │ achimota     │ Abena         │
   └──────────┴──────────────┴───────────────┘
   
   Row-Level Security ensures each school
   only sees their own rows.
```

### Q: How do new schools get added?

**Just database entries.** No infrastructure changes.

```sql
-- Adding a new school takes 3 database inserts:

INSERT INTO tenants (subdomain, name) 
VALUES ('newschool', 'New School Academy');

INSERT INTO schools (tenant_id, name) 
VALUES ('newschool-id', 'New School Academy');

INSERT INTO users (tenant_id, email, role) 
VALUES ('newschool-id', 'admin@newschool.edu.gh', 'admin');

-- DONE! newschool.simsplus.io now works.
-- Time: ~1 second
-- Cost: $0
```

### Q: How does security work?

**PostgreSQL Row-Level Security (RLS)** ensures schools can't see each other's data.

```sql
-- When logged in as Presec user:
SELECT * FROM students;

-- PostgreSQL automatically transforms this to:
SELECT * FROM students WHERE tenant_id = 'presec';

-- It's IMPOSSIBLE to see other schools' data.
-- This is enforced at the database level.
```

### Q: What happens when we have 1000 schools?

**Same infrastructure, just handle more traffic.** You might:
- Add more application pods (horizontal scaling)
- Add database read replicas
- Still ONE database, ONE codebase

```
10 schools     → $300/month infrastructure
100 schools    → $300/month infrastructure (same!)
500 schools    → $500/month infrastructure (slightly more)
1000 schools   → $1000/month infrastructure (still cheap!)
```

---

## How Subdomains Work

### DNS (One Wildcard Record)

```
DNS Configuration:
┌────────┬────────┬─────────────────┐
│ Type   │ Name   │ Value           │
├────────┼────────┼─────────────────┤
│ A      │ *      │ 123.45.67.89    │
└────────┴────────┴─────────────────┘

This ONE record means:
• presec.simsplus.io    → 123.45.67.89
• achimota.simsplus.io  → 123.45.67.89
• anything.simsplus.io  → 123.45.67.89

No new DNS records needed for new schools!
```

### SSL (One Wildcard Certificate)

```
SSL Certificate covers:
• simsplus.io
• *.simsplus.io (ANY subdomain)

This ONE certificate secures:
• presec.simsplus.io    ✅ Secure
• achimota.simsplus.io  ✅ Secure
• newschool.simsplus.io ✅ Secure

No new certificates needed for new schools!
```

### Request Flow

```
1. User visits presec.simsplus.io
              │
2. DNS resolves *.simsplus.io → Your server IP
              │
3. Request arrives at your ONE server
              │
4. Application extracts "presec" from URL
              │
5. Application looks up tenant_id for "presec"
              │
6. Application sets database context to that tenant
              │
7. All database queries automatically filtered
              │
8. User sees only Presec's data, with Presec's branding
```

---

## Real Infrastructure Setup

### Minimal Setup (Starting Out)

```
Monthly Cost: ~$100-300

┌─────────────────────────────────────────┐
│                                         │
│  DigitalOcean / AWS / Linode            │
│                                         │
│  • 1 VPS ($40-100/month)               │
│    - Next.js frontend                   │
│    - FastAPI backend                    │
│    - Nginx reverse proxy                │
│                                         │
│  • 1 Managed PostgreSQL ($50-100/month) │
│                                         │
│  • Cloudflare Free (DNS + SSL)          │
│                                         │
│  Serves: 1-100 schools easily           │
│                                         │
└─────────────────────────────────────────┘
```

### Production Setup (Growing)

```
Monthly Cost: ~$300-800

┌─────────────────────────────────────────┐
│                                         │
│  AWS / GCP / Azure                      │
│                                         │
│  • Load Balancer ($20/month)            │
│                                         │
│  • 2-3 App Servers ($100-200/month)     │
│    - Auto-scaling group                 │
│    - Docker containers                  │
│                                         │
│  • RDS PostgreSQL ($100-300/month)      │
│    - Multi-AZ for reliability           │
│                                         │
│  • ElastiCache Redis ($50-100/month)    │
│                                         │
│  • S3 for files ($20-50/month)          │
│                                         │
│  • Cloudflare Pro ($20/month)           │
│                                         │
│  Serves: 100-1000+ schools              │
│                                         │
└─────────────────────────────────────────┘
```

---

## Comparison: Multi-Tenant vs. Single-Tenant

### ❌ Single-Tenant (DON'T DO THIS)

```
Each school gets own infrastructure:

School 1: Server + Database = $100/month
School 2: Server + Database = $100/month
School 3: Server + Database = $100/month
...
School 100: Server + Database = $100/month

Total: 100 × $100 = $10,000/month 😱

Plus:
• 100 deployments to manage
• 100 servers to monitor
• 100 databases to backup
• 100 SSL certificates
```

### ✅ Multi-Tenant (THIS IS WHAT WE USE)

```
All schools share infrastructure:

Shared Server Cluster = $300/month
Shared Database = $100/month
Shared Everything Else = $100/month

Total: $500/month for ALL schools ✓

Plus:
• 1 deployment to manage
• 1 cluster to monitor
• 1 database to backup
• 1 SSL certificate
```

---

## Summary

| Question | Answer |
|----------|--------|
| How many servers? | **ONE** (or one cluster) |
| How many databases? | **ONE** |
| How many codebases? | **ONE** |
| How to add new school? | **Database insert** |
| Time to add school? | **~30 seconds** |
| Cost to add school? | **$0 infrastructure** |
| How is data separated? | **tenant_id + Row-Level Security** |
| Can schools see each other? | **NO - impossible** |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | January 2026 | Harry McNinson | Initial version |
