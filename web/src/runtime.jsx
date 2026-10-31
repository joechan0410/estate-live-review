import React, {createContext, useContext, useMemo, useState} from 'react';
import ReactMarkdown from 'react-markdown';

const ReviewContext = createContext(null);

/** App-owned adapter. No Data plugin runtime or editor is bundled. */
export function ReviewProvider({snapshot, children}) {
  const [appTitle, setAppTitle] = useState(snapshot.title);
  const value = useMemo(() => ({
    snapshot, appTitle, setAppTitle, canEdit: false, mode: 'view',
    reviewedPeriodRows: id => snapshot.queries[id]?.rows ?? [],
  }), [snapshot, appTitle]);
  return <ReviewContext.Provider value={value}>{children}</ReviewContext.Provider>;
}

export function useDataApp() {
  const context = useContext(ReviewContext);
  if (!context) throw new Error('Report must be rendered inside ReviewProvider');
  return context;
}

export function RichNarrative({value, id}) {
  return <div className="rich-narrative-content" data-narrative={id}>
    <ReactMarkdown>{String(value ?? '')}</ReactMarkdown>
  </div>;
}

export function DataComponent({id, title, queryId, queryIds = [], sourceRows,
  sourceRowsByQuery, displayRows, children}) {
  const {snapshot} = useDataApp();
  const ids = [...new Set([queryId, ...queryIds].filter(Boolean))];
  const rowsByQuery = sourceRowsByQuery ?? Object.fromEntries(ids.map(key => [
    key, key === queryId ? sourceRows ?? displayRows ?? snapshot.queries[key]?.rows ?? []
      : snapshot.queries[key]?.rows ?? [],
  ]));
  return <div className="evidence-component" data-component={id}>
    {children}
    <details className="evidence-source">
      <summary aria-label={`查看来源：${title}`}>查看数据依据</summary>
      <h4>{title}</h4>
      <p>{snapshot.demo ? '合成演示数据 · 可替换为自己的已审核快照。' : '当前快照中的来源与记录。'}</p>
      {Object.entries(rowsByQuery).map(([key, rows]) => <details key={key}>
        <summary>{key} · {rows.length} 条</summary>
        <pre>{JSON.stringify({source: snapshot.queries[key]?.source, rows}, null, 2)}</pre>
      </details>)}
    </details>
  </div>;
}

export function SortableRegion({id, label, children}) {
  return <div className="report-sections" data-region={id} aria-label={label}>{children}</div>;
}
export function SortableItem({id, children}) {
  return <div className="report-section-item" data-section={id}>{children}</div>;
}
