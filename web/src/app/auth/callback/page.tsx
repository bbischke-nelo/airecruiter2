'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

export default function SSOCallbackPage() {
  const [status, setStatus] = useState<'processing' | 'error' | 'success'>('processing');
  const [errorMessage, setErrorMessage] = useState<string>('');
  const router = useRouter();

  useEffect(() => {
    const processCallback = async () => {
      console.log('[SSO Callback] Starting processCallback');

      try {
        // Get params from URL
        const params = new URLSearchParams(window.location.search);
        const authCode = params.get('auth_code') || params.get('code');
        const error = params.get('error');
        const errorDescription = params.get('error_description');

        // Handle errors from SSO provider
        if (error) {
          throw new Error(errorDescription || error);
        }

        if (!authCode) {
          throw new Error('No authorization code received');
        }

        console.log('[SSO Callback] Exchanging auth code for token...');

        // Exchange code for token (basePath not auto-applied to fetch)
        const response = await fetch('/recruiter2/api/v1/auth/callback', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          credentials: 'include',
          body: JSON.stringify({
            code: authCode,
          }),
        });

        console.log('[SSO Callback] Exchange response status:', response.status);

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ detail: 'SSO exchange failed' }));
          console.error('[SSO Callback] Exchange failed:', errorData);
          throw new Error(errorData.detail || 'Failed to exchange authorization code');
        }

        const data = await response.json();
        console.log('[SSO Callback] Exchange successful');

        // Wait a moment for cookies to be set
        console.log('[SSO Callback] Waiting for cookies...');
        await new Promise(resolve => setTimeout(resolve, 500));

        // Verify authentication
        const maxRetries = 3;
        let verified = false;

        for (let attempt = 0; attempt < maxRetries; attempt++) {
          if (attempt > 0) {
            await new Promise(resolve => setTimeout(resolve, 500 * attempt));
          }

          try {
            const meResponse = await fetch('/recruiter2/api/v1/auth/me', {
              method: 'GET',
              credentials: 'include',
            });

            if (meResponse.ok) {
              console.log('[SSO Callback] Authentication verified');
              verified = true;
              break;
            }
          } catch (e) {
            console.warn(`[SSO Callback] Verification attempt ${attempt + 1} failed`);
          }
        }

        if (!verified) {
          console.warn('[SSO Callback] Could not verify auth, proceeding anyway');
        }

        setStatus('success');

        // Clean URL and redirect
        window.history.replaceState({}, document.title, window.location.pathname);

        setTimeout(() => {
          console.log('[SSO Callback] Redirecting to dashboard...');
          router.push('/requisitions');
        }, 500);

      } catch (error) {
        console.error('SSO callback error:', error);
        setStatus('error');
        setErrorMessage(error instanceof Error ? error.message : 'SSO callback failed');

        setTimeout(() => {
          router.push('/login?error=sso_failed');
        }, 3000);
      }
    };

    processCallback();
  }, [router]);

  return (
    <div className="min-h-screen flex flex-col justify-center items-center bg-background">
      {status === 'processing' && (
        <>
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
          <h2 className="mt-6 text-xl font-normal">Completing sign in...</h2>
        </>
      )}

      {status === 'error' && (
        <>
          <div className="p-4 bg-red-100 text-red-700 rounded-md mb-4">
            {errorMessage}
          </div>
          <p className="text-muted-foreground">Redirecting to login...</p>
        </>
      )}

      {status === 'success' && (
        <>
          <div className="text-5xl mb-4 text-green-500">&#10003;</div>
          <h2 className="text-xl font-normal">Sign in successful!</h2>
          <p className="text-muted-foreground">Redirecting...</p>
        </>
      )}
    </div>
  );
}
