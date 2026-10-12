"""Tabela-base Brasileirão 2026 (CBF, divulgada 15/12/2025; fonte: Band).
Turno (1-19) transcrito; returno (20-38) = espelho do turno com mando invertido
(confere com a lista publicada das rodadas 31-38). Datas podem ser remarcadas pela CBF.
"""
ABR = {
 "Athletico-PR":"CAP","Atlético-MG":"CAM","Bahia":"BAH","Botafogo":"BOT","Chapecoense":"CHA",
 "Corinthians":"COR","Coritiba":"CFC","Cruzeiro":"CRU","Flamengo":"FLA","Fluminense":"FLU",
 "Grêmio":"GRE","Internacional":"INT","Mirassol":"MIR","Palmeiras":"PAL","Red Bull Bragantino":"RBB",
 "Remo":"REM","Santos":"SAN","São Paulo":"SAO","Vasco":"VAS","Vitória":"VIT"}

TURNO = {
1:"Atlético-MG x Palmeiras;Botafogo x Cruzeiro;Chapecoense x Santos;Corinthians x Bahia;Coritiba x Red Bull Bragantino;Fluminense x Grêmio;Internacional x Athletico-PR;Mirassol x Vasco;São Paulo x Flamengo;Vitória x Remo",
2:"Athletico-PR x Corinthians;Bahia x Fluminense;Cruzeiro x Coritiba;Flamengo x Internacional;Grêmio x Botafogo;Palmeiras x Vitória;Red Bull Bragantino x Atlético-MG;Remo x Mirassol;Santos x São Paulo;Vasco x Chapecoense",
3:"Athletico-PR x Santos;Atlético-MG x Remo;Chapecoense x Coritiba;Corinthians x Red Bull Bragantino;Fluminense x Botafogo;Internacional x Palmeiras;Mirassol x Cruzeiro;São Paulo x Grêmio;Vasco x Bahia;Vitória x Flamengo",
4:"Bahia x Chapecoense;Botafogo x Vitória;Coritiba x São Paulo;Cruzeiro x Corinthians;Flamengo x Mirassol;Grêmio x Atlético-MG;Palmeiras x Fluminense;Red Bull Bragantino x Athletico-PR;Remo x Internacional;Santos x Vasco",
5:"Athletico-PR x Botafogo;Atlético-MG x Internacional;Bahia x Vitória;Corinthians x Coritiba;Flamengo x Cruzeiro;Grêmio x Red Bull Bragantino;Mirassol x Santos;Remo x Fluminense;São Paulo x Chapecoense;Vasco x Palmeiras",
6:"Botafogo x Flamengo;Chapecoense x Grêmio;Coritiba x Remo;Cruzeiro x Vasco;Fluminense x Athletico-PR;Internacional x Bahia;Palmeiras x Mirassol;Red Bull Bragantino x São Paulo;Santos x Corinthians;Vitória x Atlético-MG",
7:"Athletico-PR x Cruzeiro;Atlético-MG x São Paulo;Bahia x Red Bull Bragantino;Chapecoense x Corinthians;Flamengo x Remo;Grêmio x Vitória;Mirassol x Coritiba;Palmeiras x Botafogo;Santos x Internacional;Vasco x Fluminense",
8:"Athletico-PR x Coritiba;Cruzeiro x Santos;Fluminense x Atlético-MG;Corinthians x Flamengo;Internacional x Chapecoense;Red Bull Bragantino x Botafogo;Remo x Bahia;São Paulo x Palmeiras;Vasco x Grêmio;Vitória x Mirassol",
9:"Bahia x Athletico-PR;Botafogo x Mirassol;Chapecoense x Atlético-MG;Coritiba x Vasco;Cruzeiro x Vitória;Fluminense x Corinthians;Internacional x São Paulo;Palmeiras x Grêmio;Red Bull Bragantino x Flamengo;Santos x Remo",
10:"Atlético-MG x Athletico-PR;Bahia x Palmeiras;Chapecoense x Vitória;Corinthians x Internacional;Coritiba x Fluminense;Flamengo x Santos;Grêmio x Remo;Mirassol x Red Bull Bragantino;São Paulo x Cruzeiro;Vasco x Botafogo",
11:"Athletico-PR x Chapecoense;Botafogo x Coritiba;Corinthians x Palmeiras;Cruzeiro x Red Bull Bragantino;Fluminense x Flamengo;Internacional x Grêmio;Mirassol x Bahia;Remo x Vasco;Santos x Atlético-MG;Vitória x São Paulo",
12:"Chapecoense x Botafogo;Coritiba x Atlético-MG;Cruzeiro x Grêmio;Flamengo x Bahia;Internacional x Mirassol;Palmeiras x Athletico-PR;Red Bull Bragantino x Remo;Santos x Fluminense;Vasco x São Paulo;Vitória x Corinthians",
13:"Athletico-PR x Vitória;Atlético-MG x Flamengo;Bahia x Santos;Botafogo x Internacional;Corinthians x Vasco;Fluminense x Chapecoense;Grêmio x Coritiba;Red Bull Bragantino x Palmeiras;Remo x Cruzeiro;São Paulo x Mirassol",
14:"Athletico-PR x Grêmio;Botafogo x Remo;Chapecoense x Red Bull Bragantino;Cruzeiro x Atlético-MG;Flamengo x Vasco;Internacional x Fluminense;Mirassol x Corinthians;Palmeiras x Santos;São Paulo x Bahia;Vitória x Coritiba",
15:"Atlético-MG x Botafogo;Bahia x Cruzeiro;Corinthians x São Paulo;Coritiba x Internacional;Fluminense x Vitória;Grêmio x Flamengo;Mirassol x Chapecoense;Remo x Palmeiras;Santos x Red Bull Bragantino;Vasco x Athletico-PR",
16:"Athletico-PR x Flamengo;Atlético-MG x Mirassol;Bahia x Grêmio;Botafogo x Corinthians;Chapecoense x Remo;Fluminense x São Paulo;Internacional x Vasco;Palmeiras x Cruzeiro;Red Bull Bragantino x Vitória;Santos x Coritiba",
17:"Corinthians x Atlético-MG;Coritiba x Bahia;Cruzeiro x Chapecoense;Flamengo x Palmeiras;Grêmio x Santos;Mirassol x Fluminense;Remo x Athletico-PR;São Paulo x Botafogo;Vasco x Red Bull Bragantino;Vitória x Internacional",
18:"Athletico-PR x Mirassol;Bahia x Botafogo;Cruzeiro x Fluminense;Flamengo x Coritiba;Grêmio x Corinthians;Palmeiras x Chapecoense;Red Bull Bragantino x Internacional;Remo x São Paulo;Santos x Vitória;Vasco x Atlético-MG",
19:"Atlético-MG x Bahia;Chapecoense x Flamengo;Corinthians x Remo;Coritiba x Palmeiras;Fluminense x Red Bull Bragantino;Internacional x Cruzeiro;Mirassol x Grêmio;São Paulo x Athletico-PR;Vitória x Vasco;Botafogo x Santos",
}

def build():
    fx = {}
    for r, s in TURNO.items():
        pares = [tuple(ABR[t.strip()] for t in g.split(" x ")) for g in s.split(";")]
        assert len(pares) == 10 and len({c for p in pares for c in p}) == 20, r
        fx[r] = pares
        fx[r + 19] = [(b, a) for a, b in pares]  # returno espelhado
    return fx

FIX = build()
DATAS = {31:"17–19/10",32:"24–26/10",33:"28–29/10",34:"04–05/11",35:"18–19/11",36:"21–23/11",37:"28–29/11",38:"02/12"}
