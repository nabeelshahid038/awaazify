import {
  CheckCircle2,
  Clock3,
  ExternalLink,
  Globe2,
  LoaderCircle,
  ReceiptText,
  Upload,
  WalletCards,
  XCircle,
} from "lucide-react";
import { useEffect, useState } from "react";
import { supabase } from "../lib/supabase";
import {
  fetchAdminPayments,
  fetchAdminProof,
  fetchOperations,
  fetchWallet,
  reviewPayment,
  submitPaymentRequest,
  type OpsResponse,
  type CreditProduct,
  type PaymentMethod,
  type PaymentRequest,
  type WalletResponse,
} from "../services/api";

type Props = {
  token: string;
  userId: string;
  onBalance: (credits: number) => void;
  showAdmin?: boolean;
};
const ALLOWED = new Set([
  "image/jpeg",
  "image/png",
  "image/webp",
  "application/pdf",
]);

export default function WalletPanel({
  token,
  userId,
  onBalance,
  showAdmin = false,
}: Props) {
  const [wallet, setWallet] = useState<WalletResponse | null>(null);
  const [adminRows, setAdminRows] = useState<PaymentRequest[]>([]);
  const [ops, setOps] = useState<OpsResponse | null>(null);
  const [method, setMethod] = useState<PaymentMethod>("easypaisa");
  const [product, setProduct] = useState<CreditProduct>("song");
  const [market, setMarket] = useState<"pakistan" | "global">("pakistan");
  const [amount, setAmount] = useState(50);
  const [sender, setSender] = useState("");
  const [phone, setPhone] = useState("");
  const [reference, setReference] = useState("");
  const [proof, setProof] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  async function load() {
    const data = await fetchWallet(token);
    setWallet({ ...data, is_admin: data.is_admin && showAdmin });
    onBalance(data.song_credits);
    if (data.is_admin && showAdmin) {
      const [payments, operations] = await Promise.all([
        fetchAdminPayments(token),
        fetchOperations(token),
      ]);
      setAdminRows(payments);
      setOps(operations);
    }
  }
  useEffect(() => {
    load().catch((e) =>
      setError(e instanceof Error ? e.message : "Unable to load wallet"),
    );
  }, [token]);
  function chooseProof(file: File | null) {
    setError("");
    if (!file) {
      setProof(null);
      return;
    }
    if (!ALLOWED.has(file.type)) {
      setError("Use a JPG, PNG, WEBP or PDF proof.");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setError("Payment proof must be 5 MB or smaller.");
      return;
    }
    setProof(file);
  }
  async function submit() {
    setError("");
    setMessage("");
    if (!wallet || !supabase || !proof) return;
    setBusy(true);
    let path = "";
    try {
      path = `${userId}/${crypto.randomUUID()}.${
        proof.name
          .split(".")
          .pop()
          ?.toLowerCase()
          .replace(/[^a-z0-9]/g, "") || "jpg"
      }`;
      const uploaded = await supabase.storage
        .from("payment-proofs")
        .upload(path, proof, { contentType: proof.type, upsert: false });
      if (uploaded.error) throw new Error(uploaded.error.message);
      try {
        await submitPaymentRequest(token, {
          method,
          product_type: product,
          amount_pkr: amount,
          sender_name: sender.trim(),
          sender_phone: phone.trim(),
          transaction_reference: reference.trim(),
          proof_path: path,
        });
      } catch (e) {
        await supabase.storage.from("payment-proofs").remove([path]);
        throw e;
      }
      setMessage(
        "Payment proof submitted. Credits will appear after admin verification.",
      );
      setSender("");
      setPhone("");
      setReference("");
      setProof(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to submit payment");
    } finally {
      setBusy(false);
    }
  }
  async function inspect(id: string) {
    setBusy(true);
    setError("");
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
        approve ? "Optional approval note:" : "Rejection reason:",
      ) ?? "";
    if (!approve && !note.trim()) return;
    setBusy(true);
    setError("");
    try {
      await reviewPayment(token, id, approve, note);
      await load();
      setMessage(`Payment ${approve ? "approved" : "rejected"}.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to review payment");
    } finally {
      setBusy(false);
    }
  }
  if (!wallet)
    return (
      <div className="empty-state">
        <LoaderCircle className="spin" />
        Loading wallet…
      </div>
    );
  const account = wallet.payment_accounts[method];
  const selectedPack = wallet.pricing[product].packs.find(
    (pack) => pack.pkr === amount,
  );
  const credits = selectedPack?.credits || 0;
  const usdPrice = (creditCount: number) =>
    product === "voice_training"
      ? 1
      : creditCount === 10
        ? 4
        : creditCount === 5
          ? 2.25
          : 0.5;
  return (
    <div className="wallet-stack">
      {error && <div className="notice error">{error}</div>}
      {message && (
        <div className="notice success">
          <CheckCircle2 size={16} />
          {message}
        </div>
      )}
      <div className="wallet-balances">
        <div className="wallet-summary">
          <span>
            <WalletCards size={22} />
          </span>
          <div>
            <small>SONG CREDITS</small>
            <strong>{wallet.song_credits}</strong>
            <p>From PKR 50 / ${wallet.pricing.song.usd.toFixed(2)} per cover</p>
          </div>
        </div>
        <div className="wallet-summary training-balance">
          <span>
            <WalletCards size={22} />
          </span>
          <div>
            <small>VOICE TRAINING CREDITS</small>
            <strong>{wallet.training_credits}</strong>
            <p>
              PKR 150 / ${wallet.pricing.voice_training.usd.toFixed(2)} per
              private voice
            </p>
          </div>
        </div>
      </div>
      <section className="payment-card">
        <div>
          <span className="overline">CHOOSE YOUR REGION</span>
          <h2>Simple pay-as-you-go pricing.</h2>
          <p>No subscription. Buy credits only when you need them.</p>
        </div>
        <div className="market-tabs">
          <button
            className={market === "pakistan" ? "active" : ""}
            onClick={() => setMarket("pakistan")}
          >
            Pakistan · PKR
          </button>
          <button
            className={market === "global" ? "active" : ""}
            onClick={() => setMarket("global")}
          >
            <Globe2 size={16} /> Global · USD
          </button>
        </div>
        <div className="product-tabs">
          <button
            className={product === "song" ? "active" : ""}
            onClick={() => {
              setProduct("song");
              setAmount(50);
            }}
          >
            Song covers
          </button>
          <button
            className={product === "voice_training" ? "active" : ""}
            onClick={() => {
              setProduct("voice_training");
              setAmount(150);
            }}
          >
            Custom voice
          </button>
        </div>
        <div className="pricing-packs">
          {wallet.pricing[product].packs.map((pack) => (
            <button
              key={pack.pkr}
              className={
                market === "pakistan" && amount === pack.pkr ? "active" : ""
              }
              onClick={() => market === "pakistan" && setAmount(pack.pkr)}
            >
              <strong>{pack.credits}</strong>
              <span>
                {product === "song"
                  ? `song${pack.credits > 1 ? "s" : ""}`
                  : "voice training"}
              </span>
              <b>
                {market === "pakistan"
                  ? `PKR ${pack.pkr}`
                  : `$${usdPrice(pack.credits).toFixed(2)}`}
              </b>
              {market === "pakistan" &&
                product === "song" &&
                pack.credits > 1 && (
                  <small>Save PKR {pack.credits * 50 - pack.pkr}</small>
                )}
            </button>
          ))}
        </div>
        {market === "pakistan" ? (
          <>
            <div className="method-tabs">
              {(["easypaisa", "jazzcash"] as const).map((item) => (
                <button
                  key={item}
                  className={method === item ? "active" : ""}
                  onClick={() => setMethod(item)}
                >
                  {item === "easypaisa" ? "HBL" : "NayaPay"}
                </button>
              ))}
            </div>
            {account.number ? (
              <div className="account-box">
                <span>Send to</span>
                <strong>{account.number}</strong>
                <small>{account.title}</small>
              </div>
            ) : (
              <div className="notice error">
                This payment account is not configured yet. Admin must add it to
                backend `.env` before accepting payments.
              </div>
            )}
            <div className="payment-grid">
              <label>
                Selected package
                <input
                  value={`PKR ${amount} · ${credits} credit${credits === 1 ? "" : "s"}`}
                  readOnly
                />
                <small>Choose a package above</small>
              </label>
              <label>
                Sender name
                <input
                  value={sender}
                  maxLength={100}
                  onChange={(e) => setSender(e.target.value)}
                  placeholder="Account holder name"
                />
              </label>
              <label>
                Sender phone
                <input
                  value={phone}
                  maxLength={11}
                  onChange={(e) => setPhone(e.target.value.replace(/\D/g, ""))}
                  placeholder="03XXXXXXXXX"
                />
              </label>
              <label>
                Transaction ID/reference
                <input
                  value={reference}
                  maxLength={100}
                  onChange={(e) => setReference(e.target.value)}
                  placeholder="Unique transaction reference"
                />
              </label>
            </div>
            <label className="proof-drop">
              <Upload size={22} />
              <strong>
                {proof ? proof.name : "Upload payment screenshot or receipt"}
              </strong>
              <span>JPG, PNG, WEBP or PDF · maximum 5 MB</span>
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp,application/pdf"
                onChange={(e) => chooseProof(e.target.files?.[0] || null)}
              />
            </label>
            <button
              className="primary-action"
              disabled={
                busy ||
                !account.number ||
                !proof ||
                !sender.trim() ||
                phone.length !== 11 ||
                reference.trim().length < 4 ||
                credits < 1
              }
              onClick={submit}
            >
              {busy ? (
                <LoaderCircle className="spin" size={16} />
              ) : (
                <ReceiptText size={16} />
              )}{" "}
              Submit for verification
            </button>
          </>
        ) : (
          <div className="global-coming-soon">
            <span>
              <Globe2 />
            </span>
            <div>
              <small>INTERNATIONAL CHECKOUT</small>
              <h3>Global payments coming soon.</h3>
              <p>
                USD pricing is ready. We’re setting up a secure international
                payment option; no payment is collected yet.
              </p>
            </div>
            <b>COMING SOON</b>
          </div>
        )}
      </section>
      <section className="history-card">
        <span className="overline">TOP-UP HISTORY</span>
        {wallet.requests.length === 0 ? (
          <p className="empty-state">No top-up requests yet.</p>
        ) : (
          wallet.requests.map((row) => (
            <div className="history-row" key={row.id}>
              <span className={`request-icon ${row.status}`}>
                {row.status === "approved" ? (
                  <CheckCircle2 />
                ) : row.status === "rejected" ? (
                  <XCircle />
                ) : (
                  <Clock3 />
                )}
              </span>
              <div>
                <strong>
                  {row.method === "easypaisa" ? "HBL" : "NayaPay"} · PKR{" "}
                  {row.amount_pkr.toLocaleString()}
                </strong>
                <small>
                  {row.requested_credits}{" "}
                  {row.product_type === "voice_training"
                    ? "voice training"
                    : "song"}{" "}
                  credit(s) · Ref {row.transaction_reference}
                  {row.admin_note ? ` · ${row.admin_note}` : ""}
                </small>
              </div>
              <span
                className={`status ${row.status === "approved" ? "status-online" : row.status === "rejected" ? "status-offline" : ""}`}
              >
                {row.status}
              </span>
            </div>
          ))
        )}
      </section>
      {wallet.is_admin && (
        <section className="history-card admin-card">
          <span className="overline">ADMIN · PAYMENT REVIEW</span>
          {adminRows.filter((r) => r.status === "pending").length === 0 ? (
            <p className="empty-state">No pending requests.</p>
          ) : (
            adminRows
              .filter((r) => r.status === "pending")
              .map((row) => (
                <div className="admin-row" key={row.id}>
                  <div>
                    <strong>
                      {row.sender_name} · PKR {row.amount_pkr.toLocaleString()}
                    </strong>
                    <small>
                      {row.product_type === "voice_training"
                        ? "Voice training"
                        : "Song cover"}{" "}
                      · {row.method} · {row.sender_phone} · Ref{" "}
                      {row.transaction_reference} · {row.requested_credits}{" "}
                      credits
                    </small>
                  </div>
                  <div>
                    <button onClick={() => inspect(row.id)} disabled={busy}>
                      <ExternalLink size={14} /> Proof
                    </button>
                    <button
                      onClick={() => decide(row.id, true)}
                      disabled={busy}
                    >
                      <CheckCircle2 size={14} /> Approve
                    </button>
                    <button
                      className="danger"
                      onClick={() => decide(row.id, false)}
                      disabled={busy}
                    >
                      <XCircle size={14} /> Reject
                    </button>
                  </div>
                </div>
              ))
          )}
        </section>
      )}
      {wallet.is_admin && ops && (
        <section className="history-card ops-card">
          <span className="overline">ADMIN · OPERATIONS</span>
          <div className="ops-grid">
            <article>
              <small>ACTIVE JOBS</small>
              <strong>{ops.jobs.active}</strong>
            </article>
            <article>
              <small>FAILED · 24H</small>
              <strong>{ops.jobs.failed_24h}</strong>
            </article>
            <article>
              <small>PENDING PAYMENTS</small>
              <strong>{ops.queues.pending_payments}</strong>
            </article>
            <article>
              <small>TRAINING QUEUE</small>
              <strong>{ops.queues.active_training}</strong>
            </article>
            <article>
              <small>SECURITY EVENTS · 24H</small>
              <strong>{ops.security_events_24h}</strong>
            </article>
            <article>
              <small>EST. GPU COST</small>
              <strong>${ops.estimated_gpu_cost_usd_total.toFixed(2)}</strong>
            </article>
          </div>
          {ops.recent_failures.length > 0 && (
            <div className="ops-failures">
              <b>Recent failures</b>
              {ops.recent_failures.map((item) => (
                <small key={item.id}>
                  {item.error_code || "worker_error"} ·{" "}
                  {item.error_message || item.id}
                </small>
              ))}
            </div>
          )}
          <p className="ops-note">
            Environment: {ops.environment} · estimate $
            {ops.estimated_gpu_cost_usd_per_song.toFixed(2)}/completed song
          </p>
        </section>
      )}
    </div>
  );
}
