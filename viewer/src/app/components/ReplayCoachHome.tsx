"use client";
import {useMemo} from 'react';
import type {PythonAnalysis} from '@/lib/coachAnalysis';
import type {CoachingResponse,OpenEvidence} from '@/lib/coachingReview';
import {buildReplayHome,homeStatement,homeTime} from '@/lib/replayCoachHome';

export function jumpToReplayReview(){
 const target=document.querySelector<HTMLElement>('[data-replay-briefing]');
 if(target){target.tabIndex=-1;target.focus({preventScroll:true});target.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'});}
}
export function ReplayCoachHome({analysis,profileName,response,onOpenEvidence}:{analysis:PythonAnalysis;profileName:string;response:CoachingResponse|null;onOpenEvidence:OpenEvidence}){
 const home=useMemo(()=>buildReplayHome(analysis,profileName,response),[analysis,profileName,response]);
 if(!home)return <div className="panel-strong rounded-xl p-4 text-sm" data-replay-home-unavailable>Timed coaching is available for supported completed 1v1 replays. Your existing replay review remains below.</div>;
 const preparationAnchor=home.preparation.sources.find(e=>e.action==='AGE_REACHED')??home.preparation.sources[0];
 return <section data-replay-coach-home className="replay-coach-home" aria-label="Your replay coaching">
  <header className="replay-home-heading"><div><p className="replay-home-eyebrow">Your next game starts here</p><h2>Watch the moment. Make a plan.</h2><p className="replay-home-subtitle">{home.moments.length?`${home.moments.length} moments to review`:'Review your production plan'} · {analysis.players.find(p=>p.name===profileName)?.civilization} vs {home.opponent}</p></div><button className="replay-home-secondary" onClick={jumpToReplayReview}>Jump to replay review ↓</button></header>
  <div className="replay-home-grid">
   <article className="replay-home-card replay-home-moments"><p className="replay-home-eyebrow">01 / Moments worth your attention</p><h3>Start with these decisions</h3>
    {home.moments.length?home.moments.map(moment=><section data-home-moment={moment.kind} key={moment.id} className="replay-home-moment">
     <div className="replay-home-moment-heading"><button className="replay-home-clock" aria-label={`Watch ${moment.title} at ${homeTime(moment.anchor.time_seconds)}`} onClick={()=>onOpenEvidence(moment.anchor,moment.title)}>{homeTime(moment.anchor.time_seconds)} ↗</button><h4>{moment.title}</h4></div>
     <p className="replay-home-recorded">{moment.why}</p><p className="replay-home-action"><b>Try:</b> {moment.action}</p>
     <details className="replay-home-source-list"><summary>Recorded sequence · {moment.sources.length} sources</summary><div>{moment.sources.map(e=><button key={e.id} onClick={()=>onOpenEvidence(e,moment.title)}>{homeTime(e.time_seconds)} · {e.player_id===analysis.players.find(p=>p.name===profileName)?.id?'You':'Opponent'} · {homeStatement(e)} ↗</button>)}</div></details>
    </section>):<p className="mt-3 text-sm">No supported military or age-up anchors were found. Use Events to inspect this replay; no substitute moments have been invented.</p>}
   </article>
   <article className="replay-home-card replay-home-plan" data-home-army-plan><p className="replay-home-eyebrow">02 / Army & supporting mix</p><h3>{home.plan.title}</h3><p className="replay-home-stage">{home.plan.stage}</p><p className="replay-home-recorded">For {home.plan.context.toLowerCase()}</p>
    <h4 className="replay-home-small-heading">Give each part a job</h4><ul>{home.plan.jobs.map(job=><li key={job}>{job}</li>)}</ul><h4 className="replay-home-small-heading">Prepare it</h4><ul>{home.plan.prepare.map(step=><li key={step}>{step}</li>)}</ul><p className="replay-home-watch"><b>Watch for:</b> {home.plan.watch}</p>
    {home.plan.source&&<button className="replay-home-secondary mt-3" onClick={()=>onOpenEvidence(home.plan.source!,'Army-plan opposing source')}>Inspect their production at {homeTime(home.plan.source.time_seconds)} ↗</button>}
   </article>
   <article className="replay-home-card" data-home-playstyle><p className="replay-home-eyebrow">03 / How to use the army</p><h3>{home.style.title}</h3><p className="replay-home-action">{home.style.action}</p></article>
   <article className="replay-home-card" data-home-preparation><p className="replay-home-eyebrow">04 / Timing & resources</p><h3>{home.preparation.title}</h3><p className="replay-home-action">{home.preparation.action}</p><p className="replay-home-recorded">{home.preparation.check}</p>{preparationAnchor&&<button className="replay-home-secondary mt-3" onClick={()=>onOpenEvidence(preparationAnchor,'Production and resource preparation')}>Review the setup at {homeTime(preparationAnchor.time_seconds)} ↗</button>}<details className="replay-home-source-list"><summary>Production & research sequence</summary><div>{home.preparation.sources.map(e=><button key={e.id} onClick={()=>onOpenEvidence(e,'Production and resource preparation')}>{homeTime(e.time_seconds)} · {e.player_id===analysis.players.find(p=>p.name===profileName)?.id?'You':'Opponent'} · {homeStatement(e)} ↗</button>)}</div></details></article>
  </div>
  <details data-home-evidence-note className="replay-home-evidence"><summary>Evidence & reference notes{home.referenceBuild?` · DE ${home.referenceBuild}${home.patchMismatch?' · replay patch differs or is unknown':''}`:''}</summary><p>Times link to recorded commands and age milestones. Production requests are not completed or surviving armies; placements and research requests are not completion. Opposing inputs do not establish what you saw.</p><p>Army plans and playstyle tips are authored strategy, not simulated combat results. Resource questions are review prompts: banks, safe income and readiness are not measured. Named combinations require your civilization’s pinned reference availability, not proof that you could afford them here.</p><p>{home.referenceBuild?`Unit reference: DE ${home.referenceBuild}. `:''}{home.patchMismatch?'Replay patch differs or is unknown; check current balance before applying the unit plan.':'Reference facts are not effective match stats or verified standard rules.'} {home.unknownMilitary?`${home.unknownMilitary} military inputs are outside the supported unit mapping. `:''}{home.selection}</p><p>Browsing and these review tips do not select a habit, save an answer or establish progress. No cause of defeat or victory is inferred.</p></details>
 </section>;
}
