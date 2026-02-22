# Finance Module - UI Test Plan

This document contains all the manual tests to perform from a user's perspective for the Finance module.

---

## Prerequisites

Before testing, ensure you have:
- [ ] At least one active academic year
- [ ] At least one term configured
- [ ] At least 3-5 students enrolled
- [ ] At least 2-3 classes with students
- [ ] Admin or Finance Officer role access

---

## 1. Fee Types

### 1.1 View Fee Types List
| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1 | View fee types page | Navigate to Finance > Fee Types | Fee types list page loads with table |
| 2 | Empty state display | View page with no fee types | Shows empty state with "Create your first fee type" button |
| 3 | Filter by category | Select a category from filter dropdown | Table shows only fee types matching that category |
| 4 | Filter by status | Toggle active/inactive filter | Table updates to show matching fee types |
| 5 | Search fee types | Type in search box | Table filters by name as you type |

### 1.2 Create Fee Type
| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1 | Open create dialog | Click "+ New Fee Type" button | Dialog opens with empty form |
| 2 | Create with required fields | Fill name, category, default amount > Submit | Fee type created, appears in list |
| 3 | Create optional fee type | Check "Optional" checkbox > Submit | Fee type created with optional badge |
| 4 | Validation - empty name | Submit with empty name | Shows "Name is required" error |
| 5 | Validation - negative amount | Enter negative default amount | Shows validation error |
| 6 | Create with description | Fill all fields including description | Fee type created with description shown |

### 1.3 Edit Fee Type
| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1 | Open edit dialog | Click edit icon on a fee type row | Dialog opens with pre-filled data |
| 2 | Update name | Change name > Submit | Name updated in list |
| 3 | Toggle active status | Toggle is_active switch | Status updates (active/inactive badge changes) |
| 4 | Update category | Change category > Submit | Category badge updates |

### 1.4 Delete Fee Type
| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1 | Delete unused fee type | Click delete > Confirm | Fee type removed from list |
| 2 | Delete fee type in use | Try to delete fee type used in structure | Shows error - cannot delete (if implemented) |

---

## 2. Fee Structures

### 2.1 View Fee Structures List
| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1 | View fee structures page | Navigate to Finance > Fee Structures | List page loads with cards/table |
| 2 | Filter by academic year | Select year from dropdown | Shows only structures for that year |
| 3 | Filter by term | Select term from dropdown | Shows only structures for that term |
| 4 | Filter by level category | Select level (Primary, JHS, etc.) | Shows matching structures |
| 5 | View structure total | Look at any structure card | Shows correct total of all fee items |

### 2.2 Create Fee Structure
| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1 | Open create page | Click "+ New Fee Structure" | Form page loads |
| 2 | Set basic info | Fill name, select academic year, term | Fields accept input |
| 3 | Select target - All students | Choose "All Students" for student type | Applies to all students |
| 4 | Select target - Level category | Choose "JHS" for level category | Applies to all JHS classes |
| 5 | Select target - Specific class | Choose specific class | Applies to that class only |
| 6 | Add fee item manually | Click "Add Item", fill name & amount | Item added to list |
| 7 | Add fee item from fee type | Search and select existing fee type | Item added with pre-filled data |
| 8 | Create new fee type inline | Type new name > Click "Create new" | Creates fee type and adds item |
| 9 | Mark item as optional | Check "Optional" checkbox on item | Item marked with optional badge |
| 10 | Remove fee item | Click trash icon on item | Item removed from list |
| 11 | Reorder items | Drag items to reorder | Sequence numbers update |
| 12 | Submit with items | Fill all fields > Add 2+ items > Submit | Structure created, redirects to detail |
| 13 | Validation - no items | Try to submit with no fee items | Shows "At least one fee item required" |
| 14 | Validation - empty name | Submit with empty structure name | Shows validation error |

### 2.3 View Fee Structure Detail
| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1 | View detail page | Click on a fee structure | Detail page loads |
| 2 | See all fee items | Look at items table | All items displayed with amounts |
| 3 | See total amount | Check summary section | Shows correct total |
| 4 | See required vs optional totals | Check summary | Shows breakdown of required/optional |
| 5 | Edit button works | Click Edit button | Navigates to edit page |

### 2.4 Edit Fee Structure
| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1 | Load existing data | Navigate to edit page | Form pre-filled with existing data |
| 2 | Update name | Change name > Save | Name updated |
| 3 | Add new item | Add a fee item > Save | New item appears in structure |
| 4 | Remove item | Remove an item > Save | Item removed from structure |
| 5 | Update item amount | Change amount > Save | Amount updated |
| 6 | Toggle active status | Toggle is_active > Save | Status changes |

