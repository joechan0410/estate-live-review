"""Create auditable subtitle windows and conservative lexical event candidates."""
import json,re,csv,math
from pathlib import Path
ROOT=Path(__file__).resolve().parent
ALIASES={}
GENERAL_TERMS=[]

def load_lexicons(root):
 """Load bundled candidates, then optional project additions and corrections."""
 aliases={};terms={}
 bundled=Path(__file__).resolve().parent/'assets/general-lexicon.csv'
 for lexicon in (bundled,root/'knowledge/general-lexicon.csv'):
  if not lexicon.exists():continue
  with lexicon.open(encoding='utf-8-sig',newline='') as source:
   for item in csv.DictReader(source):
    if item.get('标准词'):terms[item['标准词']]=item
 project=root/'knowledge/project-lexicon.csv'
 if project.exists():
  with project.open(encoding='utf-8-sig',newline='') as source:
   for item in csv.DictReader(source):
    if item.get('auto_correct',item.get('自动纠错','')).lower() in ['true','yes','1','是']:
     standard=item.get('standard',item.get('标准词',''))
     for variant in item.get('variants',item.get('候选误识别','')).split('|'):
      if variant and standard:aliases[variant]=standard
 return aliases,list(terms.values())

CORE={
 '现房实景':r'现房|交付|交房|实景|实体|拎包|精装|装修',
 '教育配套':r'小学|中学|附中|学校|师大|书包|读书|上学|入学|转学',
 '主城区位':r'二环|三环|主城|地铁|公交|通勤|市中心',
 '户型空间':r'户型|三房|四房|三室|四室|横厅|竖厅|采光|楼层|南北|阳台|公摊|面积',
}
WIND=r'小风车|小黄车|小红车|下方小车|小峰车|小丰车|小凤车'
ACTION=r'点|预约|授权|留|填|领|打开|提交|找|按|操作|戳|进入|登记'
def dump_csv(path,rows):
 if not rows:
  path.unlink(missing_ok=True)
  return
 with path.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def normalize_local_segments(chunk, max_window_seconds=25):
 """Clip ASR-relative intervals to the recorded chunk, preserving original text."""
 start,end=chunk['start'],chunk['end']
 if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in (start,end)) or start<0 or end<=start:
  raise ValueError('local ASR chunk needs finite 0 <= start < end')
 grouped=[]
 for seg in chunk['segments']:
  lo,hi=seg['start'],seg['end']
  if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in (lo,hi)):
   raise ValueError('local ASR segment needs finite timestamps')
  if not seg['text'].strip() or hi<=lo:continue
  lo=max(start,start+lo);hi=min(end,start+hi)
  if hi<=lo:continue
  if grouped and lo>=grouped[-1]['start'] and hi-grouped[-1]['start']<=max_window_seconds:
   grouped[-1]['end']=max(grouped[-1]['end'],hi);grouped[-1]['raw']+=seg['text']
  else:grouped.append({'start':lo,'end':hi,'raw':seg['text']})
 return grouped

