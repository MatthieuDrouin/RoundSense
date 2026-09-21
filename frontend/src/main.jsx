import React, {useEffect, useMemo, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {LineChart, Line, ResponsiveContainer, YAxis, Tooltip} from 'recharts';
import {MAP_DATA, mapImageStyle, onRadar, radarUrl, toDisplayPoint, worldToRadar} from './mapData';
import './styles.css';

const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
const WS = API.replace(/^http/, 'ws') + '/ws';

function pct(v){ return `${Math.round((v ?? .5)*100)}%`; }
function money(v){ return `$${Number(v||0).toLocaleString()}`; }
function signed(v){ const n=Number(v||0); return `${n>=0?'+':''}${n.toFixed(2)}`; }
function formatClock(seconds){
  const total=Math.max(0,Math.ceil(Number(seconds)||0));
  const mins=Math.floor(total/60);
  const secs=total%60;
  return `${mins}:${String(secs).padStart(2,'0')}`;
}
function timerLabel(state){
  const phase=String(state.timer_phase||'').toLowerCase();
  if(state.bomb_state==='planted'||phase.includes('bomb')) return 'BOMB TIMER';
  if(phase.includes('freez')) return 'FREEZE TIME';
  if(state.round_phase==='over') return 'ROUND OVER';
  return 'ROUND TIMER';
}

function TacticalMap({state}){
  const positioned=(state.players||[]).filter(p=>p.x!=null&&p.y!=null&&p.alive);
  const avgZ=positioned.length?positioned.reduce((s,p)=>s+Number(p.z||0),0)/positioned.length:null;
  const bg=radarUrl(state.map_name,avgZ);
  const meta=MAP_DATA[state.map_name];

  const rawBomb=state.bomb_x!=null&&state.bomb_y!=null
    ?worldToRadar(state.map_name,state.bomb_x,state.bomb_y)
    :null;
  const bomb=toDisplayPoint(state.map_name,rawBomb);

  if(!meta) return <div className="mapFallback">No radar transform configured for <b>{state.map_name}</b> yet.</div>;

  const siteA=meta.a?toDisplayPoint(state.map_name,{x:meta.a[0],y:meta.a[1]}):null;
  const siteB=meta.b?toDisplayPoint(state.map_name,{x:meta.b[0],y:meta.b[1]}):null;

  return <div className="radarWrap">
    <div className="radar">
      {bg&&<img className="radarImage" src={bg} alt={state.map_name} style={mapImageStyle(state.map_name)} onError={e=>{e.currentTarget.style.display='none'}}/>}
      {onRadar(siteA)&&<span className="site siteA" style={{left:`${siteA.x*100}%`,top:`${siteA.y*100}%`}}>A</span>}
      {onRadar(siteB)&&<span className="site siteB" style={{left:`${siteB.x*100}%`,top:`${siteB.y*100}%`}}>B</span>}
      {positioned.map(p=>{
        const raw=worldToRadar(state.map_name,p.x,p.y);
        const pt=toDisplayPoint(state.map_name,raw);
        if(!onRadar(pt)) return null;
        return <span
          key={p.steam_id}
          className={`playerDot ${p.team==='CT'?'ctDot':'tDot'}`}
          title={`${p.name} · ${p.team} · ${p.health} HP`}
          style={{left:`${pt.x*100}%`,top:`${pt.y*100}%`}}
        />
      })}
      {onRadar(bomb)&&<span className="bombDot" title={`Bomb: ${state.bomb_state}`} style={{left:`${bomb.x*100}%`,top:`${bomb.y*100}%`}}>◆</span>}
    </div>
    <div className="legend">
      <span><i className="ctLegend"></i>CT</span>
      <span><i className="tLegend"></i>T</span>
      <span><i className="bombLegend"></i>Bomb</span>
      <small>{positioned.length} alive positioned players</small>
    </div>
  </div>
}

function TacticalIntel({tactical}){
  if(!tactical) return null;
  const adj=tactical.positioning_adjustment||0;
  return <>
    <div className="intelRow"><span>Attack focus</span><b>{tactical.target_site||'—'}</b></div>
    <div className="intelRow"><span>T pressure near site</span><b>{tactical.t_site_pressure}</b></div>
    <div className="intelRow"><span>CT coverage near site</span><b>{tactical.ct_site_coverage}</b></div>
    <div className="intelRow"><span>Positioning adjustment</span><b className={adj<0?'tAdv':adj>0?'ctAdv':''}>{signed(adj)} log-odds</b></div>
    <p className="intelNote">{tactical.note}</p>
  </>;
}

function App(){
  const [state,setState]=useState(null);
  const [history,setHistory]=useState([]);
  const [status,setStatus]=useState('connecting');

  useEffect(()=>{
    fetch(`${API}/api/state`).then(r=>r.ok?r.json():null).then(x=>x&&setState(x)).catch(()=>{});
    const ws = new WebSocket(WS);
    ws.onopen=()=>setStatus('live');
    ws.onclose=()=>setStatus('offline');
    ws.onerror=()=>setStatus('offline');
    ws.onmessage=(e)=>{
      const s=JSON.parse(e.data);
      setState(s);
      setHistory(h=>[...h,{n:s.round_number,p:Math.round(s.ct_win_probability*100)}].slice(-60));
    };
    return ()=>ws.close();
  },[]);

  const topPlayers=useMemo(()=>state?.players?.slice(0,5)||[],[state]);
  if(!state) return <div className="empty"><h1>RoundSense</h1><p>Waiting for CS2 telemetry…</p><p>Run <code>python scripts/simulate_gsi.py</code> for demo data.</p><span className={`dot ${status}`}></span> {status}</div>;

  return <main>
    <header>
      <div><h1>RoundSense</h1><p>{state.map_name} · Round {state.round_number} · {state.round_phase}</p></div>
      <div className="live"><span className={`dot ${status}`}></span>{status.toUpperCase()}</div>
    </header>

    <section className="score">
      <div className="teamScore"><b>CT</b><strong>{state.ct_score}</strong></div>
      <div className="prob">
        <small>ROUND WIN PROBABILITY</small>
        <div className="bar"><i style={{width:pct(state.ct_win_probability)}}></i></div>
        <span>{pct(state.ct_win_probability)} CT</span><span>{pct(state.t_win_probability)} T</span>
      </div>
      <div className={`timerBox ${state.bomb_state==='planted'?'bombTimer':''}`}>
        <small>{timerLabel(state)}</small>
        <strong>{formatClock(state.round_time_remaining)}</strong>
      </div>
      <div className="teamScore"><b>T</b><strong>{state.t_score}</strong></div>
    </section>

    {!state.full_team_data&&<div className="dataWarning">Limited GSI feed: full 5v5 positioning is not available, so team-wide predictions are less reliable.</div>}

    <section className="mapGrid">
      <article className="mapCard">
        <div className="cardTitle"><h2>Live Tactical Map</h2><small>Alive players, bomb location, and site pressure update live.</small></div>
        <TacticalMap state={state}/>
      </article>
      <article>
        <h2>Positioning Intelligence</h2>
        <TacticalIntel tactical={state.tactical}/>
        <div className="spatialStats">
          <span><small>CT spread</small><b>{state.tactical?.ct_spread??'—'}</b></span>
          <span><small>T spread</small><b>{state.tactical?.t_spread??'—'}</b></span>
          <span><small>Team distance</small><b>{state.tactical?.centroid_distance??'—'}</b></span>
          <span><small>Players tracked</small><b>{state.tactical?.players_with_position??0}</b></span>
        </div>
      </article>
    </section>

    <section className="grid">
      <article>
        <h2>Live State</h2>
        <div className="stats">
          <Stat k="Alive" a={state.ct.alive} b={state.t.alive}/>
          <Stat k="Health" a={state.ct.health} b={state.t.health}/>
          <Stat k="Armor" a={state.ct.armor} b={state.t.armor}/>
          <Stat k="Equipment" a={money(state.ct.equipment_value)} b={money(state.t.equipment_value)}/>
          <Stat k="Utility" a={state.ct.utility} b={state.t.utility}/>
        </div>
        <p className="bomb">Bomb: <b>{state.bomb_state}</b> · Timer: <b>{formatClock(state.round_time_remaining)}</b></p>
      </article>
      <article>
        <h2>Probability Trend</h2>
        <div className="chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={history}><YAxis domain={[0,100]} hide/><Tooltip/><Line type="monotone" dataKey="p" stroke="currentColor" strokeWidth={2} dot={false}/></LineChart></ResponsiveContainer></div>
        <small>Prediction source: {state.prediction_source}</small>
      </article>
      <article className="players">
        <h2>Top Players</h2>
        {topPlayers.map((p,i)=><div className="player" key={p.steam_id}><span>#{i+1} {p.name}<em>{p.team}</em></span><span>{p.kills}/{p.deaths} · {Number(p.impact||0).toFixed(2)}</span></div>)}
      </article>
      <article>
        <h2>Model Features</h2>
        <div className="featureList">{Object.entries(state.features).slice(0,12).map(([k,v])=><span key={k}><small>{k.replaceAll('_',' ')}</small><b>{typeof v==='number'?Number(v).toFixed(Number.isInteger(v)?0:2):v}</b></span>)}</div>
      </article>
    </section>
  </main>;
}

function Stat({k,a,b}){ return <div><span>{a}</span><small>{k}</small><span>{b}</span></div> }
createRoot(document.getElementById('root')).render(<App/>);
