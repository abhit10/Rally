import React, { useState } from 'react';
import { ArrowDownToLine, Crosshair, Zap, Shield, TrendingUp, AlertTriangle, FileText } from 'lucide-react';

export type Coaching = {
  version?: number; calibrated?: boolean; heatmap?: Record<string,number[][]>; trajectory?: Record<string,number[][]>;
  distance_m?: Record<string,number|null>; speed_mps?: Record<string,number|null>; zone_split?: Record<string,{net_pct:number|null;rear_pct:number|null;observed_seconds:number}>;
  sprints?: Record<string,number|null>; work_rate_pct?: Record<string,number|null>; front_court_leader?: string|null;
  longest_rally?: {duration_s:number;shots:number}|null; average_rally_seconds?: number|null;
  work_rest_ratio?: number|null; rally_pace_spm?: number|null; peak_shot_kmh?: number|null;
  rally_distribution?: Record<string,number>; coaching_advice?: string[]; rallies?: number[];
  player_visibility_pct?: Record<string,number|null>;
  review_moments?: {time:number;title:string;detail:string}[];
  high_intensity_seconds?: Record<string,number|null>;
  estimated_hits?: number; rally_seconds?: number; rally_count?: number;
  work_seconds?: number|null; rest_seconds?: number|null;
};
export const value = (n:number|null|undefined, unit='') => n == null ? '—' : `${Number(n.toFixed(1))}${unit}`;
export const matchStatus = (status?:string) => ({ready:'Ready to review',queued:'Waiting to begin',loading:'Preparing match',processing:'Reviewing match',encoding:'Finishing report',completed:'Report ready',failed:'Review interrupted',cancelled:'Review stopped',deleting:'Removing session',deletion_failed:'Removal interrupted'}[status||''] || 'Ready for your first session');
export const rallyStatus = (state?:string) => ({IN_RALLY:'Rally in progress',RALLY_ENDED:'Rally complete',UPDATE_SCORE:'Preparing next rally'}[state||''] || 'Preparing to serve');
export const friendlyError = (message:string) => /cuda|onnx|pytorch|weights|traceback|provider|inference|gpu/i.test(message) ? 'Match analysis is unavailable. Please check the local setup and try again.' : message;
export const profiles = {
  balanced:{label:'Balanced (Standard Match Analysis)',help:'Review rallies, court positioning and work rate with balanced detail and turnaround.',pose:'yolo-small',stride:2},
  fast:{label:'Fast Mode (Quick Screening)',help:'Find key match patterns sooner. Brief contacts and quick movements may be missed.',pose:'yolo-nano',stride:3},
  deep:{label:'Deep Analysis (Form & Stroke Technique)',help:'Capture more movement detail for a coach-led technique review. Allow more time; stroke grading is not automatic.',pose:'rtmpose',stride:1},
};
export type Profile = keyof typeof profiles;
export function ProfilePicker({profile,onChange}:{profile:Profile;onChange:(profile:Profile)=>void}) {
  return <label className="profile-picker">Analysis profile<select aria-describedby="profile-help" value={profile} onChange={e=>onChange(e.target.value as Profile)}>{Object.entries(profiles).map(([key,p])=><option key={key} value={key}>{p.label}</option>)}</select><small id="profile-help" title={profiles[profile].help}>{profiles[profile].help}</small></label>;
}
export function CoachingStats({data}:{data:Coaching}) {
  const cards = [
    ['Longest rally',value(data.longest_rally?.duration_s,' s'),data.longest_rally?.shots!=null?`${data.longest_rally.shots} shots`:'Complete a rally to begin'],
    ['Average rally',value(data.average_rally_seconds,' s'),'Completed rallies'],
    ['High-intensity sprints',`A ${value(data.sprints?.A)} · B ${value(data.sprints?.B)}`,'Sustained bursts during rallies'],
    ['Average rally pace',value(data.rally_pace_spm,' shots/min'),'Exchange frequency across completed rallies'],
  ];
  return <div className="stats-grid">{cards.map(([label,amount,note])=><div className="panel stat-card" key={label}><span className="stat-label">{label}</span><div className="stat-value">{amount}</div><span className="stat-note">{note}</span></div>)}</div>;
}

