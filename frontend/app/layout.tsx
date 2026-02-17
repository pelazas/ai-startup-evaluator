import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CRAG AI Startup Evaluator",
  description: "Frontend bootstrap for the MVP"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

