export interface BankerProfile {
  id: string;
  full_name: string;
  email: string;
  organization_name: string;
  job_title?: string;
  role: string;
  account_status: string;
  created_at?: string;
  last_login_at?: string;
}

export interface AuthResponse {
  user: BankerProfile;
  csrf_token: string;
}

export interface MeResponse {
  authenticated: boolean;
  user?: BankerProfile;
  csrf_token?: string;
  error?: string;
  code?: string;
}
