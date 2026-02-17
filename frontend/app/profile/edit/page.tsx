"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ProfileForm } from "@/components/profile/ProfileForm";
import { useAuth } from "@/contexts/auth-context";
import { getMyProfile, ProfilePayload, updateMyProfile } from "@/lib/profile";

export default function ProfileEditPage() {
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  const [initialValue, setInitialValue] = useState<ProfilePayload | null>(null);
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
        const profile = await getMyProfile();
        if (mounted) {
          setInitialValue({
            technical_skills: profile.technical_skills,
            domain_expertise: profile.domain_expertise,
            years_experience: profile.years_experience,
            team_size: profile.team_size,
            budget_range: profile.budget_range,
            network_strength: profile.network_strength,
            risk_tolerance: profile.risk_tolerance,
            geographic_location: profile.geographic_location,
          });
        }
      } catch {
        if (mounted) {
          router.replace("/profile/setup");
          return;
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }
    run().catch(() => {
      if (mounted) {
        setLoadingError("Unable to load your profile.");
        setLoading(false);
      }
    });
    return () => {
      mounted = false;
    };
  }, [isAuthenticated, router]);

  async function handleSubmit(payload: ProfilePayload) {
    await updateMyProfile(payload);
    router.push("/evaluate");
  }

  if (loading) {
    return (
      <main>
        <h1>Edit profile</h1>
        <p>Loading...</p>
      </main>
    );
  }

  if (!initialValue) {
    return (
      <main>
        <h1>Edit profile</h1>
        <p className="form-error">Profile not found.</p>
      </main>
    );
  }

  return (
    <main>
      <h1>Edit profile</h1>
      <p>Update your founder profile details.</p>
      <p className="form-note">Changes apply to future evaluations only.</p>
      {loadingError ? <p className="form-error">{loadingError}</p> : null}
      <ProfileForm initialValue={initialValue} submitLabel="Save profile" onSubmit={handleSubmit} />
    </main>
  );
}
