import { Download, FileWarning, LoaderCircle, Music2, PlayCircle, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { deleteLibrarySong, fetchFinalArtifacts, fetchLibrarySongs, type LibrarySong } from '../services/api';
import { downloadFile } from '../lib/download';

type Props={token:string};

export default function MySongs({token}:Props){
  const [songs,setSongs]=useState<LibrarySong[]>([]);const [filter,setFilter]=useState<'all'|'completed'|'failed'>('all');
  const [loading,setLoading]=useState(true);const [busy,setBusy]=useState<string|null>(null);const [error,setError]=useState('');const [audio,setAudio]=useState<Record<string,string>>({});
  useEffect(()=>{fetchLibrarySongs(token).then(setSongs).catch(e=>setError(e instanceof Error?e.message:'Unable to load songs')).finally(()=>setLoading(false));},[token]);
  async function authorize(song:LibrarySong,download=false){setBusy(song.id);setError('');try{const files=await fetchFinalArtifacts(token,song.id);if(download)await downloadFile(files.mp3_url,song.title);else setAudio(current=>({...current,[song.id]:files.mp3_url}));}catch(e){setError(e instanceof Error?e.message:'Unable to authorize song');}finally{setBusy(null);}}
  async function remove(song:LibrarySong){if(!confirm(`Permanently delete “${song.title}” and its audio files?`))return;setBusy(song.id);setError('');try{await deleteLibrarySong(token,song.id);setSongs(current=>current.filter(item=>item.id!==song.id));}catch(e){setError(e instanceof Error?e.message:'Unable to delete song');}finally{setBusy(null);}}
  const shown=songs.filter(song=>filter==='all'||song.status===filter);
  return <div className="library-stack"><div className="library-filters">{(['all','completed','failed'] as const).map(item=><button className={filter===item?'active':''} onClick={()=>setFilter(item)} key={item}>{item[0].toUpperCase()+item.slice(1)}</button>)}</div>
    {error&&<div className="notice error">{error}</div>}{loading?<div className="empty-state"><LoaderCircle className="spin"/>Loading songs…</div>:shown.length===0?<div className="empty-state"><Music2/>No {filter==='all'?'':filter} songs yet.</div>:<div className="song-list">{shown.map(song=><article className="song-card" key={song.id}><span className={`song-icon ${song.status}`}>{song.status==='completed'?<Music2/>:<FileWarning/>}</span><div className="song-main"><h3>{song.title}</h3><p>{song.source_type||'Source'} · {song.duration_seconds?`${song.duration_seconds.toFixed(1)} sec`:'—'} · {song.model_slug}</p>{audio[song.id]&&<audio controls preload="metadata" src={audio[song.id]}/>} {song.error_message&&<small>{song.error_message}</small>}</div><span className={`status ${song.status==='completed'?'status-online':'status-offline'}`}>{song.status}</span><div className="song-actions">{song.status==='completed'&&<><button onClick={()=>authorize(song)} disabled={busy===song.id}>{busy===song.id?<LoaderCircle className="spin" size={15}/>:<PlayCircle size={15}/>} Preview</button><button onClick={()=>authorize(song,true)} disabled={busy===song.id}><Download size={15}/> MP3</button></>}<button className="danger-quiet" onClick={()=>remove(song)} disabled={busy===song.id}><Trash2 size={15}/> Delete</button></div></article>)}</div>}
  </div>;
}
