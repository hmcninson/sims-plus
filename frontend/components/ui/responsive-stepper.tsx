"use client";

import { cn } from "@/lib/utils";
import { Check } from "lucide-react";

interface Step {
  label: string;
  description?: string;
}

interface ResponsiveStepperProps {
  steps: Step[];
  currentStep: number;
  onStepClick?: (step: number) => void;
  className?: string;
}

export function ResponsiveStepper({ steps, currentStep, onStepClick, className }: ResponsiveStepperProps) {
  return (
    <>
      {/* Desktop: Vertical stepper */}
      <div className={cn("hidden md:block w-48 shrink-0", className)}>
        <nav aria-label="Progress">
          <ol className="space-y-4">
            {steps.map((step, index) => {
              const isCompleted = index < currentStep;
              const isCurrent = index === currentStep;
              return (
                <li key={step.label}>
                  <button
                    type="button"
                    onClick={() => onStepClick?.(index)}
                    disabled={!onStepClick}
                    className={cn(
                      "flex items-center gap-3 text-left w-full",
                      onStepClick && "cursor-pointer hover:opacity-80",
                      !onStepClick && "cursor-default"
                    )}
                  >
                    <span
                      className={cn(
                        "flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 text-xs font-medium",
                        isCompleted && "border-primary bg-primary text-primary-foreground",
                        isCurrent && "border-primary text-primary",
                        !isCompleted && !isCurrent && "border-muted-foreground/30 text-muted-foreground"
                      )}
                    >
                      {isCompleted ? <Check className="h-4 w-4" /> : index + 1}
                    </span>
                    <span className={cn(
                      "text-sm font-medium",
                      isCurrent && "text-foreground",
                      !isCurrent && "text-muted-foreground"
                    )}>
                      {step.label}
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>
        </nav>
      </div>

      {/* Mobile: Horizontal step indicator */}
      <div className="md:hidden mb-6">
        <div className="flex items-center justify-between">
          {steps.map((step, index) => {
            const isCompleted = index < currentStep;
            const isCurrent = index === currentStep;
            return (
              <div key={step.label} className="flex flex-1 items-center">
                <button
                  type="button"
                  onClick={() => onStepClick?.(index)}
                  disabled={!onStepClick}
                  className="flex flex-col items-center gap-1"
                >
                  <span
                    className={cn(
                      "flex h-7 w-7 items-center justify-center rounded-full border-2 text-xs font-medium",
                      isCompleted && "border-primary bg-primary text-primary-foreground",
                      isCurrent && "border-primary text-primary",
                      !isCompleted && !isCurrent && "border-muted-foreground/30 text-muted-foreground"
                    )}
                  >
                    {isCompleted ? <Check className="h-3 w-3" /> : index + 1}
                  </span>
                  <span className={cn(
                    "text-[10px] font-medium text-center leading-tight max-w-[60px]",
                    isCurrent ? "text-foreground" : "text-muted-foreground"
                  )}>
                    {step.label}
                  </span>
                </button>
                {index < steps.length - 1 && (
                  <div className={cn(
                    "flex-1 h-0.5 mx-1",
                    isCompleted ? "bg-primary" : "bg-muted"
                  )} />
                )}
              </div>
            );
          })}
        </div>
        <p className="mt-2 text-xs text-muted-foreground text-center">
          Step {currentStep + 1} of {steps.length}: {steps[currentStep]?.label}
        </p>
      </div>
    </>
  );
}