### 2.5 Delete Fee Structure
| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1 | Delete structure | Click Delete > Confirm | Structure removed |
| 2 | Delete structure with invoices | Try to delete if invoices exist | Shows error or warning |

---

## 3. Invoices

### 3.1 View Invoices List
| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1 | View invoices page | Navigate to Finance > Invoices | Invoice list loads |
| 2 | See summary cards | Look at top of page | Shows total, pending, paid, overdue counts |
| 3 | Filter by status | Select "Pending" from dropdown | Shows only pending invoices |
| 4 | Filter by academic year | Select year | Shows invoices for that year |
| 5 | Filter by term | Select term | Shows invoices for that term |
| 6 | Search by student | Type student name | Filters to matching students |
| 7 | Search by invoice number | Type invoice number | Shows matching invoice |
| 8 | Pagination | Navigate to next page | Shows next set of invoices |

### 3.2 Generate Invoices (Bulk)
| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1 | Open generate page | Click "Generate Invoices" | Bulk generate form loads |
| 2 | Select fee structure | Choose from dropdown | Fee structure selected |
| 3 | Select target class | Choose class | Shows student count |
| 4 | Preview generation | See preview of invoices to create | Shows count and total |
| 5 | Generate invoices | Click Generate | Invoices created, shows success |
| 6 | Skip existing | Generate for same class again | Shows "already exists" for duplicates |
| 7 | Set due date | Select due date | Invoices created with that due date |

### 3.3 Create Single Invoice
| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1 | Open create form | Click "+ New Invoice" | Form loads |
| 2 | Search student | Type student name | Dropdown shows matching students |
| 3 | Select student | Click on student | Student selected, shows details |
| 4 | Select fee structure | Choose fee structure | Items auto-populate |
| 5 | Add custom item | Add manual line item | Item added with custom description |
| 6 | Set due date | Pick date | Due date set |
| 7 | Add notes | Type in notes field | Notes saved |
| 8 | Create as draft | Submit | Invoice created in draft status |

### 3.4 View Invoice Detail
| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1 | View invoice | Click on invoice row | Detail page loads |
| 2 | See line items | Look at items section | All items with amounts displayed |
| 3 | See payment history | Look at payments section | Shows all payments made |
| 4 | See balance | Check balance displayed | Shows correct remaining balance |
| 5 | See student info | Check student section | Shows student name, class, ID |
| 6 | Download/Print | Click print/download | PDF generated or print dialog |

### 3.5 Invoice Status Workflow
| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1 | Issue draft invoice | Click "Issue" on draft | Status changes to "issued" |
| 2 | Cancel draft | Click "Cancel" on draft | Status changes to "cancelled" |
| 3 | Cannot edit issued | Try to edit issued invoice | Edit disabled or restricted |
| 4 | Partial payment | Record partial payment | Status changes to "partial" |
| 5 | Full payment | Pay remaining balance | Status changes to "paid" |
| 6 | Overdue status | Check invoice past due date | Shows "overdue" status |

---

## 4. Payments

### 4.1 View Payments List
| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1 | View payments page | Navigate to Finance > Payments | Payment list loads |
| 2 | Summary cards | Look at top section | Shows today's, this week's, this month's totals |
| 3 | Filter by method | Select "Cash" | Shows only cash payments |
| 4 | Filter by date range | Select date range | Shows payments in range |
| 5 | Search by receipt | Type receipt number | Shows matching payment |
| 6 | Search by student | Type student name | Shows payments for student |

### 4.2 Record Payment
| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1 | Open record page | Click "Record Payment" | Payment form loads |
| 2 | Search student | Type student name | Shows matching students |
| 3 | Select student | Click student | Shows their outstanding invoices |
| 4 | Select invoice | Check invoice checkbox | Invoice selected for payment |
| 5 | Enter amount | Type payment amount | Amount entered |
| 6 | Select cash method | Choose "Cash" | Cash method selected |
| 7 | Enter payer info | Fill payer name, phone | Info captured |
| 8 | Submit payment | Click Record | Payment recorded, receipt shown |
| 9 | Partial payment | Pay less than balance | Payment recorded, invoice now "partial" |
| 10 | Overpayment | Pay more than balance | Shows warning or creates credit note |
| 11 | MoMo payment | Select "MTN MoMo" | Shows phone number field |
| 12 | Bank transfer | Select "Bank Transfer" | Shows reference field |

### 4.3 View Payment Receipt
| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1 | View receipt | Click on payment row | Receipt detail page loads |
| 2 | See payment info | Check all fields | Shows amount, method, date, payer |
| 3 | See related invoice | Click invoice link | Navigates to invoice detail |
| 4 | Print receipt | Click Print | Print dialog or PDF download |

