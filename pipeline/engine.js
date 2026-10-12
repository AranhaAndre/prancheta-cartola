// ===== Motor de projeção + otimizador (espelha model.py) =====
const POSN = {1:'GOL',2:'LAT',3:'ZAG',4:'MEI',5:'ATA',6:'TEC'};
const STATUS = {7:'Provável',2:'Dúvida',3:'Suspenso',5:'Contundido',6:'Nulo'};
const CLUB_IDS = {262:'FLA',263:'BOT',264:'COR',265:'BAH',266:'FLU',267:'VAS',275:'PAL',276:'SAO',277:'SAN',280:'RBB',282:'CAM',283:'CRU',284:'GRE',285:'INT',287:'VIT',293:'CAP',294:'CFC',315:'CHA',364:'REM',2305:'MIR'};
const RARE = ['PS','PP','PC','CV','GC','DP'];
const FORMACOES = {'3-4-3':[1,0,3,4,3],'3-5-2':[1,0,3,5,2],'4-3-3':[1,2,2,3,3],'4-4-2':[1,2,2,4,2],'4-5-1':[1,2,2,5,1],'5-3-2':[1,2,3,3,2],'5-4-1':[1,2,3,4,1]};

function pmf(l,k){let f=1;for(let i=2;i<=k;i++)f*=i;return Math.exp(-l)*Math.pow(l,k)/f;}

// wx = {rain:0..1, temp:°C} ou null; E = elasticidades
function wxMult(E, wx, s){
  if(!wx||!E) return 1;
  const r=(wx.rain||0)*(E.rain[s]||0), h=Math.max(0,(wx.temp??E.T0)-E.T0)*(E.heat[s]||0);
  return Math.max(0.5,(1+r)*(1+h));
}
function matchInfo(D, team, opp, home, wx, E){
  const T=D.teams, lh=home?D.avg_home:D.avg_away, la=home?D.avg_away:D.avg_home;
  const wm=wxMult(E,wx,'XG');
  const xg=lh*(T[team]?.att??1)*(T[opp]?.dfn??1)*wm, xga=la*(T[opp]?.att??1)*(T[team]?.dfn??1)*wm;
  let pw=0,pd=0;
  for(let i=0;i<10;i++)for(let j=0;j<10;j++){const p=pmf(xg,i)*pmf(xga,j); if(i>j)pw+=p; else if(i===j)pd+=p;}
  return {xg,xga,p_sg:Math.exp(-xga),p_win:pw,p_draw:pd};
}

// retorna {e, sd, lam, mult, m}
function project(D, pl, team, opp, home, wx, E){
  const S=D.S, W=D.W, pos=pl.p;
  const m=matchInfo(D,team,opp,home,wx,E);
  if(pos===6){ const c=D.coach; const e=c[0]+c[1]*m.xg+c[2]*m.xga+c[3]*m.p_win; return {e,sd:3,lam:{},mult:{},m}; }
  const rr = pl.r || D.pos_mean[pos];
  const r={}; S.forEach((s,i)=>r[s]=rr[i]);
  const h=home?0:1, lam={}, mult={};
  for(const s of D.ADJ){ const ci=D.teams[opp]?.conc?.[pos]?.[s]??1; const wm=wxMult(E,wx,s); mult[s]=ci; mult['wx_'+s]=wm; lam[s]=r[s]*ci*D.home_mult[s][h]*wm; }
  const gs=m.xg/Math.max(D.teams[team]?.gpg??D.mu,0.3);
  mult.G=gs; lam.G=r.G*gs; lam.A=r.A*gs;
  for(const s of RARE) lam[s]=r[s];
  if(pos===1){ mult.DE=D.teams[opp]?.shot??1; lam.DE=r.DE*mult.DE*D.home_mult.DE[h]*wxMult(E,wx,'DE'); lam.GS=m.xga; } else {lam.DE=0;lam.GS=0;}
  lam.SG=(pos<=3)?m.p_sg:0;
  let e=0,v=0; for(const s in W){ const l=lam[s]||0; e+=W[s]*l; if(s!=='SG') v+=W[s]*W[s]*l; }
  if(pos<=3) v+=25*m.p_sg*(1-m.p_sg);
  return {e,sd:Math.sqrt(v),lam,mult,m};
}

function roundMap(fix){ const mp={}; fix.forEach(([a,b])=>{mp[a]={opp:b,home:true};mp[b]={opp:a,home:false};}); return mp; }

