import React, {useMemo, useState} from 'react';
import {AudioClip,Table,f} from './ShanghaiPanels.jsx';
import './anonymous-value-review.css';

const clock=value=>{
 const s=Math.max(0,Math.floor(Number(value)||0));
 return `${String(Math.floor(s/3600)).padStart(2,'0')}:${String(Math.floor(s%3600/60)).padStart(2,'0')}:${String(s%60).padStart(2,'0')}`;
};
const knownSeconds=r=>Number.isFinite(r.denominator_seconds)?r.denominator_seconds:null;
const hasUnknown=r=>r.full_total_unknown===true||r.total_count===null||(r.unknown_seconds??0)>0||(r.rounds||[]).some(x=>x.countable==null);
const rate=(n,seconds,multiplier)=>seconds>0?f(n*multiplier/seconds,2):'待核';
const lowerBound=(n,unknown)=>unknown?(n===0?'已观察 0 · 总量待核':`≥ ${n}`):n;
const ownToggle=setOpen=>event=>{
 if(event.target===event.currentTarget)setOpen(event.currentTarget.open);
};

function RoundDetail({round,recording}){
 const [open,setOpen]=useState(false);
 return <details className="cr-disclosure av-round" data-value-round={round.id} onToggle={ownToggle(setOpen)}>
  <summary>{clock(round.audio_start)}—{clock(round.audio_end)} · {round.topic_label} · {round.countable===true?'已核 1 轮':round.countable===false?'未计轮次':'待核'}</summary>
  {open&&<div className="av-round-body">
   <p>{round.summary}</p><p className="cr-footnote">{round.semantic_rationale}</p>
   <p className="av-excerpt-label">原话摘录 · 完整逐段原话与来源证据另存</p>
   {(round.evidence||[]).map((e,i)=><blockquote key={i}>{(e.raw_segments||[]).map(s=>s.raw_text??s.text).join(' / ')||e.raw_text||e.text}</blockquote>)}
   <AudioClip url={recording.audio_url} start={round.audio_start} end={round.audio_end} title={`${recording.recording} · ${round.topic_label}`} subtitle="价值点 / 引导原话"/>
  </div>}
 </details>;
}

function RoundPager({label,page,pages,pageSize,total,onPage,onPageSize}){
 const start=total?page*pageSize+1:0,end=Math.min((page+1)*pageSize,total);
 return <nav className="av-pager" aria-label={`${label}轮次明细分页`}>
  <span aria-live="polite">第 {start}—{end} 条 / 共 {total} 条记录</span>
  <div className="av-page-actions">
   <label>每页 <select aria-label={`${label}每页条数`} value={pageSize} onChange={e=>onPageSize(Number(e.target.value))}><option value={30}>30 条</option><option value={50}>50 条</option></select></label>
   <button type="button" disabled={page===0} onClick={()=>onPage(page-1)}>上一页</button>
   <label>页码 <select aria-label={`${label}跳转页码`} value={page} onChange={e=>onPage(Number(e.target.value))}>{Array.from({length:pages},(_,i)=><option key={i} value={i}>{i+1} / {pages}</option>)}</select></label>
   <button type="button" disabled={page>=pages-1} onClick={()=>onPage(page+1)}>下一页</button>
  </div>
 </nav>;
}

