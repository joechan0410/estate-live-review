import React from 'react';
import './acquisition-insights.css';

const numeric = value => value == null || value === '' || !Number.isFinite(Number(value)) ? null : Number(value);
const count = value => numeric(value) == null ? '—' : Number(value).toLocaleString('zh-CN');
const percent = value => numeric(value) == null ? '—' : `${Number(value).toFixed(1)}%`;
const observedRate = row => numeric(row.rate_pct) ?? (numeric(row.customers) > 0 && numeric(row.conversions) != null ? 100 * Number(row.conversions) / Number(row.customers) : null);
const asArray = value => Array.isArray(value) ? value : [];

// Preview the two largest cohorts within the same category; all rows remain below.
const comparisonRows = rows => rows.filter(row => (numeric(row.customers) ?? 0) >= 5)
  .slice().sort((a, b) => Number(b.customers) - Number(a.customers) || (observedRate(b) ?? -1) - (observedRate(a) ?? -1))
  .slice(0, 2).sort((a, b) => (observedRate(b) ?? -1) - (observedRate(a) ?? -1));

function ActualCases({examples = []}) {
  const rows = asArray(examples).filter(row => row && typeof row === 'object');
  if (!rows.length) return null;
  return <details className="ai-cases">
    <summary>实际案例 · {rows.length}</summary>
    <div className="ai-case-list">{rows.map((row, index) => <article className="ai-case" key={`${row.comment_time || ''}:${row.question || ''}:${index}`}>
      <div className="ai-case-meta"><b>{row.host || '归属待核'}</b>{row.comment_time && <time>{row.comment_time}</time>}</div>
      <dl><div><dt>客户</dt><dd>{row.question || '—'}</dd></div><div><dt>回答</dt><dd>{row.answer || '答法待核'}</dd></div>{row.outcome && <div><dt>结果</dt><dd>{String(row.outcome)}</dd></div>}</dl>{row.asr_excerpt&&<details><summary>原话转写摘录</summary><blockquote>{row.asr_excerpt}</blockquote><small>自动转写摘录，疑似识别差异保留；实际录音见评论明细。</small></details>}
    </article>)}</div>
  </details>;
}

