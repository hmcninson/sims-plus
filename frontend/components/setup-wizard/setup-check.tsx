"use client";

import { useState, useEffect } from "react";
import { SetupWizard } from "./setup-wizard";
import type { SchoolProfile, AcademicYear, Class } from "@/types";

interface SetupCheckProps {
  schoolProfile: SchoolProfile;
  academicYears: AcademicYear[];
  classes: Class[];
  children: React.ReactNode;
}

export function SetupCheck({
  schoolProfile,
  academicYears,
  classes,
  children,
}: SetupCheckProps) {
  const [showWizard, setShowWizard] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    // Check if setup is needed:
    // - No academic years exist
    // - No classes exist
    // - School motto is empty (basic profile incomplete)
    const needsSetup =
      academicYears.length === 0 ||
      classes.length === 0;

    // Check if user has already dismissed the wizard in this session
    const wizardDismissed = sessionStorage.getItem("setup_wizard_dismissed");

    if (needsSetup && !wizardDismissed && !dismissed) {
      setShowWizard(true);
    }
  }, [academicYears, classes, dismissed]);

  const handleComplete = () => {
    setShowWizard(false);
    setDismissed(true);
    sessionStorage.setItem("setup_wizard_dismissed", "true");
  };

  if (showWizard) {
    return (
      <SetupWizard
        schoolProfile={schoolProfile}
        onComplete={handleComplete}
      />
    );
  }

  return <>{children}</>;
}