export function SwotAnalysis({ data }: { data: Coaching }) {
  const [player, setPlayer] = useState<'A' | 'B'>('A');

  const getSwot = (p: 'A' | 'B') => {
    const opp = p === 'A' ? 'B' : 'A';
    const dist = data.distance_m?.[p] ?? 0;
    const oppDist = data.distance_m?.[opp] ?? 0;
    const netPct = data.zone_split?.[p]?.net_pct ?? 0;
    const rearPct = data.zone_split?.[p]?.rear_pct ?? 0;
    const sprints = data.sprints?.[p] ?? 0;
    const workRate = data.work_rate_pct?.[p] ?? 0;

    const strengths = [];
    if (netPct >= 35) strengths.push(`⚡ High Net Dominance: Controls ${netPct}% of rally exchanges in front court.`);
    if (dist >= oppDist && dist > 0) strengths.push(`🏃 Superior Mobility: Covered ${dist}m, out-ranging opponent.`);
    if (sprints > 0) strengths.push(`💥 Burst Acceleration: Executed ${sprints} high-intensity rally sprints.`);
    if (!strengths.length) strengths.push(`🎯 Solid Baseline Continuity: Maintained structured positioning.`);

    const weaknesses = [];
    if (rearPct >= 65) weaknesses.push(`🛡️ Deep Court Trap: Pushed to rear court ${rearPct}% of match time.`);
    if (workRate < 35 && workRate > 0) weaknesses.push(`⚠️ Fatigue Sensitivity: Work rate drops to ${workRate}% in long rallies.`);
    if (dist < 15 && dist > 0) weaknesses.push(`🐢 Limited Lateral Spread: Movement total constrained to ${dist}m.`);
    if (!weaknesses.length) weaknesses.push(`⏳ Recovery Lag: Brief hesitation transitioning from defense to attack.`);

    const opportunities = [];
    if (data.front_court_leader === p) opportunities.push(`🎾 Net Aggression: Use sharp drop shots to capitalize on front-court leadership.`);
    else opportunities.push(`🚀 Cross-Court Passing: Exploit open angles to pull Player ${opp} away from net.`);
    opportunities.push(`📈 Pace Pressure: Force tempo above ${data.rally_pace_spm || 55} shots/min in early exchanges.`);

    const threats = [];
    if (data.front_court_leader === opp) threats.push(`🔥 Opponent Net Dominance: Player ${opp} currently controls front-court angles.`);
    if ((data.longest_rally?.duration_s || 0) > 10) threats.push(`⚡ Endurance Strain: Marathon rallies (${data.longest_rally?.duration_s}s) risk stamina drain.`);
    threats.push(`🎯 Corner Placement Risks: High vulnerability to sudden wide-baseline counterpunches.`);

    return { strengths, weaknesses, opportunities, threats };
  };

  const swot = getSwot(player);

  return (
    <section className="panel swot-panel">
      <div className="panel-title">
        <div>
          <h2><span className="title-icon"><Zap size={18}/></span> Player SWOT Analysis</h2>
          <p>AI tactical profile generated from movement, positioning, and rally tempo</p>
        </div>
        <div className="player-toggle">
          <button className={player==='A'?'active':''} onClick={()=>setPlayer('A')}>Player A</button>
          <button className={player==='B'?'active':''} onClick={()=>setPlayer('B')}>Player B</button>
        </div>
      </div>
      <div className="swot-grid">
        <div className="swot-card strength">
          <span className="swot-badge"><Zap size={12}/> STRENGTHS</span>
          <ul>{swot.strengths.map((item, i)=><li key={i}>{item}</li>)}</ul>
        </div>
        <div className="swot-card weakness">
          <span className="swot-badge"><AlertTriangle size={12}/> WEAKNESSES</span>
          <ul>{swot.weaknesses.map((item, i)=><li key={i}>{item}</li>)}</ul>
        </div>
        <div className="swot-card opportunity">
          <span className="swot-badge"><TrendingUp size={12}/> OPPORTUNITIES</span>
          <ul>{swot.opportunities.map((item, i)=><li key={i}>{item}</li>)}</ul>
        </div>
        <div className="swot-card threat">
          <span className="swot-badge"><Shield size={12}/> THREATS</span>
          <ul>{swot.threats.map((item, i)=><li key={i}>{item}</li>)}</ul>
        </div>
      </div>
    </section>
  );
}