def process(folder):
 rawpath=folder/'subtitle_snapshots.jsonl'
 if not (folder/'complete.json').exists() or not rawpath.exists():return
 complete=json.loads((folder/'complete.json').read_text()); changes=[]
 for line in rawpath.open():
  s=json.loads(line);text=s['text'].strip()
  if not text:continue
  if changes and changes[-1]['raw']==text:
   changes[-1]['last_observed']=s['offset'];continue
  corrected=text; edits=[]
  for a,b in ALIASES.items():
   if a in corrected:corrected=corrected.replace(a,b);edits.append(f'{a}→{b}')
  obs=s['offset'];prev=changes[-1]['observed'] if changes else 0
  row={'id':f'{folder.name}-T{len(changes)+1:05d}','start':round(prev,3),'end':round(obs,3),'observed':round(obs,3),'last_observed':obs,'observed_wall_time':s.get('program_time'),'raw':text,'text':corrected,'corrections':edits,'source':'platform_asr','timing':'字幕观察窗口'}
  changes.append(row)
 # Local ASR replaces only the independently transcribed missing interval.
 # The source remains explicit; a frozen platform caption is never repeated.
 local=[]
 for path in sorted((folder/'local_asr').glob('*.json')):
  chunk=json.loads(path.read_text())
  grouped=normalize_local_segments(chunk)
  for j,row in enumerate(grouped):
   corrected=row['raw'];edits=[]
   for a,b in ALIASES.items():
    if a in corrected:corrected=corrected.replace(a,b);edits.append(f'{a}→{b}')
   row.update(id=f'{folder.name}-A{path.stem}-{j:03d}',text=corrected,corrections=edits,source='local_asr',asr_model=chunk.get('model'),timing='ASR估计时间',observed=row['end'],last_observed=row['end'],observed_wall_time=None)
  local.extend(grouped)
  changes=[r for r in changes if r['end']<=chunk['start'] or r['start']>=chunk['end']]
 changes=sorted(changes+local,key=lambda r:r['start'])
 events=[];names=[];term_reviews=[]
 for r in changes:
  t=r['text'];wind=bool(re.search(WIND,t))
  operation=bool(re.search(r'(点|点击|点下|点一|按).{0,12}(预约|授权)|预约.{0,7}(点|点击)|下方.{0,15}预约|显示.{0,5}预约成功|(?:下方|下面|左下角).{0,25}(?:点|领取).{0,15}(?:福利|补贴|资料|登记)|(?:领取福利|领取补贴).{0,20}(?:点|授权|预约)',t))
  cta=(wind and bool(re.search(ACTION,t))) or operation
  r['windmill_mention']=wind;r['windmill_cta_candidate']=cta;r['cta_basis']='组件名称' if wind and cta else ('预约组件操作' if operation else None)
  r['core_topics']=[k for k,p in CORE.items() if re.search(p,t)]
  r['filler_tokens']=len(re.findall(r'呃|嗯|那个|就是说|然后|就是|的话',t))
  for term in GENERAL_TERMS:
   for variant in term.get('候选误识别','').split('|'):
    if len(variant)>=2 and variant in r['raw']:
     term_reviews.append({'transcript_id':r['id'],'start':r['start'],'end':r['end'],'observed':variant,'candidate':term['标准词'],'rule':term.get('纠错规则',''),'status':'术语候选，须按语境核实，不自动替换','context':r['raw']})
  if cta:events.append({k:r[k] for k in ['id','start','end','observed_wall_time','text']})
  if re.search(r'我是.{0,12}主播|我叫|主播.{0,6}(叫|是)|下.{0,4}主播|换.{0,4}主播|我.{0,3}下播',t):names.append(r)
 (folder/'transcript.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2))
 dump_csv(folder/'transcript.csv',[{k:(json.dumps(v,ensure_ascii=False) if isinstance(v,list) else v) for k,v in r.items()} for r in changes])
 dump_csv(folder/'windmill_cta_candidates.csv',events)
 dump_csv(folder/'term_review_candidates.csv',term_reviews)
 episodes=[]
 for i,r in enumerate(changes):
  if not r['windmill_cta_candidate']:continue
  if episodes and i==episodes[-1]['last_index']+1 and r['start']-episodes[-1]['end']<10:
   episodes[-1]['end']=r['end'];episodes[-1]['last_index']=i;episodes[-1]['ids'].append(r['id']);episodes[-1]['text']+=r['text']
  else:episodes.append({'start':r['start'],'end':r['end'],'last_index':i,'ids':[r['id']],'text':r['text']})
 (folder/'cta_episodes.json').write_text(json.dumps(episodes,ensure_ascii=False,indent=2))
 (folder/'name_evidence_candidates.json').write_text(json.dumps(names,ensure_ascii=False,indent=2))
 print(json.dumps({'label':folder.name,'transcript_windows':len(changes),'cta_windows':len(events),'cta_episodes':len(episodes),'name_candidates':len(names)},ensure_ascii=False))
if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);args=parser.parse_args();ROOT=args.root.resolve()
 ALIASES,GENERAL_TERMS=load_lexicons(ROOT)
 for f in sorted((ROOT/'data').iterdir()):
  if f.is_dir():process(f)
