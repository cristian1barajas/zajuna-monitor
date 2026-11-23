"use client";

import * as React from "react";
import { Dialog as DialogPrimitive } from "radix-ui";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Modal estilo SI Contratista sobre Radix (foco atrapado, Esc, aria):
 * radio grande, título + subtítulo, cuerpo con scroll y pie de acciones.
 */

export const Dialog = DialogPrimitive.Root;

interface DialogContentProps extends React.ComponentProps<typeof DialogPrimitive.Content> {
  title: string;
  subtitle?: React.ReactNode;
  footer?: React.ReactNode;
}

export function DialogContent({ title, subtitle, footer, className, children, ...props }: DialogContentProps) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-sena-teal-deep/50 backdrop-blur-[2px] data-[state=open]:animate-in data-[state=open]:fade-in-0" />
      <DialogPrimitive.Content
        className={cn(
          "fixed left-1/2 top-1/2 z-50 flex max-h-[90vh] w-[calc(100%-2rem)] max-w-3xl -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-2xl bg-card shadow-pop outline-none data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95",
          className
        )}
        {...props}
      >
        <div className="flex items-start justify-between gap-4 border-b px-6 py-5">
          <div className="min-w-0">
            <DialogPrimitive.Title className="text-lg font-bold tracking-tight text-foreground">
              {title}
            </DialogPrimitive.Title>
            {subtitle ? (
              <DialogPrimitive.Description className="mt-0.5 text-sm text-muted-foreground">
                {subtitle}
              </DialogPrimitive.Description>
            ) : (
              <DialogPrimitive.Description className="sr-only">{title}</DialogPrimitive.Description>
            )}
          </div>
          <DialogPrimitive.Close
            aria-label="Cerrar"
            className="shrink-0 cursor-pointer rounded-full p-1.5 text-muted-foreground transition-colors duration-150 ease-out hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <X aria-hidden="true" className="h-5 w-5" />
          </DialogPrimitive.Close>
        </div>
        <div className="flex-1 overflow-y-auto">{children}</div>
        {footer && <div className="flex flex-wrap items-center justify-between gap-3 border-t px-6 py-4">{footer}</div>}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}
