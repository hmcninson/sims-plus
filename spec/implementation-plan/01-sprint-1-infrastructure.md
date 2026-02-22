# Sprint 1: Environment + Security Foundation (Weeks 1-2)

**Version:** 1.0
**Date:** 15 February 2026
**Status:** Ready for Implementation
**Sprint Duration:** 2 weeks (10 working days)
**Depends On:** Nothing (first sprint)

---

## Goal

Every developer can run the project locally with working subdomain routing. The backend connects as a non-superuser so RLS is enforced. The CI/CD pipeline runs lint, type-check, and tests on every PR.

---

## Existing State of the Codebase

Before starting any task, the team must understand what already exists and what is broken:

| Component | Status | Issues Found |
|-----------|--------|-------------|
| `docker-compose.yml` | Exists | Connects backend as `postgres` superuser (RLS bypassed). Nginx is commented out. Uses `${POSTGRES_USER}` env var instead of explicit `sims_app_user`. |
| `backend/scripts/init-db.sql` | Exists | Does NOT create `sims_app_user`. Creates `current_tenant_id()` instead of `get_current_tenant_id()`. No extensions on test DB. |
| `backend/app/main.py` | Exists | Middleware order is correct. CORS uses static list instead of regex for wildcard subdomains. Global exception handler exists. |
| `backend/app/config.py` | Exists | Missing `SECRET_KEY` length validation. Has `CORS_ALLOW_SUBDOMAIN_PATTERN` but it is unused in `main.py`. |
| `backend/app/middleware/tenant.py` | Exists | Fully functional. Calls `set_tenant_context()` via raw SQL. |
| `backend/app/middleware/rate_limit.py` | Exists | Fully functional. Redis sliding window. |
| `backend/app/api/deps.py` | Exists | `get_db()` silently proceeds without tenant context (Finding F3). |
| `frontend/proxy.ts` | Exists | Fully functional. Subdomain extraction, validation, cookie setting all work. |
| `frontend/next.config.ts` | Exists | Missing `serverActions.bodySizeLimit`. Has `output: "standalone"` (good). |
| `frontend/lib/api.ts` | Exists | Functional but does not read subdomain from Next.js headers/cookies automatically. Requires manual `subdomain` option. |
| `.github/workflows/backend-ci.yml` | Exists | Uses `postgres` superuser for tests. No `sims_app_user`. No migration test step. |
| `.github/workflows/frontend-ci.yml` | Exists | Uses Node 20 instead of Node 22. |
| `.env.example` | **MISSING** | Must create on Day 1. |
| `.github/pull_request_template.md` | **MISSING** | Must create on Day 1. |
| `docker/nginx/nginx.conf` | **MISSING** | Must create for local wildcard subdomain routing. |
| `scripts/setup-local-dns.sh` | **MISSING** | Must create for local dev convenience. |
| `backend/Dockerfile` | Exists | Good. Multi-stage build with development and production targets. |
| `frontend/Dockerfile` | Exists | Uses Node 20. Must update to Node 22 for Next.js 16 compatibility. |

---

## Task Index

| ID | Name | Priority | Effort | Track | Dependencies |
|----|------|----------|--------|-------|-------------|
| S1-01 | Git Repository and Branching Strategy | P0 | 0.5d | Tech Lead | None |
| S1-02 | Docker Environment | P0 | 2d | Track A (DevOps) | S1-01 |
| S1-03 | FastAPI Backend Verification and Fixes | P1 | 1d | Track B (Backend 1) | S1-02 |
| S1-04 | Next.js 16 Frontend Verification | P1 | 2d | Track D (Frontend) | S1-02 |
| S1-05 | PostgreSQL Database Setup | P0 | 1.5d | Track B (Backend 1) | S1-02 |
| S1-06 | CI/CD Pipeline | P1 | 2d | Track A (DevOps) | S1-01 |
| S1-07 | Cloudflare DNS Wildcard | P1 | 1d | Track A (DevOps) | Domain registered |
| S1-08 | Wildcard SSL Certificate | P1 | 1d | Track A (DevOps) | S1-07 |
| S1-09 | Nginx Wildcard Subdomain Routing | P1 | 3d | Track A (DevOps) | S1-02, S1-07 |
| S1-10 | Local Development Subdomain Setup | P2 | 1.5d | Track A (DevOps) | S1-09 |

---

## Task S1-01: Git Repository and Branching Strategy

- **Priority:** P0 (Day 1)
- **Effort:** 0.5 days
- **Owner:** Tech Lead
- **Dependencies:** None

### Action 1: Create `.env.example`

**File:** `/sims-plus/.env.example` (NEW)

```bash
# ============================================================
# SIMS Plus - Environment Variables
# ============================================================
# Copy this file to .env and fill in the values:
#   cp .env.example .env
#
# NEVER commit .env to version control.
# ============================================================

# ----------------------------------------------------------
# PostgreSQL
# ----------------------------------------------------------
# The superuser account (used by init-db.sql and Alembic migrations ONLY)
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=sims_plus

# Application database URL (MUST use sims_app_user, NOT postgres)
# sims_app_user is a non-superuser -- RLS policies are enforced.
DATABASE_URL=postgresql+asyncpg://sims_app_user:changeme@db:5432/sims_plus

# Alembic migration URL (uses superuser for DDL operations)
ALEMBIC_DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/sims_plus

# Test database URL (used by pytest)
DATABASE_TEST_URL=postgresql+asyncpg://sims_app_user:changeme@db:5432/sims_plus_test

# ----------------------------------------------------------
# Redis
# ----------------------------------------------------------
REDIS_URL=redis://redis:6379/0

# ----------------------------------------------------------
# Security
# ----------------------------------------------------------
# CRITICAL: Generate with: openssl rand -base64 64
# Must be at least 64 characters in production.
SECRET_KEY=dev-only-not-for-production-change-me-openssl-rand-base64-64-minimum-64-chars

# JWT Configuration
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# ----------------------------------------------------------
# Application
# ----------------------------------------------------------
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000

# ----------------------------------------------------------
# CORS
# ----------------------------------------------------------
# JSON array of allowed origins. Wildcard subdomains handled by regex in main.py.
CORS_ORIGINS=["http://localhost:3000","http://frontend:3000"]

# ----------------------------------------------------------
# Email (SMTP)
# ----------------------------------------------------------
# For local development, use MailHog (docker-compose --profile tools up mailhog)
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_USE_TLS=false
SMTP_START_TLS=true
SMTP_FROM_EMAIL=noreply@simsplus.io
SMTP_FROM_NAME=SIMS Plus

# ----------------------------------------------------------
# SMS (Hubtel) - Leave empty for development
# ----------------------------------------------------------
HUBTEL_CLIENT_ID=
HUBTEL_CLIENT_SECRET=
HUBTEL_SENDER_ID=SIMSPlus

# ----------------------------------------------------------
# Mobile Money (MTN MoMo) - Leave empty for development
# ----------------------------------------------------------
MTN_MOMO_SUBSCRIPTION_KEY=
MTN_MOMO_API_USER=
MTN_MOMO_API_KEY=
MTN_MOMO_ENVIRONMENT=sandbox

# ----------------------------------------------------------
# AWS S3 / MinIO (File Storage)
# ----------------------------------------------------------
# For local development, use MinIO (docker-compose --profile tools up minio)
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin
AWS_REGION=us-east-1
AWS_S3_BUCKET=sims-plus-dev
S3_ENDPOINT_URL=http://minio:9000

# ----------------------------------------------------------
# Sentry (Error Tracking) - Leave empty for development
# ----------------------------------------------------------
SENTRY_DSN=

# ----------------------------------------------------------
# Rate Limiting
# ----------------------------------------------------------
RATE_LIMIT_ENABLED=true
RATE_LIMIT_DEFAULT_REQUESTS=500
RATE_LIMIT_DEFAULT_WINDOW=60
RATE_LIMIT_AUTH_REQUESTS=30
RATE_LIMIT_AUTH_WINDOW=60
RATE_LIMIT_SUBDOMAIN_CHECK_REQUESTS=20
RATE_LIMIT_SUBDOMAIN_CHECK_WINDOW=60
```

### Action 2: Set up branch protection rules

Run these commands (or configure via GitHub Settings > Branches):

```bash
# Create develop branch from main
git checkout -b develop
git push -u origin develop
```

Configure via GitHub UI (Settings > Branches > Branch protection rules):

**`main` branch:**
- Require a pull request before merging: ON
- Required approvals: 1
- Require status checks to pass before merging: ON
  - Required checks: `Backend CI / Lint`, `Backend CI / Test`, `Frontend CI / Lint & Type Check`, `Frontend CI / Build`
- Require branches to be up to date before merging: ON
- Do not allow bypassing the above settings: ON
- Restrict force pushes: ON

**`develop` branch:**
- Require a pull request before merging: ON
- Required approvals: 1
- Require status checks to pass before merging: ON

**Feature branch naming convention:**
```
feature/S1-XX-short-description
fix/S1-XX-short-description
chore/S1-XX-short-description
```

### Action 3: Create PR template

**File:** `/sims-plus/.github/pull_request_template.md` (NEW)

```markdown
## Summary

<!-- What does this PR do? Link to task ID (e.g., S1-02). -->

**Task:** S1-XX

## Changes

<!-- Bullet list of what changed and why. -->

-

## Type of Change

- [ ] Bug fix (non-breaking change fixing an issue)
- [ ] New feature (non-breaking change adding functionality)
- [ ] Breaking change (fix or feature that would break existing functionality)
- [ ] Infrastructure/DevOps
- [ ] Documentation

## Security Checklist

- [ ] No secrets or credentials in code
- [ ] Tenant isolation maintained (tenant_id in all queries)
- [ ] No `from __future__ import annotations` in endpoint files
- [ ] Input validation on all user inputs
- [ ] SQL injection prevention (parameterized queries only)

## Testing

- [ ] Tests added/updated
- [ ] All existing tests pass
- [ ] Manual testing performed

## Screenshots (if UI changes)

<!-- Add screenshots here -->

## Deployment Notes

<!-- Any migration, env var, or config changes required? -->

None.
```

### Action 4: Add SSL directory to `.gitignore`

**File:** `/sims-plus/.gitignore` (MODIFY -- append these lines)

Add the following lines to the end of the existing `.gitignore`:

```gitignore
# SSL certificates (never commit)
docker/nginx/ssl/
*.pem
*.key
*.crt

# Local DNS scripts output
/tmp/
```

### Acceptance Criteria

- [ ] `.env.example` exists at project root with all documented variables
- [ ] `.env.example` does NOT contain real credentials (only placeholder values)
- [ ] `.github/pull_request_template.md` exists
- [ ] `develop` branch exists and is pushed to remote
- [ ] Branch protection configured on `main` (require PR, require CI, no force push)
- [ ] `docker/nginx/ssl/` is in `.gitignore`

### Verification Commands

