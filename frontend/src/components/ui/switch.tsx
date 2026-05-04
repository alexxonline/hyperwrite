import { JSX } from "preact";

import { cn } from "@/lib/utils";

type SwitchProps = Omit<JSX.InputHTMLAttributes<HTMLInputElement>, "type"> & {
  checked?: boolean;
};

export function Switch({ className, checked, ...props }: SwitchProps) {
  return (
    <input
      type="checkbox"
      role="switch"
      checked={checked}
      className={cn(
        "h-6 w-11 cursor-pointer appearance-none rounded-full border border-transparent bg-muted transition-colors before:block before:h-5 before:w-5 before:translate-x-0 before:rounded-full before:bg-background before:shadow before:transition-transform checked:bg-primary checked:before:translate-x-5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        className,
      )}
      {...props}
    />
  );
}
