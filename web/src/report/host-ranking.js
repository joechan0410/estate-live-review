const usableScore = value => value != null && value !== '' && Number.isFinite(Number(value));

export function rankHosts(rows) {
  const ranked = rows.map(row => {
    const score = usableScore(row.final_score) ? row.final_score : row.score;
    return {...row, ranking_score: usableScore(score) ? Number(Number(score).toFixed(2)) : null};
  }).sort((a, b) => {
    if (a.ranking_score == null) return b.ranking_score == null ? 0 : 1;
    if (b.ranking_score == null) return -1;
    return b.ranking_score - a.ranking_score;
  });
  let previousScore, previousRank;
  return ranked.map((row, index) => {
    const rank = row.ranking_score == null ? null : row.ranking_score === previousScore ? previousRank : index + 1;
    previousScore = row.ranking_score;
    previousRank = rank;
    return {...row, rank};
  });
}

export function rankingExport(rows) {
  return rows.map(row => ({
    项目: row.project,
    名次: row.rank,
    主播: row.host,
    综合总分: row.ranking_score,
    评级: row.grade || '待评',
    评分状态: row.ranking_score == null ? '待核' : row.final_score != null ? '终评' : row.score_scope || (row.weight_coverage === 100 ? '七项已计分·已分析片段' : '阶段分'),
    已计分权重: `${row.weight_coverage}%`,
    静默秒每小时: row.silence_per_hour,
    静默得分: row.silence_score,
    静默加权贡献: row.silence_contribution,
    留资每小时: row.lead_per_hour,
    有效评论人次每小时: row.participants_per_hour,
  }));
}
