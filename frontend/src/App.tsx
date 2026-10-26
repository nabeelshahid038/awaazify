import { useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import {
  ArrowRight,
  AudioLines,
  Headphones,
  Home,
  LogOut,
  Mic2,
  Music2,
  Play,
  ShieldCheck,
  Settings,
  Sparkles,
  Upload,
  UserRoundCog,
  Wallet,
} from "lucide-react";
import AdminConsole from "./components/AdminConsole";
import CustomVoiceTraining from "./components/CustomVoiceTraining";
import MySongs from "./components/MySongs";
import Studio from "./components/Studio";
import VoiceCatalog from "./components/VoiceCatalog";
import WalletPanel from "./components/WalletPanel";
import AccountSettings from "./components/AccountSettings";
import LegalPage, { type LegalKind } from "./components/LegalPage";
import PublicContact from "./components/PublicContact";
import "./library.css";
import "./wallet.css";
import "./training.css";
import "./admin.css";
import "./modern.css";
import "./safety.css";
import "./support.css";
import "./diagnostics.css";
import "./phase17.css";
import {
  fetchHealth,
  fetchProfile,
  fetchVoices,
  type ProfileResponse,
} from "./services/api";
import { supabaseConfigured } from "./lib/config";
import { supabase } from "./lib/supabase";
type Health = "checking" | "online" | "offline";
type Page = "home" | "create" | "voices" | "custom_voice" | "songs" | "wallet" | "settings" | "admin";
const baseNav = [
  { id: "home" as const, label: "Home", icon: Home },
  { id: "create" as const, label: "Create Song", icon: Sparkles },
  { id: "voices" as const, label: "Voices", icon: Mic2 },
  { id: "custom_voice" as const, label: "Custom Voice", icon: UserRoundCog },
  { id: "songs" as const, label: "My Songs", icon: Music2 },
  { id: "wallet" as const, label: "Wallet", icon: Wallet },
  { id: "settings" as const, label: "Settings", icon: Settings },
];
const pageCopy: Record<Page, [string, string, string]> = {
  home: ["YOUR SPACE", "Welcome back", "Create, listen and manage your songs."],
  create: [
    "NEW COVER",
    "Create a song",
    "Choose audio, select a voice and we’ll handle the rest.",
  ],
  voices: [
    "VOICE MARKETPLACE",
    "Find your voice",
    "Listen to demos and choose a verified model for your cover.",
  ],
  custom_voice: ["PRIVATE VOICE", "Train a custom voice", "Create a private model with clear consent and guided review."],
  songs: ["YOUR LIBRARY", "Your songs", "Preview, download or safely remove your completed covers."],
  wallet: [
    "CREDITS & PAYMENTS",
    "Wallet",
    "Buy song and voice credits through secure verification.",
  ],
  settings: ["ACCOUNT & PRIVACY", "Settings", "Manage your account and personal data."],
  admin: [
    "ADMIN ONLY",
    "Admin console",
    "Review activity and keep Awaazify healthy.",
  ],
};
export default function App() {
  const [health, setHealth] = useState<Health>("checking"),
    [session, setSession] = useState<Session | null>(null),
    [authLoading, setAuthLoading] = useState(true),
    [profile, setProfile] = useState<ProfileResponse | null>(null),
    [profileError, setProfileError] = useState(""),
    [actionError, setActionError] = useState(""),
    [page, setPage] = useState<Page>("home"),
    [selectedVoice, setSelectedVoice] = useState(
      () => localStorage.getItem("awaazify_voice") || "",
    ),
    [selectedVoiceName,setSelectedVoiceName]=useState(()=>localStorage.getItem("awaazify_voice_name")||""),
    [voiceRefresh, setVoiceRefresh] = useState(0);
  const [legal,setLegal]=useState<LegalKind|null>(null);
  useEffect(() => {
    fetchHealth()
      .then(() => setHealth("online"))
      .catch(() => setHealth("offline"));
  }, []);
  useEffect(() => {
    if (!supabase) {
      setAuthLoading(false);
      return;
    }
    let active = true;
    const client = supabase;
    client.auth.getSession().then(({ data, error }) => {
      if (active) {
        setSession(data.session);
        setActionError(error?.message || "");
        setAuthLoading(false);
      }
    });
    const {
      data: { subscription },
    } = client.auth.onAuthStateChange((_e, next) => {
      if (active) {
        setSession(next);
        setAuthLoading(false);
      }
    });
    return () => {
      active = false;
      subscription.unsubscribe();
    };
  }, []);
  useEffect(() => {
    let active = true;
    if (!session) {
      setProfile(null);
      return;
    }
    fetchProfile(session.access_token)
      .then((v) => {
        if (active) setProfile(v);
      })
      .catch((e) => {
        if (active)
          setProfileError(
            e instanceof Error ? e.message : "Unable to load account",
          );
      });
    return () => {
      active = false;
    };
  }, [session?.access_token]);
  useEffect(() => {
    if (!authLoading && location.pathname === "/auth/callback")
      history.replaceState({}, "", "/");
  }, [authLoading]);
  useEffect(()=>{if(session&&localStorage.getItem("awaazify_after_auth")==="create"){setPage("create");localStorage.removeItem("awaazify_after_auth");}},[session]);
  useEffect(()=>{if(!session)return;fetchVoices(session.access_token).then(voices=>{const match=voices.find(v=>v.slug===selectedVoice);if(match){setSelectedVoiceName(match.display_name);localStorage.setItem("awaazify_voice_name",match.display_name);}else if(voices[0]){setSelectedVoice(voices[0].slug);setSelectedVoiceName(voices[0].display_name);localStorage.setItem("awaazify_voice",voices[0].slug);localStorage.setItem("awaazify_voice_name",voices[0].display_name);}else{setSelectedVoice("");setSelectedVoiceName("");localStorage.removeItem("awaazify_voice");localStorage.removeItem("awaazify_voice_name");}}).catch(()=>{});},[session?.access_token,voiceRefresh]);
  async function signIn() {
    if (!supabase) return;
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: location.origin + "/auth/callback" },
    });
    if (error) setActionError(error.message);
  }
  function choosePublicVoice(slug:string,name:string){localStorage.setItem("awaazify_voice",slug);localStorage.setItem("awaazify_voice_name",name);localStorage.setItem("awaazify_after_auth","create");setSelectedVoice(slug);setSelectedVoiceName(name);void signIn();}
  async function signOut() {
    if (!supabase) return;
    const { error } = await supabase.auth.signOut();
    if (error) setActionError(error.message);
    else {
      setPage("home");
      setProfile(null);
    }
  }
  function go(next: Page) {
    setPage(next);
    scrollTo({ top: 0, behavior: "smooth" });
  }
  const nav = profile?.is_admin
      ? [
          ...baseNav,
          { id: "admin" as const, label: "Admin", icon: ShieldCheck },
        ]
      : baseNav,
    credits =
      (profile?.free_song_credits || 0) +
      (profile?.bonus_song_credits || 0) +
      (profile?.song_credits || 0),
    copy = pageCopy[page];
  if (authLoading)
    return (
      <div className="app-loading">
        <span className="logo-mark">
          <AudioLines />
        </span>
        <div className="spinner" />
        <p>Opening your studio…</p>
      </div>
    );
  if(legal) return <LegalPage kind={legal} onBack={()=>setLegal(null)}/>;
  if (!session)
    return (
      <div className="public-shell">
        <header className="public-header">
          <a className="brand" href="/">
            <span className="logo-mark">
              <AudioLines />
            </span>
            Awaazify
          </a>
          <nav className="public-menu"><a href="#voices">Voices</a><a href="#how-it-works">How it works</a><a href="#pricing">Pricing</a><a href="#contact">Contact</a></nav>
          <button className="quiet-login" onClick={signIn}>
            Sign in
          </button>
        </header>
        <main>
          <section className="hero-modern">
            <div className="hero-copy">
              <div className="eyebrow">
                <span />
                AI VOICE COVER STUDIO
              </div>
              <h1>
                Your song.
                <br />
                <em>A new voice.</em>
              </h1>
              <p>
                Upload your audio and create an AI cover in simple steps. Your
                files stay private, and your first full song is free.
              </p>
              <div className="hero-actions">
                <button
                  className="cta-button"
                  onClick={signIn}
                  disabled={!supabaseConfigured}
                >
                  Create my first song <ArrowRight />
                </button>
                <span>
                  <ShieldCheck /> Your files stay private
                </span>
              </div>
              {actionError && <div className="notice error">{actionError}</div>}
            </div>
            <div className="hero-visual">
              <div className="now-playing">
                <div className="cover-art">
                  <AudioLines />
                </div>
                <div>
                  <small>CREATING YOUR COVER</small>
                  <strong>My favourite song</strong>
                  <span>Applying selected voice…</span>
                </div>
                <button>
                  <Play fill="currentColor" />
                </button>
              </div>
              <div className="wave-bars">
                {Array.from({ length: 34 }, (_, i) => (
                  <i key={i} style={{ height: `${18 + ((i * 17) % 58)}%` }} />
                ))}
              </div>
              <div className="mini-step">
                <b>1</b>
                <span>Upload</span>
                <b>2</b>
                <span>Choose voice</span>
                <b>3</b>
                <span>Download</span>
              </div>
            </div>
          </section>
          <section className="landing-voices" id="voices"><div className="section-intro"><span>VOICE MARKETPLACE</span><h2>Hear it before you create.</h2><p>Explore verified voices, listen to two demos and continue with your favourite.</p></div><VoiceCatalog publicMode onSelect={choosePublicVoice}/></section>
          <section className="simple-steps" id="how-it-works">
            <div className="section-intro">
              <span>HOW IT WORKS</span>
              <h2>Three simple steps.</h2>
              <p>
                No technical setup. We guide you from audio to finished cover.
              </p>
            </div>
            <div className="step-cards">
              <article>
                <span>
                  <Upload />
                </span>
                <b>01</b>
                <h3>Add your song</h3>
                <p>Upload audio now. YouTube import is coming soon.</p>
              </article>
              <article>
                <span>
                  <Mic2 />
                </span>
                <b>02</b>
                <h3>Pick a voice</h3>
                <p>Choose a voice without confusing technical settings.</p>
              </article>
              <article>
                <span>
                  <Headphones />
                </span>
                <b>03</b>
                <h3>Enjoy your cover</h3>
                <p>Preview your private song and download the MP3.</p>
              </article>
            </div>
          </section>
          <section className="landing-pricing" id="pricing"><div><small>PAY AS YOU GO</small><h2>Simple prices. No subscription.</h2><p>Your first song is free. Buy only what you use after that.</p></div><article><span>Song cover</span><strong>PKR 50</strong><small>Global · $0.50</small></article><article><span>Custom voice</span><strong>PKR 150</strong><small>Global · $1.00</small></article><button onClick={()=>{localStorage.setItem("awaazify_after_auth","create");void signIn();}}>Start free <ArrowRight/></button></section>
          <PublicContact/>
          <section className="trust-strip">
            <ShieldCheck />
            <div>
              <strong>Built around privacy and permission</strong>
              <p>Private storage, consent checks and verified payments.</p>
            </div>
            <button onClick={signIn}>
              Start free <ArrowRight />
            </button>
          </section>
        </main>
        <footer className="public-footer">
          <span>© Awaazify</span>
          <span className="footer-links"><button onClick={()=>setLegal("terms")}>Terms</button><button onClick={()=>setLegal("privacy")}>Privacy</button><button onClick={()=>setLegal("copyright")}>Copyright</button><button onClick={()=>setLegal("refund")}>Refunds</button></span>
          <span className={`live-indicator ${health}`}>
            {health === "online" ? "All systems ready" : "Checking systems"}
          </span>
        </footer>
      </div>
    );
  return (
    <div className="product-shell">
      <aside className="product-sidebar">
        <div className="sidebar-brand">
          <span className="logo-mark">
            <AudioLines />
          </span>
          Awaazify
        </div>
        <nav>
          {nav.map((item) => (
            <button
              key={item.id}
              className={page === item.id ? "active" : ""}
              onClick={() => go(item.id)}
            >
              <item.icon />
              {item.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-account">
          <div>
            {profile?.avatar_url ? (
              <img src={profile.avatar_url} alt="" />
            ) : (
              <span>{(profile?.display_name || "U")[0]}</span>
            )}
          </div>
          <p>
            <strong>{profile?.display_name || "Creator"}</strong>
            <small>{profile?.email}</small>
          </p>
          <button onClick={signOut} aria-label="Sign out">
            <LogOut />
          </button>
        </div>
      </aside>
      <div className="product-main">
        <header className="mobile-topbar">
          <span className="mobile-brand">
            <span className="logo-mark">
              <AudioLines />
            </span>
            Awaazify
          </span>
          <span className="mobile-actions">
            <button onClick={() => go("settings")} className={page === "settings" ? "active" : ""} aria-label="Open account settings"><Settings /></button>
            {profile?.is_admin && (
              <button
                onClick={() => go("admin")}
                className={page === "admin" ? "active" : ""}
                aria-label="Open admin console"
              >
                <ShieldCheck />
              </button>
            )}
            <button onClick={signOut} className="mobile-signout" aria-label="Sign out"><LogOut /></button>
            <button onClick={() => go("wallet")}>{credits} credits</button>
          </span>
        </header>
        <main className="product-content">
          <div className="page-heading">
            <div>
              <span>{copy[0]}</span>
              <h1>
                {page === "home"
                  ? `${copy[1]}, ${(profile?.display_name || "creator").split(" ")[0]}.`
                  : copy[1]}
              </h1>
              <p>{copy[2]}</p>
            </div>
          </div>
          {profileError && <div className="notice error">{profileError}</div>}
          {page === "home" ? (
            <>
              <section className="home-hero">
                <div>
                  <span>
                    <Sparkles /> YOUR STUDIO IS READY
                  </span>
                  <h2>
                    Turn a song into
                    <br />
                    your next cover.
                  </h2>
                  <p>
                    Upload audio, choose a voice and let Awaazify create the
                    final song.
                  </p>
                  <button className="cta-button" onClick={() => go("create")}>
                    Create a song <ArrowRight />
                  </button>
                </div>
                <div className="home-orb">
                  <AudioLines />
                  <i />
                  <i />
                  <i />
                </div>
              </section>
              <div className="quick-grid">
                {[
                  {
                    p: "create" as Page,
                    i: Sparkles,
                    t: "Create new song",
                    s: "Upload your audio file",
                  },
                  {
                    p: "voices" as Page,
                    i: Mic2,
                    t: "Choose a voice",
                    s: "Browse available voices",
                  },
                  {
                    p: "songs" as Page,
                    i: Music2,
                    t: "Listen to songs",
                    s: "Preview and download",
                  },
                ].map((x) => (
                  <button onClick={() => go(x.p)} key={x.t}>
                    <span>
                      <x.i />
                    </span>
                    <div>
                      <strong>{x.t}</strong>
                      <small>{x.s}</small>
                    </div>
                    <ArrowRight />
                  </button>
                ))}
              </div>
              <div className="account-summary">
                <article>
                  <small>AVAILABLE CREDITS</small>
                  <strong>{credits}</strong>
                  <p>
                    {profile?.free_song_credits || 0} free ·{" "}
                    {profile?.bonus_song_credits || 0} bonus ·{" "}
                    {profile?.song_credits || 0} paid
                  </p>
                </article>
                <article>
                  <small>{selectedVoiceName?"SELECTED VOICE":"VOICE MODEL"}</small>
                  <strong className="voice-name">
                    <Mic2 /> {selectedVoiceName||"Choose a voice"}
                  </strong>
                  <p>{selectedVoiceName?"Ready for your next cover.":"Select a verified model before creating."}</p>
                </article>
              </div>
            </>
          ) : page === "create" ? (
            <><div className={`selected-voice-banner ${selectedVoiceName?"":"missing"}`}><span><Mic2/></span><div><small>VOICE FOR THIS COVER</small><strong>{selectedVoiceName||"No voice selected"}</strong><p>{selectedVoiceName?"This model will be applied when generation starts.":"Choose an available voice model to continue."}</p></div><button onClick={()=>go("voices")}>{selectedVoiceName?"Change voice":"Choose voice"}<ArrowRight/></button></div><Studio
              token={session.access_token}
              userId={session.user.id}
              freeCredits={credits}
              modelSlug={selectedVoice}
              onCreditUsed={() =>
                setProfile((c) =>
                  c
                    ? c.free_song_credits > 0
                      ? { ...c, free_song_credits: c.free_song_credits - 1 }
                      : c.bonus_song_credits > 0
                        ? { ...c, bonus_song_credits: c.bonus_song_credits - 1 }
                      : { ...c, song_credits: Math.max(0, c.song_credits - 1) }
                    : c,
                )
              }
              onOpenWallet={() => go("wallet")}
            /></>
          ) : page === "voices" ? (
              <VoiceCatalog
                token={session.access_token}
                selected={selectedVoice}
                refreshKey={voiceRefresh}
                onSelect={(slug,name) => {
                  setSelectedVoice(slug);
                  setSelectedVoiceName(name);
                  localStorage.setItem("awaazify_voice", slug);
                  localStorage.setItem("awaazify_voice_name", name);
                }}
              />
          ) : page === "custom_voice" ? (
              <CustomVoiceTraining
                token={session.access_token}
                userId={session.user.id}
                onPublished={() => setVoiceRefresh((v) => v + 1)}
              />
          ) : page === "songs" ? (
            <MySongs token={session.access_token} />
          ) : page === "wallet" ? (
            <WalletPanel
              token={session.access_token}
              userId={session.user.id}
              onBalance={(song_credits) =>
                setProfile((c) => (c ? { ...c, song_credits } : c))
              }
            />
          ) : page === "settings" && profile ? (
            <AccountSettings token={session.access_token} profile={profile} />
          ) : profile?.is_admin ? (
            <AdminConsole token={session.access_token} />
          ) : null}
        </main>
        <footer className="product-footer"><span>© Awaazify</span><span><button onClick={()=>setLegal("terms")}>Terms</button><button onClick={()=>setLegal("privacy")}>Privacy</button><button onClick={()=>setLegal("copyright")}>Copyright & Voice Rights</button><button onClick={()=>setLegal("refund")}>Refunds</button></span></footer>
        <nav className="mobile-nav">
          {baseNav.filter(item=>!["settings","wallet"].includes(item.id)).map((item) => (
            <button
              key={item.id}
              className={page === item.id ? "active" : ""}
              onClick={() => go(item.id)}
            >
              <item.icon />
              <span>
                {item.label === "Create Song" ? "Create" : item.label}
              </span>
            </button>
          ))}
        </nav>
      </div>
    </div>
  );
}
