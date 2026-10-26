import { useEffect, useRef, useState } from "react";
import {
  CheckCircle2,
  CloudUpload,
  Download,
  FileAudio,
  LoaderCircle,
  Play,
  Youtube,
} from "lucide-react";
import { supabase } from "../lib/supabase";
import {
  createGenerationJob,
  createStudioProject,
  fetchFinalArtifacts,
  fetchGenerationJobs,
  fetchStudioProjects,
  fetchYoutubeMetadata,
  retryGenerationJob,
  type GenerationJob,
  type StudioProject,
  type YoutubeMetadata,
} from "../services/api";
import { downloadFile } from "../lib/download";

const MAX_BYTES = 100 * 1024 * 1024;
const ALLOWED = new Set([
  "audio/mpeg",
  "audio/wav",
  "audio/x-wav",
  "audio/flac",
  "audio/mp4",
  "audio/x-m4a",
  "audio/aac",
  "audio/ogg",
]);

type Props = {
  token: string;
  userId: string;
  freeCredits: number;
  modelSlug: string;
  onCreditUsed: () => void;
  onOpenWallet: () => void;
};

function safeName(name: string) {
  const extension = name.includes(".")
    ? `.${name
        .split(".")
        .pop()
        ?.toLowerCase()
        .replace(/[^a-z0-9]/g, "")}`
    : "";
  return `${crypto.randomUUID()}${extension}`;
}

function jobStageLabel(status: string) {
  const labels: Record<string, string> = {
    queued: "Waiting to start",
    preparing: "Preparing audio",
    prepared: "Audio ready",
    separating: "Separating vocals",
    converting: "Applying selected voice",
    converted: "Voice conversion ready",
    mixing: "Creating final song",
    completed: "Ready to download",
    failed: "Processing failed",
  };
  return labels[status] || status.replaceAll("_", " ");
}

