"""Modelo de projeção Cartola 2026 — cruzamento jogador x adversário por scout e posição.

Pesos oficiais (recuperados por regressão sobre 8.652 atuações de 2026, R²=1,000):
G 8 | A 5 | FT 3 | FD 1,2 | FF 0,8 | FS 0,5 | PS 1 | PP -4 | I -0,1
DS 1,5 | SG 5 | DE 1,3 | DP 7 | GS -1 | FC -0,3 | PC -1 | CA -1 | CV -3 | GC -3
"""
import numpy as np, pandas as pd
from math import exp, factorial
from fixtures import FIX

W = dict(G=8,A=5,FT=3,FD=1.2,FF=0.8,FS=0.5,PS=1,PP=-4,I=-0.1,DS=1.5,SG=5,DE=1.3,DP=7,GS=-1,FC=-0.3,PC=-1,CA=-1,CV=-3,GC=-3)
ADJ = ['DS','FD','FF','FT','FS','FC','I','CA']   # scouts cruzados com o adversário por posição
RARE = ['PS','PP','PC','CV','GC','DP']             # raros: só taxa individual
POS = {1:'GOL',2:'LAT',3:'ZAG',4:'MEI',5:'ATA',6:'TEC'}

def poisson_pmf(l, k): return exp(-l) * l**k / factorial(k)

