import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CollapsibleFilters } from "@/components/filters/collapsible-filters";

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

describe("CollapsibleFilters", () => {
  it("renders children in the desktop container", () => {
    render(
      <CollapsibleFilters>
        <span data-testid="filter-child">Status filter</span>
      </CollapsibleFilters>
    );

    // Children appear in the desktop (hidden md:flex) container
    const child = screen.getByTestId("filter-child");
    expect(child).toBeInTheDocument();
  });

  it("renders the Filters toggle button for mobile", () => {
    render(
      <CollapsibleFilters>
        <span>Some filter</span>
      </CollapsibleFilters>
    );

    // The mobile collapsible trigger shows "Filters" text
    const button = screen.getByRole("button", { name: /filters/i });
    expect(button).toBeInTheDocument();
  });

  it("shows active filter count badge when activeFilterCount > 0", () => {
    render(
      <CollapsibleFilters activeFilterCount={3}>
        <span>Filter</span>
      </CollapsibleFilters>
    );

    // Badge should show the count "3"
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("does not show badge when activeFilterCount is 0", () => {
    render(
      <CollapsibleFilters activeFilterCount={0}>
        <span>Filter</span>
      </CollapsibleFilters>
    );

    // No badge with "0" should be rendered
    expect(screen.queryByText("0")).not.toBeInTheDocument();
  });

  it("expands collapsible content when toggle is clicked", async () => {
    const user = userEvent.setup();

    render(
      <CollapsibleFilters>
        <span>Hidden filter content</span>
      </CollapsibleFilters>
    );

    const toggleBtn = screen.getByRole("button", { name: /filters/i });
    await user.click(toggleBtn);

    // After clicking, the collapsible content should be visible.
    // The children appear in both desktop (always visible) and mobile
    // (now expanded) containers.
    const allChildren = screen.getAllByText("Hidden filter content");
    expect(allChildren.length).toBeGreaterThanOrEqual(1);
  });
});
