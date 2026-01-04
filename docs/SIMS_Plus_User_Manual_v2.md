# SIMS Plus (School Information Management System Plus) - User Manual

**Version:** 2.0  
**Date:** January 2026  
**Author:** Harry McNinson  
**Audience:** School Administrators, Teachers, Finance Officers, Parents

---

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [Accessing Your School Portal](#2-accessing-your-school-portal)
3. [Dashboard Overview](#3-dashboard-overview)
4. [Student Management](#4-student-management)
5. [Staff Management](#5-staff-management)
6. [Academic Management](#6-academic-management)
7. [Attendance](#7-attendance)
8. [Examinations & Grading](#8-examinations--grading)
9. [Finance Management](#9-finance-management)
10. [Report Cards](#10-report-cards)
11. [Boarding House](#11-boarding-house)
12. [Transport](#12-transport)
13. [Communication](#13-communication)
14. [Reports](#14-reports)
15. [Parent Portal Guide](#15-parent-portal-guide)
16. [Mobile App Guide](#16-mobile-app-guide)
17. [Troubleshooting & FAQ](#17-troubleshooting--faq)

---

## 1. Getting Started

### 1.1 What is SIMS Plus?

SIMS Plus is a comprehensive School Information Management System designed specifically for Ghanaian schools. It helps you manage:

- Student enrollment and records
- Staff information
- Attendance tracking
- Examinations and grading
- Fees and payments (including Mobile Money)
- Report cards
- Boarding houses
- Transport
- Parent communication

### 1.2 System Requirements

| Device | Minimum Requirements |
|--------|---------------------|
| **Computer** | Modern web browser (Chrome, Firefox, Safari, Edge) |
| **Tablet** | iOS 12+ or Android 8+ |
| **Mobile** | iOS 12+ or Android 8+ |
| **Internet** | Stable connection (works offline for some features) |

### 1.3 Browser Recommendations

For the best experience, use:
- ✅ Google Chrome (recommended)
- ✅ Mozilla Firefox
- ✅ Microsoft Edge
- ✅ Safari (Mac/iOS)

---

## 2. Accessing Your School Portal

### 2.1 Your School's Web Address

Each school has a unique web address (subdomain). Your school's SIMS Plus portal is:

```
https://[your-school-code].simsplus.io
```

**Examples:**
| School | Web Address |
|--------|-------------|
| Presbyterian Boys' Secondary School | `https://presec.simsplus.io` |
| Achimota School | `https://achimota.simsplus.io` |
| Wesley Girls' High School | `https://wesleyg.simsplus.io` |

> 💡 **Tip:** Bookmark your school's portal for quick access!

### 2.2 How to Login

**Step 1:** Open your web browser

**Step 2:** Type your school's SIMS Plus address in the address bar
```
https://[your-school-code].simsplus.io
```

**Step 3:** You will see your school's login page with:
- Your school's logo
- Your school's name
- Login form

**Step 4:** Enter your credentials
- Email address
- Password

**Step 5:** Click "Sign In"

### 2.3 Login Page Layout

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│              [YOUR SCHOOL'S LOGO]                   │
│                                                     │
│           Welcome to [School Name]                  │
│                                                     │
│   ┌─────────────────────────────────────────────┐   │
│   │ Email                                       │   │
│   │ your.email@school.edu.gh                    │   │
│   └─────────────────────────────────────────────┘   │
│                                                     │
│   ┌─────────────────────────────────────────────┐   │
│   │ Password                                    │   │
│   │ ••••••••                                    │   │
│   └─────────────────────────────────────────────┘   │
│                                                     │
│   ☐ Remember me          Forgot password?          │
│                                                     │
│   ┌─────────────────────────────────────────────┐   │
│   │              Sign In                        │   │
│   └─────────────────────────────────────────────┘   │
│                                                     │
│              Powered by SIMS Plus                  │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### 2.4 Don't Know Your School's Address?

If you don't remember your school's subdomain:

1. Go to `https://app.simsplus.io`
2. Enter your school's name in the search box
3. Select your school from the list
4. You'll be redirected to your school's login page

### 2.5 Forgot Password

1. Click "Forgot password?" on the login page
2. Enter your email address
3. Click "Send Reset Link"
4. Check your email for the reset link
5. Click the link and create a new password

> ⚠️ Reset links expire after 24 hours

### 2.6 First-Time Login

If you're logging in for the first time:

1. Use the temporary password sent to your email/SMS
2. You'll be prompted to change your password
3. Create a strong password (minimum 8 characters)
4. Complete your profile information

---

## 3. Dashboard Overview

### 3.1 Admin Dashboard

After logging in as an administrator, you'll see:

```
┌─────────────────────────────────────────────────────────────────┐
│  [Logo]  SIMS Plus            🔔 Notifications    👤 Profile   │
├─────────────────────────────────────────────────────────────────┤
│         │                                                       │
│ MENU    │   Good morning, Administrator! 👋                    │
│         │                                                       │
│ 📊 Dashboard │   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐
│ 👥 Students  │   │  1,234  │  │    48   │  │  94.2%  │  │ ₵45,000 │
│ 👨‍🏫 Staff     │   │Students │  │  Staff  │  │Attendance│  │  Fees   │
│ 📚 Academics │   └─────────┘  └─────────┘  └─────────┘  └─────────┘
│ ✓ Attendance │                                                  │
│ 📝 Exams     │   Recent Activity                                │
│ 💰 Finance   │   ───────────────────────────────────────────   │
│ 📄 Reports   │   • New student enrolled: Kwame Asante          │
│ ⚙️ Settings  │   • Fee payment: ₵500 from Ama Mensah           │
│              │   • Attendance marked: JHS 2A                    │
│              │                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Key Dashboard Widgets

| Widget | Description |
|--------|-------------|
| **Total Students** | Current enrolled students |
| **Total Staff** | Active staff members |
| **Attendance Rate** | Today's/week's attendance percentage |
| **Fees Collected** | Total fees collected this term |
| **Recent Activity** | Latest actions in the system |
| **Quick Actions** | Common tasks (Add Student, Mark Attendance, etc.) |

---

## 4. Student Management

### 4.1 Viewing Students

1. Click **Students** in the sidebar
2. Use filters to narrow results:
   - Class
   - Section
   - Status (Active, Inactive)
   - Gender
3. Use the search box to find specific students

### 4.2 Adding a New Student

1. Click **Students** → **Add Student**
2. Fill in required information:
   - **Personal Info:** Name, Date of Birth, Gender
   - **Photo:** Upload student photo
   - **Class:** Select class and section
   - **Guardian:** Add at least one guardian
3. Click **Save**

### 4.3 Student Profile

Click on any student to view their complete profile:

- **Overview:** Basic info, photo, status
- **Academic:** Class history, subjects
- **Attendance:** Attendance record and percentage
- **Finance:** Fee invoices and payments
- **Documents:** Uploaded documents
- **History:** Timeline of changes

### 4.4 Managing Guardians

Each student must have at least one guardian:

1. Go to student profile
2. Click **Guardians** tab
3. Click **Add Guardian**
4. Enter guardian details:
   - Name
   - Relationship (Father, Mother, Guardian, etc.)
   - Phone number (required)
   - Email (optional)
5. Mark one guardian as **Primary Contact**

---

## 5. Staff Management

### 5.1 Adding Staff

1. Click **Staff** → **Add Staff**
2. Fill in details:
   - Personal information
   - Contact details
   - Role (Teacher, Admin, etc.)
   - Department
3. Assign subjects and classes (for teachers)
4. Click **Save**

### 5.2 Staff Assignments

To assign a teacher to classes:

1. Go to **Staff** → Select teacher
2. Click **Assignments** tab
3. Click **Add Assignment**
4. Select class and subject
5. Click **Save**

---

## 6. Academic Management

### 6.1 Setting Up Academic Year

1. Go to **Settings** → **Academic Years**
2. Click **Add Academic Year**
3. Enter:
   - Name (e.g., "2025/2026")
   - Start date
   - End date
4. Click **Save**
5. Click **Set as Current** to activate

### 6.2 Setting Up Terms

1. Go to **Settings** → **Terms**
2. Click **Add Term**
3. Enter:
   - Name (e.g., "Term 1")
   - Start date
   - End date
4. Click **Save**

### 6.3 Managing Classes

1. Go to **Academics** → **Classes**
2. View existing classes
3. To add a class:
   - Click **Add Class**
   - Enter name (e.g., "JHS 2")
   - Set capacity
   - Click **Save**

### 6.4 Managing Subjects

1. Go to **Academics** → **Subjects**
2. Click **Add Subject**
3. Enter:
   - Subject name
   - Subject code
   - Type (Core/Elective)
4. Assign to classes

---

## 7. Attendance

### 7.1 Marking Attendance

1. Go to **Attendance** → **Mark Attendance**
2. Select:
   - Class
   - Section
   - Date
3. For each student, select status:
   - ✅ Present
   - ❌ Absent
   - ⏰ Late
   - 📝 Excused
4. Click **Save**

> 💡 **Tip:** Use "Mark All Present" then adjust individual students

### 7.2 Attendance Statuses

| Status | Meaning |
|--------|---------|
| **Present** | Student attended |
| **Absent** | Student did not attend (no excuse) |
| **Late** | Student arrived late (enter time) |
| **Excused** | Absent with valid excuse |

### 7.3 Viewing Attendance Reports

1. Go to **Attendance** → **Reports**
2. Select date range
3. View by:
   - Class summary
   - Individual student
   - Daily breakdown

---

## 8. Examinations & Grading

### 8.1 Setting Up Exams

1. Go to **Exams** → **Manage Exams**
2. Click **Add Exam**
3. Enter:
   - Name (e.g., "End of Term 1 Exams")
   - Type (Mid-term, End-of-term, etc.)
   - Weight (e.g., 70%)
   - Date range
4. Click **Save**

### 8.2 Entering Scores

1. Go to **Exams** → **Enter Scores**
2. Select:
   - Exam
   - Class
   - Subject
3. Enter score for each student
4. Click **Save**

### 8.3 Grading Scale

Default GES grading scale:

| Score | Grade | Interpretation |
|-------|-------|----------------|
| 80-100 | 1 | Excellent |
| 70-79 | 2 | Very Good |
| 60-69 | 3 | Good |
| 55-59 | 4 | Credit |
| 50-54 | 5 | Pass |
| 40-49 | 6 | Weak Pass |
| 0-39 | 7 | Fail |

> Schools can customize grading scales in Settings

---

## 9. Finance Management

### 9.1 Fee Structure

1. Go to **Finance** → **Fee Structure**
2. Click **Add Fee Category**
3. Enter:
   - Name (e.g., "Tuition Fee")
   - Amount
   - Applicable classes
4. Click **Save**

### 9.2 Generating Invoices

1. Go to **Finance** → **Invoices**
2. Click **Generate Invoices**
3. Select:
   - Term
   - Classes (or all)
4. Click **Generate**

### 9.3 Recording Payments

1. Go to **Finance** → **Payments**
2. Click **Record Payment**
3. Search and select student
4. Enter:
   - Amount
   - Payment method:
     - Cash
     - MTN Mobile Money
     - Vodafone Cash
     - AirtelTigo Money
     - Bank Transfer
5. Click **Save**
6. Print or send receipt

### 9.4 Mobile Money Payment Steps

For MTN MoMo payments:

1. Select "MTN Mobile Money" as payment method
2. Enter payer's phone number
3. Enter amount
4. Click "Initiate Payment"
5. Customer receives prompt on their phone
6. Customer enters PIN to approve
7. Payment auto-confirms in system

---

## 10. Report Cards

### 10.1 Generating Report Cards

1. Go to **Reports** → **Report Cards**
2. Select:
   - Term
   - Class (or individual student)
3. Click **Generate**
4. Preview report cards
5. Click **Download** or **Print**

### 10.2 Report Card Contents

Each report card shows:
- Student information
- School logo and branding
- Subjects with scores and grades
- Class position
- Attendance summary
- Teacher remarks
- Head teacher remarks
- QR code for verification

### 10.3 Adding Remarks

1. Go to **Report Cards** → **Remarks**
2. Select class
3. Enter remarks for each student
4. Click **Save**

---

## 11. Boarding House

### 11.1 Managing Dormitories

1. Go to **Boarding** → **Dormitories**
2. Click **Add Dormitory**
3. Enter:
   - Name (e.g., "Peace House")
   - House Parent
   - Capacity

### 11.2 Room and Bed Assignment

1. Go to **Boarding** → **Room Assignment**
2. Select dormitory
3. Select room
4. Assign students to beds

### 11.3 Exeat Management

**For House Parents:**

1. Go to **Boarding** → **Exeat Requests**
2. View pending requests
3. Click on a request to review:
   - Student info
   - Reason
   - Pickup person details
4. Click **Approve** or **Reject**

**For Parents (via Parent Portal):**

1. Login to parent portal
2. Click **Request Exeat**
3. Fill in:
   - Reason
   - Departure date/time
   - Return date/time
   - Pickup person details
4. Submit for approval

---

## 12. Transport

### 12.1 Setting Up Routes

1. Go to **Transport** → **Routes**
2. Click **Add Route**
3. Enter:
   - Route name
   - Pickup points
   - Estimated times
4. Assign vehicle and driver

### 12.2 Assigning Students

1. Go to **Transport** → **Assignments**
2. Select student
3. Assign route and pickup point
4. Click **Save**

---

## 13. Communication

### 13.1 Sending SMS

1. Go to **Communication** → **Send SMS**
2. Select recipients:
   - All parents
   - Specific class
   - Individual parents
3. Type message (max 160 characters)
4. Click **Send**

### 13.2 Announcements

1. Go to **Communication** → **Announcements**
2. Click **New Announcement**
3. Enter:
   - Title
   - Message
   - Target audience
4. Click **Publish**

---

## 14. Reports

### 14.1 Available Reports

| Report | Description |
|--------|-------------|
| **Enrollment Report** | Student enrollment by class, gender |
| **Attendance Report** | Daily/weekly/monthly attendance |
| **Academic Report** | Performance by class, subject |
| **Financial Report** | Fee collection, outstanding |
| **Staff Report** | Staff list, assignments |

### 14.2 Generating Reports

1. Go to **Reports**
2. Select report type
3. Set parameters (date range, class, etc.)
4. Click **Generate**
5. View, download (PDF/Excel), or print

---

## 15. Parent Portal Guide

### 15.1 Accessing the Parent Portal

Parents access SIMS Plus through their child's school portal:

```
https://[school-code].simsplus.io
```

**Example:** `https://presec.simsplus.io`

### 15.2 First-Time Parent Login

When your child is enrolled:
1. The school adds your contact information
2. You receive an SMS with your login details:
   ```
   Welcome to SIMS Plus!
   Login: presec.simsplus.io
   Email: your.email@example.com
   Temporary Password: XXXX1234
   ```
3. Go to the school's portal and login
4. Change your password when prompted
5. Complete your profile

### 15.3 Parent Dashboard

After logging in, you'll see:
- Your children's overview
- Attendance summary
- Recent grades
- Outstanding fees
- Announcements

### 15.4 Paying School Fees

1. Login to parent portal
2. Click **Pay Fees**
3. Select child (if multiple)
4. View outstanding amount
5. Enter amount to pay
6. Select payment method:
   - MTN Mobile Money
   - Vodafone Cash
   - AirtelTigo Money
7. Enter your phone number
8. Click **Pay Now**
9. Approve payment on your phone
10. Download receipt

### 15.5 Viewing Report Cards

1. Login to parent portal
2. Click **Report Cards**
3. Select child and term
4. View or download PDF

### 15.6 Multiple Children

If you have children in multiple schools:
- Each school has a **separate login**
- Use each school's specific subdomain
- Your credentials may be different for each school

---

## 16. Mobile App Guide

### 16.1 Downloading the App

**Android:**
1. Open Google Play Store
2. Search "SIMS Plus"
3. Click Install

**iOS:**
1. Open App Store
2. Search "SIMS Plus"
3. Click Get

### 16.2 Setting Up the App

When you first open the app:

1. **Enter your school code**
   - Example: `presec`, `achimota`, `wesleyg`
   - The app will connect to your school's portal

2. **Login with your credentials**
   - Same email/password as the web portal

3. **Stay logged in**
   - The app remembers your school
   - You don't need to enter the code again

### 16.3 Switching Schools

If you work at or have children in multiple schools:

1. Tap the menu icon (☰)
2. Tap "Switch School"
3. Enter the new school code
4. Login with that school's credentials

### 16.4 Offline Features

The app works offline for:
- Viewing student lists
- Marking attendance
- Viewing previously loaded data

Data syncs automatically when you're back online.

---

## 17. Troubleshooting & FAQ

### 17.1 Login Issues

**Q: I can't login**
A: Try these steps:
1. Verify you're at the correct school URL
2. Check caps lock is off
3. Use "Forgot Password" to reset
4. Contact your school administrator

**Q: I see "School not found"**
A: Check that:
- You've typed the subdomain correctly
- Your school has an active SIMS Plus account
- Contact your school if the problem persists

**Q: My password reset link doesn't work**
A: Reset links expire after 24 hours. Request a new one.

### 17.2 School Portal Access

**Q: What's my school's web address?**
A: It's `https://[school-code].simsplus.io`. Ask your school administrator for the school code, or search at `app.simsplus.io`.

**Q: Can I login at simsplus.io directly?**
A: No, you must login at your specific school's subdomain (e.g., `presec.simsplus.io`). The main simsplus.io is just the marketing website.

**Q: I work at two schools. Can I use one login?**
A: No, each school has separate accounts. You'll have different logins for each school's portal.

### 17.3 Mobile Money Issues

**Q: My MoMo payment failed**
A: Common reasons:
- Insufficient balance
- Wrong PIN entered
- Network timeout
- Try again or use a different provider

**Q: I paid but it's not showing**
A: Wait 5 minutes for the system to update. If still missing, contact finance office with transaction ID.

### 17.4 Report Cards

**Q: Why can't I see report cards?**
A: Check that:
- Grades have been entered
- Report cards have been published
- You're looking at the correct term

### 17.5 General Issues

**Q: The system is slow**
A: Try:
- Refreshing the page
- Clearing browser cache
- Using a different browser
- Checking your internet connection

**Q: I found a bug**
A: Report it to your school administrator or use the feedback button in the app.

---

## Quick Reference Card

### Your School Portal URL

```
┌──────────────────────────────────────────────────────────┐
│                                                          │
│   Your SIMS Plus Portal:                                │
│                                                          │
│   https://_______________.simsplus.io                  │
│            ↑                                             │
│       (school code)                                      │
│                                                          │
│   Example: https://presec.simsplus.io                  │
│                                                          │
├──────────────────────────────────────────────────────────┤
│                                                          │
│   Don't know your school code?                           │
│   Visit: https://app.simsplus.io                       │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### Support Contact

- **Email:** support@simsplus.io
- **Phone:** +233 XX XXX XXXX
- **Hours:** Monday-Friday, 8am-5pm GMT

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | January 2026 | Harry McNinson | Initial version |
| 2.0 | January 2026 | Harry McNinson | Added subdomain access instructions, updated login flows |
