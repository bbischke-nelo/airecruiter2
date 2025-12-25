'use client';

import { useEffect, useState, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';

function LoginContent() {
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Check for error from callback
    const errorParam = searchParams.get('error');
    if (errorParam) {
      setError('SSO authentication failed. Please try again.');
      // Clear error after 3 seconds, then redirect to SSO
      setTimeout(() => {
        redirectToSSO();
      }, 3000);
      return;
    }

    // Auto-redirect to SSO
    redirectToSSO();
  }, [searchParams]);

  const redirectToSSO = () => {
    // Redirect to API's login endpoint which redirects to SSO
    window.location.href = '/recruiter2/api/v1/auth/login';
  };

  if (error) {
    return (
      <>
        <div className="p-4 bg-red-100 text-red-700 rounded-md mb-4 max-w-md text-center">
          {error}
        </div>
        <p className="text-muted-foreground">Redirecting to SSO...</p>
      </>
    );
  }

  return (
    <>
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      <h2 className="mt-6 text-xl font-normal">Redirecting to SSO...</h2>
    </>
  );
}

export default function LoginPage() {
  return (
    <div className="min-h-screen flex flex-col justify-center items-center bg-background">
      <Suspense fallback={
        <>
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
          <h2 className="mt-6 text-xl font-normal">Loading...</h2>
        </>
      }>
        <LoginContent />
      </Suspense>
    </div>
  );
}