```bash
# Verify .env.example exists
test -f .env.example && echo "PASS" || echo "FAIL: .env.example missing"

# Verify it contains sims_app_user (not just postgres)
grep -q "sims_app_user" .env.example && echo "PASS" || echo "FAIL: sims_app_user not in .env.example"

# Verify PR template exists
test -f .github/pull_request_template.md && echo "PASS" || echo "FAIL: PR template missing"

# Verify develop branch exists
git branch -r | grep -q "origin/develop" && echo "PASS" || echo "FAIL: develop branch missing"

# Verify SSL dir is gitignored
grep -q "docker/nginx/ssl/" .gitignore && echo "PASS" || echo "FAIL: SSL not in .gitignore"
```

---

## Task S1-02: Docker Environment

- **Priority:** P0 (Day 1-2)
- **Effort:** 2 days
- **Owner:** Track A (DevOps)
- **Dependencies:** S1-01

### What Is Wrong With the Current `docker-compose.yml`

1. **CRITICAL:** Backend connects as `${POSTGRES_USER}` which is `postgres` (superuser). RLS is completely bypassed for superusers.
2. Nginx service is commented out. No wildcard subdomain routing.
3. No healthcheck on backend service.
4. Frontend uses named volumes for `node_modules` and `.next` which can cause stale dependency issues.
5. Missing `command` override for backend (currently relies on Dockerfile CMD).

### Action 1: Rewrite `docker-compose.yml`

**File:** `/sims-plus/docker-compose.yml` (REPLACE ENTIRE FILE)

```yaml
# SIMS Plus - Docker Compose for Local Development
#
# Usage:
#   cp .env.example .env       # First time only
#   docker-compose up -d       # Start all services
#   docker-compose logs -f     # Watch logs
#
# With optional tools:
#   docker-compose --profile tools up -d   # Includes Adminer + MailHog
#
# SECURITY NOTE: Backend connects as sims_app_user (non-superuser).
# RLS policies are enforced. Only Alembic migrations use the superuser.

services:
  # =========================
  # PostgreSQL 16 Database
  # =========================
  db:
    image: postgres:16-alpine
    container_name: sims-plus-db
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
      POSTGRES_DB: ${POSTGRES_DB:-sims_plus}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backend/scripts/init-db.sql:/docker-entrypoint-initdb.d/init-db.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d sims_plus"]
      interval: 5s
      timeout: 5s
      retries: 5

  # =========================
  # Redis 7 Cache
  # =========================
  redis:
    image: redis:7-alpine
    container_name: sims-plus-redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  # =========================
  # Nginx Reverse Proxy
  # Handles wildcard subdomain routing for local development
  # =========================
  nginx:
    image: nginx:1.25-alpine
    container_name: sims-plus-nginx
    restart: unless-stopped
    ports:
      - "80:80"
    volumes:
      - ./docker/nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      backend:
        condition: service_healthy
      frontend:
        condition: service_started

  # =========================
  # Backend (FastAPI)
  # CRITICAL: Connects as sims_app_user (non-superuser, RLS enforced)
  # =========================
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
      target: development
    container_name: sims-plus-backend
    restart: unless-stopped
    environment:
      # CRITICAL: Use sims_app_user (non-superuser). RLS is enforced.
      # DO NOT change this to postgres. Doing so bypasses ALL tenant isolation.
      DATABASE_URL: postgresql+asyncpg://sims_app_user:changeme@db:5432/sims_plus
      # Alembic uses superuser for DDL (CREATE TABLE, ALTER TABLE, etc.)
      ALEMBIC_DATABASE_URL: postgresql+asyncpg://postgres:postgres@db:5432/sims_plus
      REDIS_URL: redis://redis:6379/0
      SECRET_KEY: ${SECRET_KEY:-dev-only-not-for-production-change-me-openssl-rand-base64-64-minimum-64-chars}
      ENVIRONMENT: development
      DEBUG: "true"
      CORS_ORIGINS: '["http://localhost:3000","http://frontend:3000"]'
      # SMTP
      SMTP_HOST: ${SMTP_HOST:-}
      SMTP_PORT: ${SMTP_PORT:-587}
      SMTP_USERNAME: ${SMTP_USERNAME:-}
      SMTP_PASSWORD: ${SMTP_PASSWORD:-}
      SMTP_USE_TLS: ${SMTP_USE_TLS:-false}
      SMTP_START_TLS: ${SMTP_START_TLS:-true}
      SMTP_FROM_EMAIL: ${SMTP_FROM_EMAIL:-noreply@simsplus.io}
      SMTP_FROM_NAME: ${SMTP_FROM_NAME:-SIMS Plus}
      # AWS S3
      AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID:-}
      AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY:-}
      AWS_REGION: ${AWS_REGION:-us-east-1}
      AWS_S3_BUCKET: ${AWS_S3_BUCKET:-sims-plus-files}
    ports:
      - "8000:8000"
    volumes:
      - ./backend:/app
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  # =========================
  # Frontend (Next.js 16)
  # =========================
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      target: development
    container_name: sims-plus-frontend
    restart: unless-stopped
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000/api/v1
      NEXT_PUBLIC_APP_NAME: SIMS Plus
      API_URL: http://backend:8000/api/v1
      NODE_ENV: development
      NEXT_TELEMETRY_DISABLED: "1"
    ports:
      - "3000:3000"
    volumes:
      - ./frontend:/app
      - frontend_node_modules:/app/node_modules
      - frontend_next:/app/.next
    depends_on:
      - backend
    command: npm run dev

  # =========================
  # Adminer (Database GUI) - Development Only
  # Usage: docker-compose --profile tools up -d adminer
  # Access: http://localhost:8080
  # =========================
  adminer:
    image: adminer:latest
    container_name: sims-plus-adminer
    restart: unless-stopped
    profiles:
      - tools
    ports:
      - "8080:8080"
    depends_on:
      - db
    environment:
      ADMINER_DEFAULT_SERVER: db

volumes:
  postgres_data:
    name: sims-plus-postgres
  redis_data:
    name: sims-plus-redis
  frontend_node_modules:
    name: sims-plus-frontend-node-modules
  frontend_next:
    name: sims-plus-frontend-next

networks:
  default:
    name: sims-plus-network
```

### Action 2: Create Nginx local development config

**File:** `/sims-plus/docker/nginx/nginx.conf` (NEW)

Create the directory structure first:
```bash
mkdir -p docker/nginx
```

```nginx
# ============================================================
# SIMS Plus - Nginx Configuration (Local Development)
# ============================================================
# This config handles wildcard subdomain routing for local dev.
#
# How it works:
#   presec.localhost     -> extracts subdomain "presec"
#   achimota.localhost   -> extracts subdomain "achimota"
#   localhost            -> no subdomain (landing page)
#
# The extracted subdomain is passed to backend/frontend as
# the X-Subdomain header.
# ============================================================

upstream frontend {
    server frontend:3000;
}

upstream backend {
    server backend:8000;
}

# ============================================================
# Wildcard subdomain server block
# Matches: presec.localhost, achimota.localhost, etc.
# ============================================================
server {
    listen 80;
    server_name ~^(?P<subdomain>[a-z0-9][a-z0-9-]*[a-z0-9])\.localhost$
                ~^(?P<subdomain>[a-z0-9])\.localhost$;

    # ---- API routes -> FastAPI backend ----
    location /api/ {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Subdomain $subdomain;
        proxy_connect_timeout 10s;
        proxy_read_timeout 60s;
    }

    # ---- Health check -> FastAPI backend ----
    location /health {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Subdomain $subdomain;
    }

    # ---- Swagger docs -> FastAPI backend ----
    location /docs {
        proxy_pass http://backend;
        proxy_set_header Host $host;
    }

    location /redoc {
        proxy_pass http://backend;
        proxy_set_header Host $host;
    }

    location /openapi.json {
        proxy_pass http://backend;
        proxy_set_header Host $host;
    }

    # ---- Next.js HMR (Hot Module Replacement) WebSocket ----
    location /_next/webpack-hmr {
        proxy_pass http://frontend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Subdomain $subdomain;
    }

    # ---- Everything else -> Next.js frontend ----
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Subdomain $subdomain;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    client_max_body_size 10M;
}

# ============================================================
# Bare localhost (no subdomain)
# Matches: localhost (landing page, login, onboarding)
# ============================================================
server {
    listen 80 default_server;
    server_name localhost;

    # ---- API routes -> FastAPI backend ----
    location /api/ {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # ---- Health check -> FastAPI backend ----
    location /health {
        proxy_pass http://backend;
        proxy_set_header Host $host;
    }

    # ---- Swagger docs ----
    location /docs {
        proxy_pass http://backend;
        proxy_set_header Host $host;
    }

    location /redoc {
        proxy_pass http://backend;
        proxy_set_header Host $host;
    }

    location /openapi.json {
        proxy_pass http://backend;
        proxy_set_header Host $host;
    }

    # ---- Next.js HMR WebSocket ----
    location /_next/webpack-hmr {
        proxy_pass http://frontend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }

    # ---- Everything else -> Next.js frontend ----
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    client_max_body_size 10M;
}
```

### Action 3: Create Nginx production config (reference only -- not used locally)

**File:** `/sims-plus/docker/nginx/nginx.production.conf` (NEW)

```nginx
# ============================================================
# SIMS Plus - Nginx Configuration (Production)
# ============================================================
# This file is a REFERENCE for production deployment.
# It is NOT mounted by docker-compose.yml.
# Deploy this to the production Nginx server or K8s ingress.
# ============================================================

upstream frontend_prod {
    server frontend:3000;
    keepalive 32;
}

upstream backend_prod {
    server backend:8000;
    keepalive 32;
}

# Rate limiting zones
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=100r/s;
limit_req_zone $binary_remote_addr zone=auth_limit:10m rate=5r/m;

# Redirect HTTP -> HTTPS
server {
    listen 80;
    server_name *.simsplus.io simsplus.io;
    return 301 https://$host$request_uri;
}

# Wildcard subdomain HTTPS
server {
    listen 443 ssl http2;
    server_name ~^(?P<subdomain>[a-z0-9][a-z0-9-]*[a-z0-9])\.simsplus\.io$
                ~^(?P<subdomain>[a-z0-9])\.simsplus\.io$;

    ssl_certificate     /etc/nginx/ssl/origin.pem;
    ssl_certificate_key /etc/nginx/ssl/origin-key.pem;

    # Security headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header Permissions-Policy "geolocation=(), microphone=(), camera=(), payment=(self)" always;

    # Auth endpoints -- strict rate limit
    location /api/v1/auth/ {
        limit_req zone=auth_limit burst=3 nodelay;
        proxy_pass http://backend_prod;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Subdomain $subdomain;
    }

    # General API -- standard rate limit
    location /api/ {
        limit_req zone=api_limit burst=20 nodelay;
        proxy_pass http://backend_prod;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Subdomain $subdomain;
        proxy_connect_timeout 10s;
        proxy_read_timeout 60s;
    }

    # Health check (no rate limit)
    location /health {
        proxy_pass http://backend_prod;
        proxy_set_header Host $host;
    }

    # Frontend
    location / {
        proxy_pass http://frontend_prod;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Subdomain $subdomain;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    client_max_body_size 10M;
}

# Bare domain redirect to app
server {
    listen 443 ssl http2;
    server_name simsplus.io www.simsplus.io;
    ssl_certificate     /etc/nginx/ssl/origin.pem;
    ssl_certificate_key /etc/nginx/ssl/origin-key.pem;
    location / {
        return 302 https://app.simsplus.io;
    }
}
```