function RecordingDetail({recording:r}){
 const [open,setOpen]=useState(false),[page,setPage]=useState(0),[pageSize,setPageSize]=useState(30);
 const rounds=r.rounds||[],seconds=knownSeconds(r),unknown=hasUnknown(r);
 const counts=useMemo(()=>rounds.reduce((map,x)=>{if(x.countable===true)map.set(x.topic_key,(map.get(x.topic_key)||0)+1);return map;},new Map()),[rounds]);
 const totalCount=[...counts.values()].reduce((a,b)=>a+b,0);
 const rateSeconds=r.review_complete_for_available_text===false?null:seconds;
 const pages=Math.max(1,Math.ceil(rounds.length/pageSize)),currentPage=Math.min(page,pages-1);
 const visible=rounds.slice(currentPage*pageSize,(currentPage+1)*pageSize);
 const changeSize=size=>{setPage(Math.floor(currentPage*pageSize/size));setPageSize(size);};
 const pagerProps={label:r.recording,page:currentPage,pages,pageSize,total:rounds.length,onPage:setPage,onPageSize:changeSize};
 return <details className="cr-review-row av-recording" data-value-recording={r.recording} onToggle={ownToggle(setOpen)}>
  <summary><span>{r.recording}</span><b>已核轮次下限 {lowerBound(totalCount,unknown)} · 可分析 {seconds==null?'待核':`${f(seconds/3600,2)} 小时`}</b></summary>
  {open&&<div className="av-recording-body">
   <p>{r.coverage_note||'采用已审音轨范围，实际主播归属待核。已核次数为观察下限，完整总量待核。'}</p>
   {(r.unknown_ranges||[]).length>0&&<details className="cr-disclosure av-unknown"><summary>证据不足范围 · {(r.unknown_ranges||[]).length} 段</summary>{r.unknown_ranges.map((x,i)=><p key={i} className="cr-footnote">{clock(x.audio_start??x.start)}—{clock(x.audio_end??x.end)} · {x.reason||'语义证据待核，未计轮次。'}</p>)}</details>}
   <Table label={`${r.recording}已核轮次下限`} heads={['主题','每小时','每两小时','已核轮次下限']}>
    {(r.topics||[]).map(t=>{const n=counts.get(t.key)||0;return <tr key={t.key}><td>{t.label}</td><td>{rate(n,rateSeconds,3600)}</td><td>{rate(n,rateSeconds,7200)}</td><td>{lowerBound(n,unknown)}</td></tr>})}
   </Table>
   {rounds.length>0?<>
    <p className="cr-footnote">下方包含全部已核、未计与待核记录。当前页只展示 {pageSize} 条以内；主题汇总使用所有页面的记录。打开具体轮次后加载原话摘录与音频控件。</p>
    <RoundPager {...pagerProps}/>
    <div className="av-round-page" data-value-page={currentPage+1}>{visible.map(x=><RoundDetail key={x.id} round={x} recording={r}/>)}</div>
    <RoundPager {...pagerProps}/>
   </>:<p className="cr-footnote">{unknown?'当前已观察主题轮次为 0，完整总次数待核。':'已审文本未观察到可计主题轮次。'}</p>}
  </div>}
 </details>;
}

export default function AnonymousValueReview({recordings=[]}){
 const [open,setOpen]=useState(false);
 const summary=useMemo(()=>{
  const topics=[...new Map(recordings.flatMap(r=>r.topics||[]).map(t=>[t.key,t.label])).entries()];
  const seconds=recordings.reduce((s,r)=>s+(knownSeconds(r)??0),0);
  const unknownSeconds=recordings.reduce((s,r)=>s+(Number.isFinite(r.unknown_seconds)?r.unknown_seconds:0),0);
  const unknown=recordings.some(hasUnknown)||recordings.some(r=>knownSeconds(r)==null);
  const counted=recordings.flatMap(r=>r.rounds||[]).filter(r=>r.countable===true);
  const topicRows=topics.map(([key,label])=>({key,label,total:counted.filter(r=>r.topic_key===key).length}));
  const ratesAllowed=recordings.every(r=>r.review_complete_for_available_text!==false);
  return {seconds,rateSeconds:ratesAllowed?seconds:null,unknownSeconds,unknown,counted:counted.length,topicRows};
 },[recordings]);
 if(!recordings.length)return null;
 const {seconds,rateSeconds,unknownSeconds,unknown,counted,topicRows}=summary;
 return <div className="av-review" data-reviewed-rows>
  <div className="sh-comment-heading"><h3>已核轮次下限 · 价值点与小风车</h3><span>匿名语义轮次 · 实际主播归属待核</span></div>
  <p className="cr-footnote">可分析文本范围 {f(seconds/3600,2)} 小时，已核主题轮次至少 {counted} 次。{rateSeconds==null?'已审范围仍有未审时段，完整次数及频率待核。':'每小时、每两小时按可分析时长换算。'}连续讲述合并，重新讲解或回应新需求另计。{unknownSeconds>0&&`另有 ${f(unknownSeconds/60,2)} 分钟证据不足，完整总次数仍待核。`}{unknown&&' 已观察 0 仅表示尚无可计证据。'}主播个人评分待实际当班区间闭合。</p>
  <Table label="匿名录音已核轮次下限汇总" heads={['价值点 / 引导','每小时','每两小时','已核轮次下限']}>
   {[...topicRows,{key:'total',label:'已核合计',total:counted}].map(r=><tr key={r.key} className={r.key==='total'?'cr-total':''}><td>{r.label}</td><td>{rate(r.total,rateSeconds,3600)}</td><td>{rate(r.total,rateSeconds,7200)}</td><td>{lowerBound(r.total,unknown)}</td></tr>)}
  </Table>
  <details className="cr-disclosure av-recordings" onToggle={ownToggle(setOpen)}><summary>录音范围与逐轮原话摘录 · {recordings.length} 条录音</summary>
   {open&&recordings.map(r=><RecordingDetail key={`${r.project}:${r.recording}`} recording={r}/>)}
  </details>
 </div>;
}
