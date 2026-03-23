"use client";

import { useState, useEffect } from "react";
import { SetupWizard } from "./setup-wizard";
import type { SchoolProfile } from "@/types/school.type";

interface SetupCheckProps {
  schoolProfile: SchoolProfile | null;
  children: React.ReactNode;
}

export function SetupCheck({
  schoolProfile,
  children,
}: SetupCheckProps) {
  const [showWizard, setShowWizard] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const [initialStep, setInitialStep] = useState(0);

  useEffect(() => {
    // Use the backend-persisted setup_completed flag as the single source of truth
    const needsSetup = schoolProfile ? !schoolProfile.setup_completed : false;

    // Check if user has already dismissed the wizard in this session
    const wizardDismissed = sessionStorage.getItem("setup_wizard_dismissed");

    if (needsSetup && !wizardDismissed && !dismissed) {
      // Resume from the last completed step if the user left mid-wizard.
      // Clamp to valid range (0-6) to prevent out-of-bounds crash if
      // setup_wizard_step is 7 (persisted on completion) but setup_completed
      // was somehow reset to false.
      const resumeStep = Math.min(schoolProfile?.setup_wizard_step ?? 0, 6);
      setInitialStep(resumeStep);
      setShowWizard(true);
    }
  }, [schoolProfile, dismissed]);

  const handleComplete = () => {
    setShowWizard(false);
    setDismissed(true);
    sessionStorage.setItem("setup_wizard_dismissed", "true");
  };

  if (showWizard) {
    return (
      <SetupWizard
        schoolProfile={schoolProfile}
        initialStep={initialStep}
        onComplete={handleComplete}
      />
    );
  }

  return <>{children}</>;
}
