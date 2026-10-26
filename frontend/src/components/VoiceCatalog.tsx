import { CheckCircle2, ChevronLeft, ChevronRight, Headphones, Languages, Mic2, Play } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { fetchPublicVoices, fetchVoices, type VoiceModel } from "../services/api";

type Props={token?:string;selected?:string;refreshKey?:number;publicMode?:boolean;onSelect:(slug:string,name:string)=>void};

function VoiceCard({voice,selected,onSelect}:{voice:VoiceModel;selected:boolean;onSelect:()=>void}){
  return <article className={`market-voice-card ${selected?"selected":""}`}>
    <div className="voice-image">{voice.image_url?<img src={voice.image_url} alt=""/>:<span>{voice.display_name.slice(0,1).toUpperCase()}</span>}<b>{voice.category||"Featured"}</b></div>
    <div className="voice-card-copy"><small><Languages/> {voice.language||"Multilingual"}</small><h3>{voice.display_name}</h3><p>{voice.description||"A verified voice ready for your next cover."}</p></div>
    <div className="voice-demos">{[voice.demo_url_1,voice.demo_url_2].map((url,index)=>url?<audio controls preload="none" src={url} key={url}/>:<span className="demo-empty" key={index}><Headphones/> Demo {index+1} coming soon</span>)}</div>
    <button className="voice-select" onClick={onSelect}>{selected?<CheckCircle2/>:<Play/>}{selected?"Selected":"Use this voice"}</button>
  </article>;
}

export default function VoiceCatalog({token,selected,refreshKey=0,publicMode=false,onSelect}:Props){
  const [voices,setVoices]=useState<VoiceModel[]>([]),[error,setError]=useState(""),[loading,setLoading]=useState(true);
  const carousel=useRef<HTMLDivElement>(null);
  useEffect(()=>{setLoading(true);(publicMode?fetchPublicVoices():fetchVoices(token||"")).then(setVoices).catch(e=>setError(e instanceof Error?e.message:"Unable to load voices")).finally(()=>setLoading(false));},[token,refreshKey,publicMode]);
  const move=(direction:number)=>carousel.current?.scrollBy({left:direction*carousel.current.clientWidth*.82,behavior:"smooth"});
  const cards=voices.map(voice=><VoiceCard key={voice.slug} voice={voice} selected={selected===voice.slug} onSelect={()=>onSelect(voice.slug,voice.display_name)}/>);
  return <div className="catalog-stack">{error&&<div className="notice error">{error}</div>}{loading?<div className="empty-state"><Mic2/> Loading voices…</div>:voices.length===0?<div className="voice-empty"><span><Mic2/></span><div><h3>New voices are being prepared</h3><p>Only verified, usable models appear here. Check back soon or train your own private voice.</p></div></div>:publicMode?<div className="public-voice-carousel"><button className="carousel-arrow previous" onClick={()=>move(-1)} aria-label="Previous voices"><ChevronLeft/></button><div className="public-voice-track" ref={carousel}>{cards}</div><button className="carousel-arrow next" onClick={()=>move(1)} aria-label="More voices"><ChevronRight/></button></div>:<div className="voice-market-grid">{cards}</div>}</div>;
}