class Model:
    def __init__(self, long, upto, half_life=10, k_player=3.0, k_team=4.0, alpha=0.7, k_goal=5.0):
        self.p = dict(half_life=half_life,k_player=k_player,k_team=k_team,alpha=alpha,k_goal=k_goal)
        L = long[(long.rodada <= upto)].copy()
        L['w'] = 0.5 ** ((upto - L.rodada) / half_life)
        self.upto = upto
        P = L[(L.entrou_em_campo == True) & (L.posicao_id != 6)].copy()
        # adversário e mando de cada clube em cada rodada
        opp, home = {}, {}
        for r in range(1, upto + 1):
            for a, b in FIX[r]:
                opp[(r, a)], opp[(r, b)] = b, a
                home[(r, a)], home[(r, b)] = 1, 0
        P['opp'] = [opp.get((r, c)) for r, c in zip(P.rodada, P.clube)]
        P['home'] = [home.get((r, c)) for r, c in zip(P.rodada, P.clube)]
        P = P.dropna(subset=['opp'])
        self.P = P
        S = list(W.keys())
        # --- médias de posição (prior) ---
        self.pos_mean = P.groupby('posicao_id')[S].mean()
        # --- mando: multiplicador por scout ---
        hm = P.groupby('home')[ADJ + ['G', 'A', 'DE']].mean()
        self.home_mult = {s: (2*hm.loc[1, s]/(hm.loc[1, s]+hm.loc[0, s]), 2*hm.loc[0, s]/(hm.loc[1, s]+hm.loc[0, s])) for s in hm.columns}
        # --- produção/concessão por clube-jogo e posição ---
        g = P.groupby(['rodada', 'clube', 'opp', 'posicao_id'])[ADJ + ['G', 'A', 'DE']].sum().reset_index()
        g = g.merge(L[['rodada']].drop_duplicates(), on='rodada')
        g['w'] = 0.5 ** ((upto - g.rodada) / half_life)
        # concedido por X = o que os adversários de X produziram contra X
        conc = g.rename(columns={'opp': 'team'})
        league = g.groupby('posicao_id')[ADJ].mean()
        self.conc_idx = {}
        kt = k_team
        for (team, pos), d in conc.groupby(['team', 'posicao_id']):
            wsum = d.w.sum()
            for s in ADJ:
                mu = league.loc[pos, s]
                if mu <= 0: self.conc_idx[(team, pos, s)] = 1.0; continue
                val = ((d[s]*d.w).sum() + kt*mu) / (wsum + kt)
                self.conc_idx[(team, pos, s)] = (val / mu) ** alpha
        # --- força de ataque/defesa (gols) ---
        tg = P.groupby(['rodada', 'clube', 'opp', 'home'])[['G']].sum().reset_index()
        gc = P.groupby(['rodada', 'clube'])['GC'].sum()   # gols contra marcados pelo clube = gol a favor do adversário
        tg['gf'] = tg.G + [gc.get((r, o), 0) for r, o in zip(tg.rodada, tg.opp)]
        tg['w'] = 0.5 ** ((upto - tg.rodada) / half_life)
        self.avg_home = tg[tg.home == 1].gf.mean(); self.avg_away = tg[tg.home == 0].gf.mean()
        mu = tg.gf.mean(); self.mu_goals = mu
        self.att, self.dfn, self.team_gpg = {}, {}, {}
        for t, d in tg.groupby('clube'):
            self.att[t] = ((d.gf*d.w).sum() + k_goal*mu) / (d.w.sum() + k_goal) / mu
            self.team_gpg[t] = ((d.gf*d.w).sum() + k_goal*mu) / (d.w.sum() + k_goal)
        for t, d in tg.groupby('opp'):
            self.dfn[t] = ((d.gf*d.w).sum() + k_goal*mu) / (d.w.sum() + k_goal) / mu
        # finalizações no alvo produzidas (para DE do goleiro adversário)
        sh = P.assign(on=P.FD + P.G).groupby(['rodada', 'clube']).on.sum().reset_index()
        sh['w'] = 0.5 ** ((upto - sh.rodada) / half_life)
        mo = sh.on.mean(); self.shot_idx = {}
        for t, d in sh.groupby('clube'):
            self.shot_idx[t] = (((d.on*d.w).sum() + kt*mo) / (d.w.sum() + kt) / mo) ** alpha
        # --- taxas individuais (encolhidas para a média da posição) ---
        self.rates = {}
        for pid, d in P.groupby('atleta_id'):
            pos = int(d.posicao_id.iloc[-1]); prior = self.pos_mean.loc[pos]
            wsum = d.w.sum()
            r = {s: ((d[s]*d.w).sum() + k_player*prior[s]) / (wsum + k_player) for s in S}
            r['_n'] = len(d); r['_pos'] = pos
            r['_tm'] = d.clube.iloc[-1]
            r['_avgpts'] = d.pontos_num.mean()
            self.rates[pid] = r

    def match(self, team, opp, is_home):
        lh = self.avg_home if is_home else self.avg_away
        la = self.avg_away if is_home else self.avg_home
        lam_for = lh * self.att.get(team, 1) * self.dfn.get(opp, 1)
        lam_ag = la * self.att.get(opp, 1) * self.dfn.get(team, 1)
        pw = pd_ = 0.0
        for i in range(10):
            for j in range(10):
                p = poisson_pmf(lam_for, i) * poisson_pmf(lam_ag, j)
                if i > j: pw += p
                elif i == j: pd_ += p
        return dict(xg=lam_for, xga=lam_ag, p_sg=exp(-lam_ag), p_win=pw, p_draw=pd_)

    def project(self, pid, team, opp, is_home):
        r = self.rates[pid]; pos = r['_pos']; m = self.match(team, opp, is_home)
        hidx = 0 if is_home else 1
        lam = {}
        for s in ADJ:
            lam[s] = r[s] * self.conc_idx.get((opp, pos, s), 1.0) * self.home_mult[s][hidx]
        gscale = m['xg'] / max(self.team_gpg.get(team, self.mu_goals), 0.3)
        lam['G'] = r['G'] * gscale; lam['A'] = r['A'] * gscale
        for s in RARE: lam[s] = r[s]
        if pos == 1:
            lam['DE'] = r['DE'] * self.shot_idx.get(opp, 1) * self.home_mult['DE'][hidx]
            lam['GS'] = m['xga']
        else:
            lam['DE'] = 0; lam['GS'] = 0
        lam['SG'] = m['p_sg'] if pos in (1, 2, 3) else 0
        exp_pts = sum(W[s]*lam.get(s, 0) for s in W)
        var = sum((W[s]**2)*lam.get(s, 0) for s in W if s != 'SG') + (25*m['p_sg']*(1-m['p_sg']) if pos in (1,2,3) else 0)
        return exp_pts, var**0.5, lam, m
