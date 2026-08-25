"use client";

import { ReactNode, useEffect } from "react";
import { useRouter } from "next/navigation";

import { clearAdminSession, getToken, isTokenValid } from "@/lib/auth";

interface ProtectedRouteProps {
  children: ReactNode;
}

const ProtectedRoute = ({ children }: ProtectedRouteProps) => {
  const router = useRouter();

  useEffect(() => {
    const token = getToken();

    if (!isTokenValid(token)) {
      clearAdminSession();
      router.replace("/login");
    }
  }, [router]);

  const token = getToken();
  const isAllowed = isTokenValid(token);

  if (!isAllowed) {
    return null;
  }

  return <>{children}</>;
};

export default ProtectedRoute;
