import type { Metadata } from "next";
import { IBM_Plex_Sans, Source_Serif_4 } from "next/font/google";
import { Providers } from "@/lib/providers";
import "./globals.css";

const sans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-sans",
});

const serif = Source_Serif_4({
  subsets: ["latin"],
  weight: ["600", "700"],
  variable: "--font-serif",
});

export const metadata: Metadata = {
  title: "SamundraSetu",
  description: "Intelligent Maritime Freight & Chartering Decision System",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${sans.variable} ${serif.variable} font-sans antialiased`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