### Action 4: Update frontend Dockerfile to Node 22

**File:** `/sims-plus/frontend/Dockerfile` (MODIFY)

Replace ALL occurrences of `node:20-alpine` with `node:22-alpine`. There are 4 occurrences:

```dockerfile
# SIMS Plus Frontend - Dockerfile
# Multi-stage build for Next.js 16

# =========================
# Dependencies Stage
# =========================
FROM node:22-alpine AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app

# Copy package files
COPY package.json package-lock.json* ./
RUN npm ci

# =========================
# Development Stage
# =========================
FROM node:22-alpine AS development
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

ENV NODE_ENV=development
ENV NEXT_TELEMETRY_DISABLED=1

EXPOSE 3000
CMD ["npm", "run", "dev"]

# =========================
# Builder Stage
# =========================
FROM node:22-alpine AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build

# =========================
# Production Stage
# =========================
FROM node:22-alpine AS production
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Create non-root user
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copy built files
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
```

### Acceptance Criteria

- [ ] `docker-compose up` starts all 5 services (db, redis, nginx, backend, frontend) within 2 minutes
- [ ] Backend container environment shows `DATABASE_URL` containing `sims_app_user` (NOT `postgres`)
- [ ] `curl http://presec.localhost/api/v1/health` returns health status (via Nginx)
- [ ] `curl http://localhost/health` works (bare localhost via Nginx)
- [ ] `curl http://localhost:8000/health` works (direct backend access)
- [ ] `curl http://localhost:3000` returns the Next.js page (direct frontend access)
- [ ] Nginx container starts without configuration errors

### Verification Commands

```bash
# Start all services
docker-compose up -d

# Wait for healthy backend
docker-compose exec backend curl -f http://localhost:8000/health

# Verify backend uses sims_app_user
docker-compose exec backend env | grep DATABASE_URL
# Expected: DATABASE_URL=postgresql+asyncpg://sims_app_user:changeme@db:5432/sims_plus

# Test Nginx wildcard routing
curl -s http://presec.localhost/health
# Expected: {"status":"healthy",...}

# Test bare localhost
curl -s http://localhost/health
# Expected: {"status":"healthy",...}

# Verify Nginx passes X-Subdomain header (check backend logs)
docker-compose logs backend | grep "X-Subdomain"
```

---

## Task S1-03: FastAPI Backend Verification and Fixes

- **Priority:** P1 (Day 2-3)
- **Effort:** 1 day
- **Owner:** Track B (Backend 1)
- **Dependencies:** S1-02

### What Is Wrong

1. **CORS:** `main.py` uses `allow_origins=settings.CORS_ORIGINS` (a static list). This does not support wildcard subdomains like `presec.localhost:3000`. The `CORS_ALLOW_SUBDOMAIN_PATTERN` setting exists in `config.py` but is never used.
2. **`get_db()` silently proceeds without tenant context** (Finding F3 from unified plan). On non-public routes, if `tenant_id` is `None`, the function should raise HTTP 400 -- not silently proceed with no RLS filtering.

### Action 1: Fix CORS in `main.py` -- use `allow_origin_regex`

**File:** `/sims-plus/backend/app/main.py` (MODIFY)

Replace the CORS middleware block (lines 60-81 in current file):

**OLD:**
```python
# CORS middleware (runs first - must allow preflight requests)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Subdomain",
        "X-Request-ID",
        "Accept",
        "Accept-Language",
        "Origin",
    ],
    expose_headers=[
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
        "X-Request-ID",
    ],
)
```

**NEW:**
```python
# CORS middleware (runs first - must allow preflight requests)
# Uses allow_origin_regex to support wildcard subdomains.
# This matches: http://localhost:3000, http://presec.localhost:3000,
# https://presec.simsplus.io, etc.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # Explicit origins (localhost:3000, etc.)
    allow_origin_regex=r"https?://[a-z0-9][a-z0-9-]*\.localhost(:\d+)?|https?://[a-z0-9][a-z0-9-]*\.simsplus\.io",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Subdomain",
        "X-Request-ID",
        "Accept",
        "Accept-Language",
        "Origin",
    ],
    expose_headers=[
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
        "X-Request-ID",
    ],
)
```

### Action 2: Fix `get_db()` to reject missing tenant context on non-public routes

**File:** `/sims-plus/backend/app/api/deps.py` (MODIFY)

Replace the `get_db` function (lines 26-59 in current file):

**OLD:**
```python
async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session dependency with tenant RLS context.

    This dependency:
    1. Creates a database session
    2. Sets the tenant context for Row-Level Security (if available)
    3. Yields the session for use in the endpoint
    4. Commits or rolls back based on success/failure

    The tenant context is extracted from request.state (set by TenantMiddleware).
    """
    async with async_session_maker() as session:
        try:
            # Set tenant context for RLS if available
            tenant_id = getattr(request.state, "tenant_id", None)
            if tenant_id:
                await session.execute(
                    text("SELECT set_tenant_context(:tenant_id)"),
                    {"tenant_id": str(tenant_id)},
                )

            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            # Clear tenant context
            try:
                await session.execute(text("SELECT clear_tenant_context()"))
            except Exception:
                pass  # Ignore errors during cleanup
            await session.close()
```

**NEW:**
```python
async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session dependency with tenant RLS context.

    This dependency:
    1. Creates a database session
    2. Sets the tenant context for Row-Level Security
    3. Yields the session for use in the endpoint
    4. Commits or rolls back based on success/failure

    SECURITY: Raises HTTP 400 if tenant context is missing.
    Use get_unscoped_db() for platform-level operations that
    intentionally operate without tenant context.
    """
    async with async_session_maker() as session:
        try:
            tenant_id = getattr(request.state, "tenant_id", None)

            if not tenant_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Tenant context required. Access via school subdomain.",
                )

            await session.execute(
                text("SELECT set_tenant_context(:tenant_id)"),
                {"tenant_id": str(tenant_id)},
            )

            yield session
            await session.commit()
        except HTTPException:
            raise
        except Exception:
            await session.rollback()
            raise
        finally:
            try:
                await session.execute(text("SELECT clear_tenant_context()"))
            except Exception:
                pass
            await session.close()


async def get_unscoped_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session WITHOUT tenant context.

    Use this ONLY for operations that intentionally bypass tenant scoping:
    - Onboarding (creating new tenants)
    - Platform admin operations
    - Tenant lookup by subdomain

    WARNING: Data returned is NOT filtered by tenant. The caller is
    responsible for ensuring proper access control.
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

Also add the type alias below the existing `DatabaseSession` alias:

```python
# Type alias for database session dependency (tenant-scoped, RLS enforced)
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]

# Type alias for unscoped database session (NO tenant context, NO RLS)
# Use ONLY for platform-level operations (onboarding, tenant lookup, etc.)
UnscopedDatabaseSession = Annotated[AsyncSession, Depends(get_unscoped_db)]
```

### Action 3: Add SECRET_KEY length validation to `config.py`

**File:** `/sims-plus/backend/app/config.py` (MODIFY)

Add a field validator after the existing `parse_cors_origins` validator (after line 76 in current file):

```python
    @field_validator("SECRET_KEY", mode="after")
    @classmethod
    def validate_secret_key_length(cls, v: str) -> str:
        """Validate SECRET_KEY is at least 32 chars (64 in production)."""
        if len(v) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters. "
                "Generate with: openssl rand -base64 64"
            )
        return v
```

Also add the `ALEMBIC_DATABASE_URL` setting to the Database section (after `DATABASE_MAX_OVERFLOW`):

```python
    # Alembic uses superuser for DDL operations
    ALEMBIC_DATABASE_URL: str | None = None
```

### Acceptance Criteria

- [ ] `curl -H "Origin: http://presec.localhost:3000" -X OPTIONS http://localhost:8000/api/v1/health` returns CORS headers with `Access-Control-Allow-Origin: http://presec.localhost:3000`
- [ ] `curl -H "Origin: http://evil.com" -X OPTIONS http://localhost:8000/api/v1/health` does NOT return `Access-Control-Allow-Origin: http://evil.com`
- [ ] API endpoints that use `get_db()` return HTTP 400 when accessed without tenant context
- [ ] `get_unscoped_db()` is available as `UnscopedDatabaseSession` for platform operations
- [ ] Application refuses to start if `SECRET_KEY` is shorter than 32 characters

### Verification Commands

```bash
# Test CORS allows subdomain origins
curl -s -o /dev/null -w "%{http_code}" \
  -H "Origin: http://presec.localhost:3000" \
  -H "Access-Control-Request-Method: GET" \
  -X OPTIONS \
  http://localhost:8000/api/v1/students
# Expected: 200 (with CORS headers)

# Test CORS rejects evil origins
curl -s -I \
  -H "Origin: http://evil.example.com" \
  -H "Access-Control-Request-Method: GET" \
  -X OPTIONS \
  http://localhost:8000/api/v1/students 2>&1 | grep -i "access-control-allow-origin"
# Expected: no Access-Control-Allow-Origin header (or not matching evil.example.com)

# Test get_db rejects missing tenant
curl -s http://localhost:8000/api/v1/students
# Expected: {"detail":"Tenant context required. Access via school subdomain."}
```

---

## Task S1-04: Next.js 16 Frontend Verification

- **Priority:** P1 (Day 2-3)
- **Effort:** 2 days
- **Owner:** Track D (Frontend)
- **Dependencies:** S1-02

### What Is Wrong

1. `next.config.ts` is missing `serverActions.bodySizeLimit` (needed for file uploads via server actions).
2. `next.config.ts` is missing `images.remotePatterns` for MinIO local development.
3. `frontend/lib/api.ts` does not automatically read the subdomain from Next.js headers/cookies. Server actions must manually pass `subdomain` every time, which is error-prone.
4. `frontend/Dockerfile` uses Node 20 (fixed in S1-02 Action 4 above).

### Action 1: Update `next.config.ts`

**File:** `/sims-plus/frontend/next.config.ts` (MODIFY)

