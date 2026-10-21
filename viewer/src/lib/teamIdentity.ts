/** Python mgz uses team-member arrays; compare values, never array references. */
export function canonicalTeam(player: {id: number; team_id?: number | number[] | null}): string {
  const team = player.team_id;
  if (Array.isArray(team)) return team.length ? `members:${[...new Set(team)].sort((a, b) => a - b).join(',')}` : `player:${player.id}`;
  return team == null ? `player:${player.id}` : `team:${team}`;
}
