"""Atualiza o modelo da Prancheta Cartola 2026.
Uso:  git clone --depth 1 https://github.com/henriquepgomide/caRtola cartola   (1ª vez; depois: git -C cartola pull)
      python3 atualizar_modelo.py          -> gera model_data.json (scouts do caRtola)
      python3 atualizar_modelo.py --api    -> idem + status/preços/partidas direto da API da Globo (rodar no Brasil, perto do fechamento)
      python3 build_html.py                -> monta prancheta_cartola.html (template + motor + dados) para abrir local ou republicar
Requer: pandas, numpy. Precisa de model.py, fixtures.py e wx.py na mesma pasta.
Clima: edite PREV_R31/KICKOFF em wx.py com a previsão mais recente (ou ligue a uma API, ex. Open-Meteo) antes de rodar.
"""
import pandas as pd, numpy as np, json
from fixtures import FIX
import glob,os,sys
RAW=os.environ.get("CARTOLA_RAW","cartola/data/01_raw/2026")
UPTO=max(int(os.path.basename(f)[7:-4]) for f in glob.glob(RAW+"/rodada-*.csv"))
SC=['A','CA','CV','DE','DP','DS','FC','FD','FF','FS','FT','G','GC','GS','I','PC','PP','PS','SG','V']
frames={}
for r in range(1,UPTO+1):
    d=pd.read_csv(f"{RAW}/rodada-{r}.csv")
    d=d.rename(columns=lambda c:c.replace('atletas.',''))
    for c in SC:
        if c not in d: d[c]=0
    d[SC]=d[SC].fillna(0)
    frames[r]=d.set_index('atleta_id')
rows=[]
prev=None
for r in range(1,UPTO+1):
    d=frames[r]
    cum=d[SC]
    if prev is None: delta=cum.copy()
    else:
        p=prev.reindex(cum.index).fillna(0); delta=cum-p
    delta=delta.clip(lower=0)
    out=d[['apelido','clube.id.full.name','posicao_id','pontos_num','entrou_em_campo','preco_num','status_id']].join(delta)
    out['rodada']=r
    rows.append(out.reset_index())
    # carry forward cumulative for players absent next file
    prev = cum if prev is None else pd.concat([prev[~prev.index.isin(cum.index)],cum])
long=pd.concat(rows,ignore_index=True)
long=long.rename(columns={'clube.id.full.name':'clube'})
played=long[long.entrou_em_campo==True]


# ---- export ----
from model import Model, W, ADJ, POS
from fixtures import FIX, DATAS
L=long
UPTO=int(L.rodada.max())
M=Model(L,UPTO,alpha=0.5)
# --- técnico: ajuste empírico pts ~ a + b*xg + c*xga + d*p_win (rodadas 10-29)
rows=[]
for r in range(10,UPTO+1):
    for a,b in FIX[r]:
        for t,o,h in ((a,b,1),(b,a,0)):
            c=L[(L.rodada==r)&(L.clube==t)&(L.posicao_id==6)&(L.entrou_em_campo==True)]
            if len(c)==0: continue
            m=M.match(t,o,h); rows.append((m['xg'],m['xga'],m['p_win'],c.pontos_num.iloc[0]))
R=np.array(rows); X=np.c_[np.ones(len(R)),R[:,:3]]; coef,*_=np.linalg.lstsq(X,R[:,3],rcond=None)
pred=X@coef; print('coach coef',coef.round(3),'corr',np.corrcoef(pred,R[:,3])[0,1].round(3),'n',len(R))
L=L.sort_values(['atleta_id','rodada'])
L['played']=L.entrou_em_campo.astype(int)
L['part5']=L.groupby('atleta_id').played.transform(lambda s:s.rolling(5,min_periods=1).mean())
# --- P(joga): logística status/participação/preço (snapshot r-1 -> entrou em campo em r)
from sklearn.linear_model import LogisticRegression
_rows=[]
for _r in range(2,UPTO+1):
    _a=L[L.rodada==_r-1][['atleta_id','status_id','posicao_id','preco_num','part5','played']].set_index('atleta_id')
    _b=L[L.rodada==_r][['atleta_id','played']].set_index('atleta_id').rename(columns={'played':'y'})
    _rows.append(_a.join(_b,how='inner'))
_J=pd.concat(_rows); _J=_J[_J.posicao_id!=6]
_X=pd.DataFrame({'s7':(_J.status_id==7).astype(int),'s2':(_J.status_id==2).astype(int),'s6':(_J.status_id==6).astype(int),'part5':_J.part5,'last':_J.played,'lp':np.log(_J.preco_num.clip(1)),'gk':(_J.posicao_id==1).astype(int)})
_m=LogisticRegression(max_iter=1000).fit(_X,_J.y)
PPLAY={'coef':dict(zip(_X.columns,_m.coef_[0].round(4).tolist())),'b':round(float(_m.intercept_[0]),4)}
print('P(joga) coef',PPLAY)
last=L[L.rodada==UPTO].set_index('atleta_id')
S=list(W.keys())
players=[]
for pid,x in last.iterrows():
    r=M.rates.get(pid)
    players.append(dict(id=int(pid),n=x.apelido,c=x.clube,p=int(x.posicao_id),pr=round(float(x.preco_num),2),
        st=int(x.status_id),mp=round(float(r['_avgpts']),2) if r else None,j=int(r['_n']) if r else 0,
        pt5=round(float(x.part5),2),lst=int(x.played),
        r=[round(float(r[s]),4) for s in S] if r else None))
