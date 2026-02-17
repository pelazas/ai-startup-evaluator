import { apiRequest } from "./api";

export type ProfilePayload = {
  technical_skills: string[];
  domain_expertise: string[];
  years_experience: string;
  team_size: string;
  budget_range: string;
  network_strength: number;
  risk_tolerance: string;
  geographic_location: string;
};

export type ProfileResponse = ProfilePayload & {
  id: string;
  user_id: string;
};

export async function createProfile(payload: ProfilePayload): Promise<ProfileResponse> {
  return apiRequest<ProfileResponse>("/api/profiles", {
    method: "POST",
    body: payload,
  });
}

export async function getMyProfile(): Promise<ProfileResponse> {
  return apiRequest<ProfileResponse>("/api/profiles/me", {
    method: "GET",
  });
}

export async function updateMyProfile(payload: ProfilePayload): Promise<ProfileResponse> {
  return apiRequest<ProfileResponse>("/api/profiles/me", {
    method: "PUT",
    body: payload,
  });
}
