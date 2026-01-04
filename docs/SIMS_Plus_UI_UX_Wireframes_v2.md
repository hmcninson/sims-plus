# SIMS Plus (School Information Management System Plus) - UI/UX Wireframes & Design System

**Version:** 2.0  
**Date:** January 2026  
**Author:** Harry McNinson  
**Status:** Complete with Subdomain Login Flows

---

## Table of Contents

1. [Design System](#1-design-system)
2. [Layout Structure](#2-layout-structure)
3. [Authentication Screens](#3-authentication-screens)
4. [School Registration](#4-school-registration)
5. [Dashboard](#5-dashboard)
6. [Student Management](#6-student-management)
7. [Attendance](#7-attendance)
8. [Exams & Grading](#8-exams--grading)
9. [Finance](#9-finance)
10. [Report Cards](#10-report-cards)
11. [Parent Portal](#11-parent-portal)
12. [Mobile App Screens](#12-mobile-app-screens)
13. [Boarding Module](#13-boarding-module)
14. [Accessibility & UX Guidelines](#14-accessibility--ux-guidelines)

---

## 1. Design System

### 1.1 Color Palette

**Primary Colors (SIMS Plus Brand)**

| Color | Hex | Usage |
|-------|-----|-------|
| Primary Blue | `#1B4F72` | Headers, buttons, links |
| Primary Light | `#2874A6` | Hover states, accents |
| Primary Dark | `#154360` | Active states, emphasis |

**Secondary Colors**

| Color | Hex | Usage |
|-------|-----|-------|
| Success Green | `#27AE60` | Success messages, positive indicators |
| Warning Orange | `#F39C12` | Warnings, pending states |
| Error Red | `#E74C3C` | Errors, destructive actions |
| Info Blue | `#3498DB` | Information, tips |

**Neutral Colors**

| Color | Hex | Usage |
|-------|-----|-------|
| Gray 900 | `#1A1A1A` | Primary text |
| Gray 700 | `#4A4A4A` | Secondary text |
| Gray 500 | `#7A7A7A` | Placeholder text |
| Gray 300 | `#CCCCCC` | Borders, dividers |
| Gray 100 | `#F5F5F5` | Backgrounds |
| White | `#FFFFFF` | Cards, content areas |

**Tenant Branding Note:**
- Schools can customize `--primary-color` via tenant settings
- Default falls back to SIMS Plus Blue (#1B4F72)

### 1.2 Typography

| Element | Font | Size | Weight |
|---------|------|------|--------|
| H1 | Inter | 30px | 700 |
| H2 | Inter | 24px | 600 |
| H3 | Inter | 20px | 600 |
| H4 | Inter | 18px | 600 |
| Body | Inter | 16px | 400 |
| Small | Inter | 14px | 400 |
| Caption | Inter | 12px | 400 |

### 1.3 Spacing System

| Token | Value | Usage |
|-------|-------|-------|
| space-1 | 4px | Tight spacing |
| space-2 | 8px | Default spacing |
| space-3 | 12px | Component padding |
| space-4 | 16px | Section spacing |
| space-5 | 24px | Card padding |
| space-6 | 32px | Section margins |
| space-8 | 48px | Page sections |

### 1.4 Component Library

**Buttons**

```
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  Primary Button  │  │ Secondary Button │  │  Outline Button  │
│   (filled blue)  │  │   (filled gray)  │  │ (border only)    │
└──────────────────┘  └──────────────────┘  └──────────────────┘

┌──────────────────┐  ┌──────────────────┐
│   Ghost Button   │  │  Danger Button   │
│ (text only)      │  │   (filled red)   │
└──────────────────┘  └──────────────────┘
```

**Form Inputs**

```
┌─────────────────────────────────────────┐
│ Label                                   │
├─────────────────────────────────────────┤
│ Placeholder text...                     │
└─────────────────────────────────────────┘
  Helper text or error message

States: Default, Focus, Error, Disabled
```

**Status Badges**

```
┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐
│ Active  │  │ Pending │  │  Paid   │  │ Overdue │
│ (green) │  │(orange) │  │ (green) │  │  (red)  │
└─────────┘  └─────────┘  └─────────┘  └─────────┘
```

---

## 2. Layout Structure

### 2.1 Main Application Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│  [School Logo]  SIMS Plus    🔍 Search...     🔔 (3)    👤 Admin  ▾  │
├─────────────────────────────────────────────────────────────────────────┤
│         │                                                               │
│   ≡     │                    MAIN CONTENT AREA                         │
│         │                                                               │
│ 📊 Dashboard │                                                          │
│ 👥 Students  │  ┌─────────────────────────────────────────────────┐    │
│ 👨‍🏫 Staff     │  │                                                 │    │
│ 📚 Academics │  │              Page Content                       │    │
│ ✓ Attendance │  │                                                 │    │
│ 📝 Exams     │  │                                                 │    │
│ 💰 Finance   │  │                                                 │    │
│ 📄 Reports   │  │                                                 │    │
│ ⚙️ Settings  │  │                                                 │    │
│              │  └─────────────────────────────────────────────────┘    │
│              │                                                          │
│  [Collapse]  │                                                          │
│              │                                                          │
└─────────────────────────────────────────────────────────────────────────┘

Sidebar: 240px (expanded) / 64px (collapsed)
Content: max-width 1440px, centered
```

### 2.2 Responsive Breakpoints

| Breakpoint | Width | Layout |
|------------|-------|--------|
| Mobile | < 768px | Single column, hamburger menu |
| Tablet | 768-1024px | Collapsed sidebar |
| Desktop | 1024-1440px | Full layout |
| Large | > 1440px | Centered with margins |

---

## 3. Authentication Screens

### 3.1 School-Specific Login (at {school}.simsplus.io)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  Browser: 🔒 https://presec.simsplus.io/login                        │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│                         ┌─────────────────────┐                         │
│                         │                     │                         │
│                         │   [SCHOOL LOGO]     │◄─── [1] Tenant logo    │
│                         │                     │                         │
│                         └─────────────────────┘                         │
│                                                                         │
│                    Presbyterian Boys' Secondary School  ◄─── [2] Name  │
│                                                                         │
│                           Welcome Back                                  │
│                     Sign in to your account                             │
│                                                                         │
│                    ┌─────────────────────────────┐                      │
│                    │ Email                       │                      │
│                    ├─────────────────────────────┤                      │
│                    │ teacher@presec.edu.gh       │                      │
│                    └─────────────────────────────┘                      │
│                                                                         │
│                    ┌─────────────────────────────┐                      │
│                    │ Password                    │                      │
│                    ├─────────────────────────────┤                      │
│                    │ ••••••••••           👁     │                      │
│                    └─────────────────────────────┘                      │
│                                                                         │
│                    ☐ Remember me    Forgot password?                    │
│                                                                         │
│                    ┌─────────────────────────────┐                      │
│                    │         Sign In             │◄─── [3] Brand color │
│                    └─────────────────────────────┘                      │
│                                                                         │
│                    Not from this school?                                │
│                    Find your school →            ◄─── [4] To app.sims  │
│                                                                         │
│                         Powered by SIMS Plus    ◄─── [5] Always shown │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Annotations:**
| # | Element | Description |
|---|---------|-------------|
| 1 | School Logo | Loaded from tenant branding settings |
| 2 | School Name | Dynamically loaded from database |
| 3 | Sign In Button | Uses school's primary brand color |
| 4 | Wrong School Link | Redirects to `app.simsplus.io` |
| 5 | Powered By | SIMS Plus branding (always shown) |

### 3.2 Generic Login Portal (at app.simsplus.io)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  Browser: 🔒 https://app.simsplus.io                                 │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│                         ┌─────────────────────┐                         │
│                         │                     │                         │
│                         │  [SIMS PLUS LOGO]  │                         │
│                         │                     │                         │
│                         └─────────────────────┘                         │
│                                                                         │
│                        Welcome to SIMS Plus                            │
│                                                                         │
│                    Find your school to continue                         │
│                                                                         │
│                    ┌─────────────────────────────┐                      │
│                    │ 🔍 Search for your school...│◄─── [1] Search box  │
│                    └─────────────────────────────┘                      │
│                                                                         │
│                    ┌─────────────────────────────┐                      │
│                    │ 🏫 Presbyterian Boys' Sec.  │◄─── [2] Results     │
│                    │    presec.simsplus.io     │                      │
│                    ├─────────────────────────────┤                      │
│                    │ 🏫 Achimota School          │                      │
│                    │    achimota.simsplus.io   │                      │
│                    ├─────────────────────────────┤                      │
│                    │ 🏫 Wesley Girls' High       │                      │
│                    │    wesleyg.simsplus.io    │                      │
│                    └─────────────────────────────┘                      │
│                                                                         │
│                    ──────────── or ────────────                         │
│                                                                         │
│                    Enter school code directly:                          │
│                                                                         │
│                    ┌─────────────────────────────┐                      │
│                    │ School code (e.g. presec)   │◄─── [3] Direct entry│
│                    └─────────────────────────────┘                      │
│                                                                         │
│                    ┌─────────────────────────────┐                      │
│                    │         Continue →          │                      │
│                    └─────────────────────────────┘                      │
│                                                                         │
│                    New school? Register here →   ◄─── [4] Registration │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.3 School Not Found Error

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  Browser: 🔒 https://invalidschool.simsplus.io                       │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│                              ⚠️                                         │
│                                                                         │
│                        School Not Found                                 │
│                                                                         │
│              We couldn't find a school at this address.                │
│                                                                         │
│              The school may have moved or doesn't exist.               │
│                                                                         │
│                    ┌─────────────────────────────┐                      │
│                    │    Find Your School →       │                      │
│                    └─────────────────────────────┘                      │
│                                                                         │
│              Or visit: app.simsplus.io to search                      │
│                                                                         │
│              ─────────────────────────────────────                      │
│                                                                         │
│              Are you a school administrator?                            │
│              Register your school →                                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.4 Password Reset

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│                         [SCHOOL LOGO]                                   │
│                                                                         │
│                       Reset Your Password                               │
│                                                                         │
│         Enter your email and we'll send you a reset link.              │
│                                                                         │
│                    ┌─────────────────────────────┐                      │
│                    │ Email                       │                      │
│                    ├─────────────────────────────┤                      │
│                    │ your.email@school.edu.gh    │                      │
│                    └─────────────────────────────┘                      │
│                                                                         │
│                    ┌─────────────────────────────┐                      │
│                    │     Send Reset Link         │                      │
│                    └─────────────────────────────┘                      │
│                                                                         │
│                    ← Back to Login                                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. School Registration

### 4.1 Registration Form (at simsplus.io/register)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│                         Register Your School                            │
│                     Start your 30-day free trial                        │
│                                                                         │
│  ┌─ School Information ─────────────────────────────────────────────┐   │
│  │                                                                   │   │
│  │   School Name *                                                   │   │
│  │   ┌─────────────────────────────────────────────────────────────┐│   │
│  │   │ Bright Future Academy                                       ││   │
│  │   └─────────────────────────────────────────────────────────────┘│   │
│  │                                                                   │   │
│  │   School Type *                                                   │   │
│  │   ┌─────────────────────────────────────────────────────────────┐│   │
│  │   │ Basic School (Primary + JHS)                              ▼ ││   │
│  │   └─────────────────────────────────────────────────────────────┘│   │
│  │                                                                   │   │
│  │   Choose your school's web address:                               │   │
│  │   ┌───────────────────────────┬─────────────────────────────────┐│   │
│  │   │ brightfuture              │ .simsplus.io                  ││   │
│  │   └───────────────────────────┴─────────────────────────────────┘│   │
│  │   ✓ brightfuture.simsplus.io is available!                     │   │
│  │                                                                   │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─ Administrator Account ──────────────────────────────────────────┐   │
│  │                                                                   │   │
│  │   ┌─────────────────┐  ┌─────────────────┐                       │   │
│  │   │ First Name *    │  │ Last Name *     │                       │   │
│  │   │ John            │  │ Mensah          │                       │   │
│  │   └─────────────────┘  └─────────────────┘                       │   │
│  │                                                                   │   │
│  │   Email *                                                         │   │
│  │   ┌─────────────────────────────────────────────────────────────┐│   │
│  │   │ admin@brightfuture.edu.gh                                   ││   │
│  │   └─────────────────────────────────────────────────────────────┘│   │
│  │                                                                   │   │
│  │   Phone Number *                                                  │   │
│  │   ┌─────────────────────────────────────────────────────────────┐│   │
│  │   │ +233 24 123 4567                                            ││   │
│  │   └─────────────────────────────────────────────────────────────┘│   │
│  │                                                                   │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ☑ I agree to the Terms of Service and Privacy Policy                   │
│                                                                         │
│                    ┌─────────────────────────────┐                      │
│                    │   Start Free Trial →        │                      │
│                    └─────────────────────────────┘                      │
│                                                                         │
│              No credit card required • Cancel anytime                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Subdomain Validation States

```
STATE: Available
┌───────────────────────────┬─────────────────────────────────┐
│ brightfuture              │ .simsplus.io                  │
└───────────────────────────┴─────────────────────────────────┘
✓ brightfuture.simsplus.io is available!
  (green checkmark)

STATE: Taken
┌───────────────────────────┬─────────────────────────────────┐
│ presec                    │ .simsplus.io                  │
└───────────────────────────┴─────────────────────────────────┘
✗ presec.simsplus.io is already taken
  (red X)

  Suggestions:
  • presec-legon.simsplus.io    [Use this]
  • presec2.simsplus.io         [Use this]

STATE: Invalid
┌───────────────────────────┬─────────────────────────────────┐
│ my school!                │ .simsplus.io                  │
└───────────────────────────┴─────────────────────────────────┘
✗ Invalid format
  Only lowercase letters, numbers, and hyphens allowed

STATE: Reserved
┌───────────────────────────┬─────────────────────────────────┐
│ admin                     │ .simsplus.io                  │
└───────────────────────────┴─────────────────────────────────┘
✗ This subdomain is reserved
  Please choose a different name
```

### 4.3 Registration Success

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│                              🎉                                         │
│                                                                         │
│                    Your School is Ready!                                │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                                                                    │  │
│  │  Your school portal:                                               │  │
│  │                                                                    │  │
│  │  ┌──────────────────────────────────────────────────────────────┐ │  │
│  │  │  🔗 https://brightfuture.simsplus.io                       │ │  │
│  │  │                                              [Copy] [Open →]  │ │  │
│  │  └──────────────────────────────────────────────────────────────┘ │  │
│  │                                                                    │  │
│  │  We've sent login instructions to:                                │  │
│  │  admin@brightfuture.edu.gh                                        │  │
│  │                                                                    │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  What's next?                                                           │
│                                                                         │
│  1. ✉ Check your email for login credentials                           │
│  2. 🔑 Login at brightfuture.simsplus.io                             │
│  3. 🏫 Complete your school setup                                       │
│  4. 👥 Add your students and staff                                      │
│                                                                         │
│  Your 30-day free trial has started!                                    │
│  Trial ends: February 5, 2026                                           │
│                                                                         │
│                    ┌─────────────────────────────┐                      │
│                    │    Go to Your Portal →      │                      │
│                    └─────────────────────────────┘                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Dashboard

### 5.1 Admin Dashboard

```
┌─────────────────────────────────────────────────────────────────────────┐
│  [Logo]  SIMS Plus                                    🔔 (3)  👤 Admin │
├─────────────────────────────────────────────────────────────────────────┤
│         │                                                               │
│ 📊 Dash │  Good morning, Administrator! 👋                             │
│ 👥 Stud │  Presbyterian Boys' Secondary School                          │
│ 👨‍🏫 Staff│                                                               │
│ 📚 Acad │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│ ✓ Atten │  │  1,234   │  │    48    │  │  94.2%   │  │ ₵45,000  │      │
│ 📝 Exams│  │ Students │  │  Staff   │  │Attendance│  │  Fees    │      │
│ 💰 Finan│  │ ↑ 12     │  │ ↑ 2      │  │ ↓ 0.3%   │  │ ↑ ₵5,000 │      │
│ 📄 Repor│  └──────────┘  └──────────┘  └──────────┘  └──────────┘      │
│ ⚙️ Setti│                                                               │
│         │  ┌─────────────────────────┐  ┌─────────────────────────┐    │
│         │  │ Attendance This Week    │  │ Fee Collection          │    │
│         │  │ ┌───────────────────┐   │  │ ┌───────────────────┐   │    │
│         │  │ │   📈 Line Chart   │   │  │ │   📊 Bar Chart    │   │    │
│         │  │ │   Mon-Fri %       │   │  │ │   by Category     │   │    │
│         │  │ └───────────────────┘   │  │ └───────────────────┘   │    │
│         │  └─────────────────────────┘  └─────────────────────────┘    │
│         │                                                               │
│         │  ┌─────────────────────────┐  ┌─────────────────────────┐    │
│         │  │ Recent Activity         │  │ Quick Actions           │    │
│         │  │ ────────────────────    │  │ ┌───────┐ ┌───────┐    │    │
│         │  │ • New student enrolled  │  │ │+ Stud │ │✓ Atten│    │    │
│         │  │ • Fee payment: ₵500     │  │ └───────┘ └───────┘    │    │
│         │  │ • Attendance: JHS 2A    │  │ ┌───────┐ ┌───────┐    │    │
│         │  │ • Staff login: Mr. Asare│  │ │💰 Pay │ │📱 SMS │    │    │
│         │  └─────────────────────────┘  │ └───────┘ └───────┘    │    │
│         │                               └─────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Student Management

### 6.1 Student List

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Students                                            [+ Add Student]    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ 🔍 Search students...    │ Class: [All ▼] │ Status: [Active ▼] │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ ☐ │ Photo │ Student ID   │ Name           │ Class  │ Status    │    │
│  ├───┼───────┼──────────────┼────────────────┼────────┼───────────┤    │
│  │ ☐ │ 👤    │ STU-2025-001 │ Kwame Asante   │ JHS 2A │ ● Active  │    │
│  │ ☐ │ 👤    │ STU-2025-002 │ Ama Mensah     │ JHS 2A │ ● Active  │    │
│  │ ☐ │ 👤    │ STU-2025-003 │ Kofi Boateng   │ JHS 2B │ ● Active  │    │
│  │ ☐ │ 👤    │ STU-2025-004 │ Abena Darko    │ JHS 1A │ ○ Inactive│    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  Showing 1-20 of 1,234 students           [← Prev] [1] [2] [3] [Next →]│
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Student Profile

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ← Back to Students                                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌────────────────────────────────────────────────────┐                 │
│  │  ┌──────┐                                          │   [Edit] [···]  │
│  │  │      │  Kwame Asante                            │                 │
│  │  │ 👤   │  STU-2025-001 • JHS 2A • Male           │                 │
│  │  │      │  ● Active                                │                 │
│  │  └──────┘                                          │                 │
│  └────────────────────────────────────────────────────┘                 │
│                                                                         │
│  [Overview] [Academic] [Attendance] [Finance] [Documents] [History]     │
│  ═══════════                                                            │
│                                                                         │
│  ┌─ Personal Info ───────────┐  ┌─ Guardian ─────────────────────────┐  │
│  │ DOB: 15 Mar 2010          │  │ Name: Mr. Kofi Asante (Father)     │  │
│  │ Age: 15 years             │  │ Phone: +233 24 123 4567 📱         │  │
│  │ Nationality: Ghanaian     │  │ Email: kofi.asante@email.com       │  │
│  │ Address: Accra, Ghana     │  │ Relationship: Father ● Primary     │  │
│  │ Ghana Card: GHA-XXX-XXX   │  │                                    │  │
│  └───────────────────────────┘  │ [+ Add Guardian]                   │  │
│                                 └────────────────────────────────────┘  │
│                                                                         │
│  ┌─ Academic Summary ────────┐  ┌─ Fee Summary ──────────────────────┐  │
│  │ Current Class: JHS 2A     │  │ Total Due: ₵2,500                  │  │
│  │ Admission: Sep 2020       │  │ Paid: ₵2,000                       │  │
│  │ Previous: JHS 1A (2024)   │  │ Balance: ₵500                      │  │
│  │ Attendance: 94.2%         │  │ Status: ● Partial                  │  │
│  └───────────────────────────┘  └────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Attendance

### 7.1 Mark Attendance

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Mark Attendance                                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Class: [JHS 2A ▼]  Section: [All ▼]  Date: [06 Jan 2026 📅]           │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ Summary: Present: 32 │ Absent: 3 │ Late: 2 │ Excused: 1          │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                           [Mark All ✓] │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ # │ Student Name    │ Present │ Absent │ Late │ Excused │ Note  │    │
│  ├───┼─────────────────┼─────────┼────────┼──────┼─────────┼───────┤    │
│  │ 1 │ Kwame Asante    │   ◉     │   ○    │  ○   │    ○    │       │    │
│  │ 2 │ Ama Mensah      │   ◉     │   ○    │  ○   │    ○    │       │    │
│  │ 3 │ Kofi Boateng    │   ○     │   ◉    │  ○   │    ○    │ Sick  │    │
│  │ 4 │ Abena Darko     │   ○     │   ○    │  ◉   │    ○    │ 8:15  │    │
│  │ 5 │ Yaw Mensah      │   ○     │   ○    │  ○   │    ◉    │ Travel│    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  ⚠ Unsaved changes                              [Cancel] [Save ✓]      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Exams & Grading

### 8.1 Score Entry

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Enter Scores                                                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Exam: End of Term 1 (70%)    Class: JHS 2A    Subject: Mathematics    │
│  Max Score: 100               Entered: 35/38 (92%)                      │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ # │ Student Name    │ Score │ Grade │ Position │ Remarks        │    │
│  ├───┼─────────────────┼───────┼───────┼──────────┼────────────────┤    │
│  │ 1 │ Kwame Asante    │  85   │   1   │    3rd   │                │    │
│  │ 2 │ Ama Mensah      │  92   │   1   │    1st   │ Excellent      │    │
│  │ 3 │ Kofi Boateng    │  78   │   2   │    5th   │                │    │
│  │ 4 │ Abena Darko     │  65   │   3   │   12th   │ Needs support  │    │
│  │ 5 │ Yaw Mensah      │  AB   │   -   │    -     │ Absent         │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  Class Stats: Avg: 74.5 │ Highest: 92 │ Lowest: 45                     │
│                                                                         │
│                                            [Save Draft] [Submit Final]  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Finance

### 9.1 Invoice List

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Invoices                                          [+ Generate Invoices]│
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  [All] [Paid] [Partial] [Pending] [Overdue]                            │
│   ═══                                                                   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ Invoice #    │ Student       │ Class │ Amount  │ Paid   │Status │    │
│  ├──────────────┼───────────────┼───────┼─────────┼────────┼───────┤    │
│  │ INV-2025-001 │ Kwame Asante  │ JHS2A │ ₵2,500  │ ₵2,000 │Partial│    │
│  │ INV-2025-002 │ Ama Mensah    │ JHS2A │ ₵2,500  │ ₵2,500 │ Paid  │    │
│  │ INV-2025-003 │ Kofi Boateng  │ JHS2B │ ₵2,500  │ ₵0     │Pending│    │
│  │ INV-2025-004 │ Abena Darko   │ JHS1A │ ₵2,200  │ ₵0     │Overdue│    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  Total Outstanding: ₵125,000                                            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 9.2 Record Payment

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Record Payment                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Student: 🔍 [Search student...                              ]          │
│                                                                         │
│  ┌─ Selected Student ───────────────────────────────────────────────┐   │
│  │  Kwame Asante (STU-2025-001) • JHS 2A                            │   │
│  │  Outstanding: ₵500                                                │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  Amount *                                                               │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ GHS │ 500.00                                                    │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  Payment Method *                                                       │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │
│  │  Cash   │ │MTN MoMo │ │Vodafone │ │AirtelTigo│ │  Bank  │          │
│  │   ○     │ │    ◉    │ │   ○     │ │    ○    │ │   ○    │          │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘          │
│                                                                         │
│  MoMo Phone Number *                                                    │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ 024 123 4567                                                    │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  ☐ Send SMS receipt to parent                                          │
│  ☐ Print receipt                                                        │
│                                                                         │
│                                            [Cancel] [Record Payment]    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 10. Report Cards

### 10.1 Report Card Preview

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Report Card Preview                           [Print] [Download] [Share]│
├─────────────────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  ╔═══════════════════════════════════════════════════════════════╗│  │
│  │  ║  [SCHOOL LOGO]                                                ║│  │
│  │  ║  PRESBYTERIAN BOYS' SECONDARY SCHOOL                          ║│  │
│  │  ║  "Excellence in Education"                                    ║│  │
│  │  ║                                                               ║│  │
│  │  ║  TERMINAL REPORT - TERM 1, 2025/2026                         ║│  │
│  │  ╠═══════════════════════════════════════════════════════════════╣│  │
│  │  ║  Name: Kwame Asante              Class: JHS 2A               ║│  │
│  │  ║  Student ID: STU-2025-001        Position: 3rd of 38         ║│  │
│  │  ╠═══════════════════════════════════════════════════════════════╣│  │
│  │  ║  Subject          │ Class │ Exam │ Total │ Grade │ Position  ║│  │
│  │  ║  ─────────────────┼───────┼──────┼───────┼───────┼────────── ║│  │
│  │  ║  Mathematics      │  28   │  57  │   85  │   1   │   3rd     ║│  │
│  │  ║  English Language │  27   │  58  │   85  │   1   │   2nd     ║│  │
│  │  ║  Science          │  25   │  52  │   77  │   2   │   5th     ║│  │
│  │  ║  Social Studies   │  26   │  54  │   80  │   1   │   4th     ║│  │
│  │  ╠═══════════════════════════════════════════════════════════════╣│  │
│  │  ║  Attendance: 94.2% (Present: 65 | Absent: 4)                 ║│  │
│  │  ╠═══════════════════════════════════════════════════════════════╣│  │
│  │  ║  Class Teacher's Remarks: Excellent performance. Keep it up! ║│  │
│  │  ║  Head Teacher's Remarks: Promoted to JHS 3                   ║│  │
│  │  ╠═══════════════════════════════════════════════════════════════╣│  │
│  │  ║  Next Term Begins: 15 April 2026                             ║│  │
│  │  ║                                           [QR Code]          ║│  │
│  │  ╚═══════════════════════════════════════════════════════════════╝│  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 11. Parent Portal

### 11.1 Parent Dashboard

```
┌─────────────────────────────────────────────────────────────────────────┐
│  [SCHOOL LOGO]  SIMS Plus                               👤 Mr. Asante │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Good morning, Mr. Asante 👋                                            │
│  Presbyterian Boys' Secondary School                                    │
│                                                                         │
│  My Children:  [Kwame Asante ▼]                                        │
│                                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐               │
│  │  94.2%   │  │  Grade 1 │  │  ₵500    │  │ View     │               │
│  │Attendance│  │  Average │  │ Balance  │  │ Report   │               │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘               │
│                                                                         │
│  ┌─ Recent Activity ────────────────────────────────────────────────┐   │
│  │ • Jan 6: Attendance marked (Present)                             │   │
│  │ • Jan 5: Math test score: 85/100                                 │   │
│  │ • Jan 3: Fee payment received: ₵2,000                            │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─ Announcements ──────────────────────────────────────────────────┐   │
│  │ 📢 PTA Meeting scheduled for Jan 15, 2026 at 2:00 PM            │   │
│  │ 📢 Mid-term exams begin Feb 1, 2026                              │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│                    ┌─────────────────────────────┐                      │
│                    │      💰 Pay Fees            │                      │
│                    └─────────────────────────────┘                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 11.2 Mobile Money Payment Flow

```
STEP 1: Amount Entry                    STEP 2: Processing
┌───────────────────────┐              ┌───────────────────────┐
│                       │              │                       │
│  Pay School Fees      │              │      Processing...    │
│                       │              │                       │
│  Student: Kwame       │              │         ⏳            │
│  Outstanding: ₵500    │              │                       │
│                       │              │  Waiting for approval │
│  Amount:              │              │  on your phone...     │
│  ┌─────────────────┐  │              │                       │
│  │ GHS 500.00      │  │              │  Check your phone for │
│  └─────────────────┘  │              │  the MTN MoMo prompt  │
│                       │              │                       │
│  Pay with:            │              │  ┌─────────────────┐  │
│  ◉ MTN MoMo           │              │  │     Cancel      │  │
│  ○ Vodafone Cash      │              │  └─────────────────┘  │
│  ○ AirtelTigo         │              │                       │
│                       │              └───────────────────────┘
│  Phone: 024 123 4567  │
│                       │              STEP 3: Success
│  ┌─────────────────┐  │              ┌───────────────────────┐
│  │     Pay Now     │  │              │                       │
│  └─────────────────┘  │              │         ✓             │
│                       │              │                       │
└───────────────────────┘              │  Payment Successful!  │
                                       │                       │
                                       │  Amount: ₵500.00      │
                                       │  Receipt: PAY-123456  │
                                       │                       │
                                       │  ┌─────────────────┐  │
                                       │  │Download Receipt │  │
                                       │  └─────────────────┘  │
                                       │                       │
                                       │  ┌─────────────────┐  │
                                       │  │      Done       │  │
                                       │  └─────────────────┘  │
                                       │                       │
                                       └───────────────────────┘
```

---

## 12. Mobile App Screens

### 12.1 App First Launch (School Selection)

```
┌───────────────────────┐     ┌───────────────────────┐
│                       │     │                       │
│    [SIMS PLUS LOGO]  │     │   [SCHOOL LOGO]       │
│                       │     │                       │
│   Welcome to          │     │   Presbyterian Boys'  │
│   SIMS Plus          │     │   Secondary School    │
│                       │     │                       │
│   Enter your school   │     │   ┌─────────────────┐ │
│   code to continue:   │     │   │ Email           │ │
│                       │     │   │                 │ │
│   ┌─────────────────┐ │     │   └─────────────────┘ │
│   │ presec          │ │     │                       │
│   └─────────────────┘ │     │   ┌─────────────────┐ │
│                       │     │   │ Password        │ │
│   ┌─────────────────┐ │     │   │ ••••••••        │ │
│   │    Continue     │ │     │   └─────────────────┘ │
│   └─────────────────┘ │     │                       │
│                       │     │   ┌─────────────────┐ │
│   Don't know your     │     │   │    Sign In      │ │
│   school code?        │     │   └─────────────────┘ │
│   Search schools →    │     │                       │
│                       │     │   Wrong school?       │
│                       │     │   Change →            │
│                       │     │                       │
└───────────────────────┘     └───────────────────────┘
   School Code Entry              School Login
```

### 12.2 Teacher App - Attendance

```
┌───────────────────────┐
│  ← Attendance         │
├───────────────────────┤
│                       │
│  JHS 2A • 06 Jan 2026 │
│                       │
│  [Mark All Present ✓] │
│                       │
│  ┌─────────────────┐  │
│  │ 🔍 Search...    │  │
│  └─────────────────┘  │
│                       │
│  ┌─────────────────┐  │
│  │ Kwame Asante    │  │
│  │ [P] [A] [L] [E] │  │
│  └─────────────────┘  │
│  ┌─────────────────┐  │
│  │ Ama Mensah      │  │
│  │ [P] [A] [L] [E] │  │
│  └─────────────────┘  │
│  ┌─────────────────┐  │
│  │ Kofi Boateng    │  │
│  │ [P] [A] [L] [E] │  │
│  └─────────────────┘  │
│                       │
│  P: 32 | A: 3 | L: 2  │
│                       │
│  ┌─────────────────┐  │
│  │     Submit      │  │
│  └─────────────────┘  │
│                       │
├───────────────────────┤
│  🏠   📋   👥   ⚙️    │
└───────────────────────┘
```

---

## 13. Boarding Module

### 13.1 Exeat Request Form

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Request Exeat                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Student *                                                              │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ 🔍 Kwame Asante (JHS 2A)                                 ▼     │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│  House: Peace House | Room: 12 | Bed: 3                                 │
│                                                                         │
│  Exeat Type *                                                           │
│  ○ Day Exeat (return same day)                                          │
│  ◉ Weekend Exeat                                                        │
│  ○ Extended Exeat                                                       │
│                                                                         │
│  Reason *                                                               │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ Family event - Sister's wedding                                 │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  Departure *               Return *                                     │
│  ┌───────────────────┐    ┌───────────────────┐                        │
│  │ 10 Jan 2026 14:00 │    │ 12 Jan 2026 18:00 │                        │
│  └───────────────────┘    └───────────────────┘                        │
│                                                                         │
│  ┌─ Pickup Person ──────────────────────────────────────────────────┐   │
│  │  Name *: Mr. Kofi Asante                                         │   │
│  │  Phone *: +233 24 123 4567                                       │   │
│  │  Relationship *: [Father ▼]                                      │   │
│  │  ☑ Use guardian from profile                                     │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│                                       [Cancel] [Submit for Approval]    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 14. Accessibility & UX Guidelines

### 14.1 Accessibility Standards

| Requirement | Implementation |
|-------------|----------------|
| Color Contrast | Minimum 4.5:1 ratio (WCAG AA) |
| Focus Indicators | Visible focus ring on all interactive elements |
| Keyboard Navigation | Full keyboard support, logical tab order |
| Screen Readers | ARIA labels, semantic HTML |
| Touch Targets | Minimum 44x44px for mobile |
| Form Labels | All inputs have associated labels |
| Error Messages | Descriptive, actionable error messages |

### 14.2 Ghana-Specific UX Considerations

| Consideration | Implementation |
|---------------|----------------|
| Low Bandwidth | Lazy loading, image compression, offline support |
| Mobile-First | 70%+ users on mobile, design accordingly |
| Power Outages | Auto-save drafts every 30 seconds |
| Name Formats | Support for Ghanaian names with special characters |
| Date Format | DD/MM/YYYY (Ghana standard) |
| Currency | GHS with ₵ symbol |
| Phone Numbers | +233 format with validation |

### 14.3 Loading States

```
List Loading:              Card Loading:
┌─────────────────────┐    ┌─────────────────────┐
│ ████████████████    │    │ ┌────┐              │
│ ████████            │    │ │░░░░│ ████████████ │
│ ████████████████    │    │ └────┘ ████████     │
│ ████████            │    │        ████████████ │
└─────────────────────┘    └─────────────────────┘
   Skeleton loading           Card skeleton

Action Loading:            Progress:
┌─────────────────────┐    ┌─────────────────────┐
│                     │    │ Uploading... 45%    │
│      ⏳ Loading...   │    │ ████████░░░░░░░░░░░ │
│                     │    │                     │
└─────────────────────┘    └─────────────────────┘
```

### 14.4 Empty States

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│                              📭                                         │
│                                                                         │
│                       No students found                                 │
│                                                                         │
│           Try adjusting your filters or add a new student.             │
│                                                                         │
│                    ┌─────────────────────────────┐                      │
│                    │      + Add Student          │                      │
│                    └─────────────────────────────┘                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | January 2026 | Harry McNinson | Initial version |
| 2.0 | January 2026 | Harry McNinson | Added subdomain login flows, registration screens, mobile app school selection |
