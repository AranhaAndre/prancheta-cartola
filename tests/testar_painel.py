#!/usr/bin/env python3
"""Abre o painel num Chromium de verdade (Playwright) e confere o comportamento ligado ao mercado embutido.

    python3 tests/testar.py && python3 tests/testar_painel.py      (o 1º gera as páginas em .trabalho/teste)

Opcional — só para quem mexer no template. Precisa de `pip install playwright` + um Chromium.
"""
import json, os, re, sys, tempfile, time
from playwright.sync_api import sync_playwright

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(RAIZ, ".trabalho", "teste")
OK, FALHAS = [], []
RX = re.compile(r'(<script type="application/json" id="model-data">)([\s\S]*?)(</script>)')


def checa(nome, cond, detalhe=""):
    (OK if cond else FALHAS).append(nome)
    print(("  ok   " if cond else "  FALHA ") + nome + (f"  [{detalhe}]" if detalhe and not cond else ""))


def variante(origem, fn):
    """Copia a página alterando os dados embutidos (para simular outros estados do build)."""
    html = open(origem, encoding="utf-8").read()
    m = RX.search(html)
    d = json.loads(m.group(2))
    fn(d)
    novo = html[:m.start(2)] + json.dumps(d, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + html[m.end(2):]
    p = os.path.join(tempfile.mkdtemp(prefix="painel_"), "index.html")
    open(p, "w", encoding="utf-8").write(novo)
    return p


def time_completo(pg):
    return pg.locator("#tab-time .pitch .chip").count() == 11 and "Técnico:" in pg.inner_text("#tab-time .coach")


def abre(navegador, caminho, armazenado=None, largura=1280, altura=900):
    ctx = navegador.new_context(viewport=dict(width=largura, height=altura), locale="pt-BR", timezone_id="America/Sao_Paulo")
    # fontes do Google não fazem parte do teste (e podem estar bloqueadas): responde vazio
    ctx.route(re.compile(r"https://fonts\.(googleapis|gstatic)\.com/.*"), lambda r: r.fulfill(status=200, content_type="text/css", body=""))
    pg = ctx.new_page()
    erros = []
    pg.on("pageerror", lambda e: erros.append(str(e)))
    pg.on("console", lambda m: erros.append(m.text) if m.type == "error" else None)
    if armazenado:
        pg.add_init_script("(()=>{const a=%s;for(const k in a)localStorage.setItem('pc26_'+k,JSON.stringify(a[k]));})()" % json.dumps(armazenado))
    pg.goto("file://" + caminho)
    pg.wait_for_selector("#datastate .pill")
    return ctx, pg, erros


def main():
    com, sem = os.path.join(BASE, "com_mercado", "index.html"), os.path.join(BASE, "sem_mercado", "index.html")
    if not (os.path.exists(com) and os.path.exists(sem)):
        sys.exit("Rode antes: python3 tests/testar.py")
    with sync_playwright() as p:
        nav = p.chromium.launch()

        print("1) build sem mercado (comportamento antigo preservado)")
        ctx, pg, erros = abre(nav, sem)
        est = pg.inner_text("#datastate")
        checa("selo de scouts", "Scouts até a R" in est, est)
        checa("pede a importação manual do mercado", "importe o mercado" in est, est)
        checa("time sugerido desenha 11 fichas no campo + técnico", time_completo(pg), str(pg.locator("#tab-time .pitch .chip").count()))
        for aba in ("jogos", "rank", "plan", "clima", "metodo", "time"):
            pg.click(f'nav.tabs button[data-tab="{aba}"]')
            pg.wait_for_timeout(150)
        checa("todas as abas abrem sem erro de script", not erros, str(erros[:3]))
        checa("título do documento", pg.title() == "Prancheta Cartola 2026", pg.title())
        ctx.close()

        print("2) build com mercado oficial embutido")
        ctx, pg, erros = abre(nav, com)
        est = pg.inner_text("#datastate")
        checa("selo 'Mercado oficial · N atletas · data/hora'", bool(re.search(r"Mercado oficial · \d+ atletas · \d{2}/\d{2}", est)), est)
        checa("não pede importação manual", "importe o mercado" not in est, est)
        checa("mostra o fechamento do mercado", "Fecha 17/10" in est, est)
        checa("não acusa 'desatualizado' em build recente", "desatualizado" not in est, est)
        checa("rodada selecionada = rodada em aberto (31)", pg.input_value("#rodada") == "31", pg.input_value("#rodada"))
        checa("time sugerido desenha 11 fichas no campo + técnico", time_completo(pg), str(pg.locator("#tab-time .pitch .chip").count()))
        pg.click('nav.tabs button[data-tab="jogos"]')
        checa("confrontos da rodada vêm de /partidas (9 jogos válidos)", pg.locator("#tab-jogos .game").count() == 9, str(pg.locator("#tab-jogos .game").count()))
        checa("sem erro de script", not erros, str(erros[:3]))
        ctx.close()

        print("3) importação manual ANTIGA guardada no navegador é descartada")
        velho = dict(mercadoOverride=dict(atletas={"1": dict(n="Fantasma", c="FLA", p=5, pr=1, st=7, mp=0)}), mercadoMeta=dict(rodada=20, n=1))
        ctx, pg, erros = abre(nav, com, armazenado=None)
        pg.evaluate("a=>{for(const k in a)localStorage.setItem('pc26_'+k,JSON.stringify(a[k]))}", velho)
        pg.reload(); pg.wait_for_selector("#datastate .pill")
        est = pg.inner_text("#datastate")
        checa("vale o mercado oficial, não o importado antigo", "Mercado oficial" in est and "Mercado importado" not in est, est)
        checa("importação antiga apagada do navegador", pg.evaluate("localStorage.getItem('pc26_mercadoOverride')") == "null")
        checa("time segue completo (11 fichas + técnico)", time_completo(pg), str(pg.locator("#tab-time .pitch .chip").count()))
        ctx.close()

        print("4) importação manual MAIS NOVA que o build é respeitada")
        ctx, pg, erros = abre(nav, com)
        merc = json.load(open(os.path.join(BASE, "com_mercado", "model_data.json"), encoding="utf-8"))
        # 28 por posição: o suficiente para o otimizador fechar um time
        ids = {}
        for pos in range(1, 7):
            for q in [x for x in merc["players"] if x["p"] == pos][:28]:
                ids[str(q["id"])] = dict(n=q["n"], c=q["c"], p=q["p"], pr=q["pr"], st=7, mp=q.get("mp"))
        novo = dict(mercadoOverride=dict(atletas=ids, ts=int(time.time() * 1000) + 60000), mercadoMeta=dict(rodada=30, n=len(ids)))
        pg.evaluate("a=>{for(const k in a)localStorage.setItem('pc26_'+k,JSON.stringify(a[k]))}", novo)
        pg.reload(); pg.wait_for_selector("#datastate .pill")
        est = pg.inner_text("#datastate")
        checa("selo 'Mercado importado' permanece", "Mercado importado" in est and "Mercado oficial" not in est, est)
        ctx.close()

        print("5) rodada salva no navegador já passou -> avança para a rodada em aberto")
        p32 = variante(com, lambda d: d["meta"]["mercado"].__setitem__("rodada_alvo", 32))
        ctx, pg, erros = abre(nav, p32, armazenado=dict(rodada="31"))
        checa("select vai para a 32", pg.input_value("#rodada") == "32", pg.input_value("#rodada"))
        ctx.close()
        ctx, pg, erros = abre(nav, p32, armazenado=dict(rodada="34"))
        checa("rodada futura escolhida pelo usuário é mantida", pg.input_value("#rodada") == "34", pg.input_value("#rodada"))
        ctx.close()

        print("6) build parado há mais de 26 h é sinalizado")
        pv = variante(com, lambda d: d["meta"]["mercado"].__setitem__("ts", int(time.time() * 1000) - 30 * 3600 * 1000))
        ctx, pg, erros = abre(nav, pv)
        est = pg.inner_text("#datastate")
        checa("selo vira alerta 'desatualizado'", "desatualizado" in est and pg.locator("#datastate .pill.warn").count() >= 1, est)
        ctx.close()

        print("7) mercado fechado")
        pf = variante(com, lambda d: d["meta"]["mercado"].update(status=2))
        ctx, pg, erros = abre(nav, pf)
        est = pg.inner_text("#datastate")
        checa("selo 'Mercado fechado'", "Mercado fechado" in est and "Fecha " not in est, est)
        ctx.close()

        print("8) celular (390 px)")
        ctx, pg, erros = abre(nav, com, largura=390, altura=844)
        sobra = pg.evaluate("document.scrollingElement.scrollWidth - window.innerWidth")
        checa("sem rolagem horizontal da página", sobra <= 0, f"sobra {sobra}px")
        pg.screenshot(path=os.path.join(BASE, "celular.png"))
        ctx.close()
        ctx, pg, erros = abre(nav, com)
        pg.screenshot(path=os.path.join(BASE, "desktop.png"))
        ctx.close()
        nav.close()

    print(f"\n{len(OK)} ok, {len(FALHAS)} falhas")
    if FALHAS:
        print("FALHARAM:", *FALHAS, sep="\n  - ")
        sys.exit(1)


if __name__ == "__main__":
    main()