export function CoachFocus({data,onReview}:{data:Coaching;onReview:(time:number)=>void}) {
  return <aside className="panel report-section coach-focus"><span className="eyebrow">YOUR COACHING NOTEBOOK</span><h2>What to work on</h2><p>Look for repeatable habits, then choose one focus for your next session.</p>
    <div className="athlete-summary"><h3>Player visibility</h3>{['A','B'].map(player=><p key={player}>Player {player} <b>{value(data.player_visibility_pct?.[player],'%')}</b></p>)}<small>Share of reviewed moments where each player is visible. Missing views can understate movement. A dash means this was not measured.</small></div>
    {data.coaching_advice?.length?<ul>{data.coaching_advice.slice(0,3).map(tip=><li key={tip}>{tip}</li>)}</ul>:<p className="report-empty">No coaching notes yet. Mark the court corners and keep both players fully in view, then analyze the match to build them.</p>}
    {!!data.review_moments?.length&&<><h3>Watch these moments</h3>{data.review_moments.slice(0,3).map((moment,i)=><button className="review-moment" key={i} onClick={()=>onReview(moment.time)}><b>{moment.title}</b><small>{Math.floor(moment.time/60)}:{Math.floor(moment.time%60).toString().padStart(2,'0')} · {moment.detail}</small></button>)}</>}
    <small>Use the video to check balance, first-step speed and recovery position. No points are awarded in badminton.</small>
  </aside>;
}

