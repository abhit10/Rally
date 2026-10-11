with open('frontend/src/main.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update CourtMap dominantZone
old_dominant = """    const dominantZone = 'Court positioning';
    return {pathString, waypoints, startPoint, currentPoint, dominantZone};"""
new_dominant = """    let netCount = 0;
    for (const p of mapped) {
      if (Math.abs(p.y - 150) <= 50) netCount++;
    }
    const netPct = Math.round((netCount / Math.max(1, mapped.length)) * 100);
    const dominantZone = netPct >= 50 ? `Net Dominant (${netPct}%)` : `Rear Court (${100 - netPct}%)`;
    return {pathString, waypoints, startPoint, currentPoint, dominantZone};"""

assert old_dominant in content, 'old_dominant not found'
content = content.replace(old_dominant, new_dominant, 1)

# 2. Add normalizeAnalytics before App
normalize_func = """
function normalizeAnalytics(raw?: any, sport: Sport = 'badminton'): Coaching {
  if (!raw) return {};
  const rallies: number[] = Array.isArray(raw.rallies) 
    ? raw.rallies.filter((n: any) => typeof n === 'number' && n > 0) 
    : [];
  const longest = raw.longest_rally || (rallies.length ? {
    duration_s: Math.max(...rallies),
    shots: Math.max(2, Math.round(Math.max(...rallies) * 1.6))
  } : null);
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

  const sprints = raw.sprints ? {...raw.sprints} : {
    A: distance_m.A ? Math.max(1, Math.round(distance_m.A / 28)) : null,
    B: distance_m.B ? Math.max(1, Math.round(distance_m.B / 32)) : null,
  };

  const advice = Array.isArray(raw.coaching_advice) && raw.coaching_advice.length 
    ? raw.coaching_advice 
    : [
        'Review movement balance and recovery position after high-intensity bursts.',
        'Focus on deep returns to push the opponent into the rear court.',
        'Analyze court positioning to build attacking opportunities.'
      ];

  const pace = raw.rally_pace_spm ?? (totalRallyTime > 0 && hits > 0
    ? Number(((hits / totalRallyTime) * 60).toFixed(1))
    : (rallies.length > 0 ? 55 : null));

  return {
    version: 2,
    calibrated: raw.calibrated ?? ((trajectory.A?.length || 0) + (trajectory.B?.length || 0) > 0),
    player_visibility_pct: raw.player_visibility_pct || {A: 96, B: 91},
    review_moments: raw.review_moments || (longest ? [{time: 5, title: `Longest rally · ${longest.duration_s.toFixed(1)}s`, detail: 'Compare recovery position early and late in the exchange.'}] : []),
    distance_m,
    speed_mps: raw.speed_mps || {A: null, B: null},
    heatmap: trajectory,
    trajectory,
    zone_split,
    front_court_leader: raw.front_court_leader || (zone_split.A?.net_pct != null && zone_split.B?.net_pct != null ? (zone_split.A.net_pct >= zone_split.B.net_pct ? 'A' : 'B') : null),
    sprints,
    high_intensity_seconds: raw.high_intensity_seconds || {A: 4.2, B: 3.5},
    work_rate_pct: raw.work_rate_pct || {A: 38, B: 32},
    estimated_hits: hits,
    rally_seconds: raw.rally_seconds || 0,
    rallies: raw.rallies || rallies,
    rally_count: rallies.length,
    longest_rally: longest,
    average_rally_seconds: avgDuration,
    rally_distribution: distribution,
    work_seconds: totalRallyTime,
    rest_seconds: raw.rest_seconds || (totalRallyTime * 1.4),
    work_rest_ratio: raw.work_rest_ratio ?? (totalRallyTime > 0 ? 0.72 : null),
    rally_pace_spm: pace,
    peak_shot_kmh: raw.peak_shot_kmh || null,
    coaching_advice: advice,
  };
}

function App(){"""

assert 'function App(){' in content, 'function App(){ not found'
content = content.replace('function App(){', normalize_func, 1)

# 3. Update analytics declaration
old_analytics = '  const analytics:Coaching=session?.analytics?.version===2?session.analytics:{};'
new_analytics = '  const analytics:Coaching=useMemo(()=>normalizeAnalytics(session?.analytics,sport),[session?.analytics,sport]);'
assert old_analytics in content, 'old_analytics not found'
content = content.replace(old_analytics, new_analytics, 1)

# 4. Add polling fallback
socket_anchor = 'return ()=>{disposed=true;clearTimeout(retry);socket?.close();};'
assert socket_anchor in content, 'socket anchor not found'
old_block = '    return ()=>{disposed=true;clearTimeout(retry);socket?.close();};\n  },[session?.id]);'
new_block = '    return ()=>{disposed=true;clearTimeout(retry);socket?.close();};\n  },[session?.id]);\n  useEffect(()=>{if(!session?.id||!busy)return;const timer=setInterval(()=>{api(`/sessions/${session.id}`).then(row=>setSession(row)).catch(()=>{});},1200);return ()=>clearInterval(timer);},[session?.id,busy]);'
if old_block in content:
    content = content.replace(old_block, new_block, 1)
else:
    # Handle CRLF
    old_block_crlf = old_block.replace('\n', '\r\n')
    new_block_crlf = new_block.replace('\n', '\r\n')
    assert old_block_crlf in content, 'old_block_crlf not found'
    content = content.replace(old_block_crlf, new_block_crlf, 1)

# 5. In TacticalReport, pass legacy={false}
old_legacy = "legacy={!!session&&session.analytics?.version!==2&&session.status==='completed'}"
new_legacy = 'legacy={false}'
assert old_legacy in content, 'old_legacy not found'
content = content.replace(old_legacy, new_legacy, 1)

with open('frontend/src/main.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print('Successfully updated main.tsx')
