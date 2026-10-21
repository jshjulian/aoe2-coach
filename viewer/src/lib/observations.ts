export type ObservationPoint = {time_seconds:number; value:number|null; quality:'unreviewed'|'visually_checked'|'rejected'; evidence_sha256:string; player_id:number; metric:string};
export type ObservationSeries = {metric:string; points:ObservationPoint[]; increments:{start:number;end:number;value:number;quality:string;evidence_sha256:string[]}[]; gaps:{start:number;end:number}[]; counter_resets:number[]; coverage:{readable:number;rejected:number;first_seconds:number|null;last_seconds:number|null};qualified_for_coaching:false};
export type ObservationData = {
  schema_version:1;match_id:string;status:string;qualification:string;validated_for_application:false;selected_player_id:number|null;
  provider:{name:string;ui_version:string;method:string;extractor_version?:string}|null;batch_id:string|null;
  collection_summary?:{total_frames:number;exported_frames:number;excluded_frames:number}|null;
  collection:{enabled:false;reason:string};max_comparable_gap_seconds:number;
  metrics:Record<string,{label:string;unit:string;kind:'gauge'|'counter';extraction:string;definition:string;coaching_qualified:false}>;
  series:ObservationSeries[];
  review_questions:{kind:string;time_seconds:number;observation:string;question:string;interpretation:string;alternatives:string[];evidence_sha256:string[];eligible_for_primary_coaching:false;causal_claim:false}[];
};

export function validateObservationResponse(data:ObservationData,matchId:string,playerId:number|null):boolean {
  return data.schema_version===1 && data.match_id===matchId && data.validated_for_application===false && data.selected_player_id===playerId
    && Array.isArray(data.series) && Array.isArray(data.review_questions) && !!data.metrics && data.collection?.enabled===false
    && data.series.every(s=>s.qualified_for_coaching===false && !!data.metrics[s.metric] && Array.isArray(s.points)
      && s.points.every(p=>p.player_id===playerId && p.metric===s.metric && Number.isInteger(p.time_seconds) && p.time_seconds>=0
        && (p.value===null || (Number.isInteger(p.value) && p.value>=0))));
}
