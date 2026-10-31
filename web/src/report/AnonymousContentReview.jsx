import React from 'react';
import {RichNarrative} from '../runtime.jsx';
import {AudioClip,Table,f} from './ShanghaiPanels.jsx';

const clock = value => {
 const seconds=Math.max(0,Math.floor(Number(value)||0));
 return `${String(Math.floor(seconds/60)).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`;
};
const scoreText = (value,max,unknown='待核',decimals=0) => value==null?unknown:`${f(value,decimals)}/${max}`;
const expressionRange = expression => expression.raw_score_lower==null||expression.raw_score_upper==null?'范围待核':`${f(expression.raw_score_lower,0)}—${f(expression.raw_score_upper,0)}`;
const calibrationNote = expression => {
 const pending=[expression.content_progression==null&&'无效重复控制',expression.filler_control==null&&'语气词'].filter(Boolean);
 return pending.length?pending.join('、')+'待校准':'分项已核';
};

export default function AnonymousContentReview({summaries=[],units=[],audits=[]}){
 if(!units.length&&!audits.length)return null;
 return <div className="sh-anonymous-content" data-reviewed-rows>
  <div className="sh-comment-heading"><h3>已审录音 · 内容评价</h3><span>匿名内容单元 · 实际身份和交接待核</span></div>
  {summaries.map(s=><div className="cr-coach-line" key={s.id}>
   <span>{s.recording}</span><div className="cr-coach-copy">
    <RichNarrative id={`anonymous-content-summary:${s.id}`} value={s.summary}/>
    <p>价值讲透 {f(s.value_native_mean,2)} / 5；表达文本阶段估计 {f(s.expression_text_stage_mean,2)} / 11，范围 {f(s.expression_lower,2)}—{f(s.expression_upper,2)}。</p>
    <small>未知分项待原声校准；以上仅为该录音的内容评价，尚未计入实名主播个人评分。</small>
   </div>
  </div>)}
  {audits.length>0&&<details className="cr-disclosure"><summary>已审未评分 · {audits.length} 条短录音</summary>{audits.map(a=><div className="cr-coach-line" key={a.id}><span>{a.recording}</span><div className="cr-coach-copy"><p>{a.summary}</p><p>{a.reason}</p><small>已读 {a.asr_segments} 段转写 · {f(a.duration_seconds,2)} 秒；未按短代播排除。</small><AudioClip url={a.audio_url} start={a.audio_start} end={a.audio_end} title={`${a.recording} · 已审未评分`} subtitle="完整短录音"/></div></div>)}</details>}
  <details className="cr-disclosure"><summary>逐段内容评分 · {units.length} 个单元</summary>
  <Table label="匿名内容单元评分" heads={['录音 · 音轨范围','主要内容','价值 / 5','表达文本估计 / 11']}>
   {units.map(u=><tr key={u.id}><td><b>{u.recording}</b><small>{clock(u.audio_start)}—{clock(u.audio_end)}</small></td><td className="cr-prose-cell">{u.summary}</td><td>{f(u.value.raw_score,0)}</td><td>{f(u.expression.raw_score_text_stage_estimate,0)}<small>{u.content_score_eligible===false?'证据待核 · 分数空缺':`${expressionRange(u.expression)} · ${calibrationNote(u.expression)}`}</small></td></tr>)}
  </Table></details>
  <details className="cr-disclosure"><summary>分项依据与录音 · {units.length} 个文本单元 / 交接片段</summary>
   {units.map(u=><details className="cr-review-row" key={u.id}>
    <summary><span>{u.recording} · {clock(u.audio_start)}—{clock(u.audio_end)}</span><b>{u.content_score_eligible===false?'证据待核 · 分数空缺':`价值 ${scoreText(u.value.raw_score,5)} · 表达阶段 ${scoreText(u.expression.raw_score_text_stage_estimate,11)}`}</b></summary>
    {u.content_score_eligible!==false&&<><p>客户利益 {scoreText(u.value.customer_benefit,2)} · 具体支撑 {scoreText(u.value.specific_support,2)}</p>
    <RichNarrative id={`anonymous-value-reason:${u.id}`} value={u.value.reason}/>
    <p>有效内容 {scoreText(u.expression.effective_content,4)} · 可理解性 {scoreText(u.expression.understandability,2)} · 无效重复控制 {scoreText(u.expression.content_progression,2,'待校准')} · 语气词 {scoreText(u.expression.filler_control,2,'待校准')}</p>
    <RichNarrative id={`anonymous-expression-reason:${u.id}`} value={`**有效内容**　${u.expression.reason_by_component.effective_content}\n\n**可理解性**　${u.expression.reason_by_component.understandability}\n\n**无效重复控制**　${u.expression.reason_by_component.content_progression}`}/>
    </>}
    {u.content_score_eligible===false&&<><p>{u.summary}</p><p>{u.value.reason}</p></>}
    {u.evidence.map(e=><details className="cr-disclosure" key={e.id}>
     <summary>原话与试听 · {clock(e.audio_start)}—{clock(e.audio_end)}</summary>
     <blockquote>{e.raw_segments.map(r=>r.raw_text).join(' / ')}</blockquote>
     <AudioClip url={u.audio_url} start={e.audio_start} end={e.audio_end} title={`${u.recording} · 内容依据`} subtitle={`${clock(e.audio_start)}—${clock(e.audio_end)} · ASR原文`}/>
    </details>)}
   </details>)}
  </details>
 </div>;
}
