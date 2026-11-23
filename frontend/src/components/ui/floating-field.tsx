import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * Campos con label flotante sobre el borde (estilo SI Contratista,
 * "Nombres", "Documento"...). El label queda siempre visible para no
 * depender del placeholder.
 */

const FIELD_CLASS =
  "peer h-12 w-full rounded-xl border border-input bg-card px-4 pt-1 text-sm text-foreground outline-none transition-[border-color,box-shadow] duration-150 ease-out placeholder:text-muted-foreground/60 focus:border-sena-green focus:ring-2 focus:ring-ring/25 disabled:cursor-not-allowed disabled:bg-muted disabled:text-muted-foreground";

const LABEL_CLASS =
  "pointer-events-none absolute -top-2 left-3 bg-card px-1 text-[11px] font-medium leading-none text-muted-foreground transition-colors duration-150 ease-out peer-focus:text-sena-green-dark dark:peer-focus:text-sena-green";

interface FloatingInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  id: string;
  label: string;
}

export function FloatingInput({ id, label, className, ...props }: FloatingInputProps) {
  return (
    <div className="relative">
      <input id={id} className={cn(FIELD_CLASS, className)} {...props} />
      <label htmlFor={id} className={LABEL_CLASS}>
        {label}
      </label>
    </div>
  );
}

interface FloatingSelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  id: string;
  label: string;
}

export function FloatingSelect({ id, label, className, children, ...props }: FloatingSelectProps) {
  return (
    <div className="relative">
      <select id={id} className={cn(FIELD_CLASS, "cursor-pointer pr-8", className)} {...props}>
        {children}
      </select>
      <label htmlFor={id} className={LABEL_CLASS}>
        {label}
      </label>
    </div>
  );
}
