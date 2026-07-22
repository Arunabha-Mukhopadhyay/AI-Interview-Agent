import React from "react";
import { cn } from "@/app/lib/utils";

export const GlassCard = ({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) => {
  return (
    <div
      className={cn(
        "glass-panel rounded-2xl p-6 md:p-8 flex flex-col gap-6",
        className
      )}
    >
      {children}
    </div>
  );
};
