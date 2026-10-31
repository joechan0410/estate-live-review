import React from 'react';
import {createRoot} from 'react-dom/client';
import {ReviewProvider} from './runtime.jsx';
import {buildDemoSnapshot} from './demo-data.js';
import {ReportContent} from './report/ReportContent.jsx';
import './base.css';

const week = new URL(location.href).searchParams.get('week');
const snapshot = buildDemoSnapshot(week);

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ReviewProvider snapshot={snapshot}>
      <div className="demo-bar"><span>Estate Live Review</span><p>开源演示 · 全部数据为合成示例</p><a href="#cr-audit">查看明细</a></div>
      <main className="report-page"><ReportContent /></main>
    </ReviewProvider>
  </React.StrictMode>,
);
