"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ProfileForm } from "@/components/profile/ProfileForm";
import { createProfile, getMyProfile, ProfilePayload } from "@/lib/profile";
import { useAuth } from "@/contexts/auth-context";

export default function ProfileSetupPage() {
  const router = useRouter();
  const { isAuthenticated, markProfileComplete } = useAuth();
  const [loading, setLoading] = useState(true);
  const [loadingError, setLoadingError] = useState<string | null>(null);

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace("/login");
      return;
    }

    let mounted = true;
    async function run() {
      try {
        await getMyProfile();
        if (mounted) {
          router.replace("/evaluate");
          return;
        }
      } catch {
        // Expected if profile does not exist yet.
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }
    run().catch(() => {
      if (mounted) {
        setLoadingError("Unable to load your profile setup state.");
        setLoading(false);
      }
    });
    return () => {
      mounted = false;
    };
  }, [isAuthenticated, router]);

  async function handleSubmit(payload: ProfilePayload) {
    await createProfile(payload);
    markProfileComplete();
    router.push("/evaluate");
  }

  if (loading) {
    return (
      <main>
        <h1>Profile setup</h1>
        <p>Loading...</p>
      </main>
    );
  }

  return (
    <main>
      <h1>Profile setup</h1>
      <p>Complete your founder profile before starting your first evaluation.</p>
      <p className="form-note">Changes apply to future evaluations only.</p>
      {loadingError ? <p className="form-error">{loadingError}</p> : null}
      <ProfileForm submitLabel="Continue to Evaluation" onSubmit={handleSubmit} />
    </main>
  );
}
