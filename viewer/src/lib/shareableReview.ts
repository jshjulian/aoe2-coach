import type { PythonAnalysis } from './coachAnalysis';
import type { CoachingResponse } from './coachingReview';
import { canonicalTeam } from './teamIdentity';

function clock(seconds: number) {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${String(secs).padStart(2, '0')}`;
}

export function makeShareableReview(analysis: PythonAnalysis, response: CoachingResponse, includeNames = false): string {
  const review = response.review;
  const profileName = review.player?.name ?? '';
  const labels = new Map<string, string>();
  const teamLabels = new Map<string, string>();
  const selfPlayer = analysis.players.find(p => p.name === profileName);
  const selfTeam = selfPlayer ? canonicalTeam(selfPlayer) : '';
  let opponentIndex = 0;
  let teammateIndex = 0;
  for (const player of analysis.players) {
    const team = canonicalTeam(player);
    if (includeNames) labels.set(player.name, player.name);
    else if (player.name === profileName) labels.set(player.name, 'You');
    else {
      if (!teamLabels.has(team)) {
        teamLabels.set(team, team === selfTeam ? `Teammate ${++teammateIndex}` : `Opponent ${++opponentIndex}`);
      }
      labels.set(player.name, teamLabels.get(team)!);
    }
  }
  const aliases = [...labels.entries()].filter(([name, label]) => name && name !== label).sort((a, b) => b[0].length - a[0].length);
  const safe = (text: string) => aliases.reduce((value, [name, label]) => value.split(name).join(label), text);
  const winners = analysis.players.filter(p => p.won === true);
  const winnerTeams = new Set(winners.map(canonicalTeam));
  const self = analysis.players.find(p => p.name === profileName);
  const result = self && winners.length && winnerTeams.size === 1
    ? (self.won ? 'WIN' : 'LOSS')
    : 'UNCONFIRMED';
  const eventById = new Map(analysis.events.map(event => [event.id, event]));
  const evidenceList = (ids: string[]) => [...new Set(ids)].map(id => {
    const event = eventById.get(id);
    return event ? `- ${event.time} — ${safe(event.player ?? 'Unknown player')} — ${event.action}${event.unit ? ` ${event.unit}` : ''}${event.building ? ` ${event.building}` : ''} [${id}]` : `- Event unavailable in this analysis: ${id}`;
  }).join('\n');
  const lines = [
    '# AoE2 Replay Lab — Match Coaching Review', '',
    `**Result for ${includeNames ? safe(profileName || 'selected player') : 'You'}: ${result}**`,
    `**Map:** ${safe(analysis.map)} · **Length:** ${analysis.duration ?? clock(analysis.duration_seconds)} AoE time${analysis.estimated_real_duration_seconds != null ? ` · ~${clock(analysis.estimated_real_duration_seconds)} real at ${analysis.game_speed_multiplier ?? '?'}× (estimate; pauses/loading excluded)` : ''} · **Format:** ${analysis.players.length} players${analysis.rated ? ' · Rated' : ''}`,
    `**Started:** ${analysis.played_at ? `${analysis.played_at} local (from replay filename)` : 'Unavailable'}`,
    '**Players:** ' + analysis.players.map(p => `${safe(labels.get(p.name) ?? 'Player')} (${safe(p.civilization)})`).join(' vs '),
    `**Intended plan:** ${safe(review.plan.label || 'Not specified')} — ${review.plan.status}`, '',
    '> Result reflects parser-reported winner flags only. Advice is deterministic and reviewable, not a diagnosis of why the game was won or lost.', '',
  ];
  const situation = response.situation;
  if (situation) {
    lines.push('## Situation review', '', 'At most two command-evidence review questions; no opening declaration or result-based diagnosis.',
      `Coverage: ${situation.coverage.searched_window_seconds?.map(clock).join('–') ?? 'unavailable'}; ${situation.coverage.spatial_scope}. Stream completeness: ${situation.coverage.command_stream_completeness}.`, '');
    if (!situation.recommendations.length) lines.push(safe(situation.abstention_reason ?? 'No supported incident.'), '');
    if (situation.positive) lines.push(`Recorded positive: ${safe(situation.positive.text)}`, safe(situation.positive.caveat), evidenceList(situation.positive.event_ids), '');
    for (const question of situation.recommendations) {
      const incident = situation.incidents.find(row => row.id === question.incident_id);
      if (!incident) continue;
      const opponent = analysis.players.find(player => player.id === incident.participants.opponent_player_id);
      const episode = situation.episodes?.find(row => row.id === question.episode_id);
      lines.push(`### Review question · ${clock(question.replay_anchor.time_seconds)}: ${safe(question.title)}`, '',
        ...(question.summary ? [safe(question.summary), `Next game: ${safe(question.practice_short ?? question.exercise)}`, safe(question.uncertainty_label ?? '')] : []),
        `Participants: ${safe(profileName)} and ${safe(opponent?.name ?? 'unresolved opponent')}. Command window ${(episode?.window_seconds ?? incident.window_seconds).map(clock).join('–')}; searched response window ${(episode?.review_window_seconds ?? incident.review_window_seconds).map(clock).join('–')}.`,
        ...(question.response_summary ? [`Recorded follow-up: ${safe(question.response_summary)}`] : []),
        `Recorded situation: ${safe(incident.observation)}`, `Possible interpretation: ${safe(incident.interpretation)}`,
        `Recorded response: ${safe(incident.actual_response)}`, `Outcome unresolved: ${safe(incident.outcome.reason)}`,
        `Review: ${safe(question.question)}`, `Transferable principle: ${safe(question.principle)}`, `Practice exercise: ${safe(question.exercise)}`, '',
        'Conditional options:', ...incident.options.map(option => `- ${safe(option.action)} Only if: ${safe(option.condition)}`), '',
        'Alternative explanations / uncertainties:', ...[...incident.alternatives, ...question.uncertainties].map(text => `- ${safe(text)}`),
        `Evidence strength: ${incident.quality.evidence_strength.replaceAll('_', ' ')} (not strategic confidence); vision ${incident.quality.vision}; response intent ${incident.quality.response_intent}.`,
        ...(incident.quality.right_censored ? ['Response window clipped by replay end; not a failed response.'] : []), '',
        'Recorded response associations (not causal):', ...incident.responses.map(row => `- ${clock(row.time_seconds)} [${row.event_id}]: ${row.temporal_relation}; ${row.spatial_relation.replaceAll('_', ' ')}.`),
        `Unlocalized garrison context only: ${incident.unlocalized_response_event_ids.join(', ') || 'none identified'}.`,
        'Age/queue/research context is not an army located at the incident or completed production.', '',
        'Why this window:', ...question.priority_reasons.map(text => `- ${safe(text)}`), '',
        `Rule ${question.rule_id} v${question.rule_version}.`, evidenceList(question.event_ids), '');
      const menu = situation.knowledge?.options_by_incident.find(row => row.incident_id === incident.id);
      if (menu) lines.push('Conditional catalog menu — not recommended counters or ready-to-queue state:',
        ...menu.options.map(option => `- [${option.name} (${option.kind} ${option.entity_id}; age ${option.minimum_age})](${option.source_url})`), '');
    }
    if (situation.knowledge) {
      const knowledge = situation.knowledge;
      lines.push(`Civilization reference: ${knowledge.status.replaceAll('_', ' ')}. ${safe(knowledge.reason)}`);
      if (knowledge.source) lines.push(`Source update ${knowledge.source.declared_update}; commit ${knowledge.source.commit}; ${knowledge.source.pack_id} v${knowledge.source.pack_version}; menu v${knowledge.menu_version}.`);
      for (const fact of knowledge.reference_facts) lines.push(`- Reference only: ${safe(fact.text)}`, ...fact.source_refs.map(ref => `  - [source](${ref.url})`));
    }
    lines.push('', ...situation.limitations.map(text => `- ${safe(text)}`), '');
  }
  const opening = analysis.opening_observations?.find(row => row.player === profileName);
  if (opening) {
    lines.push('## Observed opening & transitions', '',
      `**${safe(opening.label)}** — ${opening.confidence} command-pattern evidence strength (rule-based, not a calibrated probability).`,
      `Searched ${opening.window_seconds.map(clock).join('–')}; intended opening is not established by commands.`,
      ...opening.patterns.map(pattern => `- ${pattern.label}: ${pattern.queue_command_count} queue commands, not completed units.`),
      ...opening.transitions.map(transition => `- ${transition.label}: ${transition.interval_seconds.toFixed(1)}s between anchors, not completed production.`),
      `Adaptation: ${opening.adaptation.status}. ${opening.adaptation.reason}`, '',
      evidenceList([...opening.patterns.flatMap(pattern => pattern.event_ids), ...opening.transitions.flatMap(transition => transition.event_ids)]), '',
      `Replay build: ${analysis.replay_provenance?.build_version ?? 'unknown'}. Reference applicability is reported separately in the matchup section when available.`,
      ...opening.limitations.map(text => `- ${text}`), '');
  }
  lines.push('## Optional legacy plan-specific review (not the situation priority)', '');
  if (review.primary) {
    const p = review.primary;
    lines.push(`**${safe(p.title)}** · ${p.state.replaceAll('_', ' ')} · interpretation confidence: ${p.interpretation.confidence}`, '',
      '### Recorded observations', ...p.observations.map(o => `- **${o.evidence_class.replaceAll('_', ' ')}:** ${safe(o.text)}`), '',
      `### What it might mean\n${safe(p.interpretation.text)}`, '',
      'Alternative explanations:', ...p.interpretation.alternatives.map(a => `- ${safe(a)}`), '',
      `### What to try next time\n${safe(p.recommendation.action)}`, '',
      'Conditions / cautions:', ...p.recommendation.conditions.map(c => `- ${safe(c)}`), '',
      `### Why this priority was selected\n${p.priority_reasons.map(r => `- ${safe(r)}`).join('\n')}`, '',
      `### Evidence quality\n${p.evidence_quality.reason} Stream completeness: ${p.evidence_quality.stream_completeness}; gameplay state complete: ${p.evidence_quality.gameplay_state_complete}.`, '',
      `### Possible counterevidence\n${p.counterevidence_event_ids.length ? evidenceList(p.counterevidence_event_ids) : '- None identified in the searched window; that is not proof none occurred.'}`, '',
      `### Replay evidence\n${evidenceList(p.observations.flatMap(o => o.event_ids))}`, '',
      `Replay anchor: ${clock(p.replay_anchor.time_seconds)} [${p.replay_anchor.event_id}]`, ''
    );
  } else {
    lines.push(`No primary recommendation. ${safe(review.abstention_reason ?? 'Evidence/context was insufficient.')}`, '');
  }
  lines.push('## Legacy milestone positives', '');
  lines.push(...(review.what_went_well.length
    ? review.what_went_well.map(o => `- ${safe(o.text)}\n  Evidence: ${o.event_ids.map(id => `[${id}]`).join(', ')}`)
    : ['- No specific positive was supported by the decoded evidence.']), '');
  lines.push('## Legacy practice goal', '');
  if (review.practice_goals.length) {
    for (const goal of review.practice_goals) {
      lines.push(`- **${safe(goal.label)}**`, `  - Measure: ${safe(goal.primary_measure.target)}`,
        `  - Supporting indicator: ${safe(goal.supporting_indicator.name)}; baseline ${goal.supporting_indicator.baseline_seconds.toFixed(1)}s. No automatic pass/fail target.`,
        `  - Adaptation: ${safe(goal.stop_or_adapt)}`);
    }
  } else lines.push('- No new goal was suggested for this match.');
  lines.push('');
  const matchup = response.matchup;
  if (matchup) {
    lines.push('## Matchup briefing', '', `Status: ${matchup.status.replaceAll('_', ' ')}.`,
      ...matchup.compatibility.reasons.map(text => `- ${safe(text)}`),
      ...(matchup.abstention_reason ? [safe(matchup.abstention_reason)] : []), '',
      '> Source capabilities are not an observed army or verified applicability to this replay. Opponent commands are retrospective and may not have been visible in-game.', '');
    if (matchup.source) lines.push(`Reference update ${matchup.source.declared_update}; commit ${matchup.source.commit}; ${matchup.source.pack_id} v${matchup.source.pack_version}.`, '');
    lines.push(`Local rules declaration: ${response.state.rules_context?.rules === 'standard' ? 'standard rules reported by user; not independently verified' : 'unknown'}.`, '');
    const refs = new Map([...matchup.reference_facts.flatMap(fact => fact.source_refs), ...matchup.tips.flatMap(tip => tip.options.flatMap(option => option.source_refs))].map(ref => [ref.id, ref]));
    for (const fact of matchup.reference_facts) lines.push(`- **Reference only · ${fact.civilization}:** ${safe(fact.text)}`);
    if (refs.size) lines.push('', 'Reference sources:', ...[...refs.values()].map(ref => `- [${ref.civilization} ${ref.kind} ${ref.entity_id} · ${ref.field}](${ref.url})`), '');
    for (const observation of matchup.observations) lines.push(
      `**Recorded · ${observation.side === 'you' ? 'You' : 'Opponent'}:** ${observation.command_count} relevant queue commands (${observation.unit_labels.join(', ')}), not produced units.`,
      safe(observation.meaning), evidenceList(observation.event_ids), '');
    for (const tip of matchup.tips) {
      lines.push(`### Conditional review question: ${safe(tip.title)}`,
        '**Only if the user-reported standard rules are correct; mods remain independently unverified. Not a mistake verdict or a new selected practice goal.**',
        ...tip.observations.map(text => `- Recorded: ${safe(text)}`),
        `Possible meaning: ${safe(tip.interpretation)}`, `Review question: ${safe(tip.action)}`,
        `Window: ${tip.window_seconds.map(clock).join('–')}. Rule ${tip.rule_id} v${tip.rule_version}.`, '',
        'Options are catalog/age possibilities, not ready-to-queue state:',
        ...tip.options.map(option => `- ${option.label}: ${safe(option.requires)}`),
        'Conditions:', ...tip.conditions.map(text => `- ${safe(text)}`),
        'Alternatives / counterevidence:', ...tip.alternatives.map(text => `- ${safe(text)}`),
        `Reference facts: ${tip.fact_ids.join(', ')}. Interpretation: ${tip.evidence_quality.interpretation.replaceAll('_', ' ')}; vision: ${tip.evidence_quality.vision}.`,
        `Not claimed: ${tip.not_claimed.join(', ')}.`, evidenceList(tip.event_ids), '');
    }
    lines.push(...matchup.limitations.map(text => `- ${safe(text)}`), '');
  }
  if (response.state.feedback) {
    lines.push('## My feedback', '', `**${response.state.feedback.verdict}**${response.state.feedback.note ? ` — ${safe(response.state.feedback.note)}` : ''}`, '');
  }
  lines.push('## Scope and limitations',
    '- Queue, research and build entries are recorded commands, not proof of completed units/buildings or affordability.',
    '- Queue-command gaps are not Town Center idle time.',
    '- Opponent orders and proximity are cues, not confirmed attacks, intent or paths.',
    '- Cross-game tracking requires explicitly logged, comparable matches; timing changes do not prove improvement or causation.',
    '- Evidence event IDs are local to one replay and are useful only alongside the same recording.',
    '- This export contains no replay bytes, local file path, content match hash or raw event payload.',
    '', '_Generated locally by AoE2 Replay Lab._');
  return lines.join('\n').replace(/\n{3,}/g, '\n\n');
}
