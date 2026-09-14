import type { UUID } from "@/types/run-status";

export interface IbmCredentialProfile {
  id: UUID;
  name: string;
  channel: string;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface IbmCredentialProfileListResponse {
  profiles: IbmCredentialProfile[];
  active_profile_id: UUID | null;
  encryption_key_source: string;
  encryption_warning: string | null;
}

export interface IbmCredentialProfileCreate {
  name: string;
  token: string;
  crn: string;
  channel?: string;
  activate?: boolean;
}

export interface IbmCredentialProfileUpdate {
  name?: string | null;
  token?: string | null;
  crn?: string | null;
  channel?: string | null;
  activate?: boolean | null;
}

export interface IbmCredentialProfileTestResponse {
  id: UUID;
  ok: boolean;
  message: string;
  active_instance?: string | null;
}
