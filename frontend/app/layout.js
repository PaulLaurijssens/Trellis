import "./globals.css";
import PwaRegister from "./pwa-register";

export const metadata = {
  title: "Dendrite",
  description: "Persoonlijke kennisgraph met AI-mentor",
  applicationName: "Dendrite",
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    title: "Dendrite",
    statusBarStyle: "black-translucent",
  },
  icons: {
    icon: [
      { url: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: [{ url: "/icons/icon-192.png", sizes: "192x192", type: "image/png" }],
  },
  formatDetection: { telephone: false },
};

// Next 14: themeColor en viewport horen in deze export, niet meer in metadata.
export const viewport = {
  themeColor: "#070b11",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({ children }) {
  return (
    <html lang="nl">
      <body>
        {children}
        <PwaRegister />
      </body>
    </html>
  );
}
