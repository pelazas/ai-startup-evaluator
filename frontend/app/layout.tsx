import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "./app-shell";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "AI Startup Audit",
  description: "AI Startup Audit MVP"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