// Otimizador exato: mochila por posição (DP) + convolução entre posições; preço em décimos (arredondado p/ cima)
function optimize(cands, budget, formacoes){
  const B=Math.floor(budget*10+1e-9), NEG=-1e9;
  const byPos={1:[],2:[],3:[],4:[],5:[],6:[]};
  cands.forEach(c=>byPos[c.p].push(c));
  for(const p in byPos){ byPos[p].sort((a,b)=>b.e-a.e); const top=byPos[p].slice(0,28); byPos[p].forEach(c=>{if(c.lock&&!top.includes(c))top.push(c);}); byPos[p]=top; }
  const locked=cands.filter(c=>c.lock);
  const cache={};
  function posTable(p,k){ // melhor soma escolhendo exatamente k da posição p, custo<=c
    const key=p+'_'+k; if(cache[key])return cache[key];
    const L=byPos[p], n=L.length;
    const lockedHere=L.filter(c=>c.lock).length;
    let best=Array.from({length:k+1},()=>new Float64Array(B+1).fill(NEG));
    let pick=[]; best[0].fill(0); // best[j][c]: j escolhidos, custo<=c
    const mustAll=L.map(c=>!!c.lock);
    for(let i=0;i<n;i++){
      const cost=Math.ceil(L[i].pr*10-1e-9), val=L[i].e;
      const nb=best.map(a=>Float64Array.from(a)), choose=Array.from({length:k+1},()=>new Uint8Array(B+1));
      for(let j=1;j<=k;j++) for(let c=cost;c<=B;c++){ const v=best[j-1][c-cost]+val; if(v>nb[j][c]){nb[j][c]=v;choose[j][c]=1;} }
      if(mustAll[i]){ // travado: obrigatório escolher
        for(let j=0;j<=k;j++) for(let c=0;c<=B;c++) if(!choose[j][c]) nb[j][c]=NEG;
      }
      pick.push(choose); best=nb;
    }
    const res={val:best[k],pick,L,k}; cache[key]=res; return res;
  }
  function recon(t,c){ const out=[]; let j=t.k; for(let i=t.L.length-1;i>=0;i--){ if(j>0&&t.pick[i][j][c]){ out.push(t.L[i]); c-=Math.ceil(t.L[i].pr*10-1e-9); j--; } } return out; }
  let bestRes=null;
  for(const [nome,f] of Object.entries(formacoes)){
    const need={1:f[0],2:f[1],3:f[2],4:f[3],5:f[4],6:1};
    if(locked.some(c=>need[c.p]===0)) continue;
    if(Object.entries(need).some(([p,k])=>byPos[p].length<k)) continue;
    let acc=new Float64Array(B+1).fill(0), splits=[];
    for(const p of [1,2,3,4,5,6]){
      const t=posTable(p,need[p]); const nv=new Float64Array(B+1).fill(NEG), sp=new Int32Array(B+1);
      for(let c=0;c<=B;c++){ for(let x=0;x<=c;x++){ const a=acc[c-x], b=t.val[x]; if(a>NEG/2&&b>NEG/2&&a+b>nv[c]){nv[c]=a+b;sp[c]=x;} } }
      splits.push({p,t,sp}); acc=nv;
    }
    if(acc[B]<=NEG/2) continue;
    if(!bestRes||acc[B]>bestRes.val){
      let c=B, team=[];
      for(let i=splits.length-1;i>=0;i--){ const {t,sp}=splits[i]; const x=sp[c]; team=team.concat(recon(t,x)); c-=x; }
      bestRes={val:acc[B],formacao:nome,team};
    }
  }
  return bestRes;
}
if(typeof module!=='undefined') module.exports={project,matchInfo,wxMult,optimize,roundMap,FORMACOES,POSN,STATUS,CLUB_IDS};

// ===== Probabilidade de jogar (logística ajustada em 2026: status, participação recente, preço) =====
function pPlay(D, pl){
  if(pl.p===6) return pl.st===7?0.98:(pl.st===2?0.7:0.1);
  const c=D.pplay.coef, b=D.pplay.b;
  const s7=pl.st===7?1:0, s2=pl.st===2?1:0, s6=pl.st===6?1:0;
  if(pl.st===3||pl.st===5) return pl.st===3?0.015:0.08;
  const part5=pl.pt5??0.6, last=pl.lst??1;
  const z=b+c.s7*s7+c.s2*s2+c.s6*s6+c.part5*part5+c.last*last+c.lp*Math.log(Math.max(pl.pr,1))+c.gk*(pl.p===1?1:0);
  return 1/(1+Math.exp(-z));
}

