import {
  CheckCircle2,
  Download,
  FileArchive,
  LoaderCircle,
  MicVocal,
  ShieldCheck,
  Upload,
} from "lucide-react";
import { useEffect, useState } from "react";
import { supabase } from "../lib/supabase";
import {
  fetchAdminTraining,
  fetchTrainingAsset,
  fetchTrainingRequests,
  submitTrainingRequest,
  updateTrainingStatus,
  type TrainingRequest,
  type TrainingEvent,
  type TrainingStatus,
} from "../services/api";

type Props = {
  token: string;
  userId: string;
  onPublished: () => void;
  showAdmin?: boolean;
};
const DATA_TYPES = new Set([
  "application/zip",
  "audio/mpeg",
  "audio/wav",
  "audio/x-wav",
  "audio/flac",
]);
const CONSENT_TYPES = new Set([
  "image/jpeg",
  "image/png",
  "image/webp",
  "application/pdf",
  "audio/mpeg",
  "audio/wav",
  "video/mp4",
]);

function extension(file: File) {
  return file.name.includes(".")
    ? file.name
        .split(".")
        .pop()
        ?.toLowerCase()
        .replace(/[^a-z0-9]/g, "") || "bin"
    : "bin";
}

export default function CustomVoiceTraining({
  token,
  userId,
  onPublished,
  showAdmin = false,
}: Props) {
  const [requests, setRequests] = useState<TrainingRequest[]>([]);
  const [events, setEvents] = useState<TrainingEvent[]>([]);
  const [trainingCredits, setTrainingCredits] = useState(0);
  const [trainingPrice, setTrainingPrice] = useState(150);
  const [admin, setAdmin] = useState(false);
  const [queue, setQueue] = useState<TrainingRequest[]>([]);
  const [name, setName] = useState("");
  const [language, setLanguage] = useState("Urdu");
  const [basis, setBasis] = useState<"self_voice" | "authorized_voice">(
    "self_voice",
  );
  const [dataset, setDataset] = useState<File | null>(null);
  const [consent, setConsent] = useState<File | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  async function load() {
    const data = await fetchTrainingRequests(token);
    setRequests(data.requests);
    setEvents(data.events || []);
    setTrainingCredits(data.training_credits);
    setTrainingPrice(data.training_price_pkr);
    setAdmin(data.is_admin && showAdmin);
    if (data.is_admin && showAdmin) setQueue(await fetchAdminTraining(token));
  }
  useEffect(() => {
    load().catch((e) =>
      setError(
        e instanceof Error ? e.message : "Unable to load training requests",
      ),
    );
  }, [token]);
  function chooseData(file: File | null) {
    setError("");
    if (!file) {
      setDataset(null);
      return;
    }
    if (!DATA_TYPES.has(file.type)) {
      setError("Dataset must be ZIP, MP3, WAV or FLAC.");
      return;
    }
    if (file.size > 250 * 1024 * 1024) {
      setError("Dataset must be 250 MB or smaller.");
      return;
    }
    setDataset(file);
  }
  function chooseConsent(file: File | null) {
    setError("");
    if (!file) {
      setConsent(null);
      return;
    }
    if (!CONSENT_TYPES.has(file.type)) {
      setError("Consent proof must be an image, PDF, MP3, WAV or MP4.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError("Consent proof must be 10 MB or smaller.");
      return;
    }
    setConsent(file);
  }
  async function submit() {
    if (!supabase || !dataset) return;
    setBusy(true);
    setError("");
    setMessage("");
    let dataPath = "";
    let consentPath = "";
    try {
      dataPath = `${userId}/${crypto.randomUUID()}.${extension(dataset)}`;
      const dataUpload = await supabase.storage
        .from("voice-training-data")
        .upload(dataPath, dataset, {
          contentType: dataset.type,
          upsert: false,
        });
      if (dataUpload.error) throw new Error(dataUpload.error.message);
      if (consent) {
        consentPath = `${userId}/${crypto.randomUUID()}.${extension(consent)}`;
        const consentUpload = await supabase.storage
          .from("voice-consent-proofs")
          .upload(consentPath, consent, {
            contentType: consent.type,
            upsert: false,
          });
        if (consentUpload.error) throw new Error(consentUpload.error.message);
      }
      try {
        await submitTrainingRequest(token, {
          voice_name: name.trim(),
          language: language.trim(),
          rights_basis: basis,
          consent_confirmed: confirmed,
          dataset_path: dataPath,
          ...(consentPath ? { consent_proof_path: consentPath } : {}),
        });
      } catch (e) {
        await supabase.storage.from("voice-training-data").remove([dataPath]);
        if (consentPath)
          await supabase.storage
            .from("voice-consent-proofs")
            .remove([consentPath]);
        throw e;
      }
      setName("");
      setDataset(null);
      setConsent(null);
      setConfirmed(false);
      setMessage("Training request submitted for consent and dataset review.");
      await load();
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Unable to submit training request",
      );
    } finally {
      setBusy(false);
    }
  }
  async function openAsset(id: string, kind: "dataset" | "consent") {
    setBusy(true);
    try {
      const { url } = await fetchTrainingAsset(token, id, kind);
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to open asset");
    } finally {
      setBusy(false);
    }
  }
  async function advance(row: TrainingRequest, status: TrainingStatus) {
    let note =
      window.prompt(
        status === "rejected" ? "Rejection reason:" : "Optional admin note:",
      ) ?? "";
    let slug: string | undefined;
    if (status === "ready") {
      slug = window.prompt("Exact Modal model folder slug:")?.trim();
      if (!slug) return;
    }
    setBusy(true);
    setError("");
    try {
      await updateTrainingStatus(token, row.id, status, note, slug);
      await load();
      if (status === "ready") onPublished();
      setMessage(`Training request moved to ${status}.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to update request");
    } finally {
      setBusy(false);
    }
  }
  const next = (status: TrainingStatus): TrainingStatus | null =>
    status === "submitted"
      ? "approved"
      : status === "approved"
        ? "training"
        : status === "training"
          ? "model_validation"
          : status === "model_validation"
            ? "ready"
            : null;
  const statusLabel = (status: TrainingStatus) =>
    ({
      submitted: "Review pending",
      approved: "Approved",
      training: "Training in progress",
      model_validation: "Model validation",
      ready: "Ready to use",
      rejected: "Rejected · credit refunded",
    })[status];
  return (
    <div className="training-stack">
      {error && <div className="notice error">{error}</div>}
      {message && (
        <div className="notice success">
          <CheckCircle2 size={16} />
          {message}
        </div>
      )}
      <section className="training-card">
        <div className="training-intro">
          <span className="training-intro-icon"><MicVocal /></span>
          <div><span className="overline">PRIVATE & CONSENT-VERIFIED</span>
          <h2>Create your custom singing voice</h2>
          <p>Send a clean voice recording and the required permission. We review it first, train the private model, and add it to your Voices page.</p></div>
        </div>
        <div className="training-steps"><span><b>1</b><small>Add details</small></span><i/><span><b>2</b><small>Upload voice</small></span><i/><span><b>3</b><small>Review & train</small></span></div>
        <div className="training-price"><div><small>YOUR BALANCE</small><strong>{trainingCredits} training credit{trainingCredits === 1 ? "" : "s"}</strong></div><div><small>INTRODUCTORY PRICE</small><strong>PKR {trainingPrice} / $1</strong></div></div>
        <div className="training-grid">
          <label>
            Name your voice
            <input
              value={name}
              maxLength={80}
              onChange={(e) => setName(e.target.value)}
              placeholder="My private singing voice"
            />
          </label>
          <label>
            Main language
            <input
              value={language}
              maxLength={80}
              onChange={(e) => setLanguage(e.target.value)}
            />
          </label>
          <label>
            Voice ownership
            <select
              value={basis}
              onChange={(e) => setBasis(e.target.value as typeof basis)}
            >
              <option value="self_voice">My own voice</option>
              <option value="authorized_voice">Another consenting adult</option>
            </select>
          </label>
        </div>
        <div className="upload-pair">
          <label className="training-drop">
            <FileArchive />
            <strong>
              {dataset ? dataset.name : "Upload clean voice recordings"}
            </strong>
            <span>ZIP, MP3, WAV or FLAC · up to 250 MB</span>
            <input
              type="file"
              accept=".zip,audio/mpeg,audio/wav,audio/flac"
              onChange={(e) => chooseData(e.target.files?.[0] || null)}
            />
          </label>
          <label className="training-drop">
            <ShieldCheck />
            <strong>
              {consent
                ? consent.name
                : basis === "authorized_voice"
                  ? "Upload voice-owner consent"
                  : "Optional identity proof"}
            </strong>
            <span>Image, PDF, audio or MP4 · up to 10 MB</span>
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp,application/pdf,audio/mpeg,audio/wav,video/mp4"
              onChange={(e) => chooseConsent(e.target.files?.[0] || null)}
            />
          </label>
        </div>
        <label className="rights-check">
          <input
            type="checkbox"
            checked={confirmed}
            onChange={(e) => setConfirmed(e.target.checked)}
          />
          <span>
            I confirm the voice owner is an adult and has clearly permitted AI
            voice training and generated audio.
          </span>
        </label>
        <button
          className="primary-action"
          disabled={
            busy ||
            trainingCredits < 1 ||
            !dataset ||
            !name.trim() ||
            !language.trim() ||
            !confirmed ||
            (basis === "authorized_voice" && !consent)
          }
          onClick={submit}
        >
          {busy ? (
            <LoaderCircle className="spin" size={16} />
          ) : (
            <Upload size={16} />
          )}{" "}
          {trainingCredits < 1 ? "Buy a training credit from Wallet" : "Submit training request"}
        </button>
      </section>
      <section className="training-card">
        <span className="overline">YOUR REQUESTS</span>
        {requests.length === 0 ? (
          <p className="empty-state">No custom voice requests yet.</p>
        ) : (
          requests.map((row) => (
            <div className="training-row" key={row.id}>
              <span>
                <MicVocal />
              </span>
              <div>
                <strong>{row.voice_name}</strong>
                <small>
                  {row.language} · {row.rights_basis.replace("_", " ")}
                  {row.dataset_size_bytes
                    ? ` · ${(row.dataset_size_bytes / 1024 / 1024).toFixed(1)} MB`
                    : ""}
                  {row.admin_note ? ` · ${row.admin_note}` : ""}
                </small>
                {events.filter((event) => event.request_id === row.id).at(-1) && (
                  <small className="training-event">
                    {events.filter((event) => event.request_id === row.id).at(-1)?.message}
                  </small>
                )}
              </div>
              <b className={`training-status ${row.status}`}>
                {statusLabel(row.status)}
              </b>
            </div>
          ))
        )}
      </section>
      {admin && (
        <section className="training-card admin-training">
          <span className="overline">ADMIN · TRAINING QUEUE</span>
          {queue.filter((r) => !["ready", "rejected"].includes(r.status))
            .length === 0 ? (
            <p className="empty-state">No active training requests.</p>
          ) : (
            queue
              .filter((r) => !["ready", "rejected"].includes(r.status))
              .map((row) => {
                const upcoming = next(row.status);
                return (
                  <div className="training-admin-row" key={row.id}>
                    <div>
                      <strong>{row.voice_name}</strong>
                      <small>
                        {row.language} · {row.rights_basis.replace("_", " ")} ·{" "}
                        {row.status.replace("_", " ")}
                      </small>
                    </div>
                    <div>
                      <button
                        onClick={() => openAsset(row.id, "dataset")}
                        disabled={busy}
                      >
                        <Download size={14} /> Dataset
                      </button>
                      {row.consent_proof_path && (
                        <button
                          onClick={() => openAsset(row.id, "consent")}
                          disabled={busy}
                        >
                          <ShieldCheck size={14} /> Consent
                        </button>
                      )}
                      {upcoming && (
                        <button
                          onClick={() => advance(row, upcoming)}
                          disabled={busy}
                        >
                          {upcoming === "ready"
                            ? "Validate & publish"
                            : `Move to ${upcoming.replace("_", " ")}`}
                        </button>
                      )}
                      <button
                        className="danger"
                        onClick={() => advance(row, "rejected")}
                        disabled={busy}
                      >
                        Reject
                      </button>
                    </div>
                  </div>
                );
              })
          )}
        </section>
      )}
    </div>
  );
}
