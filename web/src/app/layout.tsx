import type { Metadata } from 'next';
import { QueryProvider } from '@/lib/query-provider';
import { ThemeProvider } from '@/components/theme-provider';
import { AuthProvider } from '@/contexts/AuthContext';
import { Toaster } from '@/components/ui/toaster';
import './globals.css';

export const metadata: Metadata = {
  title: 'AIRecruiter',
  description: 'Intelligent recruitment automation platform',
  icons: {
    icon: '/favicon.ico',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          <QueryProvider>
            <AuthProvider>
              {children}
            </AuthProvider>
            <Toaster />
          </QueryProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
