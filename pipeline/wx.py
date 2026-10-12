"""Camada meteorológica: estádios, horários detalhados (CBF) e previsão da rodada.
Previsão abaixo capturada em 12/10/2026 (fonte: serviço de previsão do app; máx/mín diária e chance de chuva).
Temperatura no horário do jogo estimada por interpolação diurna entre mín e máx.
"""
import json, math

ESTADIOS = {  # mandante -> (nome, lat, lon)
 'FLA':('Maracanã',-22.912,-43.230),'FLU':('Maracanã',-22.912,-43.230),'BOT':('Nilton Santos',-22.893,-43.293),
 'VAS':('São Januário',-22.890,-43.228),'COR':('Neo Química Arena',-23.545,-46.474),'SAO':('Morumbis',-23.600,-46.720),
 'PAL':('Allianz Parque',-23.527,-46.678),'SAN':('Vila Belmiro',-23.953,-46.338),'RBB':('Cícero de Souza Marques',-22.950,-46.545),
 'MIR':('Maião',-20.816,-49.520),'CAM':('Arena MRV',-19.927,-44.000),'CRU':('Mineirão',-19.866,-43.971),
 'GRE':('Arena do Grêmio',-29.974,-51.195),'INT':('Beira-Rio',-30.065,-51.236),'CAP':('Arena da Baixada',-25.448,-49.277),
 'CFC':('Couto Pereira',-25.418,-49.258),'CHA':('Arena Condá',-27.090,-52.643),'BAH':('Fonte Nova',-12.979,-38.504),
 'VIT':('Barradão',-12.920,-38.420),'REM':('Mangueirão',-1.391,-48.448)}

# horários detalhados CBF (rodadas 31-34), mandante -> (data, hora)
KICKOFF = {
 31:{'MIR':('2026-10-16',20.0),'BOT':('2026-10-17',18.0),'CAM':('2026-10-17',18.5),'CAP':('2026-10-17',19.5),'SAO':('2026-10-17',21.0),
     'FLU':('2026-10-18',16.0),'GRE':('2026-10-18',16.0),'BAH':('2026-10-18',18.5),'REM':('2026-10-18',19.5),'COR':('2026-10-19',20.0)},
 32:{'CRU':('2026-10-23',20.0),'MIR':('2026-10-24',16.5),'INT':('2026-10-24',16.5),'VIT':('2026-10-24',16.5),'VAS':('2026-10-24',18.5),
     'PAL':('2026-10-24',18.5),'CHA':('2026-10-24',19.5),'SAN':('2026-10-24',21.0),'CFC':('2026-10-26',19.5),'FLA':('2026-10-26',20.0)},
 33:{'FLU':('2026-10-28',19.5),'SAN':('2026-10-28',19.5),'RBB':('2026-10-28',19.5),'BAH':('2026-10-28',21.5),'REM':('2026-10-28',21.5),
     'CAM':('2026-10-29',19.5),'CFC':('2026-10-29',19.5),'VAS':('2026-10-29',20.0),'GRE':('2026-10-29',21.5),'COR':('2026-10-30',20.0)},
 34:{'RBB':('2026-11-02',20.0),'CHA':('2026-11-03',19.5),'INT':('2026-11-03',21.5),'FLA':('2026-11-04',19.5),'CAP':('2026-11-04',19.5),
     'BOT':('2026-11-04',21.5),'SAO':('2026-11-04',21.5),'PAL':('2026-11-05',19.5),'CRU':('2026-11-05',21.5),'VIT':('2026-11-06',20.0)},
}

# previsão diária capturada 12/10/2026 para os 10 estádios da rodada 31: (máx, mín, chance de chuva %)
PREV_R31 = {
 'MIR':(26.6,18.1,40),'BOT':(25.4,20.3,30),'CAM':(27.3,18.0,20),'CAP':(20.0,8.6,10),'SAO':(22.6,13.7,15),
 'FLU':(24.3,19.8,10),'GRE':(19.4,10.9,5),'BAH':(27.8,24.8,55),'REM':(31.1,25.2,10),'COR':(23.2,13.4,10)}

def temp_at(hmax, hmin, hour):
    """Ciclo diurno simplificado: mínima ~6h, máxima ~15h, decaimento à noite."""
    if hour <= 6: return hmin
    if hour <= 15: return hmin + (hmax-hmin)*math.sin(math.pi/2*(hour-6)/9)
    f = {16:0.92,17:0.84,18:0.74,19:0.64,20:0.56,21:0.48,22:0.42}
    k = min(max(int(round(hour)),16),22); return hmin + (hmax-hmin)*f[k]

# elasticidades padrão (multiplicador = 1 + chuva*rain[s]) e (1 + max(0,T-26)*heat[s]) — editáveis no painel
ELAST = {
 'rain':{'DS':0.08,'FS':0.04,'FC':0.04,'FD':-0.08,'FT':-0.08,'FF':0.06,'CA':0.03,'I':0.0,'DE':-0.04,'XG':-0.06},
 'heat':{'DS':-0.015,'FS':-0.010,'FC':-0.010,'FD':-0.005,'FT':-0.005,'FF':-0.005,'CA':0.0,'I':0.0,'DE':-0.003,'XG':-0.004},
 'T0':26.0, 'rain_scale':0.6   # fração da "chance de chuva" diária que vira chuva relevante nos ~2h do jogo
}

def wx_rodada(r):
    out = {}
    for home,(date,hour) in KICKOFF.get(r,{}).items():
        p = PREV_R31.get(home) if r == 31 else None
        e = dict(est=ESTADIOS[home][0], data=date, hora=hour)
        if p:
            e.update(tmax=p[0], tmin=p[1], chuva=p[2], temp=round(temp_at(p[0],p[1],hour),1))
        out[home] = e
    return out

if __name__ == '__main__':
    print(json.dumps(wx_rodada(31), ensure_ascii=False, indent=1))
