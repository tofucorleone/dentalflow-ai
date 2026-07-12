import { NextRequest, NextResponse } from "next/server";

const COOKIE_NAME = "dentalflow_access_token";

export function proxy(request: NextRequest) {
  const token = request.cookies.get(COOKIE_NAME)?.value;
  const pathname = request.nextUrl.pathname;

  const isLoginPage = pathname === "/login";
  const isAuthApi = pathname.startsWith("/api/auth/");
  const isPublicAsset =
    pathname.startsWith("/_next/") ||
    pathname === "/favicon.ico";

  if (isAuthApi || isPublicAsset) {
    return NextResponse.next();
  }

  if (!token && !isLoginPage) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("from", pathname);
    return NextResponse.redirect(loginUrl);
  }

  if (token && isLoginPage) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico).*)",
  ],
};
