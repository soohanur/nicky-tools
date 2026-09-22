import "./globals.css";
import { Inter } from "next/font/google";

import { ToastProvider } from "@/hooks/useToast";
import { THEME_SCRIPT } from "@/lib/theme";
import { site } from "@/data/site";

const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata = {
  title: {
    default: site.name,
    template: `${site.name} - %s`,
  },
  description: "CompanyInfo contact extraction",
  robots: { index: false, follow: false },
  icons: { icon: "/favicon.png", apple: "/favicon.png" },
};

export const viewport = {
  themeColor: "#2196F3",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={inter.variable} suppressHydrationWarning>
      <head>
        {/* Apply the saved theme before first paint (no light/dark flash). */}
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body>
        <ToastProvider>{children}</ToastProvider>
      </body>
    </html>
  );
}
