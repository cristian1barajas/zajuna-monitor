import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

/**
 * Botón del lenguaje SI Contratista. Reemplaza las cadenas de clases
 * copiadas en cada página: primario verde AA, outline, ghost y peligro.
 */
const buttonVariants = cva(
  "inline-flex shrink-0 cursor-pointer items-center justify-center gap-2 whitespace-nowrap font-semibold transition-colors duration-150 ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary: "bg-primary text-primary-foreground shadow-sm hover:bg-sena-green-dark dark:hover:bg-sena-green-light",
        outline: "border border-input bg-card text-foreground hover:bg-accent hover:text-accent-foreground",
        "outline-primary": "border border-primary bg-card text-sena-green-dark hover:bg-accent dark:text-sena-green",
        ghost: "text-muted-foreground hover:bg-muted hover:text-foreground",
        danger: "border border-danger-border bg-card text-danger-fg hover:bg-danger-soft",
      },
      size: {
        sm: "h-8 rounded-lg px-3 text-xs [&_svg]:size-3.5",
        md: "h-10 rounded-lg px-4 text-sm [&_svg]:size-4",
        lg: "h-12 rounded-xl px-5 text-sm [&_svg]:size-4",
        icon: "h-9 w-9 rounded-full [&_svg]:size-4",
      },
      pill: {
        true: "rounded-full",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export function Button({ className, variant, size, pill, type = "button", ...props }: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(buttonVariants({ variant, size, pill }), className)}
      {...props}
    />
  );
}

export { buttonVariants };