Replace the entire file:

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Output standalone for Docker deployment
  output: "standalone",

  // Server Actions configuration
  experimental: {
    serverActions: {
      bodySizeLimit: "2mb",
    },
  },

  // Image optimization
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "**.simsplus.io",
      },
      {
        protocol: "https",
        hostname: "**.amazonaws.com",
      },
      {
        // MinIO local development
        protocol: "http",
        hostname: "minio",
        port: "9000",
      },
      {
        // MinIO via localhost
        protocol: "http",
        hostname: "localhost",
        port: "9000",
      },
    ],
  },

  // Security headers
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          {
            key: "X-Frame-Options",
            value: "DENY",
          },
          {
            key: "X-Content-Type-Options",
            value: "nosniff",
          },
          {
            key: "Referrer-Policy",
            value: "strict-origin-when-cross-origin",
          },
          {
            key: "X-XSS-Protection",
            value: "1; mode=block",
          },
          {
            key: "Strict-Transport-Security",
            value: "max-age=31536000; includeSubDomains",
          },
          {
            key: "Permissions-Policy",
            value:
              "geolocation=(), microphone=(), camera=(), payment=(self)",
          },
          {
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
              "style-src 'self' 'unsafe-inline'",
              "img-src 'self' https://*.simsplus.io https://*.amazonaws.com data: blob:",
              "font-src 'self' data:",
              "connect-src 'self' http://localhost:8000 https://*.simsplus.io",
              "frame-ancestors 'none'",
              "base-uri 'self'",
              "form-action 'self'",
            ].join("; "),
          },
        ],
      },
    ];
  },
};

export default nextConfig;
```

### Action 2: Create auto-subdomain server-side API helpers

**File:** `/sims-plus/frontend/lib/server-api.ts` (NEW)

This file wraps the existing `lib/api.ts` and automatically injects the subdomain and auth token from the server context. Server actions should import from this file.

```typescript
/**
 * SIMS Plus - Server-Side API Helpers
 *
 * Automatically injects subdomain and auth token from the request context.
 * Use this in Server Actions instead of importing from lib/api.ts directly.
 *
 * Usage in a server action:
 *   import { serverGet, serverPost } from "@/lib/server-api";
 *   const students = await serverGet<Student[]>("/students");
 */
"use server";

import { cookies, headers } from "next/headers";
import { apiFetch } from "@/lib/api";

/**
 * Get subdomain from the current server request context.
 * Checks headers first (set by proxy.ts), then falls back to cookie.
 */
async function getSubdomain(): Promise<string | undefined> {
  const headerStore = await headers();
  const cookieStore = await cookies();

  // proxy.ts sets x-subdomain header
  const fromHeader = headerStore.get("x-subdomain");
  if (fromHeader) return fromHeader;

  // Fallback to cookie (set by proxy.ts response)
  const fromCookie = cookieStore.get("x-subdomain")?.value;
  if (fromCookie) return fromCookie;

  return undefined;
}

/**
 * Get access token from cookies.
 */
async function getToken(): Promise<string | undefined> {
  const cookieStore = await cookies();
  return cookieStore.get("access_token")?.value;
}

/**
 * Server-side GET request with automatic subdomain and token injection.
 */
export async function serverGet<T>(endpoint: string): Promise<T> {
  const [token, subdomain] = await Promise.all([getToken(), getSubdomain()]);
  return apiFetch<T>(endpoint, {
    method: "GET",
    token,
    subdomain,
  });
}

/**
 * Server-side POST request with automatic subdomain and token injection.
 */
export async function serverPost<T>(
  endpoint: string,
  data?: unknown
): Promise<T> {
  const [token, subdomain] = await Promise.all([getToken(), getSubdomain()]);
  return apiFetch<T>(endpoint, {
    method: "POST",
    body: data ? JSON.stringify(data) : undefined,
    token,
    subdomain,
  });
}

/**
 * Server-side PUT request with automatic subdomain and token injection.
 */
export async function serverPut<T>(
  endpoint: string,
  data?: unknown
): Promise<T> {
  const [token, subdomain] = await Promise.all([getToken(), getSubdomain()]);
  return apiFetch<T>(endpoint, {
    method: "PUT",
    body: data ? JSON.stringify(data) : undefined,
    token,
    subdomain,
  });
}

/**
 * Server-side PATCH request with automatic subdomain and token injection.
 */
export async function serverPatch<T>(
  endpoint: string,
  data?: unknown
): Promise<T> {
  const [token, subdomain] = await Promise.all([getToken(), getSubdomain()]);
  return apiFetch<T>(endpoint, {
    method: "PATCH",
    body: data ? JSON.stringify(data) : undefined,
    token,
    subdomain,
  });
}

/**
 * Server-side DELETE request with automatic subdomain and token injection.
 */
export async function serverDelete<T>(endpoint: string): Promise<T> {
  const [token, subdomain] = await Promise.all([getToken(), getSubdomain()]);
  return apiFetch<T>(endpoint, {
    method: "DELETE",
    token,
    subdomain,
  });
}
```

### Acceptance Criteria

- [ ] `http://presec.localhost:3000` loads the Next.js app
- [ ] Subdomain is extracted by `proxy.ts` and set as `x-subdomain` cookie
- [ ] `next.config.ts` includes `serverActions.bodySizeLimit: "2mb"`
- [ ] `next.config.ts` includes MinIO remote pattern for local dev
- [ ] Security headers (X-Frame-Options, CSP, etc.) present in responses
- [ ] `lib/server-api.ts` exists and auto-injects subdomain

### Verification Commands

```bash
# Check security headers
curl -s -I http://localhost:3000 | grep -E "(X-Frame|X-Content-Type|Referrer-Policy|Content-Security)"
# Expected: All 4 headers present

# Check subdomain cookie is set (via Nginx with subdomain)
curl -s -c - http://presec.localhost/ 2>/dev/null | grep "x-subdomain"
# Expected: x-subdomain cookie with value "presec"

# Verify server-api.ts exists
test -f frontend/lib/server-api.ts && echo "PASS" || echo "FAIL"
```

---

## Task S1-05: PostgreSQL Database Setup

- **Priority:** P0 (Day 1-3)
- **Effort:** 1.5 days
- **Owner:** Track B (Backend 1)
- **Dependencies:** S1-02

### What Is Wrong With the Current `init-db.sql`

The current file has multiple critical issues:

1. **Does NOT create `sims_app_user` role.** The backend connects as `postgres` superuser, bypassing all RLS.
2. **Creates `current_tenant_id()` instead of `get_current_tenant_id()`.** The codebase standardized on `get_current_tenant_id()` (see Alembic migrations and MEMORY.md).
3. **Does not create `set_tenant_context()` or `clear_tenant_context()` functions.** These are called by `deps.py` and `tenant.py`.
4. **Unconditionally runs `CREATE DATABASE sims_plus_test`** which fails if the database already exists.
5. **Does not set up extensions on the test database.**
6. **Does not grant permissions to `sims_app_user` on the test database.**

### Action 1: Rewrite `init-db.sql`

**File:** `/sims-plus/backend/scripts/init-db.sql` (REPLACE ENTIRE FILE)

```sql
-- ============================================================
-- SIMS Plus - Database Initialization Script
-- ============================================================
-- This script runs ONCE on first PostgreSQL container startup
-- (via Docker's /docker-entrypoint-initdb.d/ mechanism).
--
-- It creates:
--   1. Test database (sims_plus_test)
--   2. Required PostgreSQL extensions
--   3. Application user (sims_app_user) -- NON-SUPERUSER
--   4. RLS helper functions
--   5. Grants for sims_app_user
--
-- CRITICAL: The application MUST connect as sims_app_user,
-- NOT as postgres. RLS policies are only enforced for
-- non-superuser connections.
-- ============================================================

-- ============================================================
-- 1. Create test database
-- ============================================================
-- Note: In docker-entrypoint-initdb.d scripts, we're already
-- connected to the POSTGRES_DB (sims_plus) as the superuser.
CREATE DATABASE sims_plus_test;

-- ============================================================
-- 2. Enable extensions on main database
-- ============================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- 3. Create application user (NON-SUPERUSER)
-- ============================================================
-- CRITICAL: This user has RLS enforced. The application backend
-- MUST connect as this user. Only Alembic migrations should
-- use the postgres superuser.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM pg_catalog.pg_roles WHERE rolname = 'sims_app_user'
    ) THEN
        CREATE ROLE sims_app_user WITH LOGIN PASSWORD 'changeme';
    END IF;
END $$;

-- Grant connect on main database
GRANT CONNECT ON DATABASE sims_plus TO sims_app_user;
GRANT USAGE ON SCHEMA public TO sims_app_user;

-- Grant connect on test database
GRANT CONNECT ON DATABASE sims_plus_test TO sims_app_user;

-- Default privileges for tables created in the FUTURE by postgres
-- (i.e., tables created by Alembic migrations running as superuser)
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO sims_app_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO sims_app_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT EXECUTE ON FUNCTIONS TO sims_app_user;

-- ============================================================
-- 4. RLS helper functions (main database)
-- ============================================================
-- IMPORTANT: Only use get_current_tenant_id() in RLS policies.
-- Do NOT create current_tenant_id() -- the codebase has
-- standardized on get_current_tenant_id().

-- Set tenant context (called at start of each request)
CREATE OR REPLACE FUNCTION set_tenant_context(tenant_uuid UUID)
RETURNS VOID AS $$
BEGIN
    PERFORM set_config('app.current_tenant_id', tenant_uuid::TEXT, false);
END;
$$ LANGUAGE plpgsql;

-- Clear tenant context (called at end of each request)
CREATE OR REPLACE FUNCTION clear_tenant_context()
RETURNS VOID AS $$
BEGIN
    PERFORM set_config('app.current_tenant_id', '', false);
END;
$$ LANGUAGE plpgsql;

-- Get current tenant ID (used in RLS policies)
-- Returns NULL if no context is set (which means RLS will DENY access
-- because tenant_id = NULL is always false for non-null tenant_id columns).
CREATE OR REPLACE FUNCTION get_current_tenant_id()
RETURNS UUID AS $$
DECLARE
    tenant_str TEXT;
    tenant_uuid UUID;
BEGIN
    tenant_str := current_setting('app.current_tenant_id', true);

    -- No context set -> return NULL (RLS will deny access)
    IF tenant_str IS NULL OR tenant_str = '' THEN
        RETURN NULL;
    END IF;

    -- Try to cast to UUID
    BEGIN
        tenant_uuid := tenant_str::UUID;
        RETURN tenant_uuid;
    EXCEPTION WHEN OTHERS THEN
        RETURN NULL;
    END;
END;
$$ LANGUAGE plpgsql STABLE;

-- Grant function execution to sims_app_user
GRANT EXECUTE ON FUNCTION set_tenant_context(UUID) TO sims_app_user;
GRANT EXECUTE ON FUNCTION clear_tenant_context() TO sims_app_user;
GRANT EXECUTE ON FUNCTION get_current_tenant_id() TO sims_app_user;

-- ============================================================
-- 5. Set up test database
-- ============================================================
\c sims_plus_test

-- Enable extensions on test database
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Grant schema usage to sims_app_user
GRANT USAGE ON SCHEMA public TO sims_app_user;

-- Default privileges for test database
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO sims_app_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO sims_app_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT EXECUTE ON FUNCTIONS TO sims_app_user;

-- Replicate RLS helper functions in test database
CREATE OR REPLACE FUNCTION set_tenant_context(tenant_uuid UUID)
RETURNS VOID AS $$
BEGIN
    PERFORM set_config('app.current_tenant_id', tenant_uuid::TEXT, false);
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION clear_tenant_context()
RETURNS VOID AS $$
BEGIN
    PERFORM set_config('app.current_tenant_id', '', false);
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION get_current_tenant_id()
RETURNS UUID AS $$
DECLARE
    tenant_str TEXT;
    tenant_uuid UUID;
BEGIN
    tenant_str := current_setting('app.current_tenant_id', true);

    IF tenant_str IS NULL OR tenant_str = '' THEN
        RETURN NULL;
    END IF;

    BEGIN
        tenant_uuid := tenant_str::UUID;
        RETURN tenant_uuid;
    EXCEPTION WHEN OTHERS THEN
        RETURN NULL;
    END;
END;
$$ LANGUAGE plpgsql STABLE;

-- Grant functions to sims_app_user on test database
GRANT EXECUTE ON FUNCTION set_tenant_context(UUID) TO sims_app_user;
GRANT EXECUTE ON FUNCTION clear_tenant_context() TO sims_app_user;
GRANT EXECUTE ON FUNCTION get_current_tenant_id() TO sims_app_user;

-- ============================================================
-- 6. Switch back to main database and confirm
-- ============================================================
\c sims_plus

DO $$
BEGIN
    RAISE NOTICE '============================================================';
    RAISE NOTICE 'SIMS Plus database initialization complete.';
    RAISE NOTICE '';
    RAISE NOTICE 'Created:';
    RAISE NOTICE '  - Database: sims_plus_test';
    RAISE NOTICE '  - Role: sims_app_user (non-superuser, RLS enforced)';
    RAISE NOTICE '  - Functions: set_tenant_context(), clear_tenant_context(),';
    RAISE NOTICE '               get_current_tenant_id()';
    RAISE NOTICE '';
    RAISE NOTICE 'IMPORTANT: Backend MUST connect as sims_app_user.';
    RAISE NOTICE '           Only Alembic migrations use the postgres superuser.';
    RAISE NOTICE '============================================================';
END $$;
```

