import { apiBaseUrl } from "../lib/config";
export type HealthResponse = {
  status: string;
  service: string;
  version: string;
};
export type ProfileResponse = {
  id: string;
  email: string | null;
  display_name: string;
  avatar_url: string | null;
  created_at: string;
  free_song_credits: number;
  bonus_song_credits: number;
  song_credits: number;
  is_admin: boolean;
};
export type YoutubeMetadata = {
  video_id: string;
  canonical_url: string;
  title: string;
  author_name: string | null;
  thumbnail_url: string | null;
};
export type StudioProjectInput = {
  source_type: "youtube" | "upload";
  title: string;
  rights_confirmed: boolean;
  trim_start_seconds: number;
  trim_end_seconds: number;
  youtube_url?: string;
  youtube_video_id?: string;
  youtube_title?: string;
  youtube_thumbnail_url?: string;
  storage_path?: string;
  original_filename?: string;
  mime_type?: string;
  size_bytes?: number;
  source_duration_seconds?: number;
};
export type StudioProject = {
  id: string;
  title: string;
  source_type: "youtube" | "upload";
  status: string;
  trim_start_seconds: number;
  trim_end_seconds: number;
  created_at: string;
};
export type GenerationJob = {
  id: string;
  project_id: string;
  status: string;
  progress: number;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};
export type PitchVariant = { pitch: -3 | 0 | 3; label: string; mp3_url: string };
export type FinalArtifacts = {
  wav_url: string;
  mp3_url: string;
  minus3_url?: string;
  plus3_url?: string;
  selected_pitch: -3 | 0 | 3;
  variants: PitchVariant[];
};
export type VoiceModel = {
  slug: string;
  display_name: string;
  description: string;
  language: string | null;
  consent_status: "development_only" | "licensed" | "owner_verified";
  visibility: "public" | "private";
  category: string;
  image_url: string | null;
  demo_url_1: string | null;
  demo_url_2: string | null;
  is_active?: boolean;
  sort_order?: number;
};
export type VoiceModelInput = Omit<VoiceModel, "slug"> & {is_active:boolean;sort_order:number};
export type LibrarySong = {
  id: string;
  project_id: string;
  status: "completed" | "failed";
  progress: number;
  model_slug: string;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
  title: string;
  source_type: "upload" | "youtube" | null;
  duration_seconds: number | null;
  selected_pitch: -3 | 0 | 3;
};
export type PaymentMethod = "easypaisa" | "jazzcash";
export type CreditProduct = "song" | "voice_training";
export type PaymentRequest = {
  id: string;
  user_id?: string;
  method: PaymentMethod;
  product_type: CreditProduct;
  amount_pkr: number;
  requested_credits: number;
  sender_name?: string;
  sender_phone?: string;
  transaction_reference: string;
  proof_path?: string;
  status: "pending" | "approved" | "rejected";
  admin_note: string | null;
  created_at: string;
  reviewed_at?: string | null;
};
export type LedgerEntry = {
  id: string;
  delta: number;
  balance_after: number;
  reason: string;
  created_at: string;
};
export type WalletResponse = {
  song_credits: number;
  training_credits: number;
  pricing: Record<CreditProduct, { pkr: number; usd: number; packs: { credits: number; pkr: number }[] }>;
  payment_accounts: Record<PaymentMethod, { title: string; number: string }>;
  requests: PaymentRequest[];
  ledger: LedgerEntry[];
  is_admin: boolean;
};
export type TrainingStatus =
  | "submitted"
  | "approved"
  | "training"
  | "model_validation"
  | "ready"
  | "rejected";
