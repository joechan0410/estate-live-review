import React,{useState} from 'react';
import {AudioClip,Table,f} from './ShanghaiPanels.jsx';

const clock=n=>new Date(Math.max(0,n)*1000).toISOString().slice(11,19);
const labels={retained_automatic_consensus_non_speech:'声学复测一致',withheld_all_zero_audio_anomaly:'全零信号待核',below_or_equal_10_seconds_after_split:'复测分段≤10秒',needs_listening_source_clock_continuity:'源时间轴连续性待核',needs_listening_detector_disagreement:'两次检测结果不一致',needs_listening_unlocalized_webrtc_activity:'复测检出语音，位置待听核'};
const label=s=>labels[s]||'待进一步复核';
const anomalyLocation=x=>x.wall_start||(x.audio_start!=null?`${clock(x.audio_start)}—${clock(x.audio_end??x.audio_start)}`:x.possible_audio_range?`可能范围 ${clock(x.possible_audio_range.audio_start)}—${clock(x.possible_audio_range.audio_end)}`:'位置待核');
function Fragment({row:x,recording:r}){
 const [open,setOpen]=useState(false);
 return <tr><td>{clock(x.audio_start)}—{clock(x.audio_end)}</td><td>{f(x.seconds,2)}</td><td><details className="cr-disclosure" onToggle={e=>{if(e.target===e.currentTarget)setOpen(e.currentTarget.open)}}><summary>{label(x.status)} · 试听 {clock(x.audio_start)}</summary>{open&&<AudioClip url={r.audio_url} start={Math.max(0,x.audio_start-3)} end={Math.min(r.recorded_audio_seconds,x.audio_end+3)} title={`${r.recording} · 静默候选`} subtitle="含前后语境；自动检测，未标作人工听核"/>}</details></td></tr>;
}
function Recording({row:r}){
 const [open,setOpen]=useState(false),[limit,setLimit]=useState(30);
 return <details className="cr-review-row" data-silence-recording={r.recording} onToggle={e=>{if(e.target===e.currentTarget)setOpen(e.currentTarget.open)}}>
  <summary><span>{r.recording}</span><b>{r.candidate_count}段原始候选 · {f(r.recorded_audio_seconds/3600,2)}小时录音</b></summary>
  {open&&<div>
   <p className="cr-footnote">自动复测一致 {f(r.automatic_consensus_seconds,2)} 秒；检测结果或时间轴待核 {f(r.listening_required_seconds,2)} 秒；全零信号暂存 {f(r.audio_anomaly_withheld_seconds,2)} 秒。主播静默总量与个人评分待核。</p>
   <Table label={`${r.recording}静默复测分段`} heads={['音轨位置','秒数','处置']}>
    {r.fragments.slice(0,limit).map(x=><Fragment key={x.id} row={x} recording={r}/>)}
   </Table>
   {limit<r.fragments.length&&<button onClick={()=>setLimit(limit+30)}>继续显示30段（共{r.fragments.length}段）</button>}
   {!!r.anomalies.length&&<details className="cr-disclosure"><summary>录制与时钟异常 · {r.anomalies.length}项</summary>{r.anomalies.map(x=><p className="cr-footnote" key={x.id}>{anomalyLocation(x)} · {x.type==='all_zero_pcm_audio_anomaly'?'全零信号，原因待核':'源时钟或录制连续性待核'}；未加入主播静默秒数。</p>)}</details>}
  </div>}
 </details>;
}
export default function AnonymousSilenceReview({recordings=[]}){
 if(!recordings.length)return null;
 return <section className="cr-disclosure" aria-label="未归属录音静默复测">
  <h3>录音静默复测 · {recordings.length}条</h3>
  <p className="cr-footnote">连续严格超过10秒的候选逐段复测；电梯及视频不豁免。以下保留自动检测、待核和录制异常，尚未计入实名主播评分。</p>
  {recordings.map(r=><Recording key={`${r.project}:${r.recording}`} row={r}/>)}
 </section>;
}