### Action 2: Verify the old `current_tenant_id()` is NOT present

After running `docker-compose up`, connect to the database and verify:

```bash
docker-compose exec db psql -U postgres -d sims_plus -c "
    SELECT proname FROM pg_proc
    WHERE proname IN ('current_tenant_id', 'get_current_tenant_id', 'set_tenant_context', 'clear_tenant_context')
    ORDER BY proname;
"
```

**Expected output:**
```
        proname
------------------------
 clear_tenant_context
 get_current_tenant_id
 set_tenant_context
(3 rows)
```

If `current_tenant_id` appears in the output, the old function was not removed. You need to destroy the Docker volume and recreate:

```bash
docker-compose down -v   # -v removes volumes (destroys data)
docker-compose up -d
```

### Acceptance Criteria

- [ ] `sims_app_user` role exists after `docker-compose up`
- [ ] `sims_app_user` can connect to `sims_plus` database
- [ ] `sims_app_user` can connect to `sims_plus_test` database
- [ ] `get_current_tenant_id()` function exists in both databases
- [ ] `set_tenant_context()` function exists in both databases
- [ ] `clear_tenant_context()` function exists in both databases
- [ ] `current_tenant_id()` function does NOT exist (only `get_current_tenant_id`)
- [ ] All three functions are executable by `sims_app_user`
- [ ] `uuid-ossp` extension exists in both databases
- [ ] `pgcrypto` extension exists in both databases

### Verification Commands

```bash
# Verify sims_app_user exists
docker-compose exec db psql -U postgres -c "SELECT rolname, rolsuper FROM pg_roles WHERE rolname = 'sims_app_user';"
# Expected: sims_app_user | f   (f = not superuser)

# Verify sims_app_user can connect
docker-compose exec db psql -U sims_app_user -d sims_plus -c "SELECT 1;"
# Expected: ?column? = 1

# Verify functions exist (main DB)
docker-compose exec db psql -U postgres -d sims_plus -c "
    SELECT proname FROM pg_proc
    WHERE proname IN ('current_tenant_id', 'get_current_tenant_id', 'set_tenant_context', 'clear_tenant_context')
    ORDER BY proname;
"
# Expected: clear_tenant_context, get_current_tenant_id, set_tenant_context (3 rows)
# MUST NOT include current_tenant_id

# Verify functions exist (test DB)
docker-compose exec db psql -U postgres -d sims_plus_test -c "
    SELECT proname FROM pg_proc
    WHERE proname IN ('get_current_tenant_id', 'set_tenant_context', 'clear_tenant_context')
    ORDER BY proname;
"
# Expected: 3 rows

# Verify extensions (main DB)
docker-compose exec db psql -U postgres -d sims_plus -c "SELECT extname FROM pg_extension WHERE extname IN ('uuid-ossp', 'pgcrypto');"
# Expected: uuid-ossp, pgcrypto

# Verify extensions (test DB)
docker-compose exec db psql -U postgres -d sims_plus_test -c "SELECT extname FROM pg_extension WHERE extname IN ('uuid-ossp', 'pgcrypto');"
# Expected: uuid-ossp, pgcrypto

# Verify sims_app_user can execute functions
docker-compose exec db psql -U sims_app_user -d sims_plus -c "
    SELECT set_tenant_context('00000000-0000-0000-0000-000000000001'::UUID);
    SELECT get_current_tenant_id();
    SELECT clear_tenant_context();
"
# Expected: set_tenant_context returns void, get_current_tenant_id returns the UUID, clear returns void

# Verify RLS works: NULL tenant context returns no rows
docker-compose exec db psql -U sims_app_user -d sims_plus -c "
    SELECT clear_tenant_context();
    SELECT get_current_tenant_id();
"
# Expected: get_current_tenant_id returns NULL
```

---

## Task S1-06: CI/CD Pipeline

- **Priority:** P1 (Day 3-5)
- **Effort:** 2 days
- **Owner:** Track A (DevOps)
- **Dependencies:** S1-01

### What Is Wrong With Current CI

1. **Backend CI** uses `postgres` superuser for tests. Should create `sims_app_user` so RLS is tested.
2. **Backend CI** does not run a migration test (apply all migrations on a clean DB).
3. **Backend CI** does not check for the forbidden `from __future__ import annotations` in endpoint files.
4. **Frontend CI** uses Node 20. Must use Node 22 for Next.js 16 compatibility.
5. **Frontend CI** `SECRET_KEY` in tests is too short (will fail with new validation).

### Action 1: Rewrite `backend-ci.yml`

**File:** `/sims-plus/.github/workflows/backend-ci.yml` (REPLACE ENTIRE FILE)

```yaml
# SIMS Plus Backend CI Pipeline
name: Backend CI

on:
  push:
    branches: [main, develop]
    paths:
      - 'backend/**'
      - '.github/workflows/backend-ci.yml'
  pull_request:
    branches: [main, develop]
    paths:
      - 'backend/**'
      - '.github/workflows/backend-ci.yml'

defaults:
  run:
    working-directory: backend

jobs:
  # ============================
  # Lint + Type Check
  # ============================
  lint:
    name: Lint & Type Check
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'

      - name: Install linting tools
        run: |
          python -m pip install --upgrade pip
          pip install ruff black isort mypy

      - name: Install type stubs
        run: pip install -r requirements-dev.txt

      - name: Run Ruff
        run: ruff check .

      - name: Check formatting with Black
        run: black --check .

      - name: Check imports with isort
        run: isort --check-only .

      # CRITICAL: Detect the forbidden import that breaks 204 responses
      - name: Check for forbidden __future__ annotations in endpoints
        run: |
          if grep -r "from __future__ import annotations" app/api/v1/endpoints/; then
            echo ""
            echo "ERROR: 'from __future__ import annotations' found in endpoint files!"
            echo "This breaks FastAPI 204 responses (causes AssertionError)."
            echo "Remove this import from all files under app/api/v1/endpoints/"
            exit 1
          fi
          echo "PASS: No forbidden __future__ imports in endpoint files."

  # ============================
  # Test
  # ============================
  test:
    name: Test
    runs-on: ubuntu-latest
    needs: lint

    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: sims_plus_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements-dev.txt

      # Create sims_app_user and RLS helper functions in test DB
      # This mirrors what init-db.sql does in Docker
      - name: Set up test database (sims_app_user + RLS functions)
        env:
          PGHOST: localhost
          PGPORT: 5432
          PGUSER: postgres
          PGPASSWORD: postgres
          PGDATABASE: sims_plus_test
        run: |
          # Create sims_app_user role
          psql -c "
            DO \$\$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'sims_app_user') THEN
                    CREATE ROLE sims_app_user WITH LOGIN PASSWORD 'changeme';
                END IF;
            END \$\$;
          "

          # Grant permissions
          psql -c "GRANT CONNECT ON DATABASE sims_plus_test TO sims_app_user;"
          psql -c "GRANT USAGE ON SCHEMA public TO sims_app_user;"
          psql -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO sims_app_user;"
          psql -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO sims_app_user;"
          psql -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO sims_app_user;"

          # Create extensions
          psql -c "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";"
          psql -c "CREATE EXTENSION IF NOT EXISTS \"pgcrypto\";"

          # Create RLS helper functions
          psql -c "
            CREATE OR REPLACE FUNCTION set_tenant_context(tenant_uuid UUID)
            RETURNS VOID AS \$\$
            BEGIN
                PERFORM set_config('app.current_tenant_id', tenant_uuid::TEXT, false);
            END;
            \$\$ LANGUAGE plpgsql;

            CREATE OR REPLACE FUNCTION clear_tenant_context()
            RETURNS VOID AS \$\$
            BEGIN
                PERFORM set_config('app.current_tenant_id', '', false);
            END;
            \$\$ LANGUAGE plpgsql;

            CREATE OR REPLACE FUNCTION get_current_tenant_id()
            RETURNS UUID AS \$\$
            DECLARE
                tenant_str TEXT;
                tenant_uuid UUID;
            BEGIN
                tenant_str := current_setting('app.current_tenant_id', true);
                IF tenant_str IS NULL OR tenant_str = '' THEN
                    RETURN NULL;
                END IF;
                BEGIN
                    tenant_uuid := tenant_str::UUID;
                    RETURN tenant_uuid;
                EXCEPTION WHEN OTHERS THEN
                    RETURN NULL;
                END;
            END;
            \$\$ LANGUAGE plpgsql STABLE;
          "

          # Grant functions to sims_app_user
          psql -c "GRANT EXECUTE ON FUNCTION set_tenant_context(UUID) TO sims_app_user;"
          psql -c "GRANT EXECUTE ON FUNCTION clear_tenant_context() TO sims_app_user;"
          psql -c "GRANT EXECUTE ON FUNCTION get_current_tenant_id() TO sims_app_user;"

          echo "Test database setup complete."

      - name: Run tests
        env:
          # Tests use sims_app_user so RLS is enforced during tests
          DATABASE_URL: postgresql+asyncpg://sims_app_user:changeme@localhost:5432/sims_plus_test
          # Admin URL for test setup (DDL operations that need superuser)
          DATABASE_ADMIN_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/sims_plus_test
          REDIS_URL: redis://localhost:6379/0
          SECRET_KEY: ci-test-secret-key-minimum-32-characters-for-validation
          ENVIRONMENT: testing
        run: pytest --cov=app --cov-report=xml -x

      - name: Upload coverage
        if: always()
        uses: codecov/codecov-action@v4
        with:
          file: backend/coverage.xml
          flags: backend
        continue-on-error: true

  # ============================
  # Migration Test
  # ============================
  migration-test:
    name: Migration Test
    runs-on: ubuntu-latest
    needs: lint

    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: sims_plus_migration_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Create extensions and RLS functions
        env:
          PGHOST: localhost
          PGPORT: 5432
          PGUSER: postgres
          PGPASSWORD: postgres
          PGDATABASE: sims_plus_migration_test
        run: |
          psql -c "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";"
          psql -c "CREATE EXTENSION IF NOT EXISTS \"pgcrypto\";"
          psql -c "
            CREATE OR REPLACE FUNCTION set_tenant_context(tenant_uuid UUID)
            RETURNS VOID AS \$\$ BEGIN PERFORM set_config('app.current_tenant_id', tenant_uuid::TEXT, false); END; \$\$ LANGUAGE plpgsql;

            CREATE OR REPLACE FUNCTION clear_tenant_context()
            RETURNS VOID AS \$\$ BEGIN PERFORM set_config('app.current_tenant_id', '', false); END; \$\$ LANGUAGE plpgsql;

            CREATE OR REPLACE FUNCTION get_current_tenant_id()
            RETURNS UUID AS \$\$
            DECLARE tenant_str TEXT; tenant_uuid UUID;
            BEGIN
                tenant_str := current_setting('app.current_tenant_id', true);
                IF tenant_str IS NULL OR tenant_str = '' THEN RETURN NULL; END IF;
                BEGIN tenant_uuid := tenant_str::UUID; RETURN tenant_uuid;
                EXCEPTION WHEN OTHERS THEN RETURN NULL; END;
            END; \$\$ LANGUAGE plpgsql STABLE;
          "

      - name: Run all migrations on clean database
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/sims_plus_migration_test
          SECRET_KEY: ci-test-secret-key-minimum-32-characters-for-validation
          ENVIRONMENT: testing
        run: |
          alembic upgrade head
          echo "All migrations applied successfully."

      - name: Verify migration can downgrade
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/sims_plus_migration_test
          SECRET_KEY: ci-test-secret-key-minimum-32-characters-for-validation
          ENVIRONMENT: testing
        run: |
          alembic downgrade -1
          alembic upgrade head
          echo "Migration downgrade/upgrade cycle successful."

  # ============================
  # Build Docker Image
  # ============================
  build:
    name: Build Docker Image
    runs-on: ubuntu-latest
    needs: [test, migration-test]
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'

    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build image
        uses: docker/build-push-action@v5
        with:
          context: ./backend
          push: false
          tags: sims-plus-backend:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

### Action 2: Rewrite `frontend-ci.yml`

**File:** `/sims-plus/.github/workflows/frontend-ci.yml` (REPLACE ENTIRE FILE)

```yaml
# SIMS Plus Frontend CI Pipeline
name: Frontend CI

