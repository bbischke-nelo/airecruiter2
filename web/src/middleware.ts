import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  const { pathname, searchParams } = request.nextUrl;
  const authCode = searchParams.get('auth_code') || searchParams.get('code');

  // If there's an auth_code in the URL, redirect to the callback handler
  if (authCode) {
    console.log(`[Middleware] Auth code detected on ${pathname}`);

    // Check if we're already on the callback page to prevent infinite loops
    // Note: In middleware, pathnames don't include the basePath
    if (pathname !== '/auth/callback') {
      const url = request.nextUrl.clone();
      url.pathname = '/auth/callback';

      console.log(`[Middleware] Redirecting to ${url.pathname} with auth_code`);

      const response = NextResponse.redirect(url, { status: 302 });
      response.headers.set('Cache-Control', 'no-store, no-cache, must-revalidate');
      response.headers.set('Pragma', 'no-cache');
      response.headers.set('Expires', '0');

      return response;
    }
  }

  return NextResponse.next();
}

// Configure which routes the middleware runs on
export const config = {
  matcher: [
    '/(.*)',
    { source: '/' },
  ],
};
