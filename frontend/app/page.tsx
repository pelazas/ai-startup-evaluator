"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "../contexts/auth-context";

export default function HomePage() {
  const router = useRouter();
  const { isAuthenticated, user } = useAuth();

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace("/login");
      return;
    }
    router.replace(user?.has_profile ? "/evaluate" : "/profile/setup");
  }, [isAuthenticated, router, user?.has_profile]);

  return null;
}
