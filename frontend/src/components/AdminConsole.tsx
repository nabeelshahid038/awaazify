import {
  Activity,
  Check,
  CircleDollarSign,
  ExternalLink,
  Gift,
  HeartPulse,
  LoaderCircle,
  MicVocal,
  Shield,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import "../admin-bonus.css";
import AdminVoiceModels from "./AdminVoiceModels";
import {
  fetchAdminPayments,
  fetchAdminProof,
  fetchAdminSupport,
  fetchAdminContact,
  fetchDiagnostics,
  fetchAdminTraining,
  fetchOperations,
  fetchTrainingAsset,
  fetchWallet,
  grantBonusCredits,
  reviewPayment,
  reviewSupport,
  resolveContact,
  updateTrainingStatus,
  type OpsResponse,
  type PaymentRequest,
  type TrainingRequest,
  type TrainingStatus,
  type SupportRequest,
  type DiagnosticsResponse,
  type ContactMessage,
  type WalletResponse,
} from "../services/api";

type Props = { token: string };

export default function AdminConsole({ token }: Props) {
  const [ops, setOps] = useState<OpsResponse | null>(null);
  const [payments, setPayments] = useState<PaymentRequest[]>([]);
  const [training, setTraining] = useState<TrainingRequest[]>([]);
  const [support, setSupport] = useState<SupportRequest[]>([]);
  const [contacts,setContacts]=useState<ContactMessage[]>([]);
  const [diagnostics, setDiagnostics] = useState<DiagnosticsResponse|null>(null);
  const [wallet, setWallet] = useState<WalletResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [bonusEmail, setBonusEmail] = useState("");
  const [bonusAmount, setBonusAmount] = useState(1);
  const [bonusReason, setBonusReason] = useState("Giveaway bonus");
  const [bonusMessage, setBonusMessage] = useState("");
  async function load() {
    const [o, p, t, w, s, c] = await Promise.all([
      fetchOperations(token),
      fetchAdminPayments(token),
      fetchAdminTraining(token),
      fetchWallet(token),
      fetchAdminSupport(token),
      fetchAdminContact(token),
    ]);
    setOps(o);
    setPayments(p);
    setTraining(t);
    setWallet(w);
    setSupport(s);
    setContacts(c);
  }
  useEffect(() => {
    load().catch((e) =>
      setError(e instanceof Error ? e.message : "Unable to load admin console"),
    );
  }, [token]);
  async function proof(id: string) {
    setBusy(true);
    try {
      const { url } = await fetchAdminProof(token, id);
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to open proof");
    } finally {
      setBusy(false);
    }
  }
  async function decide(id: string, approve: boolean) {
    const note =
      window.prompt(
        approve ? "Optional approval note" : "Reason for rejection",
      ) ?? "";
    if (!approve && !note.trim()) return;
    setBusy(true);
    try {
      await reviewPayment(token, id, approve, note);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to review payment");
    } finally {
      setBusy(false);
    }
  }
  async function asset(id: string, kind: "dataset" | "consent") {
    setBusy(true);
    try {
      const { url } = await fetchTrainingAsset(token, id, kind);
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to open file");
    } finally {
      setBusy(false);
    }
  }
  async function advanceTraining(row: TrainingRequest, status: TrainingStatus) {
    const note = window.prompt(
      status === "rejected" ? "Rejection reason (credit will be refunded):" : "Optional admin note:",
    ) ?? "";
    if (status === "rejected" && !note.trim()) return;
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
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to update training request");
    } finally {
      setBusy(false);
    }
  }
  async function grantBonus() {
    setError("");
    setBonusMessage("");
    setBusy(true);
    try {
      const result = await grantBonusCredits(token, bonusEmail, bonusAmount, bonusReason);
      setBonusMessage(
        `${result.granted} bonus song credit(s) added to ${result.email}. New bonus balance: ${result.bonus_balance}.`,
      );
      setBonusEmail("");
      setBonusAmount(1);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to grant bonus credits");
    } finally {
      setBusy(false);
    }
  }
  async function closeSupport(item:SupportRequest,status:"in_review"|"resolved"|"closed") {const note=window.prompt(status==="in_review"?"Optional review note:":"Reply or resolution note:",item.admin_note||"")??"";if(status==="resolved"&&!note.trim())return;setBusy(true);setError("");try{await reviewSupport(token,item.id,status,note);await load();}catch(e){setError(e instanceof Error?e.message:"Unable to update support request");}finally{setBusy(false);}}
  async function closeContact(item:ContactMessage){const note=window.prompt("Optional internal resolution note:",item.admin_note||"")??"";setBusy(true);setError("");try{await resolveContact(token,item.id,note);await load();}catch(e){setError(e instanceof Error?e.message:"Unable to resolve contact message");}finally{setBusy(false);}}
  async function runDiagnostics(){setBusy(true);setError("");try{setDiagnostics(await fetchDiagnostics(token));}catch(e){setError(e instanceof Error?e.message:"Unable to run production checks");}finally{setBusy(false);}}
  if (!ops || !wallet)
    return (
      <div className="empty-state admin-loading">
        <LoaderCircle className="spin" /> Loading admin console…
      </div>
    );
  const pending = payments.filter((item) => item.status === "pending");
  const activeTraining = training.filter(
    (item) => !["ready", "rejected"].includes(item.status),
  );
  return (
    <div className="admin-console">
      {error && <div className="notice error">{error}</div>}
      <div className="admin-banner">
        <span>
          <Shield size={22} />
        </span>
        <div>
          <small>PRIVATE ADMIN AREA</small>
          <h2>System control centre</h2>
          <p>Payments, voice requests and platform health in one place.</p>
        </div>
        <b>{ops.environment}</b>
      </div>
      <div className="admin-metrics">
        <article>
          <Activity />
          <div>
            <span>Active songs</span>
            <strong>{ops.jobs.active}</strong>
          </div>
        </article>
        <article>
          <HeartPulse />
          <div>
            <span>Failed · 24h</span>
            <strong>{ops.jobs.failed_24h}</strong>
          </div>
        </article>
        <article>
          <CircleDollarSign />
          <div>
            <span>Payments waiting</span>
            <strong>{ops.queues.pending_payments}</strong>
          </div>
        </article>
        <article>
          <MicVocal />
          <div>
            <span>Voice requests</span>
            <strong>{ops.queues.active_training}</strong>
          </div>
        </article>
      </div>
      <section className="admin-section diagnostics-panel"><div className="admin-section-head"><div><small>PRODUCTION READINESS</small><h3>Live system checks</h3></div><button className="diagnostic-button" onClick={runDiagnostics} disabled={busy}>{busy?<LoaderCircle className="spin"/>:<HeartPulse/>} Run checks</button></div>{!diagnostics?<p className="bonus-help">Checks database access, private artifact storage, worker configuration and the production frontend origin.</p>:<div className="diagnostic-grid">{Object.entries(diagnostics.checks).map(([name,result])=><article className={result.ok?"passed":"attention"} key={name}><span>{result.ok?<Check/>:<X/>}</span><div><strong>{name.replaceAll("_"," ")}</strong><small>{result.detail}</small></div></article>)}</div>}</section>
      <div className="admin-columns">
        <section className="admin-section">
          <div className="admin-section-head">
            <div>
              <small>PAYMENTS</small>
              <h3>Waiting for review</h3>
            </div>
            <span>{pending.length}</span>
          </div>
          {pending.length === 0 ? (
            <p className="admin-empty">
              <Check /> Everything is clear.
            </p>
          ) : (
            pending.map((item) => (
              <article className="review-item" key={item.id}>
                <div>
                  <strong>{item.sender_name}</strong>
                  <p>
                    PKR {item.amount_pkr.toLocaleString()} · {item.method} ·{" "}
                    {item.requested_credits} {item.product_type === "voice_training" ? "training" : "song"} credit(s)
                  </p>
                  <small>Transaction: {item.transaction_reference}</small>
                </div>
                <div className="review-actions">
                  <button onClick={() => proof(item.id)} disabled={busy}>
                    <ExternalLink /> Proof
                  </button>
                  <button
                    className="approve"
                    onClick={() => decide(item.id, true)}
                    disabled={busy}
                  >
                    <Check /> Approve
                  </button>
                  <button
                    className="reject"
                    onClick={() => decide(item.id, false)}
                    disabled={busy}
                  >
                    <X /> Reject
                  </button>
                </div>
              </article>
            ))
          )}
        </section>
        <section className="admin-section">
          <div className="admin-section-head">
            <div>
              <small>VOICE TRAINING</small>
              <h3>Active requests</h3>
            </div>
            <span>{activeTraining.length}</span>
          </div>
          {activeTraining.length === 0 ? (
            <p className="admin-empty">
              <Check /> No voice request waiting.
            </p>
          ) : (
            activeTraining.map((item) => (
              <article className="review-item" key={item.id}>
                <div>
                  <strong>{item.voice_name}</strong>
                  <p>
                    {item.language} · {item.rights_basis.replace("_", " ")}
                  </p>
                  <small>Status: {item.status.replace("_", " ")}</small>
                </div>
                <div className="review-actions">
                  <button
                    onClick={() => asset(item.id, "dataset")}
                    disabled={busy}
                  >
                    <ExternalLink /> Recordings
                  </button>
                  {item.consent_proof_path && (
                    <button
                      onClick={() => asset(item.id, "consent")}
                      disabled={busy}
                    >
                      <Shield /> Consent
                    </button>
                  )}
                  {item.status === "submitted" && (
                    <button className="approve" onClick={() => advanceTraining(item, "approved")} disabled={busy}>
                      <Check /> Approve
                    </button>
                  )}
                  {item.status === "approved" && (
                    <button className="approve" onClick={() => advanceTraining(item, "training")} disabled={busy}>
                      <MicVocal /> Start training
                    </button>
                  )}
                  {item.status === "training" && (
                    <button className="approve" onClick={() => advanceTraining(item, "model_validation")} disabled={busy}>
                      <Shield /> Model ready
                    </button>
                  )}
                  {item.status === "model_validation" && (
                    <button className="approve" onClick={() => advanceTraining(item, "ready")} disabled={busy}>
                      <Shield /> Validate & publish
                    </button>
                  )}
                  <button className="reject" onClick={() => advanceTraining(item, "rejected")} disabled={busy}>
                    <X /> Reject
                  </button>
                </div>
              </article>
            ))
          )}
        </section>
      </div>
      <section className="admin-section support-admin">
        <div className="admin-section-head"><div><small>SUPPORT</small><h3>Open user requests</h3></div><span>{support.length}</span></div>
        {support.length===0?<p className="admin-empty"><Check/> No support request waiting.</p>:support.map(item=><article className="review-item" key={item.id}><div><strong>{item.subject}</strong><p>{item.profiles?.display_name||"User"} · {item.category.replace("_"," ")} · {new Date(item.created_at).toLocaleString()}</p><small>{item.message}</small>{item.admin_note&&<small>Current note: {item.admin_note}</small>}</div><div className="review-actions">{item.status==="open"&&<button onClick={()=>closeSupport(item,"in_review")} disabled={busy}><ExternalLink/> Start review</button>}<button className="approve" onClick={()=>closeSupport(item,"resolved")} disabled={busy}><Check/> Resolve</button><button className="reject" onClick={()=>closeSupport(item,"closed")} disabled={busy}><X/> Close</button></div></article>)}
      </section>
      <section className="admin-section support-admin"><div className="admin-section-head"><div><small>PUBLIC CONTACT</small><h3>Website messages</h3></div><span>{contacts.length}</span></div>{contacts.length===0?<p className="admin-empty"><Check/> No contact message waiting.</p>:contacts.map(item=><article className="review-item" key={item.id}><div><strong>{item.subject}</strong><p>{item.name} · <a href={`mailto:${item.email}`}>{item.email}</a> · {new Date(item.created_at).toLocaleString()}</p><small>{item.message}</small></div><div className="review-actions"><a className="admin-mail" href={`mailto:${item.email}?subject=${encodeURIComponent(`Re: ${item.subject}`)}`}><ExternalLink/> Reply by email</a><button className="approve" onClick={()=>closeContact(item)} disabled={busy}><Check/> Mark resolved</button></div></article>)}</section>
      <AdminVoiceModels token={token}/>
      <section className="admin-section bonus-panel">
        <div className="admin-section-head">
          <div>
            <small>BONUS & GIVEAWAY</small>
            <h3>Grant free song credits</h3>
          </div>
          <span><Gift /></span>
        </div>
        <p className="bonus-help">
          These credits appear only in the user's Home available-credit summary.
          They remain separate from purchased credits.
        </p>
        <div className="bonus-form">
          <label>User email<input type="email" value={bonusEmail} onChange={(event) => setBonusEmail(event.target.value)} placeholder="user@example.com" /></label>
          <label>Song credits<input type="number" min="1" max="100" value={bonusAmount} onChange={(event) => setBonusAmount(Number(event.target.value))} /></label>
          <label>Reason<input value={bonusReason} onChange={(event) => setBonusReason(event.target.value)} maxLength={120} /></label>
          <button className="grant-button" disabled={busy || !bonusEmail.trim() || bonusAmount < 1 || !bonusReason.trim()} onClick={grantBonus}>
            {busy ? <LoaderCircle className="spin" /> : <Gift />} Grant bonus
          </button>
        </div>
        {bonusMessage && <div className="notice success">{bonusMessage}</div>}
      </section>
      <section className="admin-section settings-panel">
        <div>
          <small>LIVE SETTINGS</small>
          <h3>Payments & usage</h3>
          <p>
            Server-managed values. Change them through the Modal production
            secret.
          </p>
        </div>
        <div className="settings-grid">
          <article>
            <span>Song price</span>
            <strong>PKR {wallet.pricing.song.pkr}</strong>
          </article>
          <article>
            <span>HBL</span>
            <strong>
              {wallet.payment_accounts.easypaisa.number || "Not configured"}
            </strong>
          </article>
          <article>
            <span>NayaPay</span>
            <strong>
              {wallet.payment_accounts.jazzcash.number || "Not configured"}
            </strong>
          </article>
          <article>
            <span>Estimated GPU cost</span>
            <strong>
              ${ops.estimated_gpu_cost_usd_per_song.toFixed(2)} / song
            </strong>
          </article>
        </div>
      </section>
    </div>
  );
}
