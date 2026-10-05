import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LocalRAG",
  description: "Portable open-source RAG assistant",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}