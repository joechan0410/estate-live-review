export const REPORT_WEEKS = Object.freeze([
 {id:'2026-09-19',start:'2026-09-13',label:'第 2 周 · 9月13日—19日',periodLabel:'示例周期 · 9月13日—19日',periodFooter:'第 2 周 · 合成演示'},
 {id:'2026-09-12',start:'2026-09-06',label:'第 1 周 · 9月6日—12日',periodLabel:'示例周期 · 9月6日—12日',periodFooter:'第 1 周 · 合成演示'},
]);
export const currentReportWeek = snapshot => REPORT_WEEKS.find(w=>w.id===snapshot.report?.asOf) ?? REPORT_WEEKS[0];
export function initialReportProject(rows,location=globalThis.location){
 const requested=location?.href?new URL(location.href).searchParams.get('project'):null;
 return rows.some(r=>r.project===requested)?requested:rows[0]?.project;
}
export function reportWeekHref(id,project,location=globalThis.location){
 if(!REPORT_WEEKS.some(w=>w.id===id)||!location?.href)return null;
 const url=new URL(location.href);url.searchParams.set('week',id);url.searchParams.delete('period');
 if(project)url.searchParams.set('project',project);return url.href;
}