### 4.4 Void Payment
| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1 | Void payment | Click Void > Enter reason > Confirm | Payment voided |
| 2 | Invoice balance updates | Check related invoice | Balance restored |
| 3 | Cannot void twice | Try to void already voided | Button disabled or error |

---

## 5. Scholarships

### 5.1 View Scholarships List
| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1 | View scholarships page | Navigate to Finance > Scholarships | List page loads |
| 2 | See scholarship summary | Look at cards | Shows active count, total value |
| 3 | Filter by type | Select "Merit" | Shows only merit scholarships |
| 4 | Filter by status | Toggle active/inactive | Shows matching scholarships |
| 5 | See recipient count | Look at scholarship row | Shows X/Y recipients |

### 5.2 Create Scholarship
| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1 | Open create page | Click "+ New Scholarship" | Form loads |
| 2 | Fill basic info | Enter name, code | Fields accept input |
| 3 | Select type | Choose "Merit" | Type selected |
| 4 | Set percentage coverage | Choose "Percentage" > Enter 50 | 50% coverage set |
| 5 | Set fixed amount | Choose "Fixed Amount" > Enter 500 | GHS 500 coverage set |
| 6 | Set max recipients | Enter 10 | Limit set to 10 |
| 7 | Select academic year | Choose year | Year selected |
| 8 | Apply to all fees | Check "All Fees" | Applies to entire invoice |
| 9 | Apply to specific fees | Uncheck all, check specific | Only those fees covered |
| 10 | Add description | Enter description | Description saved |
| 11 | Submit | Click Create | Scholarship created |

### 5.3 View Scholarship Detail
| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1 | View detail | Click scholarship | Detail page loads |
| 2 | See coverage info | Check coverage section | Shows type and value |
| 3 | See recipients list | Look at recipients table | Shows all awarded students |
| 4 | See available spots | Check recipient count | Shows X/Y (available/max) |

### 5.4 Award Scholarship
| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1 | Open award page | Click "Award" button | Award form loads |
| 2 | Search student | Type student name | Shows matching students |
| 3 | Filter by class | Select class | Shows students in that class |
| 4 | Select student | Check student checkbox | Student selected |
| 5 | Set effective date | Choose start date | Date set |
| 6 | Set end date | Choose end date (optional) | End date set |
| 7 | Override coverage | Enter different value | Override set |
| 8 | Add notes | Enter notes | Notes saved |
| 9 | Award | Click Award | Student receives scholarship |
| 10 | Award at capacity | Try to award when max reached | Shows error - max recipients |
| 11 | Duplicate award | Try to award same student | Shows error - already has this |

### 5.5 Revoke Scholarship
| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1 | Revoke scholarship | Click Revoke on recipient | Confirmation dialog |
| 2 | Enter reason | Type revocation reason | Required field |
| 3 | Confirm revoke | Click Confirm | Scholarship revoked |
| 4 | Check invoice impact | View student's invoices | Discount removed, balance updated |

### 5.6 Edit Scholarship
| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1 | Edit scholarship | Click Edit | Form loads with data |
| 2 | Update coverage | Change value | Updated on save |
| 3 | Deactivate | Toggle is_active off | Scholarship inactive |
| 4 | Increase max recipients | Change max from 5 to 10 | More slots available |

---

## 6. Credit Notes

### 6.1 View Credit Notes List
| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1 | View credit notes page | Navigate to Finance > Credit Notes | List page loads |
| 2 | Summary cards | Check summary section | Shows draft, issued, applied totals |
| 3 | Filter by status | Select "Issued" | Shows only issued notes |
| 4 | Filter by type | Select "Overpayment" | Shows only overpayment notes |
| 5 | Search by number | Type credit note number | Shows matching note |

### 6.2 Create Credit Note
| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1 | Open create page | Click "+ New Credit Note" | Form loads |
| 2 | Select type | Choose "Overpayment" | Type selected |
| 3 | Search student | Type student name | Shows matching students |
| 4 | Select student | Click student | Student selected |
| 5 | Link to invoice | Select related invoice (optional) | Invoice linked |
| 6 | Enter amount | Type amount | Amount entered |
| 7 | Enter reason | Type reason (required) | Reason captured |
| 8 | Add notes | Type additional notes | Notes saved |
| 9 | Submit | Click Create | Credit note created as draft |

### 6.3 View Credit Note Detail
| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1 | View detail | Click credit note | Detail page loads |
| 2 | See all info | Check all sections | Shows amount, student, reason |
| 3 | See related invoice | Click invoice link | Navigates to invoice |
| 4 | See status history | Check status section | Shows when issued/applied/etc |

