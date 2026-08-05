import './globals.css';

export const metadata = {
  title: 'Robotics Desk — Automated Field Report',
  description: 'One click files one robotics field report, sourced from live news.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}