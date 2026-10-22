/**
 * لا نعلن فائزًا عند التعادل. يعيد المتصدر أو tie=true.
 */
export function getPodiumResult(teams) {
  if (!Array.isArray(teams) || teams.length !== 2) {
    return { tie: true, winner: null, loser: null, margin: 0 };
  }
  const [first, second] = teams;
  if (first.score === second.score) {
    return { tie: true, winner: null, loser: null, margin: 0 };
  }
  const winner = first.score > second.score ? first : second;
  const loser = winner.id === first.id ? second : first;
  return {
    tie: false,
    winner,
    loser,
    margin: Math.abs(first.score - second.score),
  };
}
