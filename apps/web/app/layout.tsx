import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SceneCraft",
  description: "Script in. Working previs app out.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen font-display antialiased">{children}</body>
    </html>
  );
}
