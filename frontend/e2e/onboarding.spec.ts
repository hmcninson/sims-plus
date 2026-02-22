import { test, expect } from "@playwright/test";

test.describe("School Onboarding", () => {
  test("complete registration flow", async ({ page }) => {
    await page.goto("/register");

    // School information section
    await page.fill('[name="school_name"]', "Playwright Test School");

    // Wait for the subdomain to be auto-generated from school name.
    // The useEffect that generates the subdomain fires after the
    // schoolName state update, so we need a small wait.
    const subdomainInput = page.locator('[name="subdomain"]');
    await expect(subdomainInput).not.toHaveValue("", { timeout: 2000 });

    // Override the auto-generated subdomain with a unique one to avoid
    // collisions across test runs
    const uniqueSubdomain = `e2etest${Date.now()}`;
    await subdomainInput.clear();
    await subdomainInput.fill(uniqueSubdomain);

    // Select school type using the Radix Select component.
    // Radix Select renders a <button role="combobox"> as the trigger.
    await page.locator('[role="combobox"]').click();
    await page.locator('[role="option"]:has-text("Basic School (Primary + JHS)")').click();

    // Wait for subdomain availability check to complete.
    // The component auto-checks after a 300ms debounce.
    await expect(
      page.locator("text=.simsplus.io is available")
    ).toBeVisible({ timeout: 10000 });

    // Administrator account section
    await page.fill('[name="first_name"]', "E2E");
    await page.fill('[name="last_name"]', "Admin");
    await page.fill('[name="email"]', "admin@e2etest.edu.gh");
    await page.fill('[name="phone"]', "+233244000000");
    await page.fill('[name="password"]', "SecureP@ss1");
    await page.fill('[name="confirm_password"]', "SecureP@ss1");

    // Submit the form -- button text is "Start Free Trial"
    await page.click('button:has-text("Start Free Trial")');

    // Successful registration redirects to /register/success
    await expect(page).toHaveURL(/.*register\/success/, { timeout: 15000 });
  });

  test("duplicate subdomain shows error", async ({ page }) => {
    await page.goto("/register");

    // Clear any auto-generated value first, then type a known taken subdomain.
    // The subdomain availability is auto-checked after a 300ms debounce.
    const subdomainInput = page.locator('[name="subdomain"]');
    await subdomainInput.clear();
    await subdomainInput.fill("presec");

    // Wait for the availability check to complete and show the error.
    // The error message appears as a red text element below the subdomain input.
    await expect(
      page.locator(".text-red-600, .text-destructive")
    ).toBeVisible({ timeout: 10000 });

    // Verify the error indicates the subdomain is taken or unavailable
    await expect(
      page.locator(".text-red-600, .text-destructive")
    ).toContainText(/taken|unavailable|reserved/i);
  });

  test("reserved subdomain shows error", async ({ page }) => {
    await page.goto("/register");

    // Clear any auto-generated value, then type a reserved subdomain.
    // Client-side check catches reserved subdomains immediately (no API call).
    const subdomainInput = page.locator('[name="subdomain"]');
    await subdomainInput.clear();
    await subdomainInput.fill("admin");

    // The reserved subdomain error should appear without waiting for API
    await expect(
      page.locator(".text-red-600, .text-destructive")
    ).toBeVisible({ timeout: 5000 });

    await expect(
      page.locator(".text-red-600, .text-destructive")
    ).toContainText(/reserved/i);
  });

  test("submit button disabled when subdomain is not available", async ({ page }) => {
    await page.goto("/register");

    // Without a valid available subdomain, the submit button should be disabled.
    // The button is disabled when: isLoading || subdomainStatus !== "available"
    // Initially subdomainStatus is "idle", so the button starts disabled.
    const submitButton = page.locator('button:has-text("Start Free Trial")');
    await expect(submitButton).toBeDisabled();
  });

  test("password mismatch shows toast error", async ({ page }) => {
    await page.goto("/register");

    // Fill school name to generate a subdomain
    await page.fill('[name="school_name"]', "Mismatch Test School");

    // Wait for subdomain auto-generation and availability check
    await expect(
      page.locator("text=.simsplus.io is available")
    ).toBeVisible({ timeout: 10000 });

    // Select school type
    await page.locator('[role="combobox"]').click();
    await page.locator('[role="option"]:has-text("Primary School")').click();

    // Fill admin details with mismatched passwords
    await page.fill('[name="first_name"]', "Test");
    await page.fill('[name="last_name"]', "User");
    await page.fill('[name="email"]', "test@mismatch.edu.gh");
    await page.fill('[name="phone"]', "+233244000001");
    await page.fill('[name="password"]', "SecureP@ss1");
    await page.fill('[name="confirm_password"]', "DifferentP@ss1");

    // Submit the form
    await page.click('button:has-text("Start Free Trial")');

    // The form handler checks for password mismatch and shows a toast error.
    // Sonner toasts appear as elements with role="status" or in a toast container.
    await expect(
      page.locator('[data-sonner-toast]', { hasText: /passwords do not match/i })
    ).toBeVisible({ timeout: 5000 });
  });
});
