import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ResponsiveStepper } from "@/components/ui/responsive-stepper";

const steps = [
  { label: "Basic Info", description: "School details" },
  { label: "Academic", description: "Academic setup" },
  { label: "Review", description: "Final review" },
];

describe("ResponsiveStepper", () => {
  it("renders all step labels", () => {
    render(<ResponsiveStepper steps={steps} currentStep={0} />);

    // Each label appears in both desktop and mobile containers
    for (const step of steps) {
      const labels = screen.getAllByText(step.label);
      expect(labels.length).toBeGreaterThanOrEqual(1);
    }
  });

  it("renders step numbers for non-completed steps", () => {
    render(<ResponsiveStepper steps={steps} currentStep={1} />);

    // Step 2 (index=1) is current, step 3 (index=2) is upcoming
    // Both should show their number. Step 1 (index=0) is completed.
    // "2" appears in both desktop and mobile
    const twos = screen.getAllByText("2");
    expect(twos.length).toBeGreaterThanOrEqual(1);

    const threes = screen.getAllByText("3");
    expect(threes.length).toBeGreaterThanOrEqual(1);
  });

  it("shows current step indicator text on mobile", () => {
    render(<ResponsiveStepper steps={steps} currentStep={1} />);

    // Mobile shows "Step 2 of 3: Academic"
    expect(screen.getByText(/step 2 of 3/i)).toBeInTheDocument();
  });

  it("calls onStepClick when a step is clicked", async () => {
    const user = userEvent.setup();
    const handleClick = vi.fn();

    render(
      <ResponsiveStepper
        steps={steps}
        currentStep={0}
        onStepClick={handleClick}
      />
    );

    // Click on the "Review" step label (in either desktop or mobile view)
    const reviewButtons = screen.getAllByText("Review");
    // Click the first one that is a button's descendant
    await user.click(reviewButtons[0].closest("button")!);

    expect(handleClick).toHaveBeenCalledWith(2);
  });

  it("disables step buttons when onStepClick is not provided", () => {
    render(<ResponsiveStepper steps={steps} currentStep={0} />);

    const buttons = screen.getAllByRole("button");
    buttons.forEach((btn) => {
      expect(btn).toBeDisabled();
    });
  });
});
