import type { Metadata } from "next";
import { Work_Sans, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { AppShell } from "@/components/layout/app-shell";
import { ThemeProvider } from "@/components/layout/theme-provider";

const workSans = Work_Sans({
  variable: "--font-work-sans",
  subsets: ["latin"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Zajuna Monitor",
  description: "Dashboard de calificaciones SENA",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="es"
      className={`${workSans.variable} ${jetbrainsMono.variable}`}
      suppressHydrationWarning
    >
      {/* suppressHydrationWarning: extensiones del navegador (p. ej.
          ColorZilla inyecta cz-shortcut-listen) agregan atributos al body
          antes de hidratar; no es un mismatch de la app */}
      <body className="antialiased" suppressHydrationWarning>
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          <AppShell>{children}</AppShell>
        </ThemeProvider>
      </body>
    </html>
  );
}