clubs=sorted(L.clube.unique())
clube_ids=last.reset_index().groupby('clube').clube_id.first().astype(int).to_dict() if 'clube_id' in last else {}
data=dict(
  meta=dict(ate_rodada=UPTO,gerado=pd.Timestamp.now().strftime('%Y-%m-%d'),fonte='github.com/henriquepgomide/caRtola (snapshots oficiais da API Cartola) + tabela CBF',
            params=M.p),
  W=W,S=S,ADJ=ADJ,
  pos_mean={int(k):[round(float(v),4) for v in M.pos_mean.loc[k,S]] for k in M.pos_mean.index},
  home_mult={s:[round(v[0],4),round(v[1],4)] for s,v in M.home_mult.items()},
  avg_home=M.avg_home,avg_away=M.avg_away,mu=M.mu_goals,
  teams={t:dict(att=round(M.att.get(t,1),4),dfn=round(M.dfn.get(t,1),4),gpg=round(M.team_gpg.get(t,M.mu_goals),4),
        shot=round(M.shot_idx.get(t,1),4),
        conc={str(p):{s:round(M.conc_idx.get((t,p,s),1.0),4) for s in ADJ} for p in range(1,6)}) for t in clubs},
  fixtures={str(r):[list(g) for g in FIX[r]] for r in range(31,39)},
  datas=DATAS,coach=[round(float(c),4) for c in coef],players=players)
# rodada 33: CBF/Band publicou Palmeiras x Santos (mando invertido vs espelho do turno)
f33=data['fixtures']['33']; f33[[i for i,g in enumerate(f33) if set(g)=={'PAL','SAN'}][0]]=['PAL','SAN']
from wx import wx_rodada, ELAST, ESTADIOS
data['wx']={str(r):wx_rodada(r) for r in range(31,39) if wx_rodada(r)}
data['elast']=ELAST
data['pplay']=PPLAY
data['estadios']={k:v[0] for k,v in ESTADIOS.items()}
if '--api' in sys.argv:
    import urllib.request, time
    # [repo] dois hosts da mesma API: o 2º é o que o próprio caRtola usa no GitHub Actions (comprovadamente alcançável de lá)
    HOSTS=('https://api.cartola.globo.com','https://api.cartolafc.globo.com')
    def _get(path):
        err=None
        for h in HOSTS:
            try:
                req=urllib.request.Request(h+path,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
                return json.load(urllib.request.urlopen(req,timeout=30))
            except Exception as e: err=e; print('falhou',h+path,'->',repr(e))
        raise err
    try:
        merc=_get('/atletas/mercado'); json.dump(merc,open('mercado.json','w'),ensure_ascii=False)
        # [repo] código do clube = o mesmo dos CSVs do caRtola (campo "nome" da API), que é a chave de data['teams']
        _f=frames[UPTO]; id2c={int(k):v for k,v in _f.groupby('clube_id')['clube.id.full.name'].first().items()} if 'clube_id' in _f else {}
        ab={int(k):(id2c.get(int(k)) or v.get('nome') or v.get('abreviacao')) for k,v in merc['clubes'].items()}
        byid={p['id']:p for p in data['players']}
        for a in merc['atletas']:
            p=byid.get(a['atleta_id'])
            if p: p['st']=a['status_id']; p['pr']=a['preco_num']; p['c']=ab.get(a['clube_id'],p['c'])
            else: data['players'].append(dict(id=a['atleta_id'],n=a['apelido'],c=ab.get(a['clube_id']),p=a['posicao_id'],pr=a['preco_num'],st=a['status_id'],mp=a.get('media_num'),j=0,r=None,pt5=0.5,lst=0,novo=True))
        # [repo] quem saiu do mercado oficial sai do painel (mesma regra da importação manual no navegador)
        _ids={a['atleta_id'] for a in merc['atletas']}
        if len(_ids)>=400:
            _antes=len(data['players']); data['players']=[p for p in data['players'] if p['id'] in _ids]
            print('fora do mercado, removidos:',_antes-len(data['players']))
        data['meta']['mercado']=dict(rodada=merc['atletas'][0]['rodada_id'] if merc['atletas'] else None,n=len(merc['atletas']),capturado=pd.Timestamp.now().strftime('%Y-%m-%d %H:%M'),ts=int(time.time()*1000))
        print('mercado aplicado:',len(merc['atletas']),'atletas')
        part=_get('/partidas'); json.dump(part,open('partidas.json','w'),ensure_ascii=False)
        jogos=[[ab.get(x['clube_casa_id']),ab.get(x['clube_visitante_id'])] for x in part['partidas'] if x.get('valida',True)]
        if part.get('rodada') and str(part['rodada']) in data['fixtures']: data['fixtures'][str(part['rodada'])]=jogos; data['meta']['mercado']['rodada_alvo']=int(part['rodada']); print('partidas da rodada',part['rodada'],':',len(jogos),'válidas')
        # [repo] opcional: situação do mercado e horário de fechamento (não derruba nada se o formato mudar)
        try:
            stt=_get('/mercado/status'); json.dump(stt,open('status.json','w'),ensure_ascii=False)
            _m=data['meta']['mercado']
            if isinstance(stt.get('status_mercado'),int): _m['status']=stt['status_mercado']
            _fts=(stt.get('fechamento') or {}).get('timestamp')
            if isinstance(_fts,(int,float)) and _fts>0: _m['fecha_ts']=int(_fts)
            if isinstance(stt.get('rodada_atual'),int) and 'rodada_alvo' not in _m and str(stt['rodada_atual']) in data['fixtures']: _m['rodada_alvo']=stt['rodada_atual']
        except Exception as e: print('status do mercado indisponível:',repr(e))
    except Exception as e: print('API indisponível:',repr(e))
json.dump(data,open('model_data.json','w'),ensure_ascii=False,separators=(',',':'))
print(len(players),'jogadores', round(len(json.dumps(data))/1024),'KB')
