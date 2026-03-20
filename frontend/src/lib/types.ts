export interface User {
  id: string;
  email: string;
  username: string;
  display_name?: string;
  onboarding_complete: boolean;
  created_at: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface UserProfile {
  id: string;
  user_id: string;
  height_cm: number;
  division: Division;
  competition_date?: string;
  training_experience_years: number;
  sex: "male" | "female";
}

export type Division =
  | "mens_open"
  | "classic_physique"
  | "mens_physique"
  | "womens_figure"
  | "womens_bikini"
  | "womens_physique";

export interface HealthCheck {
  status: string;
  version: string;
  system: string;
}
