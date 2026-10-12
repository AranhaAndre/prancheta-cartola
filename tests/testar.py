#!/usr/bin/env python3
"""Testes do repositório sem depender da API da Globo (ela é simulada no formato oficial).

    CARTOLA_RAW=/caminho/01_raw/2026 python3 tests/testar.py
    (sem CARTOLA_RAW usa .trabalho/cartola, que o ci/build.sh baixa)

Cobre: (1) ramo --api do pipeline — aplicação de status/preço, saída de quem deixou o mercado,
entrada de atleta novo, partidas válidas, host reserva, API fora do ar, respostas tortas;
(2) regras de publicação do ci/publicar.py — primeira vez, sem mudança, API caída não derruba
mercado bom, regressão de rodada, clube desconhecido, renovação de carimbo, publicação forçada.
"""
import io, json, os, runpy, shutil, subprocess, sys, tempfile, time, urllib.error, urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.abspath(os.environ.get("CARTOLA_RAW") or os.path.join(RAIZ, ".trabalho", "cartola", "data", "01_raw", "2026"))
H1, H2 = "https://api.cartola.globo.com", "https://api.cartolafc.globo.com"
OK, FALHAS = [], []


def checa(nome, cond, detalhe=""):
    (OK if cond else FALHAS).append(nome)
    print(("  ok   " if cond else "  FALHA ") + nome + (f"  [{detalhe}]" if detalhe and not cond else ""))


def api_falsa():
    """Monta /atletas/mercado, /partidas e /mercado/status a partir do último CSV (mesmos campos da API oficial)."""
    import pandas as pd
    n = max(int(f[7:-4]) for f in os.listdir(RAW) if f.startswith("rodada-") and f.endswith(".csv"))
    d = pd.read_csv(os.path.join(RAW, f"rodada-{n}.csv")).rename(columns=lambda c: c.replace("atletas.", ""))
    cod = d.groupby("clube_id")["clube.id.full.name"].first().to_dict()
    # "abreviacao" propositalmente diferente de "nome": o pipeline tem de usar o código dos CSVs
    clubes = {str(int(k)): dict(id=int(k), nome=v, abreviacao="X" + v[:2], nome_fantasia=v) for k, v in cod.items()}
    atletas = [dict(atleta_id=int(r.atleta_id), apelido=r.apelido, clube_id=int(r.clube_id), posicao_id=int(r.posicao_id),
                    status_id=int(r.status_id), preco_num=float(r.preco_num), media_num=float(r.media_num),
                    rodada_id=n + 1, scout={}) for r in d.itertuples()]
    jog = [a for a in atletas if a["posicao_id"] != 6]
    mudado, saiu = jog[0], [a["atleta_id"] for a in jog[1:6]]
    mudado["status_id"], mudado["preco_num"] = 5, 1.23
    atletas = [a for a in atletas if a["atleta_id"] not in saiu]
    novo = dict(atleta_id=99999901, apelido="Reforço Teste", clube_id=262, posicao_id=5, status_id=7, preco_num=4.5,
                media_num=0.0, rodada_id=n + 1, scout={})
    atletas.append(novo)
    ids = sorted(int(k) for k in clubes)
    partidas = [dict(clube_casa_id=ids[i], clube_visitante_id=ids[i + 10], valida=(i != 0)) for i in range(10)]
    return dict(
        n=n, mudado=mudado, saiu=saiu, novo=novo, cod={int(k): v for k, v in cod.items()},
        mercado=dict(clubes=clubes, atletas=atletas),
        partidas=dict(clubes=clubes, partidas=partidas, rodada=31),
        status=dict(rodada_atual=31, status_mercado=1, fechamento=dict(dia=17, mes=10, ano=2026, hora=18, minuto=59, timestamp=1792277940)),
    )


