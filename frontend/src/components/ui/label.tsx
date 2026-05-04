import { JSX } from "preact";

import { cn } from "@/lib/utils";

export function Label({ className, ...props }: JSX.LabelHTMLAttributes<HTMLLabelElement>) {
  return <label className={cn("text-sm font-medium leading-none", className)} {...props} />;
}
