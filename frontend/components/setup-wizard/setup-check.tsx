"use client";

import { useState, useEffect } from "react";
import { SetupWizard } from "./setup-wizard";
import type { SchoolProfile, AcademicYear, Class, Term, Subject } from "@/types";

interface SetupCheckProps {
  schoolProfile: SchoolProfile | null;
  academicYears: AcademicYear[];
  classes: Class[];
  terms: Term[];
  subjects: Subject[];
  children: React.ReactNode;
}

export function SetupCheck({
  schoolProfile,
  academicYears,
  classes,
  terms,
  subjects,
  children,
}: SetupCheckProps) {
  const [showWizard, setShowWizard] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    // Check if setup is needed:
    // - No academic years exist
    // - No classes exist
    // - No terms exist
    // - No subjects exist
    const needsSetup =
      academicYears.length === 0 ||
      classes.length === 0 ||
      terms.length === 0 ||
      subjects.length === 0;

    // Check if user has already dismissed the wizard in this session
    const wizardDismissed = sessionStorage.getItem("setup_wizard_dismissed");

    if (needsSetup && !wizardDismissed && !dismissed) {
      setShowWizard(true);
    }
  }, [academicYears, classes, terms, subjects, dismissed]);

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