export function downloadPdfReport(data: Coaching, sessionName = 'Match') {
  const printWindow = window.open('', '_blank');
  if (!printWindow) {
    alert('Please allow popups to export the PDF report.');
    return;
  }

  const htmlContent = `
    <!DOCTYPE html>
    <html>
    <head>
      <title>Tactical Performance Report - ${sessionName}</title>
      <style>
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@600;700;800&family=DM+Sans:wght@400;500;700&display=swap');
        body { font-family: 'DM Sans', sans-serif; color: #0f172a; margin: 0; padding: 40px; background: #ffffff; }
        .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #0f172a; padding-bottom: 20px; margin-bottom: 30px; }
        .brand { font-family: 'Manrope', sans-serif; font-size: 28px; font-weight: 800; color: #0f172a; text-transform: lowercase; }
        .brand span { color: #84cc16; }
        .meta { text-align: right; font-size: 13px; color: #64748b; }
        h1 { font-family: 'Manrope', sans-serif; font-size: 24px; font-weight: 800; margin: 0 0 20px; }
        h2 { font-family: 'Manrope', sans-serif; font-size: 18px; font-weight: 700; color: #1e293b; border-bottom: 1px solid #e2e8f0; padding-bottom: 8px; margin-top: 30px; }
        .grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
        .card { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; }
        .card-label { font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.08em; }
        .card-value { font-family: 'Manrope', sans-serif; font-size: 22px; font-weight: 800; color: #0f172a; margin: 6px 0 4px; }
        .card-note { font-size: 12px; color: #64748b; }
        .two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 16px; }
        .table { width: 100%; border-collapse: collapse; margin-top: 12px; }
        .table th, .table td { border: 1px solid #e2e8f0; padding: 10px 14px; text-align: left; font-size: 14px; }
        .table th { background: #f1f5f9; font-weight: 700; }
        .swot-box { border-radius: 8px; padding: 16px; margin-bottom: 16px; }
        .swot-s { background: #f7fee7; border: 1px solid #bef264; }
        .swot-w { background: #fff1f2; border: 1px solid #fecdd3; }
        .swot-o { background: #f0f9ff; border: 1px solid #bae6fd; }
        .swot-t { background: #fffbeb; border: 1px solid #fde68a; }
        .swot-title { font-weight: 800; font-size: 12px; letter-spacing: 0.1em; margin-bottom: 8px; text-transform: uppercase; }
        .swot-s .swot-title { color: #4d7c0f; }
        .swot-w .swot-title { color: #be123c; }
        .swot-o .swot-title { color: #0369a1; }
        .swot-t .swot-title { color: #b45309; }
        ul { margin: 0; padding-left: 20px; }
        li { margin-bottom: 6px; font-size: 13px; line-height: 1.5; }
        .footer { margin-top: 40px; padding-top: 20px; border-top: 1px solid #e2e8f0; text-align: center; font-size: 12px; color: #94a3b8; }
        @media print { body { padding: 0; } }
      </style>
    </head>
    <body>
      <div class="header">
        <div class="brand">rally<span>.</span> intelligence</div>
        <div class="meta">
          <div><b>Session:</b> ${sessionName}</div>
          <div><b>Date:</b> ${new Date().toLocaleDateString()}</div>
        </div>
      </div>

      <h1>Tactical Performance Report</h1>

      <div class="grid">
        <div class="card">
          <div class="card-label">Longest Rally</div>
          <div class="card-value">${value(data.longest_rally?.duration_s, ' s')}</div>
          <div class="card-note">${data.longest_rally?.shots ?? 0} shots</div>
        </div>
        <div class="card">
          <div class="card-label">Average Rally</div>
          <div class="card-value">${value(data.average_rally_seconds, ' s')}</div>
          <div class="card-note">Completed exchanges</div>
        </div>
        <div class="card">
          <div class="card-label">High-Intensity Sprints</div>
          <div class="card-value">A ${value(data.sprints?.A)} · B ${value(data.sprints?.B)}</div>
          <div class="card-note">Active rally bursts</div>
        </div>
        <div class="card">
          <div class="card-label">Rally Tempo</div>
          <div class="card-value">${value(data.rally_pace_spm, ' spm')}</div>
          <div class="card-note">Exchanges / min</div>
        </div>
      </div>

      <h2>Movement & Court Positioning</h2>
      <table class="table">
        <thead>
          <tr>
            <th>Player</th>
            <th>Distance Covered</th>
            <th>Net Play Share</th>
            <th>Rear Court Share</th>
            <th>Work Rate</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><b>Player A</b></td>
            <td>${value(data.distance_m?.A, ' m')}</td>
            <td>${value(data.zone_split?.A?.net_pct, '%')}</td>
            <td>${value(data.zone_split?.A?.rear_pct, '%')}</td>
            <td>${value(data.work_rate_pct?.A, '%')}</td>
          </tr>
          <tr>
            <td><b>Player B</b></td>
            <td>${value(data.distance_m?.B, ' m')}</td>
            <td>${value(data.zone_split?.B?.net_pct, '%')}</td>
            <td>${value(data.zone_split?.B?.rear_pct, '%')}</td>
            <td>${value(data.work_rate_pct?.B, '%')}</td>
          </tr>
        </tbody>
      </table>

      <h2>Player SWOT Analysis (Strategic Profile)</h2>
      <div class="two-col">
        <div class="swot-box swot-s">
          <div class="swot-title">Strengths</div>
          <ul>
            <li>Net Dominance: ${value(data.zone_split?.A?.net_pct, '%')} front court presence for Player A</li>
            <li>Distance Mobility: Player A covered ${value(data.distance_m?.A, 'm')}</li>
          </ul>
        </div>
        <div class="swot-box swot-w">
          <div class="swot-title">Weaknesses</div>
          <ul>
            <li>Rear Court Exposure: ${value(data.zone_split?.A?.rear_pct, '%')} defensive positioning</li>
            <li>Rally Fatigue: Work rate ${value(data.work_rate_pct?.A, '%')}</li>
          </ul>
        </div>
        <div class="swot-box swot-o">
          <div class="swot-title">Opportunities</div>
          <ul>
            <li>Exploit Cross-Court Passing Lanes</li>
            <li>Increase Exchange Tempo (${value(data.rally_pace_spm, ' spm')})</li>
          </ul>
        </div>
        <div class="swot-box swot-t">
          <div class="swot-title">Threats</div>
          <ul>
            <li>Opponent Net Aggression</li>
            <li>Stamina Drain in Long Exchanges (${value(data.longest_rally?.duration_s, 's')})</li>
          </ul>
        </div>
      </div>

      <h2>Coaching Recommendations</h2>
      <ul>
        ${data.coaching_advice?.length ? data.coaching_advice.map(tip => `<li>${tip}</li>`).join('') : '<li>Analyze completed rallies to generate specific tactical notes.</li>'}
      </ul>

      <div class="footer">
        Generated by Rally Intelligence AI · Single-camera match analytics
      </div>

      <script>
        window.onload = function() {
          setTimeout(function() {
            window.print();
          }, 300);
        };
      </script>
    </body>
    </html>
  `;

  printWindow.document.write(htmlContent);
  printWindow.document.close();
}

