import { apiRequest } from "./api";

export type ProfilePayload = {
  full_name: string;
  role_title: string;
  linkedin_url: string | null;
  location_city_country: string;
  timezone: string;
  current_stage: string;
  industry_focus: string[];
  business_model: string;
  target_market: string;
  team_size: string;
  weekly_hours_available: number;
  budget_range: string;
  hiring_ability: string;
  cloud_deployment_level: string;
  ai_coding_agents_level: string;
  backend_engineering_level: string;
  product_ux_level: string;
  data_ml_engineering_level: string;
  shipping_velocity: string;
  domain_expertise_level: number;
  distribution_channels: string[];
  audience_access: string;
  sales_experience: string;
  risk_tolerance: string;
  preferred_time_to_revenue: string;
  motivation_type: string;
  commitment_horizon: string;
  regulatory_constraints: boolean;
  regulatory_constraints_notes: string | null;
  ip_constraints: boolean;
  ip_constraints_notes: string | null;
  geo_legal_constraints: boolean;
  geo_legal_constraints_notes: string | null;
  confidence_style: string;
  priority_dimensions: string[];
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