// ===== Simulação Monte Carlo da rodada =====
function rpois(l){ if(l<=0) return 0; if(l>30){ const v=Math.round(l+Math.sqrt(l)*gauss()); return v<0?0:v; } const L=Math.exp(-l); let k=0,p=1; do{k++;p*=Math.random();}while(p>L); return k-1; }
function gauss(){ let u=0,v=0; while(u===0)u=Math.random(); while(v===0)v=Math.random(); return Math.sqrt(-2*Math.log(u))*Math.cos(2*Math.PI*v); }
// starters: [{id,p,lam,m,c,pp,cap}], bench: {pos:{id,p,lam,m,c,pp}}, luxo: pos|null
function simulate(D, starters, bench, luxoPos, N){
  N=N||3000; const W=D.W; const tot=new Float64Array(N); const contrib={}; let luxoGain=0, benchGain=0;
  const all=starters.concat(Object.values(bench)); all.forEach(p=>contrib[p.id]=0);
  const teamsOf=[...new Set(all.map(p=>p.c))];
  for(let n=0;n<N;n++){
    const gs={}; teamsOf.forEach(t=>{ const q=all.find(p=>p.c===t); gs[t]=rpois(q.m.xga); });
    const pts={}, played={};
    for(const p of all){
      const pl=Math.random()<p.pp; played[p.id]=pl; if(!pl){pts[p.id]=0;continue;}
      if(p.p===6){ pts[p.id]=p.e+3*gauss(); continue; }
      let s=0; for(const k in p.lam){ if(k==='SG'||k==='GS') continue; const l=p.lam[k]; if(l>0) s+=W[k]*rpois(l); }
      if(p.p<=3){ if(gs[p.c]===0) s+=W.SG; if(p.p===1) s+=W.GS*gs[p.c]; }
      pts[p.id]=s;
    }
    let total=0;
    const byPos={}; starters.forEach(p=>{(byPos[p.p]=byPos[p.p]||[]).push(p);});
    const used=new Set();
    // Reserva de Luxo (antes do banco normal): só se todos os titulares da posição jogaram
    let luxoApplied=null;
    if(luxoPos&&bench[luxoPos]&&played[bench[luxoPos].id]){
      const S=byPos[luxoPos]||[]; if(S.length&&S.every(p=>played[p.id])){
        let worst=S[0]; for(const p of S){ if(pts[p.id]<pts[worst.id]||(pts[p.id]===pts[worst.id]&&p.cap)) worst=p; }
        if(pts[bench[luxoPos].id]>pts[worst.id]){ luxoApplied=worst.id; used.add(bench[luxoPos].id); luxoGain+=pts[bench[luxoPos].id]-pts[worst.id]; contrib[bench[luxoPos].id]+=pts[bench[luxoPos].id]; }
      }
    }
    for(const p of starters){
      let v;
      if(luxoApplied===p.id){ v=pts[bench[luxoPos].id]; }
      else if(played[p.id]){ v=pts[p.id]*(p.cap?1.5:1); contrib[p.id]+=v; }
      else { const r=bench[p.p]; if(r&&!used.has(r.id)&&played[r.id]&&pts[r.id]>0){ v=pts[r.id]; used.add(r.id); benchGain+=v; contrib[r.id]+=v; } else v=0; }
      total+=v;
    }
    tot[n]=total;
  }
  const sorted=Float64Array.from(tot).sort(); const mean=tot.reduce((a,b)=>a+b,0)/N;
  const sd=Math.sqrt(tot.reduce((a,b)=>a+(b-mean)**2,0)/N);
  for(const k in contrib) contrib[k]/=N;
  return {mean,sd,p10:sorted[Math.floor(N*0.1)],p50:sorted[Math.floor(N*0.5)],p90:sorted[Math.floor(N*0.9)],luxoGain:luxoGain/N,benchGain:benchGain/N,contrib};
}

// ===== Banco: melhor reserva por posição com preço <= titular mais barato da posição =====
function pickBench(starters, pool){
  const bench={}; const ids=new Set(starters.map(p=>p.id));
  const byPos={}; starters.forEach(p=>{(byPos[p.p]=byPos[p.p]||[]).push(p);});
  for(const pos in byPos){ if(+pos===6) continue;
    const minPr=Math.min(...byPos[pos].map(p=>p.pr));
    const c=pool.filter(p=>p.p===+pos&&!ids.has(p.id)&&p.pr<=minPr+1e-9).sort((a,b)=>b.ev-a.ev)[0];
    if(c) bench[pos]=c;
  }
  return bench;
}
if(typeof module!=='undefined') Object.assign(module.exports,{pPlay,simulate,pickBench});
