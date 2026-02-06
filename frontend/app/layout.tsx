import "./globals.css";

export const metadata = {
  title: "Travel Planner",
  description: "Backend-first travel planning with grounding and SSE progress",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {/* Spinner animation is now in globals.css or component */}
        {children}
      </body>
    </html>
  );
}
