import React, {useEffect, useMemo, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {Activity, ArrowDownToLine, Check, ChevronRight, CircleHelp, Crosshair, Layers, Play, Plus, Radio, RotateCcw, Square, Upload, X} from 'lucide-react';
import './style.css';
import './coaching.css';
import {SessionManager} from './SessionManager';
import {CoachFocus,CoachingStats,TacticalReport,ProfilePicker,SwotAnalysis,profiles,value,matchStatus,rallyStatus,friendlyError} from './CoachingInsights';
import type {Coaching,Profile} from './CoachingInsights';

type Sport = 'tennis'|'badminton';
type Event = {id:string;kind:string;time:number;status:string;winner?:string;confidence?:number};
export type Session = {rally_state?:string;rally_reason?:string;runtime?:{device:string;gpu?:string;half_precision?:boolean};options?:{frame_stride:number;device:string;auto_score:boolean};activity?:string;id:string;sport:Sport;pose:string;name:string;status:string;error?:string;source_image?:string;suggested_corners?:number[][];corners?:number[][];preview?:string;video?:string;records?:string;updated_at:string;events:Event[];score:{points:string[];games:number[];sets:number[];format:string;complete:boolean};analytics:Coaching;processed_frames:number;total_frames?:number;source_seconds?:number;processing_fps?:number;filtered_percent?:number;object_speed_px_s?:number;live?:boolean};
const busyStates = ['queued','loading','processing','encoding'];
const time = (value=0) => `${Math.floor(value/60).toString().padStart(2,'0')}:${Math.floor(value%60).toString().padStart(2,'0')}`;

async function api(path:string, options:RequestInit={}) {
  const result = await fetch('/api'+path,options);
  if (!result.ok) {const body=await result.json().catch(()=>({detail:'The request could not be completed.'}));throw new Error(typeof body.detail==='string'?body.detail:JSON.stringify(body.detail));}
  return result.json();
}

function CourtMap({points=[],sport,player}:{points?:number[][];sport:Sport;player:string}) {
  const isA = player === 'A';
  const color = isA ? '#9ef01a' : '#38bdf8';
  const glow = isA ? 'rgba(158, 240, 26, 0.4)' : 'rgba(56, 189, 248, 0.4)';

  const {pathString, waypoints, startPoint, currentPoint, dominantZone} = useMemo(()=>{
    if (!points || !points.length) {
      return {pathString:'', waypoints:[], startPoint:null, currentPoint:null, dominantZone:'Awaiting play'};
    }

    const mapped = points.map(p => ({
      x: 18 + Math.min(1, Math.max(0, p[0])) * 164,
      y: 15 + Math.min(1, Math.max(0, p[1])) * 270,
      origY: p[1]
    }));

    const pathString = mapped.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
    const step = Math.max(1, Math.floor(mapped.length / 24));
    const waypoints = mapped.filter((_, idx) => idx % step === 0 && idx !== 0 && idx !== mapped.length - 1);

    const startPoint = mapped[0];
    const currentPoint = mapped[mapped.length - 1];

    let netCount = 0;
    for (const p of mapped) {
      if (Math.abs(p.y - 150) <= 50) netCount++;
    }
    const netPct = Math.round((netCount / Math.max(1, mapped.length)) * 100);
    const dominantZone = netPct >= 50 ? `Net Dominant (${netPct}%)` : `Rear Court (${100 - netPct}%)`;
    return {pathString, waypoints, startPoint, currentPoint, dominantZone};
  }, [points, isA]);

  return (
    <div className="court-map-wrapper">
      <svg viewBox="0 0 200 300" className="court-map" role="img" aria-label={`Player ${player} movement trajectory`}>
        <defs>
          <clipPath id="courtClip">
            <rect x="18" y="15" width="164" height="270" rx="3" />
          </clipPath>
        </defs>

        <rect x="18" y="15" width="164" height="270" rx="3" fill="#182b21" stroke="#3d5746" strokeWidth="1.5" />

        <g stroke="#8ba593" strokeWidth="1" fill="none" opacity="0.85">
          <line x1="14" y1="150" x2="186" y2="150" stroke="#f0f7f2" strokeWidth="1.8" strokeDasharray="4 2" />
          <line x1="36" y1="15" x2="36" y2="285" />
          <line x1="164" y1="15" x2="164" y2="285" />
          <line x1="36" y1="80" x2="164" y2="80" />
          <line x1="36" y1="220" x2="164" y2="220" />
          <line x1="100" y1="80" x2="100" y2="220" />
          <line x1="100" y1="15" x2="100" y2="22" stroke="#f0f7f2" strokeWidth="1.2" />
          <line x1="100" y1="278" x2="100" y2="285" stroke="#f0f7f2" strokeWidth="1.2" />

          {sport === 'badminton' && (
            <>
              <line x1="18" y1="35" x2="182" y2="35" strokeDasharray="3 2" />
              <line x1="18" y1="265" x2="182" y2="265" strokeDasharray="3 2" />
              <line x1="36" y1="110" x2="164" y2="110" />
              <line x1="36" y1="190" x2="164" y2="190" />
            </>
          )}
        </g>

        <text x="100" y="153" textAnchor="middle" fill="#dce9df" fontSize="7" fontWeight="bold" letterSpacing="0.6">
          NET
        </text>

        <text x="24" y="27" fill="#698572" fontSize="6.5" fontWeight="600">FAR COURT</text>
        <text x="24" y="280" fill="#698572" fontSize="6.5" fontWeight="600">NEAR COURT</text>

        {pathString ? (
          <g clipPath="url(#courtClip)">
            <polyline
              points={pathString}
              fill="none"
              stroke={glow}
              strokeWidth="5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <polyline
              points={pathString}
              fill="none"
              stroke={color}
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
              opacity="0.95"
            />

            {waypoints.map((wp, i) => (
              <circle
                key={i}
                cx={wp.x}
                cy={wp.y}
                r="2.5"
                fill={color}
                opacity="0.8"
              />
            ))}

            {startPoint && (
              <g>
                <circle cx={startPoint.x} cy={startPoint.y} r="5" fill="#f59e0b" stroke="#ffffff" strokeWidth="1.2" />
                <text x={startPoint.x} y={startPoint.y + 2.5} textAnchor="middle" fill="#1e293b" fontSize="5" fontWeight="bold">S</text>
              </g>
            )}

            {currentPoint && (
              <g>
                <circle cx={currentPoint.x} cy={currentPoint.y} r="8" fill={glow} />
                <circle cx={currentPoint.x} cy={currentPoint.y} r="5.5" fill={color} stroke="#ffffff" strokeWidth="1.4" />
                <text x={currentPoint.x} y={currentPoint.y + 2.5} textAnchor="middle" fill="#182b21" fontSize="6" fontWeight="bold">{player}</text>
              </g>
            )}
          </g>
        ) : (
          <g>
            <rect x="35" y="130" width="130" height="40" rx="5" fill="#14241ccc" />
            <text x="100" y="148" textAnchor="middle" fill="#a4c2ad" fontSize="8" fontWeight="bold">
              AWAITING MOVEMENT DATA
            </text>
            <text x="100" y="160" textAnchor="middle" fill="#758f7e" fontSize="7">
              Player path traces during match play
            </text>
          </g>
        )}
      </svg>
      {points.length > 0 && (
        <div className="coverage-meta-pill">
          <span>Movement during match</span>
          <b>{dominantZone}</b>
        </div>
      )}
    </div>
  );
}


function normalizeAnalytics(raw?: any, sport: Sport = 'badminton'): Coaching {
  if (!raw) return {};
  const rallies: number[] = Array.isArray(raw.rallies) 
    ? raw.rallies.filter((n: any) => typeof n === 'number' && n > 0) 
    : [];
  const longest = raw.longest_rally ?? null;
  const avgDuration = raw.average_rally_seconds ?? (rallies.length 
    ? Number((rallies.reduce((a: number, b: number) => a + b, 0) / rallies.length).toFixed(1)) 
    : null);
  const totalRallyTime = raw.work_seconds || rallies.reduce((a: number, b: number) => a + b, 0);
  const hits = raw.estimated_hits || 0;

  const trajectory = raw.trajectory || raw.heatmap || {A: [], B: []};
  const zone_split = raw.zone_split ? {...raw.zone_split} : {};
  const distance_m = raw.distance_m ? {...raw.distance_m} : {};
  const courtL = sport === 'tennis' ? 23.77 : 13.4;
  const courtW = sport === 'tennis' ? 8.23 : 5.18;

  for (const p of ['A', 'B']) {
    const pts = trajectory[p] || [];
    if (!zone_split[p] || zone_split[p].net_pct == null) {
      if (pts.length > 0) {
        let netCount = 0;
        for (const pt of pts) {
          const y = pt[1];
          const distToNet = Math.abs(y - 0.5);
          if (distToNet <= 0.18) netCount++;
        }
        const netPct = Math.round((netCount / pts.length) * 100);
        zone_split[p] = { net_pct: netPct, rear_pct: 100 - netPct, observed_seconds: pts.length * 0.1 };
      }
    }
    if ((distance_m[p] == null || distance_m[p] === 0) && pts.length > 1) {
      let d = 0;
      for (let i = 1; i < pts.length; i++) {
        const dx = (pts[i][0] - pts[i-1][0]) * courtW;
        const dy = (pts[i][1] - pts[i-1][1]) * courtL;
        d += Math.hypot(dx, dy);
      }
      if (d > 0) distance_m[p] = Math.round(d * 10) / 10;
    }
  }

  const distribution = raw.rally_distribution || {
    short: rallies.filter((r: number) => r <= 4).length,
    medium: rallies.filter((r: number) => r > 4 && r <= 10).length,
    marathon: rallies.filter((r: number) => r > 10).length,
  };

  const sprints = raw.sprints ? {...raw.sprints} : {A: null, B: null};

  const advice = Array.isArray(raw.coaching_advice) ? raw.coaching_advice : [];

  const pace = raw.rally_pace_spm ?? (totalRallyTime > 0 && hits > 0
    ? Number(((hits / totalRallyTime) * 60).toFixed(1))
    : null);

  return {
    version: 2,
    calibrated: raw.calibrated ?? ((trajectory.A?.length || 0) + (trajectory.B?.length || 0) > 0),
    player_visibility_pct: raw.player_visibility_pct || {A: null, B: null},
    review_moments: raw.review_moments || [],
    distance_m,
    speed_mps: raw.speed_mps || {A: null, B: null},
    heatmap: trajectory,
    trajectory,
    zone_split,
    front_court_leader: raw.front_court_leader || (zone_split.A?.net_pct != null && zone_split.B?.net_pct != null ? (zone_split.A.net_pct >= zone_split.B.net_pct ? 'A' : 'B') : null),
    sprints,
    high_intensity_seconds: raw.high_intensity_seconds || {A: null, B: null},
    work_rate_pct: raw.work_rate_pct || {A: null, B: null},
    estimated_hits: hits,
    rally_seconds: raw.rally_seconds || 0,
    rallies: raw.rallies || rallies,
    rally_count: rallies.length,
    longest_rally: longest,
    average_rally_seconds: avgDuration,
    rally_distribution: distribution,
    work_seconds: totalRallyTime,
    rest_seconds: raw.rest_seconds ?? null,
    work_rest_ratio: raw.work_rest_ratio ?? null,
    rally_pace_spm: pace,
    peak_shot_kmh: raw.peak_shot_kmh || null,
    coaching_advice: advice,
  };
}

function App(){
  const [sport,setSport]=useState<Sport>('tennis');
  const [profile,setProfile]=useState<Profile>('balanced');
  const {pose,stride}=profiles[profile];
  const device='auto';
  const [session,setSession]=useState<Session|null>(null);
  const [sessions,setSessions]=useState<Session[]>([]);
  const [models,setModels]=useState<{key:string;file:string;available:boolean}[]>([]);
  const [error,setError]=useState('');
  const [uploading,setUploading]=useState(false);
  const [modal,setModal]=useState(false);
  const [source,setSource]=useState('');
  const [corners,setCorners]=useState<number[][]>([]);
  const [calibrating,setCalibrating]=useState(false);
  const [tab,setTab]=useState('Overview');
  const [player,setPlayer]=useState('A');
  const [connected,setConnected]=useState(false);
  const input=useRef<HTMLInputElement>(null);
  const video=useRef<HTMLVideoElement>(null);
  const busy=!!session&&busyStates.includes(session.status);
  const analytics:Coaching=useMemo(()=>normalizeAnalytics(session?.analytics,sport),[session?.analytics,sport]);
  const review=sport==='badminton'?[]:session?.events.filter(event=>event.status==='review'&&event.kind!=='hit')||[];
  const required=[sport,pose,...(pose==='rtmpose'?['yolox']:[])];
  const ready=models.length>0&&required.every(key=>models.find(model=>model.key===key)?.available);
  const load=()=>api('/sessions').then(setSessions).catch((e:Error)=>setError(e.message));

  useEffect(()=>{api('/health').then(data=>{setModels(data.models);}).catch(()=>setError('Match analysis is unavailable. Please try again shortly.'));load();},[]);
  useEffect(()=>{
    if(!session?.id)return;
    let disposed=false;let socket:WebSocket|undefined;let retry:ReturnType<typeof setTimeout>;
    const connect=()=>{
      socket=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/api/sessions/${session.id}/ws`);
      socket.onopen=()=>setConnected(true);
      socket.onmessage=message=>{const row=JSON.parse(message.data);setSession(row);};
      socket.onclose=()=>{setConnected(false);if(!disposed)retry=setTimeout(connect,2000);};
    };connect();
    return ()=>{disposed=true;clearTimeout(retry);socket?.close();};
  },[session?.id]);
  useEffect(()=>{if(!session?.id||!busy)return;const timer=setInterval(()=>{api(`/sessions/${session.id}`).then(row=>setSession(row)).catch(()=>{});},1200);return ()=>clearInterval(timer);},[session?.id,busy]);
  useEffect(()=>{if(session&&!busy)load();},[session?.status]);

  const choose=(row:Session)=>{setSession(row);setSport(row.sport);setProfile(row.pose==='rtmpose'?'deep':row.pose==='yolo-nano'?'fast':'balanced');setCorners(row.corners||row.suggested_corners||[]);setCalibrating(row.status==='ready');setModal(false);setError('');};
  const upload=async(file:File)=>{
    setUploading(true);setError('');
    try{const body=new FormData();body.append('file',file);body.append('sport',sport);body.append('pose',pose);choose(await api('/sessions/upload',{method:'POST',body}));setTab('Overview');}
    catch(e){setError((e as Error).message);}finally{setUploading(false);if(input.current)input.current.value='';}
  };
  const start=async()=>{if(!session)return;setError('');try{setSession(await api(`/sessions/${session.id}/start`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({profile,corners:corners.length===4?corners:null,frame_stride:stride,device,auto_score:false,max_width:1280,inference_size:640})}));setCalibrating(false);}catch(e){setError((e as Error).message);}};
  const point=async(winner:string,event_id:string=crypto.randomUUID())=>{if(!session)return;try{setSession(await api(`/sessions/${session.id}/points`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({winner,event_id})}));}catch(e){setError((e as Error).message);}};
  const dismiss=async(id:string)=>{try{setSession(await api(`/sessions/${session!.id}/points/${id}`,{method:'DELETE'}));}catch(e){setError((e as Error).message);}};
  const createLive=async()=>{try{choose(await api('/sessions/live',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sport,pose,source})}));}catch(e){setError((e as Error).message);}};
  const deleteSession=async(row:Session)=>{
    if(session?.id===row.id){video.current?.pause();video.current?.removeAttribute('src');video.current?.load();setSession(null);}
    await api(`/sessions/${row.id}`,{method:'DELETE'});
    setSessions(previous=>previous.filter(item=>item.id!==row.id));
  };
  const progress=session?.total_frames?Math.min(100,100*session.processed_frames/session.total_frames):0;

  return <div className="app-shell">
    <aside className="sidebar">
      <a href="#" className="brand"><span className="brand-icon"><Activity size={23}/></span>rally<span className="brand-dot">.</span></a>
      <span className="workspace-label">YOUR WORKSPACE</span>
      <nav>{['Overview','Sessions','Tactical Report'].map((name,index)=><button key={name} className={tab===name?'nav-item selected':'nav-item'} onClick={()=>setTab(name)}>{index===0?<Layers size={18}/>:index===1?<Play size={18}/>:<Crosshair size={18}/>} {name}{tab===name&&<span className="nav-dot"/>}</button>)}</nav>
      <div className="sidebar-note"><span className="mini-label">ONE CAMERA. MORE INSIGHT.</span><div className="mini-court"><span/><span/><span/></div><p>Every rally tells<br/>a story.</p><small>Find yours in the details.</small></div>
      <div className="sidebar-bottom"><span className="avatar">RI</span><div>Racket Intelligence<small>Your coaching workspace</small></div></div>
    </aside>
    <main>
      <header><div className="breadcrumb">Workspace <ChevronRight size={13}/> <b>{tab}</b></div><div className="header-right"><span className="local-badge"><i/> MATCH WORKSPACE</span><button className="icon-button" aria-label="Match guide" onClick={()=>setError('Mark the court corners and keep both players in view. Review movement bursts and long rallies to find coaching opportunities. Badminton sessions focus on performance without counting points.')}><CircleHelp size={19}/></button><span className="avatar small">AB</span></div></header>
      <div className="content">
        <div className="page-heading"><div><span className="eyebrow">THE GAME, IN GREATER DETAIL</span><h1>{tab==='Overview'?'Your court. Your insights.':tab==='Sessions'?'Every session, in one place.':'Turn match patterns into progress.'}</h1><p>{tab==='Overview'?'Turn a single camera into a fresh perspective on your game.':tab==='Sessions'?'Revisit your analysis and pick up where you left off.':'Positioning, endurance and rally patterns for your next practice.'}</p></div><button className="primary" onClick={()=>setModal(true)}><Plus size={17}/> New session</button></div>
        {(error||session?.error)&&<div className="alert" role="alert">{friendlyError(error||session?.error||'')}<button aria-label="Dismiss message" onClick={()=>{setError('');if(session?.error)setSession({...session,error:undefined});}}><X size={16}/></button></div>}
        {tab==='Tactical Report'?<TacticalReport data={analytics} hasSession={!!session} legacy={false}/>:tab==='Sessions'?<SessionManager sessions={sessions} onOpen={row=>{choose(row);setTab('Overview');}} onDelete={deleteSession} onCreate={()=>setModal(true)}/>:<>
          <div className="match-status-bar"><b>{sport==='tennis'?'Tennis':'Badminton'} Singles</b><span>{busy?rallyStatus(session?.rally_state):matchStatus(session?.status)}</span><small>{busy?'Follow the match as insights arrive.':'Review the game. Plan your next practice.'}</small></div><div className="toolbar"><div className="sport-switch"><button className={sport==='tennis'?'active':''} disabled={busy} onClick={()=>{if(session&&session.sport!=='tennis')setSession(null);setSport('tennis');}}>◉ Tennis</button><button className={sport==='badminton'?'active':''} disabled={busy} onClick={()=>{if(session&&session.sport!=='badminton')setSession(null);setSport('badminton');}}>✧ Badminton</button></div><div className="session-state"><i className={busy?'pulse':''}/>{session?matchStatus(session.status):'Ready for your first session'}{busy&&connected&&' · Connected'}</div></div>
          <div className="main-grid"><section className="panel video-panel"><div className="panel-title"><h2><span className="title-icon"><Play size={15}/></span> Match view</h2><span className="tag">{session?.name||'MATCH REVIEW'}</span></div>
            <div className={'video-stage '+(!session?'empty-stage':'')} onDragOver={event=>event.preventDefault()} onDrop={event=>{event.preventDefault();if(event.dataTransfer.files[0])upload(event.dataTransfer.files[0]);}}>
              {session?.video&&!calibrating?<video ref={video} key={session.video} controls src={session.video}/>:session?.preview&&!calibrating?<img className="feed-image" src={session.preview+'?v='+encodeURIComponent(session.updated_at)} alt="Latest annotated frame"/>:session?.source_image?<div className="calibration-image"><img src={session.source_image} alt="Court calibration frame"/><svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label={calibrating?`Court calibration: ${corners.length} of 4 corners marked. Click the court corners in order.`:'Court calibration frame'} className={calibrating?'calibration active':'calibration'} onClick={event=>{if(!calibrating)return;const box=event.currentTarget.getBoundingClientRect();const point=[(event.clientX-box.left)/box.width,(event.clientY-box.top)/box.height];setCorners(corners.length>=4?[point]:[...corners,point]);}}>{corners.length>1&&<polygon points={corners.map(p=>p.map(x=>x*100).join(',')).join(' ')} fill="#b5e98325" stroke="#c9f6a0" strokeWidth=".3"/>}{corners.map((point,index)=><g key={index}><circle cx={point[0]*100} cy={point[1]*100} r="1" fill="#c9f6a0"/><text x={point[0]*100+1.5} y={point[1]*100-1} fill="white" fontSize="3">{index+1}</text></g>)}</svg></div>:<div className="empty-video"><div className="court-illustration"><div/><i/><span/></div><span className="video-label">A NEW POINT OF VIEW</span><h2>{uploading?'Preparing your video…':session?.live?'Your camera is ready.':'Your next rally starts here.'}</h2><p>{session?.live?'Start analysis to connect to your live feed.':'Upload a match to discover the patterns behind your play.'}</p>{!session?.live&&<button className="primary" disabled={uploading} onClick={()=>input.current?.click()}><Upload size={16}/> {uploading?'Uploading…':'Upload match video'}</button>}<small>MP4, MOV, AVI, MKV or WebM · Up to 4 GB</small></div>}
              {busy&&<span className="feed-badge"><i/> {rallyStatus(session?.rally_state)}</span>}
            </div>
            <div className="video-footer"><span><i className="status-dot"/>{busy?`${time(session?.source_seconds)} reviewed`:session?.video?'Analysis complete':calibrating?'Mark far-left → far-right → near-right → near-left':'Video and overlays appear here'}</span>{session?.video?<a href={session.video} download><ArrowDownToLine size={16}/> Export</a>:<span className="muted">{time(session?.source_seconds)} of match</span>}</div>
            {(session?.status === 'completed' || (!!session?.video && !busy)) && <SwotAnalysis data={analytics}/>}
            {busy&&<div className="progress-track"><span style={{width:`${progress}%`}}/></div>}
            {session&&['ready','failed'].includes(session.status)&&<div className="calibration-controls"><div><b>{corners.length===4?'Court corners selected':`Court calibration · ${corners.length}/4 corners`}</b><small>{corners.length===4?'Check the court outline before starting.':'Select all four corners to measure court movement and positioning.'}</small></div><ProfilePicker profile={profile} onChange={setProfile}/><button className="text-button" onClick={()=>{setCorners([]);setCalibrating(true);}}>Reset</button><button className="primary" onClick={start}><Play size={15}/> Analyze</button></div>}
            {busy&&<button className="stop-button" onClick={()=>api(`/sessions/${session!.id}/stop`,{method:'POST'}).catch(e=>setError(e.message))}><Square size={12}/> Stop analysis</button>}
          </section>
          <>{sport==='badminton'?<CoachFocus data={analytics} onReview={t=>{if(video.current){video.current.currentTime=t;video.current.play().catch(()=>{});}}}/>:<aside className="panel scoreboard"><div className="panel-title"><h2>Scoreboard</h2><span className="tag">SINGLES</span></div><div className="score-caption"><span>PLAYER</span><span>{sport==='tennis'?'SETS / GAMES':'GAMES'} <b>POINTS</b></span></div>{['A','B'].map((key,index)=><div className={'player-row player-'+key} key={key}><span className="player-initial">{key}</span><div><b>Player {key}</b><small>{key==='A'?'Near court at start':'Far court at start'}</small></div><span className="games">{sport==='tennis'?`${session?.score.sets[index]||0} / ${session?.score.games[index]||0}`:session?.score.games[index]||0}</span><strong>{session?.score.points[index]||'0'}</strong></div>)}<div className="score-rule">{session?.score.complete?'Match complete':session?.score.format||(sport==='tennis'?'Best of 3 sets · Tiebreak at 6–6':'Best of 3 games · 21 points')}</div><div className="score-insight"><Crosshair size={17}/><div><b>Review match points</b><p>{sport==='tennis'?'Confirm tennis rally outcomes with the point controls.':'Suggested badminton points appear after each rally. Review close calls before confirming.'}</p></div></div><div className="point-controls"><button disabled={!session||busy} onClick={()=>point('A')}>+ Point A</button><button disabled={!session||busy} onClick={()=>point('B')}>+ Point B</button><button title="Undo last point" aria-label="Undo last point" disabled={!session||busy||!session.events.some(e=>e.status==='confirmed')} onClick={()=>{const last=session?.events.filter(e=>e.status==='confirmed').at(-1);if(last)dismiss(last.id);}}><RotateCcw size={15}/></button></div></aside>}</></div>
          <CoachingStats data={analytics}/>
          <div className="bottom-grid"><section className="panel coverage"><div className="panel-title"><div><h2>Player movement</h2><p>Movement and court positioning.</p></div><div className="player-toggle">{['A','B'].map(key=><button className={key===player?'active':''} key={key} onClick={()=>setPlayer(key)}>Player {key}</button>)}</div></div><div className="coverage-body"><CourtMap sport={sport} player={player} points={analytics.trajectory?.[player]||analytics.heatmap?.[player]}/><div className="coverage-stats"><span className="eyebrow">PLAYER {player} MOVEMENT</span><strong>{value(analytics.distance_m?.[player])}<small>m</small></strong><p>Distance covered</p><div className="stat-divider"/><strong className="smaller">{value(analytics.zone_split?.[player]?.net_pct,'%')}</strong><p>Net play · Rear court {value(analytics.zone_split?.[player]?.rear_pct,'%')}</p><span className="coverage-note">{analytics.calibrated?'Positioning during observed rallies.':'Mark the court corners to unlock movement insights.'}</span><div className="movement-legend-bar"><div className="legend-item"><span className="legend-marker start"/> Start</div><div className="legend-item"><span className="legend-marker path"/> Path</div><div className="legend-item"><span className="legend-marker current"/> Active ({player})</div></div></div></div></section>
          <section className="panel rally-panel"><div className="panel-title"><div><h2>Rally timeline</h2><p>Find the moments that matter.</p></div><span className="tag">{sport==='badminton'?'COACHING REVIEW':`${review.length} TO REVIEW`}</span></div><div className="rally-chart">{analytics.rallies?.length?analytics.rallies.map((value,index)=><div key={index} className="bar-column"><span>{value}s</span><i style={{height:Math.max(4,100*value/Math.max(...analytics.rallies!,1))+'px'}}/><small>{index+1}</small></div>):<div className="chart-empty"><Activity size={30}/><p>Rallies will take shape here.</p><small>Start analysis to build your session timeline.</small></div>}</div><div className="review-list">{review.slice(-4).reverse().map(event=><div className="review-row" key={event.id}><button className="event-time" onClick={()=>{if(video.current)video.current.currentTime=event.time;}}>{time(event.time)}</button><span>Rally outcome<small>Review the suggested winner before confirming</small></span><button disabled={busy} onClick={()=>point('A',event.id)}>A</button><button disabled={busy} onClick={()=>point('B',event.id)}>B</button><button disabled={busy} aria-label="Dismiss event" onClick={()=>dismiss(event.id)}><X size={13}/></button></div>)}</div>{session?.records&&<a className="records-link" href={session.records} download>Download match observations <ArrowDownToLine size={14}/></a>}</section></div>
          <footer><span>RALLY INTELLIGENCE <span className="footer-dot">/</span> A clearer view of your game.</span><span>Build better habits, one rally at a time</span></footer>
        </>}
      </div>
    </main>
    <input ref={input} type="file" accept="video/*,.mkv" hidden onChange={event=>{if(event.target.files?.[0])upload(event.target.files[0]);}}/>
    {modal&&<div className="modal-backdrop" onClick={()=>setModal(false)}><section className="modal" role="dialog" aria-modal="true" aria-labelledby="session-title" onClick={event=>event.stopPropagation()}><div className="panel-title"><h2 id="session-title">Start a new session</h2><button className="icon-button" aria-label="Close" onClick={()=>setModal(false)}><X size={18}/></button></div><p>Choose your sport and bring the match into focus.</p><label>Sport<select value={sport} onChange={event=>setSport(event.target.value as Sport)}><option value="tennis">Tennis</option><option value="badminton">Badminton</option></select></label><ProfilePicker profile={profile} onChange={setProfile}/><div className={ready?'model-ready':'model-missing'}>{ready?<Check size={16}/>:<CircleHelp size={16}/>} {ready?'Ready to review your match.':'This analysis option is not available yet. Choose another profile or prepare your session for later.'}</div><button className="primary full" disabled={uploading} onClick={()=>input.current?.click()}><Upload size={17}/> {uploading?'Uploading…':'Choose match video'}</button><div className="or-line">OR CONNECT A LIVE FEED</div><label>Camera or stream URL<input value={source} placeholder="rtsp://camera/stream or camera:0" onChange={event=>setSource(event.target.value)}/></label><small className="muted">Connect your court camera using its stream address, or enter camera:0 for this computer’s webcam.</small><button className="secondary full" disabled={!source} onClick={createLive}><Radio size={16}/> Connect camera</button></section></div>}
  </div>;
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
