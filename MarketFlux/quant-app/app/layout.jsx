import "./globals.css";

export const metadata = {
  title: "MarketFlux Quant Research OS",
  description: "Public AI-native quant research workflows for serious self-directed investors.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

