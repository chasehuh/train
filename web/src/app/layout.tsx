import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono, Sora } from "next/font/google";
import "./globals.css";

const sora = Sora({
  variable: "--font-sans",
  subsets: ["latin"],
});

const mono = IBM_Plex_Mono({
  variable: "--font-mono",
  weight: ["400", "500"],
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "train.chasehuh",
  description: "Closed SRT/Korail reservation console",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#0a0c10",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${sora.variable} ${mono.variable} h-full`}>
      <body className="min-h-full overflow-x-hidden font-[family-name:var(--font-sans)] antialiased">
        {children}
      </body>
    </html>
  );
}