export default function Studio({
  token,
  userId,
  freeCredits,
  modelSlug,
  onCreditUsed,
  onOpenWallet,
}: Props) {
  const [mode, setMode] = useState<"youtube" | "upload">("upload");
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [metadata, setMetadata] = useState<YoutubeMetadata | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [duration, setDuration] = useState(0);
  const [trimStart, setTrimStart] = useState(0);
  const [trimEnd, setTrimEnd] = useState(360);
  const [rights, setRights] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [projects, setProjects] = useState<StudioProject[]>([]);
  const [jobs, setJobs] = useState<GenerationJob[]>([]);
  const [startingProject, setStartingProject] = useState<string | null>(null);
  const objectUrl = useRef<string | null>(null);

  useEffect(() => {
    fetchStudioProjects(token)
      .then(setProjects)
      .catch(() => {});
    fetchGenerationJobs(token)
      .then(setJobs)
      .catch(() => {});
  }, [token]);
  useEffect(() => {
    if (
      !jobs.some((j) =>
        [
          "queued",
          "preparing",
          "prepared",
          "separating",
          "converting",
          "converted",
          "mixing",
        ].includes(
          j.status,
        ),
      )
    )
      return;
    const timer = window.setInterval(
      () =>
        fetchGenerationJobs(token)
          .then(setJobs)
          .catch(() => {}),
      3000,
    );
    return () => window.clearInterval(timer);
  }, [jobs, token]);
  useEffect(
    () => () => {
      if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
    },
    [],
  );

  function resetFeedback() {
    setError("");
    setMessage("");
  }
  async function inspectYoutube() {
    resetFeedback();
    setBusy(true);
    setMetadata(null);
    try {
      const data = await fetchYoutubeMetadata(token, youtubeUrl);
      setMetadata(data);
      setMessage("Metadata verified. Select a range and confirm your rights.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to inspect the video");
    } finally {
      setBusy(false);
    }
  }
  function chooseFile(next: File | null) {
    resetFeedback();
    setFile(null);
    setDuration(0);
    if (!next) return;
    if (!ALLOWED.has(next.type)) {
      setError("Choose MP3, WAV, FLAC, M4A, AAC or OGG audio.");
      return;
    }
    if (next.size > MAX_BYTES) {
      setError("Audio file must be 100 MB or smaller.");
      return;
    }
    if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
    objectUrl.current = URL.createObjectURL(next);
    const audio = new Audio(objectUrl.current);
    audio.onloadedmetadata = () => {
      if (!Number.isFinite(audio.duration) || audio.duration <= 0) {
        setError("Could not read the audio duration.");
        return;
      }
      if (audio.duration > 360.05) {
        setError(
          "V1 accepts audio up to six minutes. Trim longer audio before uploading.",
        );
        return;
      }
      const seconds = Math.round(audio.duration * 1000) / 1000;
      setFile(next);
      setDuration(seconds);
      setTrimStart(0);
      setTrimEnd(seconds);
      setMessage("Audio validated locally. It has not been uploaded yet.");
    };
    audio.onerror = () =>
      setError("This audio file could not be decoded by the browser.");
  }
  async function saveProject() {
    resetFeedback();
    if (!rights) {
      setError("Confirm that you own or have permission to use this audio.");
      return;
    }
    if (trimEnd <= trimStart || trimEnd - trimStart > 360) {
      setError("Choose a valid range of up to six minutes.");
      return;
    }
    if (!supabase) {
      setError("Supabase is not configured.");
      return;
    }
    setBusy(true);
    let uploadedPath: string | undefined;
    try {
      if (mode === "youtube") {
        if (!metadata) throw new Error("Verify the YouTube URL first.");
        const created = await createStudioProject(token, {
          source_type: "youtube",
          title: metadata.title,
          rights_confirmed: true,
          trim_start_seconds: trimStart,
          trim_end_seconds: trimEnd,
          youtube_url: metadata.canonical_url,
          youtube_video_id: metadata.video_id,
          youtube_title: metadata.title,
          youtube_thumbnail_url: metadata.thumbnail_url || undefined,
        });
        setProjects((p) => [created, ...p]);
      } else {
        if (!file || !duration)
          throw new Error("Choose a valid audio file first.");
        uploadedPath = `${userId}/${safeName(file.name)}`;
        const { error: uploadError } = await supabase.storage
          .from("source-audio")
          .upload(uploadedPath, file, {
            contentType: file.type,
            upsert: false,
          });
        if (uploadError) throw new Error(uploadError.message);
        try {
          const created = await createStudioProject(token, {
            source_type: "upload",
            title: file.name.replace(/\.[^.]+$/, ""),
            rights_confirmed: true,
            trim_start_seconds: trimStart,
            trim_end_seconds: trimEnd,
            storage_path: uploadedPath,
            original_filename: file.name,
            mime_type: file.type,
            size_bytes: file.size,
            source_duration_seconds: duration,
          });
          setProjects((p) => [created, ...p]);
        } catch (e) {
          await supabase.storage.from("source-audio").remove([uploadedPath]);
          throw e;
        }
      }
      setMessage(
        "Song saved privately. You can now start creating your cover.",
      );
      setRights(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to save project");
    } finally {
      setBusy(false);
    }
  }
  async function startProcessing(projectId: string) {
    resetFeedback();
    if (freeCredits < 1) {
      setError("You do not have a song credit. Add credits from Wallet.");
      return;
    }
    setStartingProject(projectId);
    try {
      const created = await createGenerationJob(token, projectId, modelSlug);
      setJobs((current) => [
        {
          id: created.job_id,
          project_id: projectId,
          status: created.status,
          progress: created.progress,
          error_message: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
        ...current,
      ]);
      setProjects((current) =>
        current.map((project) =>
          project.id === projectId ? { ...project, status: "queued" } : project,
        ),
      );
      onCreditUsed();
      setMessage(
        "Processing accepted. Audio preparation is running privately.",
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to start processing");
    } finally {
      setStartingProject(null);
    }
  }
  async function retryProcessing(jobId: string) {
    resetFeedback();
    setStartingProject(jobId);
    try {
      await retryGenerationJob(token, jobId);
      onCreditUsed();
      setMessage("Retry accepted. Processing will continue automatically.");
      window.setTimeout(
        () =>
          fetchGenerationJobs(token)
            .then(setJobs)
            .catch(() => {}),
        1500,
      );
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Unable to retry processing",
      );
    } finally {
      setStartingProject(null);
    }
  }
  async function downloadSong(jobId: string, title: string) {
    resetFeedback();
    setStartingProject(jobId);
    try {
      const artifacts = await fetchFinalArtifacts(token, jobId);
      await downloadFile(artifacts.mp3_url, title);
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Unable to authorize the final download",
      );
    } finally {
      setStartingProject(null);
    }
  }
  const ready = mode === "youtube" ? Boolean(metadata) : Boolean(file);
  return (
    <div className="studio-stack">
      {freeCredits < 1 && (
        <div className="credit-warning" role="status">
          <div>
            <strong>No song credits available</strong>
            <span>
              You can prepare a song now, but one credit is required to start
              generation.
            </span>
          </div>
          <button onClick={onOpenWallet}>Buy credits</button>
        </div>
      )}
      <section className="studio-card">
        <div className="source-tabs" role="tablist" aria-label="Audio source">
          <button
            className="coming-soon-tab"
            disabled
            aria-disabled="true"
            title="YouTube import is coming soon"
          >
            <Youtube size={18} /> YouTube URL
            <small>Coming soon</small>
          </button>
          <button
            className={mode === "upload" ? "active" : ""}
            onClick={() => {
              setMode("upload");
              resetFeedback();
            }}
          >
            <CloudUpload size={18} /> Upload audio
          </button>
        </div>
        {mode === "youtube" ? (
          <div className="source-panel">
            <label htmlFor="youtube-url">YouTube video URL</label>
            <div className="inline-input">
              <input
                id="youtube-url"
                value={youtubeUrl}
                onChange={(e) => {
                  setYoutubeUrl(e.target.value);
                  setMetadata(null);
                }}
                placeholder="https://www.youtube.com/watch?v=…"
              />
              <button
                onClick={inspectYoutube}
                disabled={busy || !youtubeUrl.trim()}
              >
                {busy ? <LoaderCircle className="spin" size={17} /> : null}{" "}
                Verify
              </button>
            </div>
            <p className="field-help">
              Paste a public YouTube link that you have permission to use.
            </p>
            {metadata && (
              <div className="metadata-card">
                {metadata.thumbnail_url && (
                  <img src={metadata.thumbnail_url} alt="Video thumbnail" />
                )}
                <div>
                  <strong>{metadata.title}</strong>
                  <span>
                    {metadata.author_name || "YouTube"} · ID {metadata.video_id}
                  </span>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="source-panel">
            <label className="drop-zone">
              <CloudUpload size={28} />
              <strong>{file ? file.name : "Choose your audio file"}</strong>
              <span>
                MP3, WAV, FLAC, M4A, AAC or OGG · maximum 100 MB and 6 minutes
              </span>
              <input
                type="file"
                accept="audio/mpeg,audio/wav,audio/x-wav,audio/flac,audio/mp4,audio/x-m4a,audio/aac,audio/ogg"
                onChange={(e) => chooseFile(e.target.files?.[0] || null)}
              />
            </label>
            {file && (
              <div className="file-summary">
                <FileAudio size={20} />
                <span>
                  {(file.size / 1024 / 1024).toFixed(2)} MB ·{" "}
                  {duration.toFixed(1)} seconds
                </span>
              </div>
            )}
          </div>
        )}
        {ready && (
          <div className="trim-panel">
            <div>
              <label htmlFor="trim-start">Start (seconds)</label>
              <input
                id="trim-start"
                type="number"
                min="0"
                max="359.9"
                step="0.1"
                value={trimStart}
                onChange={(e) => setTrimStart(Number(e.target.value))}
              />
            </div>
            <div>
              <label htmlFor="trim-end">End (seconds)</label>
              <input
                id="trim-end"
                type="number"
                min="0.1"
                max={mode === "upload" ? duration : 360}
                step="0.1"
                value={trimEnd}
                onChange={(e) => setTrimEnd(Number(e.target.value))}
              />
            </div>
            <span>{Math.max(0, trimEnd - trimStart).toFixed(1)}s selected</span>
          </div>
        )}
        {ready && (
          <label className="rights-check">
            <input
              type="checkbox"
              checked={rights}
              onChange={(e) => setRights(e.target.checked)}
            />
            <span>
              I own this audio or have permission to create and store a
              transformed version.
            </span>
          </label>
        )}
        {error && (
          <div className="notice error" role="alert">
            {error}
          </div>
        )}
        {message && (
          <div className="notice success">
            <CheckCircle2 size={16} />
            {message}
          </div>
        )}
        <button
          className="primary-action save-project"
          disabled={!ready || !rights || busy}
          onClick={saveProject}
        >
          {busy ? <LoaderCircle className="spin" size={17} /> : null} Save
          project
        </button>
      </section>
      <section className="project-list">
        <div className="section-heading">
          <div>
            <span className="overline">YOUR SONGS</span>
            <h2>Recent creations</h2>
          </div>
          <span className="section-note">Private to your account</span>
        </div>
        {projects.length === 0 ? (
          <p className="empty-state">
            No songs yet. Your first creation will appear here.
          </p>
        ) : (
          projects.map((p) => {
            const job = jobs.find((item) => item.project_id === p.id);
            const active =
              job &&
              [
                "queued",
                "preparing",
                "prepared",
                "separating",
                "converting",
                "converted",
                "mixing",
              ].includes(job.status);
            return (
              <article key={p.id}>
                <span className={`source-mark ${p.source_type}`}>
                  {p.source_type === "youtube" ? (
                    <Youtube size={16} />
                  ) : (
                    <FileAudio size={16} />
                  )}
                </span>
                <div>
                  <strong>{p.title}</strong>
                  <span>
                    {p.source_type === "youtube" ? "YouTube" : "Upload"} ·{" "}
                    {Number(p.trim_end_seconds) - Number(p.trim_start_seconds)}{" "}
                    seconds
                  </span>
                  {job && (
                    <div className="job-progress">
                      <span style={{ width: `${job.progress}%` }} />
                      <small>
                        {jobStageLabel(job.status)} · {job.progress}%
                        {job.error_message ? ` · ${job.error_message}` : ""}
                      </small>
                    </div>
                  )}
                </div>
                {!job && p.status === "ready" ? (
                  <button
                    className="prepare-button"
                    disabled={startingProject === p.id || freeCredits < 1}
                    onClick={() => startProcessing(p.id)}
                  >
                    {startingProject === p.id ? (
                      <LoaderCircle className="spin" size={15} />
                    ) : (
                      <Play size={15} />
                    )}{" "}
                    Start processing
                  </button>
                ) : job?.status === "failed" ? (
                  <button
                    className="prepare-button"
                    disabled={startingProject === job.id}
                    onClick={() => retryProcessing(job.id)}
                  >
                    {startingProject === job.id ? (
                      <LoaderCircle className="spin" size={15} />
                    ) : (
                      <Play size={15} />
                    )}{" "}
                    Retry processing
                  </button>
                ) : job?.status === "completed" ? (
                  <button
                    className="prepare-button"
                    disabled={startingProject === job.id}
                    onClick={() => downloadSong(job.id, p.title)}
                  >
                    {startingProject === job.id ? (
                      <LoaderCircle className="spin" size={15} />
                    ) : (
                      <Download size={15} />
                    )}{" "}
                    Download MP3
                  </button>
                ) : (
                  <span className="status status-online">
                    {active ? (
                      <LoaderCircle className="spin" size={14} />
                    ) : null}
                    {job?.status || p.status}
                  </span>
                )}
              </article>
            );
          })
        )}
      </section>
    </div>
  );
}