def roda_pipeline(respostas, api=True):
    """Executa pipeline/atualizar_modelo.py numa cópia temporária, com urlopen trocado. Devolve (pasta, dados, urls pedidas)."""
    pasta = tempfile.mkdtemp(prefix="prancheta_t_")
    for f in os.listdir(os.path.join(RAIZ, "pipeline")):
        if os.path.isfile(os.path.join(RAIZ, "pipeline", f)):
            shutil.copy(os.path.join(RAIZ, "pipeline", f), pasta)
    pedidas = []

    def falso(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else req
        pedidas.append(url)
        r = respostas.get(url)
        if r is None:
            raise urllib.error.URLError("simulado: host fora do ar")
        return io.BytesIO(json.dumps(r).encode("utf-8"))

    real, argv, cwd, path0 = urllib.request.urlopen, sys.argv, os.getcwd(), list(sys.path)
    for m in ("model", "fixtures", "wx"):
        sys.modules.pop(m, None)
    os.environ["CARTOLA_RAW"] = RAW
    try:
        urllib.request.urlopen = falso
        sys.argv = ["atualizar_modelo.py"] + (["--api"] if api else [])
        os.chdir(pasta)
        sys.path.insert(0, pasta)
        saida_real, sys.stdout = sys.stdout, io.StringIO()
        try:
            runpy.run_path("atualizar_modelo.py", run_name="__main__")
        finally:
            log, sys.stdout = sys.stdout.getvalue(), saida_real
    finally:
        urllib.request.urlopen, sys.argv = real, argv
        os.chdir(cwd)
        sys.path[:] = path0
    subprocess.run([sys.executable, "build_html.py"], cwd=pasta, check=True, capture_output=True)
    with open(os.path.join(pasta, "model_data.json"), encoding="utf-8") as f:
        return pasta, json.load(f), pedidas, log


def publica(build, site, forcar=False):
    env = dict(os.environ, FORCAR="1" if forcar else "0")
    env.pop("GITHUB_OUTPUT", None)
    env.pop("GITHUB_STEP_SUMMARY", None)
    r = subprocess.run([sys.executable, os.path.join(RAIZ, "ci", "publicar.py"), "--build", build, "--site", site],
                       capture_output=True, text=True, env=env)
    mudou = "[saida] mudou=true" in r.stdout
    return r.returncode, mudou, r.stdout + r.stderr


def main():
    if not os.path.isdir(RAW):
        sys.exit(f"CSV não encontrados em {RAW}. Rode antes: USAR_API=0 bash ci/build.sh (ou defina CARTOLA_RAW).")
    F = api_falsa()
    tudo = lambda h: {h + "/atletas/mercado": F["mercado"], h + "/partidas": F["partidas"], h + "/mercado/status": F["status"]}

    print("A) API responde no host principal")
    pA, dA, urls, _ = roda_pipeline(tudo(H1))
    m = dA["meta"].get("mercado") or {}
    por_id = {p["id"]: p for p in dA["players"]}
    checa("meta.mercado presente com n e ts", m.get("n") == len(F["mercado"]["atletas"]) and isinstance(m.get("ts"), int), str(m))
    checa("rodada_alvo = rodada de /partidas", m.get("rodada_alvo") == 31, str(m))
    checa("status e fechamento do mercado gravados", m.get("status") == 1 and m.get("fecha_ts") == 1792277940, str(m))
    a = F["mudado"]
    checa("status/preço oficiais aplicados", por_id[a["atleta_id"]]["st"] == 5 and por_id[a["atleta_id"]]["pr"] == 1.23)
    checa("quem saiu do mercado saiu do painel", not any(i in por_id for i in F["saiu"]))
    nv = por_id.get(F["novo"]["atleta_id"])
    checa("atleta novo entra com código de clube dos CSVs", bool(nv) and nv.get("novo") is True and nv["c"] == F["cod"][262], str(nv))
    checa("nenhum clube com a 'abreviacao' torta da API", all(p["c"] in dA["teams"] for p in dA["players"]))
    checa("partidas: só as 9 válidas, com clubes conhecidos",
          len(dA["fixtures"]["31"]) == 9 and all(c in dA["teams"] for g in dA["fixtures"]["31"] for c in g), str(dA["fixtures"]["31"]))
    checa("só o host principal foi chamado", all(u.startswith(H1) for u in urls), str(urls))

    print("B) host principal fora, host reserva responde")
    pB, dB, urls, _ = roda_pipeline(tudo(H2))
    checa("mercado aplicado pelo host reserva", (dB["meta"].get("mercado") or {}).get("n") == m.get("n"))
    checa("tentou o principal antes do reserva", urls[0].startswith(H1) and any(u.startswith(H2) for u in urls), str(urls))

    print("C) API totalmente fora do ar")
    pC, dC, _, log = roda_pipeline({})
    checa("modelo sai só com scouts, sem meta.mercado", "mercado" not in dC["meta"] and len(dC["players"]) >= 400)
    checa("log registra 'API indisponível'", "API indisponível" in log)

    print("D) /mercado/status em formato inesperado")
    r = tudo(H1); r[H1 + "/mercado/status"] = {"mensagem": "qualquer coisa"}
    pD, dD, _, _ = roda_pipeline(r)
    mD = dD["meta"].get("mercado") or {}
    checa("mercado segue aplicado, sem campos de status", mD.get("n") == m.get("n") and "status" not in mD and "fecha_ts" not in mD, str(mD))

    print("E) /atletas/mercado em manutenção (JSON sem atletas)")
    r = tudo(H1); r[H1 + "/atletas/mercado"] = {"mensagem": "Em manutenção"}
    pE, dE, _, _ = roda_pipeline(r)
    checa("sem meta.mercado e nenhum jogador perdido", "mercado" not in dE["meta"] and len(dE["players"]) == len(dC["players"]))

    print("F) sem --api nenhuma URL é chamada")
    pF, dF, urls, _ = roda_pipeline(tudo(H1), api=False)
    checa("zero chamadas de rede", urls == [], str(urls))
    checa("mesmos jogadores do cenário C", [p["id"] for p in dF["players"]] == [p["id"] for p in dC["players"]])

    print("G) regras de publicação")
    site = tempfile.mkdtemp(prefix="prancheta_site_")
    rc, mudou, out = publica(pA, site)
    checa("1ª publicação acontece", rc == 0 and mudou and os.path.exists(os.path.join(site, "index.html")), out[-300:])
    html = open(os.path.join(site, "index.html"), encoding="utf-8").read()
    checa("index.html é documento completo (doctype, lang, 1 title)",
          html.startswith("<!doctype html>") and 'lang="pt-BR"' in html and html.count("<title>") == 1)
    rc, mudou, out = publica(pA, site)
    checa("mesmo build de novo: não publica", rc == 0 and not mudou, out[-300:])
    rc, mudou, out = publica(pB, site)
    checa("build igual com outro carimbo de hora: não publica", rc == 0 and not mudou, out[-300:])
    rc, mudou, out = publica(pC, site)
    v = json.load(open(os.path.join(site, "versao.json"), encoding="utf-8"))
    checa("API caída não derruba o mercado já publicado", rc == 0 and not mudou and v["mercado"] is True, out[-300:])
    rc, mudou, out = publica(pD, site)
    checa("mudança real nos dados: publica", rc == 0 and mudou, out[-300:])
    rc, mudou, out = publica(pD, site, forcar=True)
    checa("FORCAR=1 publica mesmo sem mudança", rc == 0 and mudou, out[-300:])
    v = json.load(open(os.path.join(site, "versao.json"), encoding="utf-8"))
    v["publicado_ts"] = int(time.time()) - 13 * 3600
    json.dump(v, open(os.path.join(site, "versao.json"), "w", encoding="utf-8"))
    rc, mudou, out = publica(pD, site)
    checa("publicação com mais de 12 h é renovada", rc == 0 and mudou and "renova" in out, out[-300:])

    def estraga(origem, fn):
        p = tempfile.mkdtemp(prefix="prancheta_ruim_")
        shutil.copytree(origem, p, dirs_exist_ok=True)
        d = json.load(open(os.path.join(p, "model_data.json"), encoding="utf-8"))
        fn(d)
        json.dump(d, open(os.path.join(p, "model_data.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        subprocess.run([sys.executable, "build_html.py"], cwd=p, check=True, capture_output=True)
        return p

    antes = open(os.path.join(site, "index.html"), encoding="utf-8").read()
    rc, mudou, out = publica(estraga(pD, lambda d: d["meta"].__setitem__("ate_rodada", d["meta"]["ate_rodada"] - 1)), site, forcar=True)
    checa("rodada menor que a publicada: erro, mesmo forçando", rc != 0 and "regressão" in out, out[-300:])
    rc, mudou, out = publica(estraga(pD, lambda d: d["fixtures"]["31"].__setitem__(0, [None, "FLA"])), site, forcar=True)
    checa("clube desconhecido na tabela: erro", rc != 0 and "clube desconhecido" in out, out[-300:])
    rc, mudou, out = publica(estraga(pD, lambda d: d.__setitem__("players", d["players"][:50])), site, forcar=True)
    checa("poucos jogadores: erro", rc != 0 and "jogadores" in out, out[-300:])
    p = estraga(pD, lambda d: None)
    with open(os.path.join(p, "prancheta_cartola.html"), "a", encoding="utf-8") as f:
        f.write("<script>function (</script>")
    rc, mudou, out = publica(p, site, forcar=True)
    checa("script com erro de sintaxe: erro", rc != 0 and "sintaxe" in out, out[-300:])
    checa("depois dos builds ruins o site publicado ficou intacto", open(os.path.join(site, "index.html"), encoding="utf-8").read() == antes)

    site2 = tempfile.mkdtemp(prefix="prancheta_site2_")
    publica(pC, site2)
    rc, mudou, out = publica(pA, site2)
    checa("site sem mercado recebe o mercado quando a API volta", rc == 0 and mudou, out[-300:])

    # guarda os builds A e C para o teste de navegador (tests/testar_painel.py)
    alvo = os.path.join(RAIZ, ".trabalho", "teste")
    shutil.rmtree(alvo, ignore_errors=True)
    os.makedirs(alvo)
    for nome, b in (("com_mercado", pA), ("sem_mercado", pC)):
        s = os.path.join(alvo, nome)
        publica(b, s)
    print(f"\n{len(OK)} ok, {len(FALHAS)} falhas")
    if FALHAS:
        print("FALHARAM:", *FALHAS, sep="\n  - ")
        sys.exit(1)


if __name__ == "__main__":
    main()
