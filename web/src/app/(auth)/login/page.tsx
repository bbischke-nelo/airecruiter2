'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export default function LoginPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);

  const handleSSOLogin = () => {
    // Redirect to SSO login
    window.location.href = '/api/v1/auth/login';
  };

  return (
    <div className="min-h-screen flex">
      {/* Left side - branding */}
      <div className="hidden lg:flex lg:w-2/5 bg-gradient-to-br from-ccfs-blue to-ccfs-blue/80 text-white p-12 flex-col justify-between">
        <div>
          <h1 className="text-3xl font-bold">AI Recruiter</h1>
          <div className="w-16 h-1 bg-white/50 mt-4" />
        </div>

        <div className="space-y-6">
          <p className="text-xl font-light leading-relaxed">
            Intelligent recruitment automation platform
          </p>
          <ul className="space-y-3 text-white/80">
            <li className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-white/60" />
              AI-powered resume screening
            </li>
            <li className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-white/60" />
              Automated candidate interviews
            </li>
            <li className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-white/60" />
              Workday integration
            </li>
          </ul>
        </div>

        <p className="text-sm text-white/60">
          CCFS - Consumer Credit Financial Services
        </p>
      </div>

      {/* Right side - login form */}
      <div className="flex-1 flex items-center justify-center p-8 bg-background">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <CardTitle className="text-2xl">Welcome Back</CardTitle>
            <p className="text-muted-foreground">
              Sign in to access AI Recruiter
            </p>
          </CardHeader>
          <CardContent className="space-y-6">
            <Button
              onClick={handleSSOLogin}
              className="w-full"
              size="lg"
              disabled={isLoading}
            >
              {isLoading ? (
                <div className="animate-spin h-5 w-5 border-2 border-white border-t-transparent rounded-full" />
              ) : (
                'Sign in with SSO'
              )}
            </Button>

            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <span className="w-full border-t" />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-background px-2 text-muted-foreground">
                  Or continue with
                </span>
              </div>
            </div>

            <form className="space-y-4">
              <div>
                <label className="text-sm font-medium" htmlFor="email">
                  Email
                </label>
                <Input
                  id="email"
                  type="email"
                  placeholder="you@company.com"
                  className="mt-1"
                />
              </div>
              <div>
                <label className="text-sm font-medium" htmlFor="password">
                  Password
                </label>
                <Input
                  id="password"
                  type="password"
                  placeholder="••••••••"
                  className="mt-1"
                />
              </div>
              <Button type="submit" variant="outline" className="w-full">
                Sign in with Email
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
