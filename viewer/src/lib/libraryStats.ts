import type {LibraryGame} from '../app/components/ReplayLibrary';
import {canonicalTeam} from './teamIdentity';
export type Mode='1v1'|'teams'|'other';
export type Result='win'|'loss'|'unknown';
type Player=LibraryGame['players'][number];
export interface RecordRow {game:LibraryGame;own:Player;opponents:Player[];mode:Mode;result:Result;seconds:number|null;map:string;ownCiv:string;opponentCivs:string[]}
export interface Counts {played:number;wins:number;losses:number;unknown:number;known:number;rate:number|null}
export interface Group extends Counts {key:string}
export interface LibraryStats {records:RecordRow[];files:number;analyzedFiles:number;unavailableFiles:number;duplicateFiles:number;conflictingContents:number;invalidContents:number;absentIdentity:number;ambiguousIdentity:number}
export const civ=(p:Player)=>p.civilization||'Unknown civilization';
export function counts(records:RecordRow[]):Counts {const wins=records.filter(r=>r.result==='win').length,losses=records.filter(r=>r.result==='loss').length,known=wins+losses;return {played:records.length,wins,losses,unknown:records.length-known,known,rate:known?wins/known*100:null};}
export function groupRecords(records:RecordRow[],keys:(r:RecordRow)=>string[]):Group[]{
 const groups=new Map<string,RecordRow[]>();for(const r of records)for(const key of new Set(keys(r))){const list=groups.get(key)??[];list.push(r);groups.set(key,list);}
 return [...groups].map(([key,rows])=>({key,...counts(rows)})).sort((a,b)=>b.played-a.played||a.key.localeCompare(b.key));
}
function teams(players:Player[]):Map<number,string>|null {
 const ids=new Set(players.map(p=>p.id));if(ids.size!==players.length||players.some(p=>!Number.isInteger(p.id)))return null;
 for(const p of players){const t=p.team_id;
  if(Array.isArray(t)){if(!t.length||t.length>8||new Set(t).size!==t.length||!t.includes(p.id)||t.some(id=>!Number.isInteger(id)||!ids.has(id)))return null;}
  else if(typeof t!=='number'||!Number.isInteger(t)||t<1)return null;
 }
 const map=new Map(players.map(p=>[p.id,canonicalTeam(p)]));
 for(const p of players)if(Array.isArray(p.team_id)&&p.team_id.some(id=>map.get(id)!==map.get(p.id)))return null;
 return map;
}
function signature(g:LibraryGame){return JSON.stringify([g.map??null,g.duration_seconds??null,g.rated??null,g.game_type_id??null,[...g.players].sort((a,b)=>a.id-b.id).map(p=>[p.id,p.name,p.civilization??null,Array.isArray(p.team_id)?[...p.team_id].sort((a,b)=>a-b):p.team_id??null,p.won??null])]);}
/** Exact local display-name cohorts, not verified public-account identities or strategic evaluations. */
export function buildLibraryStats(games:LibraryGame[],profile:string):LibraryStats|null {
 if(!Array.isArray(games)||games.length>10000||games.some(g=>!g||typeof g.game_id!=='string')||typeof profile!=='string'||profile.length>256)return null;
 const result:LibraryStats={records:[],files:games.length,analyzedFiles:0,unavailableFiles:0,duplicateFiles:0,conflictingContents:0,invalidContents:0,absentIdentity:0,ambiguousIdentity:0},byContent=new Map<string,LibraryGame[]>();
 for(const g of games){
  if(g.status!=='ready'){result.unavailableFiles++;continue;}result.analyzedFiles++;
  if(!g.match_id||!/^[a-f0-9]{64}$/.test(g.match_id)||!Array.isArray(g.players)||g.players.length<1||g.players.length>8||new Set(g.players.map(p=>p?.id)).size!==g.players.length||['map','duration','played_at'].some(k=>{const v=g[k as keyof LibraryGame];return v!=null&&(typeof v!=='string'||v.length>512);})||g.players.some(p=>!p||typeof p.name!=='string'||!p.name||p.name.length>256||!Number.isInteger(p.id)||p.civilization!=null&&(typeof p.civilization!=='string'||p.civilization.length>256))){result.invalidContents++;continue;}
  const rows=byContent.get(g.match_id)??[];rows.push(g);byContent.set(g.match_id,rows);
 }
 for(const rows of byContent.values()){
  result.duplicateFiles+=rows.length-1;
  if(new Set(rows.map(signature)).size!==1){result.conflictingContents++;continue;}
  const g=rows[0],own=g.players.filter(p=>p.name===profile);
  if(!own.length){result.absentIdentity++;continue;}if(own.length!==1){result.ambiguousIdentity++;continue;}
  const team=teams(g.players),ownTeam=team?.get(own[0].id),opponents=team?g.players.filter(p=>team.get(p.id)!==ownTeam):[];
  const teamSizes=team?[...new Set(team.values())].map(k=>g.players.filter(p=>team.get(p.id)===k).length):[];
  const mode:Mode=team&&teamSizes.length===2&&g.players.length===2?'1v1':team&&teamSizes.length>=2&&teamSizes.some(n=>n>1)?'teams':'other';
  const winnerTeams=team?new Set(g.players.filter(p=>p.won===true).map(p=>team.get(p.id))):new Set();
  const winner=winnerTeams.size===1?[...winnerTeams][0]:null;
  const coherent=!!team&&!!winner&&teamSizes.length>=2&&g.players.every(p=>typeof p.won==='boolean'&&p.won===(team.get(p.id)===winner));
  const outcome:Result=coherent?(own[0].won?'win':'loss'):'unknown';
  result.records.push({game:g,own:own[0],opponents,mode,result:outcome,seconds:typeof g.duration_seconds==='number'&&Number.isFinite(g.duration_seconds)&&g.duration_seconds>=0?g.duration_seconds:null,map:g.map||'Unknown map',ownCiv:civ(own[0]),opponentCivs:[...new Set(opponents.map(civ))]});
 }
 result.records.sort((a,b)=>{const aDate=Date.parse(a.game.played_at??''),bDate=Date.parse(b.game.played_at??'');return (Number.isFinite(bDate)?bDate:0)-(Number.isFinite(aDate)?aDate:0)||a.game.game_id.localeCompare(b.game.game_id);});
 return result;
}
export interface Filters {mode:Mode|'all';map:string;ownCiv:string;opponentCiv:string;opponent:string;gameType:'all'|'rm'|'other'|'unknown';rated:'all'|'rated'|'unrated'|'unknown'}
export const INITIAL_FILTERS:Filters={mode:'1v1',map:'',ownCiv:'',opponentCiv:'',opponent:'',gameType:'all',rated:'all'};
export function filterRecords(records:RecordRow[],f:Filters){return records.filter(r=>(f.mode==='all'||r.mode===f.mode)&&(!f.map||r.map===f.map)&&(!f.ownCiv||r.ownCiv===f.ownCiv)&&(!f.opponentCiv||r.opponentCivs.includes(f.opponentCiv))&&(!f.opponent||r.opponents.some(p=>p.name===f.opponent))&&(f.gameType==='all'||f.gameType==='rm'&&r.game.game_type_id===0||f.gameType==='other'&&typeof r.game.game_type_id==='number'&&r.game.game_type_id!==0||f.gameType==='unknown'&&typeof r.game.game_type_id!=='number')&&(f.rated==='all'||f.rated==='rated'&&r.game.rated===true||f.rated==='unrated'&&r.game.rated===false||f.rated==='unknown'&&typeof r.game.rated!=='boolean'));}
export const durationBuckets=[['Under 5 min',0,300],['5–<15 min',300,900],['15–<25 min',900,1500],['25–<40 min',1500,2400],['40+ min',2400,Infinity]] as const;
export function durationGroups(records:RecordRow[]){const rows:Group[]=durationBuckets.map(([key,lo,hi])=>({key,...counts(records.filter(r=>r.seconds!==null&&r.seconds>=lo&&r.seconds<hi))}));if(records.some(r=>r.seconds===null))rows.push({key:'Duration unknown',...counts(records.filter(r=>r.seconds===null))});return rows;}