export function downloadReport(data: Coaching, sessionName = 'Match') {
  const reportText = `RALLY INTELLIGENCE - TACTICAL PERFORMANCE REPORT
Session: ${sessionName}
Generated: ${new Date().toLocaleString()}

==================================================
1. PERFORMANCE METRICS
==================================================
Longest Rally: ${value(data.longest_rally?.duration_s, 's')} (${data.longest_rally?.shots ?? 0} shots)
Average Rally Duration: ${value(data.average_rally_seconds, 's')}
High-Intensity Sprints: Player A: ${value(data.sprints?.A)} | Player B: ${value(data.sprints?.B)}
Average Rally Pace: ${value(data.rally_pace_spm, ' shots/min')}
Peak Shot Speed: ${value(data.peak_shot_kmh, ' km/h')}

==================================================
2. MOVEMENT & POSITIONING
==================================================
Player A:
  - Distance Covered: ${value(data.distance_m?.A, 'm')}
  - Net Play Share: ${value(data.zone_split?.A?.net_pct, '%')}
  - Rear Court Share: ${value(data.zone_split?.A?.rear_pct, '%')}

Player B:
  - Distance Covered: ${value(data.distance_m?.B, 'm')}
  - Net Play Share: ${value(data.zone_split?.B?.net_pct, '%')}
  - Rear Court Share: ${value(data.zone_split?.B?.rear_pct, '%')}

Work-to-Rest Ratio: ${value(data.work_rest_ratio, ':1')}

==================================================
3. RALLY BREAKDOWN
==================================================
Short Rallies (1-4 shots): ${data.rally_distribution?.short || 0}
Medium Rallies (5-10 shots): ${data.rally_distribution?.medium || 0}
Marathon Rallies (11+ shots): ${data.rally_distribution?.marathon || 0}

==================================================
4. COACHING RECOMMENDATIONS
==================================================
${data.coaching_advice?.length ? data.coaching_advice.map(tip => `- ${tip}`).join('\n') : '- Complete more rallies for tactical recommendations.'}
`;

  const blob = new Blob([reportText], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${sessionName.toLowerCase().replace(/[^a-z0-9]+/g, '-')}-tactical-report.txt`;
  link.click();
  URL.revokeObjectURL(url);
}

export function TacticalReport({data,hasSession,legacy,sessionName='Match'}:{data:Coaching;hasSession:boolean;legacy:boolean;sessionName?:string}) {
  if(!hasSession)return <div className="panel empty-small">Open a saved match or start a new session to build your coaching report.</div>;
  if(legacy)return <div className="panel empty-small">This match was reviewed before coaching reports were available. Analyze its video in a new session to build a performance breakdown.</div>;
  const counts=data.rally_distribution||{};
  const total=Object.values(counts).reduce((a,b)=>a+b,0);
  return <div className="coaching-report">
    <div className="report-action-bar">
      <div>
        <span className="eyebrow">TACTICAL PERFORMANCE EXPORT</span>
        <h2 className="report-title">Match Analysis Summary</h2>
      </div>
      <div style={{ display: 'flex', gap: '10px' }}>
        <button className="primary" onClick={() => downloadPdfReport(data, sessionName)}>
          <FileText size={16} /> Download PDF Report
        </button>
        <button className="secondary" onClick={() => downloadReport(data, sessionName)}>
          <ArrowDownToLine size={16} /> Export Text (.txt)
        </button>
      </div>
    </div>
    <CoachingStats data={data}/>
    <div className="bottom-grid">
      <section className="panel report-section"><h2>Movement & endurance</h2><p>Use observed match effort to plan your next training session.</p>{['A','B'].map(player=><div className="athlete-summary" key={player}><h3>Player {player}</h3><dl><div><dt>Distance covered</dt><dd>{value(data.distance_m?.[player],' m')}</dd></div><div><dt>High-intensity sprints</dt><dd>{value(data.sprints?.[player])}</dd></div><div><dt>High-intensity share of rally time</dt><dd>{value(data.work_rate_pct?.[player],'%')}</dd></div></dl></div>)}<p>Work-to-rest ratio <b>{value(data.work_rest_ratio,':1')}</b></p><small>Measured rally time compared with recovery between completed rallies. This describes match effort, not a diagnosis of fatigue.</small></section>
      <section className="panel report-section"><h2>Court positioning</h2><p>Front 35% of each half: net zone. Remaining 65%: rear court.</p>{['A','B'].map(player=>{const zone=data.zone_split?.[player];return <div className="athlete-summary" key={player}><h3>Player {player}</h3><div className="zone-bar" role="img" aria-label={`Player ${player}: net ${value(zone?.net_pct,'%')}, rear ${value(zone?.rear_pct,'%')}`}><i style={{width:`${zone?.net_pct||0}%`}}/></div><p>Net play <b>{value(zone?.net_pct,'%')}</b> · Rear court <b>{value(zone?.rear_pct,'%')}</b></p></div>})}<small>{data.front_court_leader?`Player ${data.front_court_leader} spent a greater share of rally time near the net. Review whether those positions led to attacking opportunities.`:'More rally time will reveal each player’s positioning tendencies.'}</small></section>
      <section className="panel report-section"><h2>Rally breakdown</h2><p>{total} completed rallies</p>{[['short','Short · 1–4 shots'],['medium','Medium · 5–10 shots'],['marathon','Marathon · 11+ shots']].map(([key,label])=><div className="distribution-row" key={key}><span>{label}</span><meter min={0} max={Math.max(total,1)} value={counts[key]||0}/><b>{counts[key]||0}</b></div>)}<h3>Peak shot speed</h3><strong>{value(data.peak_shot_kmh,' km/h')}</strong><p>{data.peak_shot_kmh==null?'Shot speed needs reliable ball-flight measurements. Use rally pace to compare exchange tempo.':'Fastest measured shot in this match.'}</p></section>
      <section className="panel report-section"><h2>Your next practice</h2>{data.coaching_advice?.length?<ul>{data.coaching_advice.map(tip=><li key={tip}>{tip}</li>)}</ul>:<p className="report-empty">Coaching notes appear once a few rallies have been completed and reviewed.</p>}{!data.calibrated&&<p>Mark the court corners before analysis to measure distance and positioning.</p>}</section>
    </div>
    <SwotAnalysis data={data} />
  </div>;
}
