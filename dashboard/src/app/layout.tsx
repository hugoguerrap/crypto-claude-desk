import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/sidebar";
import { PersistentTerminal } from "@/components/persistent-terminal";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Crypto Trading Desk",
  description: "Multi-agent crypto trading intelligence dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`dark ${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full bg-background text-foreground">
        <div className="relative flex min-h-screen">
          <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
            <div className="absolute -top-40 -left-40 h-[28rem] w-[28rem] rounded-full bg-violet-500/10 blur-3xl" />
            <div className="absolute top-1/3 -right-40 h-[28rem] w-[28rem] rounded-full bg-emerald-500/10 blur-3xl" />
          </div>
          <Sidebar />
          <main className="flex-1 min-w-0">
            {children}
            <PersistentTerminal />
          </main>
        </div>
      </body>
    </html>
  );
}
