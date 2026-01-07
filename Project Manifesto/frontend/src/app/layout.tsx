import "./globals.css";
import type { ReactNode } from "react";
import { Space_Grotesk } from "next/font/google";
import { SWRProvider } from "@/components/SWRProvider";
import { SiteHeader } from "@/components/SiteHeader";

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-sans"
});

export const metadata = {
  title: "Quark Media System",
  description: "Virtual-first media library with on-demand provisioning"
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={spaceGrotesk.variable}>
      <body>
        <SWRProvider>
          <div className="app-shell">
            <SiteHeader />
            <main className="main-content">{children}</main>
          </div>
        </SWRProvider>
      </body>
    </html>
  );
}