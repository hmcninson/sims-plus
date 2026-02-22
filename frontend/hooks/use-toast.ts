"use client";

import { toast as sonnerToast } from "sonner";

type ToastOptions = {
  title?: string;
  description?: string;
  variant?: "default" | "destructive";
  duration?: number;
};

export function useToast() {
  const toast = ({ title, description, variant, duration }: ToastOptions) => {
    if (variant === "destructive") {
      sonnerToast.error(title, {
        description,
        duration,
      });
    } else {
      sonnerToast.success(title, {
        description,
        duration,
      });
    }
  };

  return { toast };
}

export { sonnerToast as toast };