/** Aggregate rows are supplied by the review pipeline; this component never filters by host identity. */
export default function AcquisitionInsights({frequency = [], effectiveness = [], findings = [], intentScope, separateIntents = [], confirmedStrategies = [], confirmedScope}) {
  const closedSamples = asArray(effectiveness).some(row => row?.rate_basis === 'verified_closed_samples_only');
  const frequencies = asArray(frequency).filter(Boolean).slice().sort((a, b) => (numeric(b.question_count) ?? -1) - (numeric(a.question_count) ?? -1));
  const grouped = new Map();
  asArray(effectiveness).filter(Boolean).forEach(row => {
    const category = row.category || '其他问题';
    if (!grouped.has(category)) grouped.set(category, []);
    grouped.get(category).push(row);
  });
  const categoryOrder = new Map(frequencies.map((row, index) => [row.category, index]));
  const groups = [...grouped].sort(([a], [b]) => (categoryOrder.get(a) ?? Infinity) - (categoryOrder.get(b) ?? Infinity) || a.localeCompare(b, 'zh-CN'));
  const insights = asArray(findings).map(item => typeof item === 'string' ? {text: item} : item).filter(item => item && (item.text || item.summary || item.finding || item.title));
  if (!frequencies.length && !groups.length && !insights.length) return null;

  return <div className="ai-insights" data-reviewed-rows>
    {insights.length > 0 && <section className="ai-findings" aria-label="获客观察"><div className="ai-heading"><h3>获客观察</h3></div><ul>{insights.slice(0,3).map((item, index) => <li key={index}>{item.title && <b>{item.title}</b>}{(item.text || item.summary || item.finding) && <p>{item.text || item.summary || item.finding}</p>}</li>)}</ul>{insights.length>3&&<details className="ai-category-detail"><summary>其余获客观察与已核案例 · {insights.length-3} 条</summary><ul>{insights.slice(3).map((item,index)=><li key={index}>{item.title&&<b>{item.title}</b>}<p>{item.text||item.summary||item.finding}</p></li>)}</ul></details>}</section>}
    {frequencies.length > 0 && <section className="ai-frequency" aria-label="客户最常问">
      <div className="ai-heading"><h3>{intentScope ? (intentScope.literal_question_count==null?'已归类客户关注主题':'全量客户关注主题') : frequencies[0]?.scope_label?'已采范围 · 客户问题':'客户最常问'}</h3><span>{frequencies[0]?.scope_label||'按评论条数排序'}</span></div>
      {intentScope && <p className="ai-preview-note">{count(intentScope.non_team_customer_comments)} 条客户评论；{intentScope.literal_question_count==null?'历史提问、陈述和确认形式尚待统一。':`${count(intentScope.literal_question_count)} 条为提问，主题汇总同时保留明确需求和陈述异议。`}实际答法已审 {count(intentScope.actual_answer_review_count)} 条。</p>}
      <div className="ai-table-scroll"><table className="ai-frequency-table">
        <thead><tr><th scope="col">{intentScope ? '关注主题' : '问题类别'}</th><th scope="col">评论条数</th>{intentScope && <th scope="col">其中提问</th>}<th scope="col">客户数</th><th scope="col">占比</th><th scope="col">典型问法</th></tr></thead>
        <tbody>{frequencies.map((row, index) => <tr key={`${row.category}:${index}`}>
          <th scope="row"><span className="ai-rank">{String(index + 1).padStart(2, '0')}</span>{row.category || '其他问题'}</th>
          <td>{count(row.comment_count ?? row.question_count)}</td>{intentScope && <td>{count(row.literal_question_count)}</td>}<td>{count(row.customers)}</td><td>{percent(row.share_pct)}</td>
          <td className="ai-question-examples">{asArray(row.examples).filter(text => typeof text === 'string' && text).map((text, i) => <span key={`${i}:${text}`}>{text}</span>)}</td>
        </tr>)}</tbody>
      </table></div>
      {intentScope && <p className="ai-preview-note">占比按 {count(intentScope.topic_comment_count)} 条有明确主题的评论计算。另列 {intentScope.separate_comment_count==null?'未归类及历史排除，具体范围见来源说明':`${count(intentScope.separate_comment_count)} 条：`+asArray(separateIntents).map(row => `${row.label || row.intent_form || row.bucket} ${count(row.comment_count)} 条`).join('、')}。所有原评论保留在下方明细。</p>}
    </section>}
    {asArray(confirmedStrategies).length>0&&<section className="ai-confirmed" aria-label="已核问题答法留资"><div className="ai-heading"><h3>已核问题 × 答法留资</h3><span>同场同客去重 · 已核数量下限</span></div><p className="ai-preview-note">已核有效 {count(confirmedScope?.confirmed_effective_events)} 人次；其中 {count(confirmedScope?.pre_submission_strategy_linked_events)} 人次可核到提交前答法，另 {count(confirmedScope?.strategy_pending_events)} 人次的答法先后仍待核。完整留资率随其余样本核清后更新。</p>{confirmedScope?.source_scope_note&&<p className="ai-preview-note">{confirmedScope.source_scope_note}</p>}<div className="ai-table-scroll"><table aria-label="已核问题与提交前答法留资"><thead><tr><th>原业务问题</th><th>实际答法</th><th>已核留资</th><th>案例</th></tr></thead><tbody>{confirmedStrategies.map((r,i)=><tr key={`${r.category}:${r.strategy}:${i}`}><th>{r.category}</th><td>{r.strategy}</td><td>≥ {count(r.confirmed_effective_lead_lower_bound)} 人次</td><td><ActualCases examples={r.examples}/></td></tr>)}</tbody></table></div></section>}
    {groups.length > 0 && <section className="ai-effectiveness" aria-label="同类问题答法获客对比">
      <div className="ai-heading"><h3>同类问题 · 答法与留资结果</h3><span>默认对照同类中客户数最多的两种答法 · 每种至少5位客户</span></div>
      {closedSamples && <p className="ai-preview-note">按已核留资与未留资客户比较；待核结果单列。百分比仅代表已核样本，完整样本率仍待核。</p>}
      <div className="ai-category-groups">{groups.map(([category, sourceRows]) => {
        const rows = sourceRows.slice().sort((a, b) => (observedRate(b) ?? -1) - (observedRate(a) ?? -1) || (numeric(b.customers) ?? -1) - (numeric(a.customers) ?? -1));
        const preview = comparisonRows(rows);
        return <article className="ai-category" key={category}>
          <div className="ai-category-header"><h4>{category}</h4><span>{rows.length} 种答法</span></div>
          {preview.length > 0 ? <div className="ai-table-scroll"><table className="ai-compare-table" aria-label={`${category}主要答法概览`}>
            <thead><tr><th scope="col">实际答法</th><th scope="col">留资 / {closedSamples ? '已核客户' : '客户'}</th><th scope="col">{closedSamples ? '已核样本率' : '留资率'}</th></tr></thead>
            <tbody>{preview.map((row, index) => <tr key={`${row.strategy}:${index}`}>
              <th scope="row">{row.strategy || '答法待归类'}</th><td>{count(row.conversions)} / {count(row.customers)}{row.rate_basis === 'verified_closed_samples_only' && <small className="ai-small-sample">待核 {count(row.pending_customers)}</small>}</td><td>{percent(observedRate(row))}</td>
            </tr>)}</tbody>
          </table>{preview.length === 1 && <p className="ai-preview-note">该类目前仅一种答法达到5位客户。</p>}</div> : <p className="ai-preview-note">该类答法样本较少，可展开查看全部记录。</p>}
          <details className="ai-category-detail">
          <summary>完整答法与案例<span>{rows.length} 种答法</span></summary>
          <div className="ai-table-scroll"><table className="ai-strategy-table" aria-label={`${category}答法与留资对比`}>
            <thead><tr><th scope="col">实际答法</th><th scope="col">留资 / {closedSamples ? '已核客户' : '客户'}</th><th scope="col">{closedSamples ? '已核样本率' : '留资率'}</th><th scope="col">案例</th></tr></thead>
            <tbody>{rows.map((row,index)=><tr key={`${row.strategy}:${index}`}>
              <th scope="row">{row.strategy||'答法待归类'}{numeric(row.customers)!=null&&Number(row.customers)<5&&<span className="ai-small-sample">少量样本</span>}</th>
              <td>{count(row.conversions)} / {count(row.customers)}{row.rate_basis === 'verified_closed_samples_only' && <small className="ai-small-sample">未留资 {count(row.negative_customers)} · 待核 {count(row.pending_customers)}</small>}</td><td className="ai-rate-cell">{percent(observedRate(row))}</td>
              <td className="ai-examples-cell"><ActualCases examples={row.examples}/></td>
            </tr>)}</tbody>
          </table></div>
          </details>
        </article>;
      })}</div>
    </section>}

  </div>;
}