export type TrainingRequest = {
  id: string;
  user_id?: string;
  voice_name: string;
  language: string;
  rights_basis: "self_voice" | "authorized_voice";
  dataset_path?: string;
  consent_proof_path?: string | null;
  status: TrainingStatus;
  model_slug: string | null;
  admin_note: string | null;
  dataset_size_bytes?: number | null;
  dataset_mime_type?: string | null;
  created_at: string;
  updated_at: string;
};
export type TrainingEvent = {
  id: number;
  request_id: string;
  status: TrainingStatus;
  message: string;
  created_at: string;
};
export type OpsResponse = {
  environment: string;
  jobs: { completed_total: number; active: number; failed_24h: number };
  queues: { pending_payments: number; active_training: number };
  security_events_24h: number;
  estimated_gpu_cost_usd_total: number;
  estimated_gpu_cost_usd_per_song: number;
  recent_failures: {
    id: string;
    error_code: string | null;
    error_message: string | null;
    created_at: string;
  }[];
  generated_at: string;
};
export type DiagnosticsResponse={status:"pass"|"attention";checks:Record<string,{ok:boolean;detail:string}>};
export type SupportCategory="song"|"payment"|"voice_training"|"account"|"copyright"|"other";
export type SupportRequest={id:string;user_id?:string;category:SupportCategory;subject:string;message:string;status:"open"|"in_review"|"resolved"|"closed";admin_note:string|null;created_at:string;updated_at:string;profiles?:{display_name:string|null}|null};
export type ContactMessage={id:string;name:string;email:string;subject:string;message:string;status:"open"|"resolved"|"closed";admin_note:string|null;created_at:string};
async function apiJson<T>(
  path: string,
  token: string,
  init?: RequestInit,
  timeoutMs = 15000,
): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(init?.headers || {}),
    },
    signal: AbortSignal.timeout(timeoutMs),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : `Request failed (${response.status})`,
    );
  }
  return response.json() as Promise<T>;
}
export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch(`${apiBaseUrl}/api/v1/health`, {
    signal: AbortSignal.timeout(7000),
  });
  if (!response.ok) throw new Error(`API returned HTTP ${response.status}`);
  return response.json() as Promise<HealthResponse>;
}
export async function fetchProfile(token: string): Promise<ProfileResponse> {
  const response = await fetch(`${apiBaseUrl}/api/v1/me`, {
    headers: { Authorization: `Bearer ${token}` },
    signal: AbortSignal.timeout(12000),
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(
      typeof detail.detail === "string"
        ? detail.detail
        : `Profile request failed (${response.status})`,
    );
  }
  return response.json() as Promise<ProfileResponse>;
}
export function fetchYoutubeMetadata(token: string, url: string) {
  return apiJson<YoutubeMetadata>("/api/v1/studio/youtube/metadata", token, {
    method: "POST",
    body: JSON.stringify({ url }),
  });
}
export function createStudioProject(token: string, input: StudioProjectInput) {
  return apiJson<StudioProject>("/api/v1/studio/projects", token, {
    method: "POST",
    body: JSON.stringify(input),
  });
}
export function fetchStudioProjects(token: string) {
  return apiJson<StudioProject[]>("/api/v1/studio/projects", token);
}
export function createGenerationJob(
  token: string,
  projectId: string,
  modelSlug: string,
) {
  return apiJson<{ job_id: string; status: string; progress: number }>(
    "/api/v1/jobs",
    token,
    {
      method: "POST",
      body: JSON.stringify({ project_id: projectId, model_slug: modelSlug }),
    },
    70000,
  );
}
export function continueVoiceConversion(token: string, jobId: string) {
  return apiJson<{
    job_id: string;
    status: string;
    progress: number;
    accepted: boolean;
  }>(`/api/v1/jobs/${jobId}/convert`, token, { method: "POST" }, 70000);
}
export function retryGenerationJob(token: string, jobId: string) {
  return apiJson<{
    job_id: string;
    status: string;
    progress: number;
    accepted: boolean;
  }>(`/api/v1/jobs/${jobId}/retry`, token, { method: "POST" }, 70000);
}
export function continueFinalMix(token: string, jobId: string) {
  return apiJson<{
    job_id: string;
    status: string;
    progress: number;
    accepted: boolean;
  }>(`/api/v1/jobs/${jobId}/mix`, token, { method: "POST" }, 70000);
}
export function fetchFinalArtifacts(token: string, jobId: string) {
  return apiJson<FinalArtifacts>(
    `/api/v1/jobs/${jobId}/artifacts`,
    token,
  );
}
export function selectSongPitch(token: string, jobId: string, pitch: -3 | 0 | 3) {
  return apiJson<{id:string;selected_pitch:-3|0|3}>(`/api/v1/jobs/${jobId}/selected-pitch`, token, {
    method: "POST",
    body: JSON.stringify({pitch}),
  });
}
export function fetchGenerationJobs(token: string) {
  return apiJson<GenerationJob[]>("/api/v1/jobs", token);
}
export function fetchVoices(token: string) {
  return apiJson<VoiceModel[]>("/api/v1/voices", token);
}
export async function fetchPublicVoices() {
  const response=await fetch(`${apiBaseUrl}/api/v1/public/voices`,{signal:AbortSignal.timeout(12000)});
  if(!response.ok) throw new Error("Unable to load voice catalog");
  return response.json() as Promise<VoiceModel[]>;
}
export function fetchAdminVoices(token:string){return apiJson<VoiceModel[]>("/api/v1/admin/voices",token);}
export function saveAdminVoice(token:string,slug:string,input:VoiceModelInput){return apiJson<VoiceModel>(`/api/v1/admin/voices/${slug}`,token,{method:"POST",body:JSON.stringify(input)});}
export function fetchLibrarySongs(token: string) {
  return apiJson<LibrarySong[]>("/api/v1/library/songs", token);
}
export function fetchSupportRequests(token:string){return apiJson<SupportRequest[]>("/api/v1/support/requests",token);}
export function createSupportRequest(token:string,input:{category:SupportCategory;subject:string;message:string}){return apiJson<SupportRequest>("/api/v1/support/requests",token,{method:"POST",body:JSON.stringify(input)});}
export function fetchAdminSupport(token:string){return apiJson<SupportRequest[]>("/api/v1/admin/support/requests",token);}
export function fetchDiagnostics(token:string){return apiJson<DiagnosticsResponse>("/api/v1/admin/diagnostics",token,undefined,30000);}
export function reviewSupport(token:string,id:string,status:SupportRequest["status"],note:string){return apiJson<SupportRequest>(`/api/v1/admin/support/requests/${id}/review`,token,{method:"POST",body:JSON.stringify({status,note:note||null})});}
export function submitContact(input:{name:string;email:string;subject:string;message:string}){return apiJson<{id:string;status:string}>("/api/v1/contact","",{method:"POST",body:JSON.stringify(input)});}
export function fetchAdminContact(token:string){return apiJson<ContactMessage[]>("/api/v1/admin/contact",token);}
export function resolveContact(token:string,id:string,note:string){return apiJson<ContactMessage>(`/api/v1/admin/contact/${id}/resolve`,token,{method:"POST",body:JSON.stringify({status:"resolved",note:note||null})});}
export function deleteLibrarySong(token: string, jobId: string) {
  return apiJson<{deleted:boolean;job_id:string}>(`/api/v1/library/songs/${jobId}`, token, {method:"DELETE"});
}
export function fetchWallet(token: string) {
  return apiJson<WalletResponse>("/api/v1/wallet", token);
}
export function submitPaymentRequest(
  token: string,
  input: {
    method: PaymentMethod;
    product_type: CreditProduct;
    amount_pkr: number;
    sender_name: string;
    sender_phone: string;
    transaction_reference: string;
    proof_path: string;
  },
) {
  return apiJson<PaymentRequest>("/api/v1/wallet/payment-requests", token, {
    method: "POST",
    body: JSON.stringify(input),
  });
}
export function fetchAdminPayments(token: string) {
  return apiJson<PaymentRequest[]>("/api/v1/admin/payment-requests", token);
}
export function fetchAdminProof(token: string, id: string) {
  return apiJson<{ url: string }>(
    `/api/v1/admin/payment-requests/${id}/proof`,
    token,
  );
}
export function reviewPayment(
  token: string,
  id: string,
  approve: boolean,
  note: string,
) {
  return apiJson<{ id: string; status: string }>(
    `/api/v1/admin/payment-requests/${id}/review`,
    token,
    { method: "POST", body: JSON.stringify({ approve, note: note || null }) },
  );
}
export function grantBonusCredits(
  token: string,
  user_email: string,
  amount: number,
  reason: string,
) {
  return apiJson<{ email: string; granted: number; bonus_balance: number }>(
    "/api/v1/admin/bonus-credits",
    token,
    { method: "POST", body: JSON.stringify({ user_email, amount, reason }) },
  );
}
export function fetchTrainingRequests(token: string) {
  return apiJson<{ requests: TrainingRequest[]; events: TrainingEvent[]; training_credits: number; training_price_pkr: number; is_admin: boolean }>(
    "/api/v1/voice-training",
    token,
  );
}
export function submitTrainingRequest(
  token: string,
  input: {
    voice_name: string;
    language: string;
    rights_basis: "self_voice" | "authorized_voice";
    consent_confirmed: boolean;
    dataset_path: string;
    consent_proof_path?: string;
  },
) {
  return apiJson<TrainingRequest>(
    "/api/v1/voice-training",
    token,
    { method: "POST", body: JSON.stringify(input) },
    30000,
  );
}
export function fetchAdminTraining(token: string) {
  return apiJson<TrainingRequest[]>("/api/v1/admin/voice-training", token);
}
export function fetchTrainingAsset(
  token: string,
  id: string,
  kind: "dataset" | "consent",
) {
  return apiJson<{ url: string }>(
    `/api/v1/admin/voice-training/${id}/asset/${kind}`,
    token,
  );
}
export function updateTrainingStatus(
  token: string,
  id: string,
  status: TrainingStatus,
  note: string,
  model_slug?: string,
) {
  return apiJson<{ id: string; status: string }>(
    `/api/v1/admin/voice-training/${id}/status`,
    token,
    {
      method: "POST",
      body: JSON.stringify({
        status,
        note: note || null,
        model_slug: model_slug || null,
      }),
    },
    320000,
  );
}
export function fetchOperations(token: string) {
  return apiJson<OpsResponse>("/api/v1/admin/ops", token);
}
