'use client';

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useRouter, usePathname } from 'next/navigation';

interface UserInfo {
  sub: string;
  email: string | null;
  name: string | null;
  roles: string[];
  accessible_apps: string[];
}

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: UserInfo | null;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const PUBLIC_PATHS = ['/login', '/auth/callback'];
const PUBLIC_PATH_PREFIXES = ['/interview/'];

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [user, setUser] = useState<UserInfo | null>(null);

  const isPublicPath = useCallback(() => {
    if (!pathname) return false;
    return PUBLIC_PATHS.includes(pathname) ||
      PUBLIC_PATH_PREFIXES.some(prefix => pathname.startsWith(prefix));
  }, [pathname]);

  const checkAuth = useCallback(async (): Promise<void> => {
    // Skip auth check on public paths
    if (isPublicPath()) {
      setIsLoading(false);
      return;
    }

    try {
      const response = await fetch('/recruiter2/api/v1/auth/me', {
        credentials: 'include',
      });

      if (response.ok) {
        const userData = await response.json();
        setUser(userData);
        setIsAuthenticated(true);
      } else {
        setIsAuthenticated(false);
        setUser(null);
        // Redirect to login if not authenticated
        if (!isPublicPath()) {
          console.log('[AuthContext] Not authenticated, redirecting to login');
          router.push('/login');
        }
      }
    } catch (error) {
      console.error('Auth check failed:', error);
      setIsAuthenticated(false);
      setUser(null);
      if (!isPublicPath()) {
        router.push('/login');
      }
    } finally {
      setIsLoading(false);
    }
  }, [router, isPublicPath]);

  const logout = useCallback(async () => {
    try {
      await fetch('/recruiter2/api/v1/auth/logout', {
        method: 'POST',
        credentials: 'include',
      });
    } catch (error) {
      console.error('Logout failed:', error);
    } finally {
      setIsAuthenticated(false);
      setUser(null);
      // Redirect to SSO portal
      window.location.href = process.env.NEXT_PUBLIC_SSO_URL || 'https://sso.ccfs.com';
    }
  }, []);

  // Check authentication on mount and when pathname changes
  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const value = {
    isAuthenticated,
    isLoading,
    user,
    logout,
    checkAuth,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
