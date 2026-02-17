"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/contexts/auth-context";

export default function EvaluatePage() {
  const router = useRouter();
  const { isAuthenticated, user } = useAuth();
  const [status, setStatus] = useState<"checking" | "ready" | "error">("checking");

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace("/login");
      return;
    }

    if (!user) {
      setStatus("checking");
      return;
    }

    if (!user.has_profile) {
      router.replace("/profile/setup");
      return;
    }
    setStatus("ready");
  }, [isAuthenticated, router, user]);

  if (status === "checking") {
    return (
      <main>
        <h1>New Evaluation</h1>
        <p>Checking profile status...</p>
      </main>
    );
  }

  if (status === "error") {
    return (
      <main>
        <h1>New Evaluation</h1>
        <p className="form-error">Unable to verify your account. Please log in again.</p>
      </main>
    );
  }

  return (
    <main>
      <h1>New Evaluation</h1>
      <p>Profile check passed. Idea input flow is next.</p>
    </main>
  );
}
