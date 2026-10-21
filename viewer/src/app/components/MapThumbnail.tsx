"use client";
import {useEffect,useRef,useState} from 'react';
import type {LibraryGame} from './ReplayLibrary';
import {TERRAIN_MINIMAP_COLORS} from '@/lib/terrainMappings';
interface Preview {preview_version:number;match_id:string;dimension:number;sample_step:number;grid_size:number;terrain_ids:number[];starts:Array<{player_id:number;color_id:number|null;x:number;y:number}>;source:{kind:string;parser_header_sha256:string;adapter_sha256:string};}
const cache=new Map<string,Preview>();
const colors=['#315df2','#ed4444','#49b853','#f3d552','#4fd3d7','#d76ddc','#68686e','#ed933b'];
const hex=(s:unknown)=>typeof s==='string'&&/^[a-f0-9]{64}$/.test(s);
export function usableMapPreview(p:Preview,id:string):boolean {
 return !!p&&p.preview_version===1&&p.match_id===id&&hex(id)&&Number.isInteger(p.dimension)&&p.dimension>0&&p.dimension<=480&&Number.isInteger(p.sample_step)&&p.sample_step===Math.max(1,Math.ceil(p.dimension/96))&&p.grid_size===Math.ceil(p.dimension/p.sample_step)&&Array.isArray(p.terrain_ids)&&p.terrain_ids.length===p.grid_size**2&&p.terrain_ids.every(v=>Number.isInteger(v))&&Array.isArray(p.starts)&&p.starts.length<=8&&p.starts.every(s=>!!s&&Number.isInteger(s.player_id)&&Number.isFinite(s.x)&&Number.isFinite(s.y)&&s.x>=0&&s.y>=0&&s.x<p.dimension&&s.y<p.dimension&&(s.color_id===null||Number.isInteger(s.color_id)&&s.color_id>=0&&s.color_id<8))&&p.source?.kind==='recorded_header_snapshot'&&hex(p.source.parser_header_sha256)&&hex(p.source.adapter_sha256);
}
export function MapThumbnail({game,large=false}:{game:LibraryGame;large?:boolean}){
 const host=useRef<HTMLSpanElement>(null),canvas=useRef<HTMLCanvasElement>(null),[visible,setVisible]=useState(false),[data,setData]=useState<Preview|null>(null),[failed,setFailed]=useState(false);
 const id=game.match_id,key=`${game.game_id}:${id}`,ready=game.status==='ready'&&game.map_preview_available===true&&!!id;
 useEffect(()=>{const el=host.current;if(!el||!ready)return;const observer=new IntersectionObserver(entries=>{if(entries.some(e=>e.isIntersecting)){setVisible(true);observer.disconnect();}},{rootMargin:'120px'});observer.observe(el);return()=>observer.disconnect();},[key,ready]);
 useEffect(()=>{
  setData(null);setFailed(false);if(!visible||!ready||!id)return;
  const cached=cache.get(key);if(cached){cache.delete(key);cache.set(key,cached);setData(cached);return;}
  const controller=new AbortController();let current=true;
  const api=process.env.NEXT_PUBLIC_COACH_API_URL||'http://127.0.0.1:8765';
  void fetch(`${api}/api/map-preview?${new URLSearchParams({game_id:game.game_id,match_id:id})}`,{signal:controller.signal}).then(async r=>{if(!r.ok)throw new Error('Preview unavailable');const p=await r.json();if(!usableMapPreview(p,id))throw new Error('Invalid map identity');if(!current)return;cache.set(key,p);while(cache.size>128)cache.delete(cache.keys().next().value!);setData(p);}).catch(()=>{if(current)setFailed(true);});
  return()=>{current=false;controller.abort();};
 },[visible,ready,key,id,game.game_id]);
 useEffect(()=>{
  const ctx=canvas.current?.getContext('2d');if(!ctx||!data||data.match_id!==id)return;
  ctx.resetTransform();ctx.clearRect(0,0,240,144);ctx.setTransform(1.08,.54,-1.08,.54,120,12);
  ctx.fillStyle='#57452b';ctx.fillRect(0,0,100,100);
  const unit=100/data.dimension;
  for(let y=0;y<data.grid_size;y++)for(let x=0;x<data.grid_size;x++){
   const sx=x*data.sample_step,sy=y*data.sample_step;
   ctx.fillStyle=TERRAIN_MINIMAP_COLORS[data.terrain_ids[y*data.grid_size+x]]??'#85828c';
   ctx.fillRect(sx*unit,sy*unit,Math.min(data.sample_step,data.dimension-sx)*unit+.02,Math.min(data.sample_step,data.dimension-sy)*unit+.02);
  }
  for(const start of data.starts){const x=start.x*unit,y=start.y*unit;ctx.fillStyle='#fff9dd';ctx.fillRect(x-1.8,y-1.8,3.6,3.6);ctx.fillStyle=start.color_id===null?'#54545b':colors[start.color_id];ctx.fillRect(x-1.15,y-1.15,2.3,2.3);}
 },[data,id]);
 const boundData=data?.match_id===id?data:null;
 const label=boundData?`${game.map??'Map'} · recorded-header terrain preview; stylized, not player vision or live positions`:failed?'Map preview unavailable':ready?'Map preview loading when visible':'Map preview not available yet';
 return <span ref={host} data-map-thumbnail data-map-state={boundData?'ready':failed?'unavailable':'pending'} className={`map-thumbnail relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-lg border border-[color:var(--border-subtle)] ${large?'h-[66px] w-[100px]':'h-12 w-[62px]'}`} style={{background:'linear-gradient(145deg,rgba(162,126,70,.18),rgba(79,116,112,.08))'}} title={label}>
  {boundData?<canvas ref={canvas} width={240} height={144} role="img" aria-label={label} className="h-full w-full object-contain"/>:<svg role="img" aria-label={label} width="44" height="32" viewBox="0 0 44 32" fill="none"><path d="M3 8 15 3 29 8 41 3v21l-12 5-14-5-12 5Z" stroke="currentColor" opacity=".4"/><path d="M15 3v21M29 8v21M8 14l4-2m7 3 5 2m9-4 4-2" stroke="currentColor" opacity=".3"/></svg>}
 </span>;
}
