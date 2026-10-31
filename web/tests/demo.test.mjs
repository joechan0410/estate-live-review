import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {buildDemoSnapshot,PROJECTS,HOSTS,WEEKS,DIMENSIONS,GRADE_THRESHOLDS,demoGrade} from '../src/demo-data.js';
import {REPORT_WEEKS,reportWeekHref} from '../src/report/report-weeks.js';
const rows=(snapshot,key)=>snapshot.queries[key].rows;

test('two weekly snapshots cover three projects, three hosts and seven dimensions',()=>{
 assert.deepEqual(REPORT_WEEKS.map(w=>w.id).sort(),WEEKS);
 for(const week of WEEKS){
  const s=buildDemoSnapshot(week);
  assert.equal(s.report.asOf,week);
  assert.deepEqual(rows(s,'weekly').map(r=>r.project),PROJECTS);
  assert.equal(rows(s,'host_rollup').length,PROJECTS.length*HOSTS.length);
  for(const h of rows(s,'host_rollup')){
   const d=rows(s,'host_dimensions').filter(r=>r.person_id===h.person_id);
   assert.equal(d.length,7);assert.equal(d.reduce((n,r)=>n+r.weight,0),100);
   assert.ok(Math.abs(d.reduce((n,r)=>n+r.contribution,0)-h.final_score)<1e-5);
  }
  for(const project of PROJECTS){
   const total=rows(s,'weekly').find(r=>r.project===project);
   const daily=rows(s,'daily').filter(r=>r.project===project);
   for(const field of ['hours','comments','leads','spend'])assert.ok(Math.abs(daily.reduce((n,r)=>n+r[field],0)-total[field])<1e-8,field);
  }
 }
 assert.equal(DIMENSIONS.reduce((n,r)=>n+r[2],0),100);
});

test('cumulative merges counts and hours; monthly resolves the same two-week data',()=>{
 const weeks=WEEKS.map(buildDemoSnapshot),s=weeks[1],prefix='period__cumulative__';
 const monthly=s.periodViews.find(v=>v.type==='monthly');
 assert.equal(monthly.datasetsRef,'cumulative');assert.deepEqual(monthly.sourceWeeks,WEEKS);
 for(const current of rows(s,prefix+'weekly')){
  for(const field of ['hours','comments','leads','scenes']){
   const expected=weeks.reduce((n,w)=>n+rows(w,'weekly').find(r=>r.project===current.project)[field],0);
   assert.ok(Math.abs(current[field]-expected)<1e-8);
  }
 }
 assert.equal(rows(s,prefix+'question_details').length,216);
 for(const host of rows(s,prefix+'host_rollup')){
  const dims=rows(s,prefix+'host_dimensions').filter(d=>d.person_id===host.person_id);
  assert.ok(Math.abs(dims.reduce((n,d)=>n+d.contribution,0)-host.final_score)<1e-5);
  const answers=rows(s,prefix+'question_details').filter(r=>r.person_id===host.person_id);
  assert.equal(answers.length,host.conversion_d);
  assert.equal(answers.filter(r=>r.converted).length,host.conversion_n);
  const strategies=rows(s,prefix+'host_comment_strategies').filter(r=>r.person_id===host.person_id);
  assert.equal(strategies.length,4);
  assert.equal(new Set(strategies.map(r=>`${r.category}:${r.strategy}`)).size,strategies.length);
  assert.equal(strategies.reduce((n,r)=>n+r.customers,0),host.conversion_d);
  assert.equal(strategies.reduce((n,r)=>n+r.conversions,0),host.conversion_n);
 }
});

test('all fixtures have synthetic provenance, unique question ids and playable local media',()=>{
 const s=buildDemoSnapshot();
 const qs=rows(s,'period__cumulative__question_details');
 assert.equal(new Set(qs.map(q=>q.id)).size,qs.length);
 for(const q of Object.values(s.queries)){assert.ok(Array.isArray(q.rows));assert.equal(q.source.provider,'synthetic-demo-generator');}
 assert.deepEqual(JSON.parse(readFileSync(new URL('../src/report/audio-segments.json',import.meta.url),'utf8')),{});
 const wav=readFileSync(new URL('../public/audio/demo-tones.wav',import.meta.url));
 assert.equal(wav.subarray(0,4).toString(),'RIFF');assert.equal(wav.subarray(8,12).toString(),'WAVE');
 assert.equal((wav.length-44)/16000,24);
 assert.ok(qs.every(q=>q.audio_start>=0&&q.audio_end<24&&q.audio_url==='./audio/demo-tones.wav'));
});

test('week navigation preserves project and deployment subpath',()=>{
 const url=reportWeekHref(WEEKS[0],PROJECTS[2],{href:'https://example.test/review/?period=cumulative'});
 const parsed=new URL(url);assert.equal(parsed.pathname,'/review/');assert.equal(parsed.searchParams.get('project'),PROJECTS[2]);assert.equal(parsed.searchParams.get('week'),WEEKS[0]);assert.equal(parsed.searchParams.has('period'),false);
 assert.equal(buildDemoSnapshot('unknown').report.asOf,WEEKS[1]);
});

test('weekly and cumulative grades follow the shared scoring policy thresholds',()=>{
 const policy=JSON.parse(readFileSync(new URL('../../pipeline/assets/scoring-policy.json',import.meta.url),'utf8'));
 assert.deepEqual(GRADE_THRESHOLDS,policy.grade_thresholds);
 assert.equal(demoGrade(80),'A');assert.equal(demoGrade(79.99),'B');
 assert.equal(demoGrade(65),'B');assert.equal(demoGrade(64.99),'C');
 for(const week of WEEKS){const s=buildDemoSnapshot(week);for(const prefix of ['', 'period__cumulative__']){
  for(const host of rows(s,prefix+'host_rollup'))assert.equal(host.grade,demoGrade(host.final_score));
 }}
});
