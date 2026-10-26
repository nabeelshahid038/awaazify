import { ArrowLeft, Copyright, FileText, ShieldCheck } from "lucide-react";

export type LegalKind="privacy"|"terms"|"copyright"|"refund";
const content:Record<LegalKind,{title:string;intro:string;sections:{h:string;p:string}[]}>= {
  privacy:{title:"Privacy Policy",intro:"How Awaazify handles your account, audio and payment information.",sections:[
    {h:"Information we use",p:"We process your sign-in profile, uploaded audio, YouTube link details, generated songs, credit activity, payment proof and—only when requested—voice-training data and consent proof."},
    {h:"Why we use it",p:"We use this information to operate the studio, create your requested audio, verify payments, secure the service, provide support and prevent abuse."},
    {h:"Storage and processors",p:"Account data and private files are stored with our infrastructure providers, including Supabase and Modal. Signed links are temporary. We do not sell your personal information."},
    {h:"Your controls",p:"You can delete individual completed or failed songs from My Songs. For account or privacy assistance, submit a request through Settings → Help & Support. Infrastructure backups may expire on the provider’s normal backup cycle."},
    {h:"Contact",p:"For privacy, access or deletion questions, contact the Awaazify support address shown on the Support page. We may update this policy when the product or legal requirements change."},
  ]},
  terms:{title:"Terms of Use",intro:"Simple rules for safely using Awaazify.",sections:[
    {h:"Your account",p:"You are responsible for activity under your account and for keeping access secure. You must provide truthful payment and consent information."},
    {h:"Rights and permission",p:"Only upload or link audio you own, are licensed to use, or otherwise have lawful permission to process. A short clip is not automatically free to use. You are responsible for how you publish or monetize output."},
    {h:"Voice safety",p:"Do not clone or imitate another person without clear authorization. Do not use Awaazify for fraud, deception, harassment, impersonation, unlawful content or to mislead people about a real person’s speech or endorsement."},
    {h:"Credits and service",p:"Credits pay for processing attempts as described in the product. Failed jobs are handled by the displayed retry/refund rules. Processing time and availability can vary, and the service is provided without a guarantee of uninterrupted operation."},
    {h:"Enforcement",p:"We may reject training data, remove content, suspend access or preserve limited evidence when reasonably necessary for safety, abuse prevention, payment disputes or legal compliance."},
  ]},
  copyright:{title:"Copyright & Voice Rights",intro:"Awaazify is for permitted creative use—not unauthorized copying or impersonation.",sections:[
    {h:"Before creating",p:"Confirm that you have the necessary rights or permission for the music, recording and voice. A YouTube URL does not give you ownership or a license."},
    {h:"Custom voices",p:"Self-voice training requires confirmation that it is your voice. An authorized voice requires consent evidence. Awaazify may reject unclear, misleading or unverifiable requests."},
    {h:"Reporting",p:"If you believe Awaazify content infringes your copyright, voice, likeness or other rights, send the work or person involved, the relevant Awaazify details, your contact information and a clear explanation to support."},
    {h:"Response",p:"We may restrict access while reviewing a good-faith report and may request identity, ownership or authorization evidence. False reports and repeated violations may lead to account action."},
  ]},
  refund:{title:"Credit & Refund Policy",intro:"How Awaazify handles credits, failed processing and payment corrections.",sections:[
    {h:"Song credits",p:"One song credit covers one generation request within the supported duration. If our processing system fails before completing the song, the automated retry/refund rules shown in the app apply."},
    {h:"Training credits",p:"A custom voice training credit is reserved when a valid request is submitted. If Awaazify rejects the request during consent or dataset review, that training credit is returned automatically."},
    {h:"Completed work",p:"Credits normally are not returned after a song is successfully completed or a custom voice model is successfully delivered, because cloud processing costs have already been incurred."},
    {h:"Payment mistakes",p:"For a duplicate payment, incorrect credit grant or unauthorized transaction concern, submit a Payment or credits support request with the transaction reference. Do not post sensitive payment details publicly."},
    {h:"Review",p:"Approved cash refunds, where applicable, are handled manually to the verified original payment source. Processing time may depend on HBL, NayaPay or the relevant payment provider."},
  ]},
};
export default function LegalPage({kind,onBack}:{kind:LegalKind;onBack:()=>void}){const page=content[kind];return <main className="legal-shell"><button className="legal-back" onClick={onBack}><ArrowLeft/> Back to Awaazify</button><div className="legal-title"><span>{kind==="privacy"?<ShieldCheck/>:kind==="copyright"?<Copyright/>:<FileText/>}</span><div><small>LAST UPDATED: 20 OCTOBER 2026</small><h1>{page.title}</h1><p>{page.intro}</p></div></div><div className="legal-content">{page.sections.map((s,i)=><section key={s.h}><b>{String(i+1).padStart(2,"0")}</b><div><h2>{s.h}</h2><p>{s.p}</p></div></section>)}</div><p className="legal-note">This plain-language policy is an operational template and should be reviewed by a qualified lawyer before large-scale commercial launch.</p></main>}

