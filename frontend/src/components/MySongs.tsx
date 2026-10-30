import { Download, FileWarning, LoaderCircle, Music2, PlayCircle, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { deleteLibrarySong, fetchFinalArtifacts, fetchLibrarySongs, selectSongPitch, type FinalArtifacts, type LibrarySong } from "../services/api";
import { downloadFile } from "../lib/download";

type Props = { token: string };

export default function MySongs({ token }: Props) {
  const [songs, setSongs] = useState<LibrarySong[]>([]);
  const [filter, setFilter] = useState<"all" | "completed" | "failed">("all");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [files, setFiles] = useState<Record<string, FinalArtifacts>>({});
  const [preview, setPreview] = useState<Record<string, string>>({});

  useEffect(() => {
    fetchLibrarySongs(token).then(setSongs).catch((e) => setError(e instanceof Error ? e.message : "Unable to load songs")).finally(() => setLoading(false));
  }, [token]);

  async function loadVersions(song: LibrarySong) {
    setBusy(song.id); setError("");
    try {
      const result = await fetchFinalArtifacts(token, song.id);
      setFiles((current) => ({ ...current, [song.id]: result }));
      const selected = result.variants.find((item) => item.pitch === result.selected_pitch) || result.variants[0];
      if (selected) setPreview((current) => ({ ...current, [song.id]: selected.mp3_url }));
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to load song versions"); }
    finally { setBusy(null); }
  }

  async function choose(song: LibrarySong, pitch: -3 | 0 | 3, url: string) {
    setBusy(song.id); setError("");
    try {
      await selectSongPitch(token, song.id, pitch);
      setSongs((current) => current.map((item) => item.id === song.id ? { ...item, selected_pitch: pitch } : item));
      setFiles((current) => current[song.id] ? { ...current, [song.id]: { ...current[song.id], selected_pitch: pitch } } : current);
      setPreview((current) => ({ ...current, [song.id]: url }));
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to select version"); }
    finally { setBusy(null); }
  }

  async function remove(song: LibrarySong) {
    if (!confirm(`Permanently delete “${song.title}” and all three audio versions?`)) return;
    setBusy(song.id); setError("");
    try { await deleteLibrarySong(token, song.id); setSongs((current) => current.filter((item) => item.id !== song.id)); }
    catch (e) { setError(e instanceof Error ? e.message : "Unable to delete song"); }
    finally { setBusy(null); }
  }

  const shown = songs.filter((song) => filter === "all" || song.status === filter);
  return <div className="library-stack">
    <div className="library-filters">{(["all", "completed", "failed"] as const).map((item) => <button className={filter === item ? "active" : ""} onClick={() => setFilter(item)} key={item}>{item[0].toUpperCase() + item.slice(1)}</button>)}</div>
    {error && <div className="notice error">{error}</div>}
    {loading ? <div className="empty-state"><LoaderCircle className="spin" />Loading songs…</div> : shown.length === 0 ? <div className="empty-state"><Music2 />No {filter === "all" ? "" : filter} songs yet.</div> : <div className="song-list">{shown.map((song) => {
      const variants = files[song.id];
      return <article className="song-card" key={song.id}>
        <span className={`song-icon ${song.status}`}>{song.status === "completed" ? <Music2 /> : <FileWarning />}</span>
        <div className="song-main"><h3>{song.title}</h3><p>{song.source_type || "Source"} · {song.duration_seconds ? `${song.duration_seconds.toFixed(1)} sec` : "—"} · {song.model_slug}</p>{preview[song.id] && <audio controls preload="metadata" src={preview[song.id]} />}{song.error_message && <small>{song.error_message}</small>}</div>
        <span className={`status ${song.status === "completed" ? "status-online" : "status-offline"}`}>{song.status}</span>
        {variants && <div className="song-variants">{variants.variants.map((variant) => <button className={variants.selected_pitch === variant.pitch ? "active" : ""} key={variant.pitch} onClick={() => choose(song, variant.pitch, variant.mp3_url)} disabled={busy === song.id}><PlayCircle size={14} /> {variant.label} <small>{variant.pitch > 0 ? `+${variant.pitch}` : variant.pitch}</small></button>)}</div>}
        <div className="song-actions">{song.status === "completed" && !variants && <button onClick={() => loadVersions(song)} disabled={busy === song.id}>{busy === song.id ? <LoaderCircle className="spin" size={15} /> : <PlayCircle size={15} />} Versions</button>}{variants && <button onClick={() => { const current = variants.variants.find((item) => item.pitch === variants.selected_pitch); if (current) downloadFile(current.mp3_url, `${song.title}-${current.label.toLowerCase()}`); }}><Download size={15} /> Selected MP3</button>}<button className="danger-quiet" onClick={() => remove(song)} disabled={busy === song.id}><Trash2 size={15} /> Delete</button></div>
      </article>;
    })}</div>}
  </div>;
}
