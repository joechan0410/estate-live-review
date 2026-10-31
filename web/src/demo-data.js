/** Deterministic fictional fixtures. No production data is read by this module. */
export const PROJECTS=['示例楼盘 A','示例楼盘 B','示例楼盘 C'];
export const HOSTS=['主播甲','主播乙','主播丙'];
export const WEEKS=['2026-09-12','2026-09-19'];
export const GRADE_THRESHOLDS={A:80,B:65};
export const demoGrade=score=>score>=GRADE_THRESHOLDS.A?'A':score>=GRADE_THRESHOLDS.B?'B':'C';
export const DIMENSIONS=[['lead','留资效率',25],['interaction','互动效率',11],['conversion','评论后留资',16],['core','价值讲透',5],['flow','表达组织',11],['cta','小风车引导',16],['silence','静默控制',16]];
const TOPICS=['户型空间','区位交通','生活配套','交付品质','小风车'];
const AUDIO='./audio/demo-tones.wav';
const QUESTIONS=[
 ['价格预算','三房大概需要多少预算？','先确认总价预算，再说明不同面积的价格范围，提供房源对照表。','确认预算与可选范围'],
 ['户型房源','有适合三口之家的户型吗？','展示三房的动静分区、收纳位置和书房用途，询问家庭的使用习惯。','连接家庭需要与空间用途'],
 ['区位交通','上班通勤可以怎么走？','先问工作地点，按轨道交通、自驾两种方式说明路线和换乘。','确认出发点并解释路线'],
 ['看房留资','周末可以预约看样板间吗？','说明可选时段，指引点击预约入口并确认提交成功，再发送到访路线。','明确预约操作并确认完成'],
];
const KEYS=`weekly daily host_rollup host_dimensions host_content_summary host_profile_evidence host_intervals host_value_blocks project_value_blocks project_value_topics project_coverage confirmed_host_identity pending_host_confirmation question_details named_topics customer_attributions comment_response_coverage comment_question_frequency comment_answer_effectiveness comment_acquisition_findings component_audit comment_lead_audit interaction_recheck lead_credit_audit reply_cohorts silence_coverage silence_events silence_shifts host_comment_strategies host_cta_quality_evidence stage_evidence reviewed_presenter_passages anonymous_content_units anonymous_content_summary anonymous_content_unscored anonymous_value_recordings anonymous_silence_recordings comment_intent_scope comment_intent_separate_counts accepted_conversion_strategy_lower_bounds accepted_conversion_strategy_scope`.split(' ');
const sum=(rows,key)=>rows.reduce((n,r)=>n+(r[key]??0),0);
const rounded=n=>Number(n.toFixed(6));
function createWeek(wi){
 const q=Object.fromEntries(KEYS.map(k=>[k,[]])),add=(key,row)=>q[key].push(row),firstDay=6+wi*7;
 PROJECTS.forEach((project,pi)=>{
  const date=`2026-09-${String(firstDay).padStart(2,'0')}`,recording=`demo-${pi+1}-week-${wi+1}`;
  HOSTS.forEach((host,hi)=>{
   const person_id=`demo-project-${pi+1}-host-${hi+1}`,id=`${person_id}-week-${wi+1}`,hours=2+pi*.5+hi*.25+wi*.25,leads=6+hi+wi,participants=12,cn=4+wi;
   const scores=[76+hi*4+wi*3,84-hi*3+wi*2,74+hi*3+wi*3,85-hi*5+pi,81+hi*2,80+hi*4+wi,91-hi*3];
   const score=rounded(DIMENSIONS.reduce((n,[,,weight],i)=>n+scores[i]*weight/100,0));
   add('host_rollup',{project,host,person_id,hours,operating_hours:hours,intervals:1,participants,leads,participants_per_hour:participants/hours,lead_per_hour:leads/hours,conversion_n:cn,conversion_d:12,cta_per_hour:8+hi,silence_per_hour:35+hi*12,score,final_score:score,grade:demoGrade(score),weight_coverage:100,score_is_full_period:true,score_scope:'合成演示 · 七项完整评分',score_total_min:score,score_total_max:score,silence_score:scores[6],silence_contribution:scores[6]*.16});
   DIMENSIONS.forEach(([key,dimension,weight],i)=>add('host_dimensions',{project,host,person_id,key,dimension,weight,score:scores[i],contribution:scores[i]*weight/100,contribution_min:scores[i]*weight/100,contribution_max:scores[i]*weight/100,native_score:key==='core'?scores[i]/20:key==='flow'?scores[i]*.11:scores[i],native_max:key==='core'?5:key==='flow'?11:100,reason:'合成评分示例，展示原生量表与加权贡献。',...(key==='cta'?{quality_score:scores[i],frequency_score:scores[i],quality_share:.6,frequency_share:.4,reviewed_sample_rounds:1,selected_sample_rounds:1,quality_reviewed_hours:10/3600,quality_scope:'合成引导任务，展示质量分与频次分的组合。',quality_time_basis:'合成样本定位窗口；音频为程序生成提示音。',whole_week_quality_review_complete:true}:{})}));
   add('host_cta_quality_evidence',{project,host,person_id,id:`${id}-cta`,quality_score:scores[5],audio_url:AUDIO,audio_start:0,audio_end:10,summary:'说明可领取的资料，再指引点击预约入口并确认完成。',synthetic:true});
   add('host_content_summary',{project,host,person_id,strength:['先问家庭需要，再用空间用途解释户型价值。','价格回答给出范围，用房源对照帮助客户继续选择。','预约操作清楚，确认提交结果后补充到访路线。'][hi],weakness:['可增加预算与通勤追问，让选择条件更明确。','配套讲述可加入具体的日常使用场景。','资料介绍可压缩重复句，给客户留出提问时间。'][hi]});
   add('host_profile_evidence',{project,host,person_id,id:`${id}-profile`,date,time:'10:00',recording,audio_label:'程序生成提示音',audio_url:AUDIO,audio_start:0,audio_end:10,strength:'把户型特点与家庭需要联系起来。',weakness:'预算追问还可以更具体。'});
   add('host_intervals',{project,host,person_id,id:`${id}-shift`,date,time:'10:00—12:00',hours,comment_people:participants,leads,comment_people_per_hour:participants/hours,leads_per_hour:leads/hours,watch_per_hour:150,comment_per_100_views:4,lead_per_100_views:2,traffic_coverage:1,identity_evidence_level:'synthetic_fixture'});
   const values={project,host,person_id,shift_id:`${id}-shift`,date,time:'10:00',hours};TOPICS.forEach((t,i)=>{values[t]=5+hi+i+wi});values.total=TOPICS.reduce((n,t)=>n+values[t],0);add('host_value_blocks',values);add('project_value_blocks',{...values});
   QUESTIONS.forEach(([category,question,answer,strategy],ci)=>{
    for(let n=0;n<3;n++){
     const qid=`${id}-q-${ci+1}-${n+1}`,converted=ci===0||(ci===1&&n<1+wi);
     const r={id:qid,project,host,person_id,date,comment_time:`${date}T10:${String(ci*8+n).padStart(2,'0')}:00+08:00`,category,original_category:category,question,answer,answered:true,reply_confirmed:true,effective_comment:true,assessment:'确认需求，补充可比较的信息，并给出具体下一步。',suggestion:'先确认最关键的预算或使用需要，再提供对应资料。',outcome:converted?'合成客户在问答后完成预约。':'合成客户本次问答后未提交预约。',converted,lead_badge:converted,lead_status_label:converted?'演示 · 已预约':'演示 · 未预约',audio_url:AUDIO,audio_start:ci*3,audio_end:ci*3+6};
     add('question_details',r);add('customer_attributions',{project,host,person_id,id:`${qid}-outcome`,category,last_comment_id:qid,converted,included:true});
     add('comment_lead_audit',{...r,customer_key:`synthetic-${qid}`,time:r.comment_time,content:question,effective:true,is_operator:false,lead_status:r.outcome,badge_lead_count:converted?1:0,matched_lead_count:converted?1:0,lead_time:converted?`${date}T11:00:00+08:00`:null});
    }
    const case_keys=q.question_details.filter(r=>r.person_id===person_id&&r.category===category).map(r=>r.id);
    add('named_topics',{project,name:host,topic:category,pattern:strategy,gap:'可继续补充一个客户选择条件。',case_keys});
    add('host_comment_strategies',{project,host,person_id,category,strategy,customers:3,conversions:ci===0?3:ci===1?1+wi:0,examples:[]});
   });
   add('silence_shifts',{project,host,person_id,id:`${id}-silence`,analyzed_hours:hours,detected_seconds:(35+hi*12)*hours,detected_count:2,confirmed_excluded_seconds:0,longest_seconds:18,visual_sampled_count:2});
   add('reply_cohorts',{project,cohort_id:`${id}-cohort`,scope:`${host} · 第${wi+1}周`,comment_people:participants,reviewed_comments:12,numerator:cn,denominator:12,rate_pct:cn/12*100});
  });
  const hosts=q.host_rollup.filter(r=>r.project===project),questions=q.question_details.filter(r=>r.project===project),hours=sum(hosts,'hours'),leads=sum(hosts,'leads'),comments=sum(hosts,'participants');
  add('weekly',{project,account:`${project} · 演示直播间`,hours,scenes:7,comments,leads,viewers:2700+pi*300,spend:2100+pi*350,raw_comments:questions.length+3,operator_comments:3});
  for(let day=0;day<7;day++){const dailyComments=day===0?6:5,dailyLeads=Math.floor(leads/7)+(day<leads%7?1:0);add('daily',{project,date:`2026-09-${String(firstDay+day).padStart(2,'0')}`,hours:hours/7,comments:dailyComments,leads:dailyLeads,spend:300+pi*50,comment_per_hour:dailyComments/(hours/7),lead_per_hour:dailyLeads/(hours/7)});}
  add('project_value_topics',{project,topics:TOPICS,definition:'同一连续讲述按一轮计数。'});add('project_coverage',{project,backend_hours:hours,named_hours:hours,reviewed_questions:questions.length});
  add('comment_response_coverage',{project,raw_comments:questions.length+3,primary_reviewed_assessed_comments:questions.length,primary_reviewed_comments:questions.length,excluded_team_comments:3,excluded_comments:3,needs_response_review:0,capture_complete:true});
  add('interaction_recheck',{project,scope_label:'合成周度',badge_comment_people:questions.filter(r=>r.converted).length,excluded_social_rows:0,social_with_lead_retained:0,qualification_pending:0,qualification_summary:true});
  add('silence_coverage',{project,recording,recorded_hours:hours,raw_candidate_seconds:240,confirmed_exclusion_overlap_seconds:0,retained_vad_seconds:240});
  QUESTIONS.forEach(([category,question,,strategy],ci)=>{add('comment_question_frequency',{project,category,question_count:9,comment_count:9,customers:9,share_pct:25,examples:[question]});add('comment_answer_effectiveness',{project,category,strategy,customers:9,conversions:ci===0?9:ci===1?3+3*wi:0,examples:questions.filter(r=>r.category===category).slice(0,1)});});
  add('comment_acquisition_findings',{project,title:'需求与答法对应',text:'预算、户型和预约问题采用不同回答路径，便于观察同类问题的后续结果。'});add('comment_acquisition_findings',{project,title:'把下一步说具体',text:'确认使用需要，再提供对应资料与预约操作。'});
  add('component_audit',{project,scene_id:`${recording}-scene`,date,time:'10:00—12:00',hours,clicks:35,leads,comment_people:comments,watch_people:2700+pi*300,spend:2100+pi*350});
  const rounds=TOPICS.map((topic,i)=>({id:`${recording}-round-${i}`,topic_key:topic,topic_label:topic,audio_start:i*3,audio_end:i*3+5,countable:true,summary:`${topic}的合成讲解示例。`,semantic_rationale:'用于演示逐轮证据与音轨定位。',evidence:[{raw_text:'合成文本，用于展示证据结构。'}]}));
  add('anonymous_value_recordings',{project,recording,audio_url:AUDIO,denominator_seconds:24,review_complete_for_available_text:true,full_total_unknown:false,total_count:rounds.length,unknown_seconds:0,topics:TOPICS.map(label=>({key:label,label})),rounds,unknown_ranges:[],coverage_note:'合成轮次演示。音频为程序生成提示音，用于体验播放与定位。'});
 });return q;
}
function cumulative(weeks){
 const q=Object.fromEntries(KEYS.map(k=>[k,weeks.flatMap(w=>w[k])]));
 q.weekly=PROJECTS.map(project=>{const rows=q.weekly.filter(r=>r.project===project);return {project,account:`${project} · 演示直播间`,...Object.fromEntries(['hours','scenes','comments','leads','viewers','spend','raw_comments','operator_comments'].map(k=>[k,sum(rows,k)]))};});
 q.host_rollup=PROJECTS.flatMap(project=>HOSTS.map(host=>{const rows=q.host_rollup.filter(r=>r.project===project&&r.host===host),hours=sum(rows,'hours'),leads=sum(rows,'leads'),participants=sum(rows,'participants'),score=rounded(rows.reduce((n,r)=>n+r.score*r.hours,0)/hours);return {...rows[0],hours,operating_hours:hours,leads,participants,intervals:rows.length,participants_per_hour:participants/hours,lead_per_hour:leads/hours,conversion_n:sum(rows,'conversion_n'),conversion_d:sum(rows,'conversion_d'),cta_per_hour:rows.reduce((n,r)=>n+r.cta_per_hour*r.hours,0)/hours,silence_per_hour:rows.reduce((n,r)=>n+r.silence_per_hour*r.hours,0)/hours,score,final_score:score,grade:demoGrade(score),score_total_min:score,score_total_max:score};}));
 q.host_dimensions=q.host_rollup.flatMap(host=>DIMENSIONS.map(([key])=>{const rows=weeks.flatMap(w=>w.host_dimensions.filter(r=>r.person_id===host.person_id&&r.key===key)),base=rows[0],score=rows.reduce((n,r,i)=>n+r.score*weeks[i].host_rollup.find(h=>h.person_id===host.person_id).hours,0)/host.hours;return {...base,score,contribution:score*base.weight/100,contribution_min:score*base.weight/100,contribution_max:score*base.weight/100,native_score:score*base.native_max/100};}));
 q.host_content_summary=weeks.at(-1).host_content_summary;q.project_value_topics=weeks[0].project_value_topics;
 q.host_comment_strategies=weeks[0].host_comment_strategies.map(base=>{const rows=weeks.flatMap(w=>w.host_comment_strategies.filter(r=>r.person_id===base.person_id&&r.category===base.category&&r.strategy===base.strategy));return {...base,customers:sum(rows,'customers'),conversions:sum(rows,'conversions'),examples:rows.flatMap(r=>r.examples)};});
 q.host_dimensions=q.host_dimensions.map(d=>d.key==='cta'?{...d,quality_score:d.score,frequency_score:d.score,reviewed_sample_rounds:weeks.length,selected_sample_rounds:weeks.length,quality_reviewed_hours:weeks.length*10/3600}:d);
 q.project_coverage=PROJECTS.map(project=>({project,backend_hours:sum(q.weekly.filter(r=>r.project===project),'hours'),reviewed_questions:q.question_details.filter(r=>r.project===project).length}));
 q.comment_response_coverage=PROJECTS.map(project=>({project,...Object.fromEntries(['raw_comments','primary_reviewed_assessed_comments','primary_reviewed_comments','excluded_team_comments','excluded_comments','needs_response_review'].map(k=>[k,sum(weeks.flatMap(w=>w.comment_response_coverage.filter(r=>r.project===project)),k)]))}));
 q.interaction_recheck=PROJECTS.map(project=>({project,scope_label:'合成累计',badge_comment_people:q.question_details.filter(r=>r.project===project&&r.converted).length,excluded_social_rows:0,social_with_lead_retained:0,qualification_pending:0,qualification_summary:true}));
 q.comment_question_frequency=PROJECTS.flatMap(project=>QUESTIONS.map(([category,question])=>({project,category,question_count:18,comment_count:18,customers:18,share_pct:25,examples:[question]})));
 q.comment_answer_effectiveness=PROJECTS.flatMap(project=>QUESTIONS.map(([category,,,strategy])=>{const rows=weeks.flatMap(w=>w.comment_answer_effectiveness.filter(r=>r.project===project&&r.category===category));return {project,category,strategy,customers:sum(rows,'customers'),conversions:sum(rows,'conversions'),examples:rows.flatMap(r=>r.examples).slice(0,2)};}));
 q.comment_acquisition_findings=weeks.at(-1).comment_acquisition_findings;return q;
}
export function buildDemoSnapshot(selectedWeek=WEEKS.at(-1)){
 const wi=WEEKS.indexOf(WEEKS.includes(selectedWeek)?selectedWeek:WEEKS.at(-1)),weeks=WEEKS.map((_,i)=>createWeek(i)),queries={};
 const bind=(input,prefix,sourceWeeks)=>Object.entries(input).forEach(([key,rows])=>{queries[prefix+key]={rows,source:{provider:'synthetic-demo-generator',source_weeks:sourceWeeks,description:'合成演示数据；无真实客户、项目或直播记录。'}};});
 bind(weeks[wi],'',[WEEKS[wi]]);bind(cumulative(weeks),'period__cumulative__',WEEKS);
 return {id:'estate-live-review-demo',title:'地产直播复盘报告',surface:'report',demo:true,buildStatus:'complete',report:{asOf:WEEKS[wi]},queries,periodViews:[{id:'cumulative',type:'cumulative',label:'累计',periodLabel:'示例累计 · 9月6日—19日',periodFooter:'2 周合成演示 · 全部记录可展开',sourceWeeks:WEEKS,queryPrefix:'period__cumulative__'},{id:'month:2026-09',type:'monthly',label:'2026年9月',periodLabel:'示例月度 · 9月已覆盖两周',periodFooter:'9 月合成演示 · 覆盖 9月6日—19日',sourceWeeks:WEEKS,datasetsRef:'cumulative'}]};
}
