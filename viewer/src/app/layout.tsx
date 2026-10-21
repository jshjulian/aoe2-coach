import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Agewise · Local AoE2 replay coach",
  description:
    "Age of Empires 2 replay viewer with minimap playback, key stats, and build timeline.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased" suppressHydrationWarning>
        {children}
      </body>
    </html>
  );
}