on:
  push:
    branches: [main, develop]
    paths:
      - 'frontend/**'
      - '.github/workflows/frontend-ci.yml'
  pull_request:
    branches: [main, develop]
    paths:
      - 'frontend/**'
      - '.github/workflows/frontend-ci.yml'

defaults:
  run:
    working-directory: frontend

jobs:
  # ============================
  # Lint & Type Check
  # ============================
  lint:
    name: Lint & Type Check
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        run: npm ci

      - name: Run ESLint
        run: npm run lint

      - name: Type check
        run: npx tsc --noEmit

  # ============================
  # Build
  # ============================
  build:
    name: Build
    runs-on: ubuntu-latest
    needs: lint

    steps:
      - uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        run: npm ci

      - name: Build
        env:
          NEXT_PUBLIC_API_URL: http://localhost:8000/api/v1
          NEXT_PUBLIC_APP_NAME: SIMS Plus
          API_URL: http://localhost:8000/api/v1
        run: npm run build

  # ============================
  # Build Docker Image
  # ============================
  docker:
    name: Build Docker Image
    runs-on: ubuntu-latest
    needs: build
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'

    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build image
        uses: docker/build-push-action@v5
        with:
          context: ./frontend
          push: false
          tags: sims-plus-frontend:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

### Acceptance Criteria

- [ ] Backend CI runs 4 jobs: lint, test, migration-test, build
- [ ] Backend CI lint step flags `from __future__ import annotations` in endpoint files
- [ ] Backend CI test job creates `sims_app_user` before running pytest
- [ ] Backend CI test job uses `sims_app_user` for `DATABASE_URL`
- [ ] Backend CI migration-test applies all migrations on a clean database
- [ ] Backend CI uses `SECRET_KEY` that passes 32-char validation
- [ ] Frontend CI uses Node 22 (all jobs)
- [ ] Frontend CI runs: lint, type-check, build, docker

### Verification Commands

```bash
# Verify Node version in frontend CI
grep "node-version" .github/workflows/frontend-ci.yml
# Expected: '22' (not '20')

# Verify sims_app_user in backend CI
grep "sims_app_user" .github/workflows/backend-ci.yml
# Expected: multiple matches (DATABASE_URL, role creation, grants)

# Verify __future__ check exists
grep "__future__" .github/workflows/backend-ci.yml
# Expected: match in the lint step

# Verify migration-test job exists
grep "migration-test" .github/workflows/backend-ci.yml
# Expected: match
```

---

## Task S1-07: Cloudflare DNS Wildcard

- **Priority:** P1 (Day 3-5, parallel with backend work)
- **Effort:** 1 day
- **Owner:** Track A (DevOps)
- **Dependencies:** Domain `simsplus.io` registered (pre-sprint)

### Actions

#### 1. Configure Cloudflare DNS records

Log into Cloudflare dashboard for `simsplus.io` and add these records:

| Type | Name | Content | Proxy Status | TTL |
|------|------|---------|-------------|-----|
| A | `simsplus.io` | `<server-ip>` | Proxied (orange cloud) | Auto |
| CNAME | `*` | `simsplus.io` | Proxied (orange cloud) | Auto |
| A | `api` | `<server-ip>` | Proxied (orange cloud) | Auto |

The wildcard CNAME (`*`) ensures that ANY subdomain resolves to the same server. Cloudflare's proxy handles SSL termination.

#### 2. Configure SSL/TLS settings

In Cloudflare dashboard (SSL/TLS section):

| Setting | Value |
|---------|-------|
| SSL/TLS encryption mode | Full (Strict) |
| Minimum TLS Version | 1.2 |
| Automatic HTTPS Rewrites | On |
| Always Use HTTPS | On |
| TLS 1.3 | On |
| Opportunistic Encryption | On |

#### 3. Configure Cloudflare Page Rules

Create these page rules (Rules > Page Rules):

| Rule | URL Pattern | Setting |
|------|-------------|---------|
| 1 | `*simsplus.io/api/*` | Cache Level: Bypass |
| 2 | `*simsplus.io/_next/static/*` | Cache Level: Cache Everything, Edge Cache TTL: 1 month |
| 3 | `*simsplus.io/*.ico` | Cache Level: Cache Everything, Edge Cache TTL: 1 month |

#### 4. Create Terraform configuration (for reproducibility)

**File:** `/sims-plus/infrastructure/cloudflare/dns.tf` (NEW)

Create the directory first:
```bash
mkdir -p infrastructure/cloudflare
```

```hcl
# SIMS Plus - Cloudflare DNS Configuration
# This is a reference for the DNS setup. Apply only after
# configuring the Cloudflare provider with API tokens.

terraform {
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.0"
    }
  }
}

variable "cloudflare_zone_id" {
  description = "Cloudflare zone ID for simsplus.io"
  type        = string
  sensitive   = true
}

variable "server_ip" {
  description = "IP address of the origin server"
  type        = string
}

# Root domain
resource "cloudflare_record" "root" {
  zone_id = var.cloudflare_zone_id
  name    = "simsplus.io"
  content = var.server_ip
  type    = "A"
  proxied = true
}

# Wildcard subdomain (covers all school subdomains)
resource "cloudflare_record" "wildcard" {
  zone_id = var.cloudflare_zone_id
  name    = "*"
  content = "simsplus.io"
  type    = "CNAME"
  proxied = true
}

# API subdomain (explicit for clarity)
resource "cloudflare_record" "api" {
  zone_id = var.cloudflare_zone_id
  name    = "api"
  content = var.server_ip
  type    = "A"
  proxied = true
}
```

### Acceptance Criteria

- [ ] `presec.simsplus.io` resolves (dig or nslookup)
- [ ] `achimota.simsplus.io` resolves
- [ ] `anyrandomname.simsplus.io` resolves (wildcard working)
- [ ] SSL certificate covers `*.simsplus.io` (Cloudflare Universal SSL)
- [ ] HTTPS redirect works (http -> https)
- [ ] Terraform file exists for reference

### Verification Commands

```bash
# Test DNS resolution
dig presec.simsplus.io +short
# Expected: Cloudflare IP (e.g., 104.x.x.x)

dig achimota.simsplus.io +short
# Expected: Cloudflare IP

dig randomtest123.simsplus.io +short
# Expected: Cloudflare IP (wildcard working)

# Test SSL
curl -s -o /dev/null -w "%{http_code}" https://presec.simsplus.io
# Expected: 5xx or valid response (server may not be deployed yet, but SSL works)

# Test HTTPS redirect
curl -s -o /dev/null -w "%{redirect_url}" http://presec.simsplus.io
# Expected: https://presec.simsplus.io/
```

---

## Task S1-08: Wildcard SSL Certificate

- **Priority:** P1 (Day 4-5)
- **Effort:** 1 day
- **Owner:** Track A (DevOps)
- **Dependencies:** S1-07

### Actions

#### 1. Cloudflare Universal SSL (automatic)

Cloudflare Universal SSL automatically covers `*.simsplus.io` and `simsplus.io`. No action needed -- this is enabled by default when the domain is proxied through Cloudflare.

Verify in Cloudflare dashboard: SSL/TLS > Edge Certificates. You should see a certificate covering:
- `simsplus.io`
- `*.simsplus.io`

#### 2. Create Cloudflare Origin Certificate (for origin server)

In Cloudflare dashboard: SSL/TLS > Origin Server > Create Certificate.

Settings:
- Private key type: RSA (2048)
- Hostnames: `*.simsplus.io`, `simsplus.io`
- Certificate Validity: 15 years