### 6.4 Issue Credit Note
| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1 | Issue from list | Click Issue on draft row | Confirmation dialog |
| 2 | Confirm issue | Click Confirm | Status changes to "issued" |
| 3 | Issue from detail | Click Issue on detail page | Same result |
| 4 | Student credit balance | Check student's credit balance | Balance increased |

### 6.5 Apply Credit Note to Invoice
| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1 | Apply from detail | Click "Apply to Invoice" | Dialog opens |
| 2 | See available invoices | Look at invoice dropdown | Shows student's unpaid invoices |
| 3 | Select invoice | Choose invoice | Invoice selected |
| 4 | Apply full amount | Leave amount empty > Submit | Full credit applied |
| 5 | Apply partial | Enter partial amount > Submit | Partial credit applied |
| 6 | Invoice balance updates | Check invoice | Balance reduced by credit |
| 7 | Credit note status | Check credit note | Status is "applied" |

### 6.6 Refund Credit Note
| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1 | Refund from detail | Click "Refund" button | Refund dialog opens |
| 2 | Select method | Choose Cash/MoMo/etc | Method selected |
| 3 | Enter reference | Type reference number | Reference captured |
| 4 | Submit refund | Click Record Refund | Refund recorded |
| 5 | Status updates | Check credit note | Status is "refunded" |

### 6.7 Cancel Credit Note
| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1 | Cancel draft | Click Cancel on draft | Confirmation dialog |
| 2 | Enter reason | Type cancellation reason | Reason required |
| 3 | Confirm cancel | Click Confirm | Status is "cancelled" |
| 4 | Cannot cancel issued | Check issued credit note | Cancel button not available |

---

## 7. Finance Dashboard

### 7.1 Dashboard Overview
| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1 | View dashboard | Navigate to Finance > Overview | Dashboard loads |
| 2 | See summary stats | Check top cards | Shows expected, collected, outstanding |
| 3 | See recent payments | Check recent section | Shows latest payments |
| 4 | See outstanding by class | Check chart/table | Shows breakdown by class |
| 5 | Date range filter | Change date range | Stats update for range |
| 6 | Quick actions | Check quick action buttons | Links to common tasks work |

---

## 8. Student Finance View

### 8.1 Student Profile - Finance Tab
| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1 | View student finance | Go to student > Finance tab | Shows finance summary |
| 2 | See invoices | Check invoices section | Lists all student invoices |
| 3 | See payments | Check payments section | Lists all payments made |
| 4 | See scholarships | Check scholarships section | Shows active scholarships |
| 5 | See credit balance | Check credit section | Shows available credit |
| 6 | Record payment here | Click Record Payment | Opens payment form for student |
| 7 | Create invoice here | Click Create Invoice | Opens invoice form for student |

---

## 9. Reports

### 9.1 Finance Reports
| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1 | View reports page | Navigate to Finance > Reports | Reports page loads |
| 2 | Collection report | Select Collection Summary | Shows collections by period |
| 3 | Outstanding report | Select Outstanding Fees | Shows all unpaid balances |
| 4 | Export to Excel | Click Export | Downloads Excel file |
| 5 | Export to PDF | Click PDF | Downloads PDF file |
| 6 | Filter by date | Set date range | Report filters to range |
| 7 | Filter by class | Select class | Report filters to class |

---

## 10. Edge Cases & Error Handling

### 10.1 Error Scenarios
| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1 | Network error | Disconnect network > Try action | Shows error message, retry option |
| 2 | Session expired | Wait for timeout > Try action | Redirects to login |
| 3 | Permission denied | Try action without permission | Shows access denied message |
| 4 | Invalid data | Submit form with invalid data | Shows validation errors |
| 5 | Concurrent edit | Two users edit same record | Shows conflict warning |

### 10.2 Data Integrity
| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1 | Delete with dependencies | Delete item with linked records | Shows warning or prevents deletion |
| 2 | Negative balance | Check invoices never go negative | Balance stops at 0 |
| 3 | Payment exceeds balance | Pay more than owed | Creates credit or shows warning |
| 4 | Decimal precision | Enter amount with 3+ decimals | Rounds to 2 decimal places |

---

## Test Sign-off

| Module | Tested By | Date | Status | Notes |
|--------|-----------|------|--------|-------|
| Fee Types | | | | |
| Fee Structures | | | | |
| Invoices | | | | |
| Payments | | | | |
| Scholarships | | | | |
| Credit Notes | | | | |
| Dashboard | | | | |
| Student Finance | | | | |
| Reports | | | | |

---

## Known Issues / Bugs Found

| # | Description | Severity | Module | Status |
|---|-------------|----------|--------|--------|
| | | | | |

---

*Document Version: 1.0*
*Last Updated: January 2026*