Save the certificate and key:

```bash
# Create SSL directory (git-ignored)
mkdir -p docker/nginx/ssl

# Save certificate (paste from Cloudflare)
# File: docker/nginx/ssl/origin.pem

# Save private key (paste from Cloudflare)
# File: docker/nginx/ssl/origin-key.pem

# Set restrictive permissions
chmod 600 docker/nginx/ssl/origin-key.pem
chmod 644 docker/nginx/ssl/origin.pem
```

#### 3. Verify SSL directory is git-ignored

Confirm that `.gitignore` contains `docker/nginx/ssl/` (added in S1-01).

### Acceptance Criteria

- [ ] Cloudflare Universal SSL shows certificate for `*.simsplus.io`
- [ ] Origin certificate files exist in `docker/nginx/ssl/` (on server only, not in git)
- [ ] No SSL warnings in browser when accessing `https://presec.simsplus.io`
- [ ] `docker/nginx/ssl/` is in `.gitignore`

### Verification Commands

```bash
# Verify SSL directory is gitignored
git check-ignore docker/nginx/ssl/origin.pem
# Expected: docker/nginx/ssl/origin.pem (means it IS ignored)

# Test SSL from browser or curl (once deployed)
curl -vvv https://presec.simsplus.io 2>&1 | grep "SSL certificate"
# Expected: SSL certificate verify ok
```

---

## Task S1-09: Nginx Wildcard Subdomain Routing (Verification)

- **Priority:** P1 (Day 5-7)
- **Effort:** 3 days
- **Owner:** Track A (DevOps)
- **Dependencies:** S1-02, S1-07

### Context

The Nginx config was created in S1-02. This task is about verifying it works correctly with multiple subdomains and debugging any issues.

### Actions

#### 1. Verify Nginx starts without errors

```bash
docker-compose up -d nginx
docker-compose logs nginx
# Should show: "start worker processes" with no errors
```

#### 2. Test wildcard routing with multiple subdomains

```bash
# Test 1: presec.localhost
curl -s -H "Host: presec.localhost" http://localhost/health
# Expected: {"status":"healthy",...}

# Test 2: achimota.localhost
curl -s -H "Host: achimota.localhost" http://localhost/health
# Expected: {"status":"healthy",...}

# Test 3: wesleyg.localhost
curl -s -H "Host: wesleyg.localhost" http://localhost/health
# Expected: {"status":"healthy",...}

# Test 4: Single-char subdomain (edge case)
curl -s -H "Host: a.localhost" http://localhost/health
# Expected: {"status":"healthy",...}

# Test 5: Bare localhost (no subdomain)
curl -s http://localhost/health
# Expected: {"status":"healthy",...}
```

#### 3. Verify X-Subdomain header reaches the backend

Add a temporary debug log to verify. Check the backend logs:

```bash
# Make request with subdomain
curl -s http://presec.localhost/api/v1/health

# Check backend received the header
docker-compose logs backend --tail=20 | grep -i subdomain
```

Alternatively, add a debug endpoint temporarily:

**File:** `/sims-plus/backend/app/main.py` (TEMPORARY -- remove after testing)

Add this endpoint temporarily:

```python
@app.get("/debug/headers", tags=["Debug"])
async def debug_headers(request: Request) -> dict:
    """Debug endpoint to see incoming headers. REMOVE IN PRODUCTION."""
    if not settings.is_development:
        return {"error": "only available in development"}
    return {
        "host": request.headers.get("host"),
        "x-subdomain": request.headers.get("x-subdomain"),
        "x-real-ip": request.headers.get("x-real-ip"),
        "x-forwarded-for": request.headers.get("x-forwarded-for"),
        "x-forwarded-proto": request.headers.get("x-forwarded-proto"),
    }
```

Test it:
```bash
curl -s http://presec.localhost/debug/headers | python3 -m json.tool
# Expected:
# {
#   "host": "presec.localhost",
#   "x-subdomain": "presec",
#   "x-real-ip": "172.x.x.x",
#   "x-forwarded-for": "172.x.x.x",
#   "x-forwarded-proto": "http"
# }

curl -s http://achimota.localhost/debug/headers | python3 -m json.tool
# Expected: "x-subdomain": "achimota"

curl -s http://localhost/debug/headers | python3 -m json.tool
# Expected: "x-subdomain": null (no subdomain for bare localhost)
```

**IMPORTANT:** Remove the `/debug/headers` endpoint after verification.

#### 4. Verify WebSocket passthrough (Next.js HMR)

Open `http://presec.localhost` in a browser. The browser console should NOT show WebSocket connection errors. Hot Module Replacement should work (edit a frontend file and see the change reflected in the browser).

#### 5. Verify API passthrough with subdomain

```bash
# This should reach the backend with X-Subdomain: presec
curl -s http://presec.localhost/api/v1/health
# Expected: {"status":"healthy",...}

# The tenant middleware will try to look up "presec" in the tenants table.
# If no tenant exists yet, you'll get a 404. That is CORRECT behavior.
# The important thing is that the request REACHED the backend.
```

### Acceptance Criteria

- [ ] Nginx starts without configuration errors
- [ ] `curl -H "Host: presec.localhost" http://localhost/api/v1/health` reaches the backend
- [ ] `curl -H "Host: achimota.localhost" http://localhost/api/v1/health` reaches the backend
- [ ] Backend receives correct `X-Subdomain` header value for each subdomain
- [ ] Bare `localhost` requests work (no subdomain)
- [ ] WebSocket connections work through Nginx (Next.js HMR)
- [ ] The debug endpoint is removed after verification

### Verification Commands

See the test commands in the Actions section above.

---

## Task S1-10: Local Development Subdomain Setup

- **Priority:** P2 (Day 5-7)
- **Effort:** 1.5 days
- **Owner:** Track A (DevOps) + Tech Lead
- **Dependencies:** S1-09

### Actions

#### 1. Create local DNS setup script

**File:** `/sims-plus/scripts/setup-local-dns.sh` (NEW)

Create the directory first:
```bash
mkdir -p scripts
```

```bash
#!/usr/bin/env bash
# ============================================================
# SIMS Plus - Local DNS Setup for Development
# ============================================================
# This script adds /etc/hosts entries for local subdomain testing.
#
# Usage:
#   chmod +x scripts/setup-local-dns.sh
#   ./scripts/setup-local-dns.sh
#
# NOTE: Modern Chrome and Firefox automatically resolve
# *.localhost to 127.0.0.1. You may not need this script
# unless you're using Safari or an older browser.
# ============================================================

set -euo pipefail

echo "============================================================"
echo "SIMS Plus - Local DNS Setup"
echo "============================================================"
echo ""

# Define test subdomains
SUBDOMAINS=(
    "presec"
    "achimota"
    "wesleyg"
    "demo"
    "test1"
)

# Check if entries already exist
if grep -q "# SIMS Plus Local Development" /etc/hosts 2>/dev/null; then
    echo "SIMS Plus entries already exist in /etc/hosts."
    echo "To update, first remove the existing entries and run again."
    echo ""
    echo "Current entries:"
    grep -A 20 "# SIMS Plus Local Development" /etc/hosts | head -20
    exit 0
fi

# Build the hosts entries
HOSTS_BLOCK="
# SIMS Plus Local Development (added by setup-local-dns.sh)
# Remove this block if you no longer need local subdomain testing."

for sub in "${SUBDOMAINS[@]}"; do
    HOSTS_BLOCK="${HOSTS_BLOCK}
127.0.0.1 ${sub}.localhost"
done

HOSTS_BLOCK="${HOSTS_BLOCK}
# End SIMS Plus Local Development
"

echo "The following entries will be added to /etc/hosts:"
echo "${HOSTS_BLOCK}"
echo ""

read -p "Proceed? (y/N) " confirm
if [[ "${confirm}" != "y" && "${confirm}" != "Y" ]]; then
    echo "Aborted."
    exit 0
fi

# Add entries (requires sudo)
echo "${HOSTS_BLOCK}" | sudo tee -a /etc/hosts > /dev/null

echo ""
echo "Done! Entries added to /etc/hosts."
echo ""
echo "You can now access:"
for sub in "${SUBDOMAINS[@]}"; do
    echo "  http://${sub}.localhost        -> frontend (via Nginx on port 80)"
    echo "  http://${sub}.localhost:3000   -> frontend (direct, bypass Nginx)"
done
echo ""
echo "To remove these entries later, edit /etc/hosts and delete"
echo "the block between '# SIMS Plus Local Development' comments."
```

Make it executable:
```bash
chmod +x scripts/setup-local-dns.sh
```

#### 2. Create dnsmasq setup script (alternative for teams)

**File:** `/sims-plus/scripts/setup-dnsmasq.sh` (NEW)

```bash
#!/usr/bin/env bash
# ============================================================
# SIMS Plus - dnsmasq Setup (macOS)
# ============================================================
# Alternative to /etc/hosts for teams. Resolves ALL *.localhost
# to 127.0.0.1 without individual entries.
#
# Usage:
#   chmod +x scripts/setup-dnsmasq.sh
#   ./scripts/setup-dnsmasq.sh
# ============================================================

set -euo pipefail

echo "============================================================"
echo "SIMS Plus - dnsmasq Setup (macOS)"
echo "============================================================"
echo ""

# Check if on macOS
if [[ "$(uname)" != "Darwin" ]]; then
    echo "This script is for macOS only."
    echo "On Linux, *.localhost typically resolves to 127.0.0.1 by default."
    exit 0
fi

# Check if Homebrew is installed
if ! command -v brew &> /dev/null; then
    echo "Homebrew is required. Install from https://brew.sh"
    exit 1
fi

# Install dnsmasq
echo "Installing dnsmasq..."
brew install dnsmasq

# Configure dnsmasq to resolve *.localhost to 127.0.0.1
DNSMASQ_CONF="$(brew --prefix)/etc/dnsmasq.conf"
if ! grep -q "address=/localhost/127.0.0.1" "${DNSMASQ_CONF}" 2>/dev/null; then
    echo "" >> "${DNSMASQ_CONF}"
    echo "# SIMS Plus - Resolve *.localhost to 127.0.0.1" >> "${DNSMASQ_CONF}"
    echo "address=/localhost/127.0.0.1" >> "${DNSMASQ_CONF}"
    echo "Added localhost resolution to dnsmasq config."
else
    echo "dnsmasq already configured for *.localhost."
fi

# Start dnsmasq service
echo "Starting dnsmasq service..."
sudo brew services start dnsmasq

# Create resolver directory
sudo mkdir -p /etc/resolver

# Create resolver file for .localhost TLD
echo "nameserver 127.0.0.1" | sudo tee /etc/resolver/localhost > /dev/null

echo ""
echo "Done! dnsmasq is running."
echo ""
echo "Verify with:"
echo "  dig presec.localhost @127.0.0.1"
echo "  ping -c 1 presec.localhost"
echo ""
echo "Any subdomain of .localhost will now resolve to 127.0.0.1:"
echo "  http://presec.localhost"
echo "  http://achimota.localhost"
echo "  http://anyname.localhost"
```

Make it executable:
```bash
chmod +x scripts/setup-dnsmasq.sh
```

#### 3. Document all approaches in a developer setup section

This documentation should be included in the project README. The three approaches are:

**Option A: Modern browsers (no setup needed)**
Chrome 117+ and Firefox 117+ automatically resolve `*.localhost` to `127.0.0.1`. Just navigate to `http://presec.localhost` directly.

**Option B: `/etc/hosts` entries**
Run `./scripts/setup-local-dns.sh` to add entries for known test subdomains.

**Option C: dnsmasq (recommended for macOS teams)**
Run `./scripts/setup-dnsmasq.sh` to resolve ALL `*.localhost` patterns.

### Acceptance Criteria

- [ ] `scripts/setup-local-dns.sh` exists and is executable
- [ ] `scripts/setup-dnsmasq.sh` exists and is executable
- [ ] At least 2 of 3 approaches verified working on a developer machine
- [ ] Scripts are idempotent (safe to run multiple times)
- [ ] `http://presec.localhost` loads the application in the browser

### Verification Commands

```bash
# Verify scripts are executable
test -x scripts/setup-local-dns.sh && echo "PASS" || echo "FAIL"
test -x scripts/setup-dnsmasq.sh && echo "PASS" || echo "FAIL"

# Test Option A (modern browser)
# Open Chrome/Firefox and navigate to http://presec.localhost
# If it loads -> Option A works, no scripts needed.

# Test DNS resolution
ping -c 1 presec.localhost
# Expected: PING presec.localhost (127.0.0.1)

# Test via curl
curl -s http://presec.localhost/health
# Expected: {"status":"healthy",...}
```

---

## Week-by-Week Schedule

### Week 1 (Days 1-5)

| Day | Track A (DevOps) | Track B (Backend 1) | Track C (Backend 2) | Track D (Frontend) |
|-----|-----------------|--------------------|--------------------|-------------------|
| 1 | **S1-01:** `.env.example`, PR template, branch protection | **S1-05:** Rewrite `init-db.sql` | RLS workshop prep; review existing RLS migrations | **S1-04:** Verify Next.js config |
| 2 | **S1-02:** Rewrite `docker-compose.yml`, create Nginx config | **S1-05:** Verify DB setup, test `sims_app_user` | Research: audit all existing RLS policies | **S1-04:** Create `server-api.ts`, update `next.config.ts` |
| 3 | **S1-06:** Write `backend-ci.yml` with `sims_app_user` | **S1-03:** Fix CORS regex, fix `get_db()`, add `SECRET_KEY` validation | Begin RLS policy rework design (Sprint 2 prep) | **S1-04:** Final verification, subdomain cookie testing |
| 4 | **S1-06:** Write `frontend-ci.yml` with Node 22 | **S1-03:** Test all fixes end-to-end | RLS design document review | Auth pages scaffolding (Sprint 2 prep) |
| 5 | **S1-07:** Cloudflare DNS wildcard + **S1-08:** Origin cert | Begin Alembic migration verification | RLS design finalization | Auth pages scaffolding continued |

### Week 2 (Days 6-10)

| Day | Track A (DevOps) | Track B (Backend 1) | Track C (Backend 2) | Track D (Frontend) |
|-----|-----------------|--------------------|--------------------|-------------------|
| 6 | **S1-09:** Nginx testing with multiple subdomains | Sprint 2 prep: tenant tables verification | Sprint 2 prep: RLS implementation begins | Sprint 2 prep: Next.js proxy integration testing |
| 7 | **S1-09:** WebSocket testing, debug headers | Sprint 2 prep: school/user table verification | Sprint 2 prep: RLS policy writing | Sprint 2 prep: TenantProvider design |
| 8 | **S1-10:** Local DNS scripts | Sprint 2 prep: migration chain verification | Sprint 2 prep: RLS testing | Sprint 2 prep: TenantProvider implementation |
| 9 | **S1-06:** CI refinement based on test results | Full integration test run | Sprint 2 prep: RLS hardening | Sprint 2 prep: auth page integration |
| 10 | Sprint 1 review + retrospective | Sprint 1 review | Sprint 1 review | Sprint 1 review |

---

## Sprint 1 Exit Criteria

**All of these must be true before Sprint 1 is considered complete:**

### Infrastructure
- [ ] `docker-compose up` starts all 5 services (db, redis, nginx, backend, frontend) without errors within 2 minutes
- [ ] `curl http://localhost:8000/health` returns `{"status": "healthy", ...}`
- [ ] `curl http://localhost:3000` returns the Next.js page
- [ ] `curl http://localhost/health` works via Nginx (bare localhost)
- [ ] Nginx routes `http://presec.localhost/api/v1/health` to backend with `X-Subdomain: presec` header

### Database Security
- [ ] Two PostgreSQL roles exist: `postgres` (superuser) and `sims_app_user` (non-superuser, RLS enforced)
- [ ] Backend container connects as `sims_app_user` (verify with `docker-compose exec backend env | grep DATABASE_URL`)
- [ ] `init-db.sql` creates `sims_app_user` role and `get_current_tenant_id()`, `set_tenant_context()`, `clear_tenant_context()` functions
- [ ] `init-db.sql` does NOT create the old `current_tenant_id()` function
- [ ] Functions exist in both `sims_plus` and `sims_plus_test` databases
- [ ] `sims_app_user` can execute all three RLS functions

### Application Security
- [ ] CORS allows `http://presec.localhost:3000` (wildcard subdomain regex)
- [ ] CORS rejects non-matching origins
- [ ] `get_db()` raises HTTP 400 if tenant context is missing
- [ ] `get_unscoped_db()` exists for platform-level operations
- [ ] `SECRET_KEY` validation rejects keys shorter than 32 characters
- [ ] Global exception handler returns generic message in production mode

### CI/CD
- [ ] Backend CI pipeline runs: lint, `__future__` check, test (with `sims_app_user`), migration test, build
- [ ] Frontend CI pipeline runs: lint, type-check (tsc --noEmit), build, docker
- [ ] Frontend CI uses Node 22
- [ ] Backend CI uses Python 3.12
- [ ] All CI checks pass on the `develop` branch

### Developer Experience
- [ ] `.env.example` file exists with all documented variables
- [ ] `.github/pull_request_template.md` exists
- [ ] `scripts/setup-local-dns.sh` is executable
- [ ] `scripts/setup-dnsmasq.sh` is executable
- [ ] At least one developer has verified `http://presec.localhost` loads in their browser

### DNS (if domain is available)
- [ ] Cloudflare DNS wildcard resolves `*.simsplus.io`
- [ ] SSL certificate covers `*.simsplus.io`
- [ ] Terraform file exists at `infrastructure/cloudflare/dns.tf`

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `init-db.sql` not re-run (Docker volume already initialized) | High | Critical | Document: `docker-compose down -v` required after `init-db.sql` changes |
| Nginx config syntax error blocks all traffic | Medium | High | Test config: `docker-compose exec nginx nginx -t` before restart |
| `sims_app_user` missing permissions on existing tables | High | High | After Alembic migrations, run: `GRANT ALL ON ALL TABLES IN SCHEMA public TO sims_app_user;` |
| Frontend node_modules volume stale after dependency changes | Medium | Medium | Document: `docker-compose down -v && docker-compose up --build` for clean state |
| CI fails due to SECRET_KEY length validation | Medium | Low | CI templates above use 40+ char keys |
| `*.localhost` not resolving in Safari | Medium | Low | Provide `/etc/hosts` and dnsmasq alternatives |

### Critical Recovery: Rebuilding the Database

If `init-db.sql` changes are not taking effect:

```bash
# DESTRUCTIVE: Removes ALL data (safe for development only)
docker-compose down -v        # Remove containers AND volumes
docker volume rm sims-plus-postgres 2>/dev/null || true
docker-compose up -d          # Recreate everything from scratch
```

### Granting Permissions to Existing Tables

If Alembic migrations were run before `sims_app_user` was created, the user will not have access to those tables. Fix with:

```bash
docker-compose exec db psql -U postgres -d sims_plus -c "
    GRANT ALL ON ALL TABLES IN SCHEMA public TO sims_app_user;
    GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO sims_app_user;
    GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO sims_app_user;
"
```

Run the same for the test database:

```bash
docker-compose exec db psql -U postgres -d sims_plus_test -c "
    GRANT ALL ON ALL TABLES IN SCHEMA public TO sims_app_user;
    GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO sims_app_user;
    GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO sims_app_user;
"
```

---

## Files Created or Modified (Summary)

### New Files

| File | Task | Description |
|------|------|-------------|
| `.env.example` | S1-01 | Environment variable template |
| `.github/pull_request_template.md` | S1-01 | PR template with security checklist |
| `docker/nginx/nginx.conf` | S1-02 | Nginx local development config |
| `docker/nginx/nginx.production.conf` | S1-02 | Nginx production config (reference) |
| `frontend/lib/server-api.ts` | S1-04 | Auto-subdomain server-side API helpers |
| `scripts/setup-local-dns.sh` | S1-10 | `/etc/hosts` setup script |
| `scripts/setup-dnsmasq.sh` | S1-10 | dnsmasq setup script (macOS) |
| `infrastructure/cloudflare/dns.tf` | S1-07 | Terraform DNS configuration |

### Modified Files

| File | Task | What Changed |
|------|------|-------------|
| `docker-compose.yml` | S1-02 | Rewrote: added Nginx service, fixed `DATABASE_URL` to use `sims_app_user`, added healthcheck on backend |
| `frontend/Dockerfile` | S1-02 | Updated Node 20 -> Node 22 (all 4 stages) |
| `backend/scripts/init-db.sql` | S1-05 | Rewrote: added `sims_app_user`, replaced `current_tenant_id()` with `get_current_tenant_id()`, added `set_tenant_context()`, `clear_tenant_context()`, test DB setup |
| `backend/app/main.py` | S1-03 | Added `allow_origin_regex` to CORS middleware |
| `backend/app/config.py` | S1-03 | Added `SECRET_KEY` length validator, added `ALEMBIC_DATABASE_URL` setting |
| `backend/app/api/deps.py` | S1-03 | `get_db()` now raises HTTP 400 without tenant context. Added `get_unscoped_db()` and `UnscopedDatabaseSession`. |
| `frontend/next.config.ts` | S1-04 | Added `serverActions.bodySizeLimit`, MinIO remote pattern |
| `.github/workflows/backend-ci.yml` | S1-06 | Rewrote: added `sims_app_user` setup, `__future__` check, migration test job |
| `.github/workflows/frontend-ci.yml` | S1-06 | Updated Node 20 -> Node 22 |
| `.gitignore` | S1-01 | Added `docker/nginx/ssl/`, `*.pem`, `*.key`, `*.crt` |
