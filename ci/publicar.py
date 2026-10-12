#!/usr/bin/env python3
"""Confere o build e, se estiver são e tiver novidade, publica em site/.

Entrada : --build DIR  (pasta com model_data.json e prancheta_cartola.html gerados pelo pipeline)
Saída   : --site DIR   (index.html, model_data.json, versao.json) — é o que o GitHub Pages / Northflank servem

Regras (nesta ordem):
  1. Build inválido (HTML pequeno, script com erro de sintaxe, poucos jogadores, clube desconhecido
     na tabela)                                              -> sai com erro; o site antigo fica no ar.
  2. Rodada de scouts MENOR que a publicada                  -> sai com erro (regressão).
  3. API da Globo falhou agora, mas o site publicado tem mercado oficial da mesma rodada
                                                             -> não publica (mantém o último mercado bom).
  4. Nada mudou (ignorando carimbos de hora) e a publicação tem menos de REFRESH_H horas
                                                             -> não publica.
  5. Caso contrário                                          -> publica.

FORCAR=1 (ou --forcar) ignora as regras 3 e 4, nunca as regras 1 e 2.
Escreve mudou/resumo/api/rodada em $GITHUB_OUTPUT e um resumo em $GITHUB_STEP_SUMMARY quando existem.
"""
import argparse, copy, hashlib, json, os, re, shutil, subprocess, sys, tempfile, time

MIN_HTML = 150 * 1024      # bytes
MIN_JOGADORES = 400
REFRESH_H = 12             # republica ao menos a cada 12 h para o selo "Mercado oficial · hora" não envelhecer à toa

CASCA = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Prancheta Cartola 2026</title>
<meta name="description" content="Projeções, time sugerido e confrontos do Cartola 2026, atualizados automaticamente.">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='6' fill='%230E7C4A'/%3E%3Cpath d='M4 16h24M16 6v20' stroke='%23fff' stroke-width='2' opacity='.7'/%3E%3Ccircle cx='16' cy='16' r='5' fill='none' stroke='%23fff' stroke-width='2'/%3E%3C/svg%3E">
<style>:root{color-scheme:light;box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}html{scroll-padding-top:env(safe-area-inset-top,0px)}body{margin:0;padding:0;font:14px -apple-system,BlinkMacSystemFont,sans-serif;background:#fff;color:#000}img{max-width:100%}[hidden]:not([hidden=until-found i]){display:none!important}</style>
</head>
<body>
__CORPO__
</body>
</html>
"""


def falha(msg):
    print(f"::error::{msg}")
    print("ERRO:", msg, file=sys.stderr)
    sys.exit(1)


def aviso(msg):
    print(f"::warning::{msg}")


def saida(**kv):
    """Grava pares chave=valor em $GITHUB_OUTPUT (se existir) e ecoa no log."""
    alvo = os.environ.get("GITHUB_OUTPUT")
    for k, v in kv.items():
        print(f"[saida] {k}={v}")
        if alvo:
            with open(alvo, "a", encoding="utf-8") as f:
                f.write(f"{k}={v}\n")


def resumo_md(linhas):
    alvo = os.environ.get("GITHUB_STEP_SUMMARY")
    if alvo:
        with open(alvo, "a", encoding="utf-8") as f:
            f.write("\n".join(linhas) + "\n")


def normalizado(data):
    """Cópia dos dados sem os carimbos de hora, para saber se algo de fato mudou."""
    d = copy.deepcopy(data)
    d.get("meta", {}).pop("gerado", None)
    m = d.get("meta", {}).get("mercado")
    if isinstance(m, dict):
        m.pop("capturado", None)
        m.pop("ts", None)
    return d


def impressao(data, extras):
    h = hashlib.sha256()
    h.update(json.dumps(normalizado(data), sort_keys=True, ensure_ascii=False).encode("utf-8"))
    for e in extras:
        h.update(b"\0")
        h.update(e)
    return h.hexdigest()


def embrulhar(html):
    """O template é só o miolo da página (no claude.ai a casca é posta na publicação). Fora de lá, a casca é esta."""
    if html.lstrip()[:9].lower() == "<!doctype":
        return html
    corpo = re.sub(r"<title>.*?</title>\s*", "", html, count=1, flags=re.S)
    return CASCA.replace("__CORPO__", corpo)


def checar_sintaxe_js(html):
    """Compila (sem executar) cada <script> inline que não seja JSON. Exige node; sem node, só avisa."""
    node = shutil.which("node")
    if not node:
        aviso("node não encontrado: sintaxe dos scripts NÃO foi verificada")
        return None
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html)
        caminho = f.name
    prog = (
        "const h=require('fs').readFileSync(process.argv[1],'utf8');"
        "const s=[...h.matchAll(/<script>([\\s\\S]*?)<\\/script>/g)];"
        "if(!s.length){console.error('nenhum <script> inline');process.exit(2)}"
        "s.forEach(m=>new Function(m[1]));console.log(s.length)"
    )
    try:
        r = subprocess.run([node, "-e", prog, caminho], capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(caminho)
    if r.returncode != 0:
        falha("script inline com erro de sintaxe: " + (r.stderr.strip().splitlines() or ["?"])[-1])
    return int(r.stdout.strip() or 0)


def validar(data, html):
    meta = data.get("meta") or {}
    rod = meta.get("ate_rodada")
    if not isinstance(rod, int) or rod < 1:
        falha(f"meta.ate_rodada inválido: {rod!r}")
    jog = data.get("players") or []
    if len(jog) < MIN_JOGADORES:
        falha(f"só {len(jog)} jogadores (mínimo {MIN_JOGADORES})")
    times = set((data.get("teams") or {}).keys())
    if len(times) != 20:
        falha(f"esperava 20 clubes, vieram {len(times)}")
    fix = data.get("fixtures") or {}
    if not fix:
        falha("sem tabela de jogos (fixtures)")
    for r, jogos in fix.items():
        for g in jogos:
            if len(g) != 2 or g[0] not in times or g[1] not in times:
                falha(f"rodada {r}: jogo com clube desconhecido {g!r}")
    # clube de jogador fora da tabela não quebra o painel, mas zera o cruzamento: avisa
    orfaos = sum(1 for p in jog if p.get("c") not in times)
    if orfaos:
        aviso(f"{orfaos} jogadores com clube fora dos 20 da Série A (ficam sem confronto)")
    tam = len(html.encode("utf-8"))
    if tam < MIN_HTML:
        falha(f"HTML com {tam} bytes (mínimo {MIN_HTML})")
    if "__DATA__" in html or "__ENGINE__" in html:
        falha("template com marcador não substituído (__DATA__/__ENGINE__)")
    embutido = re.search(r'<script type="application/json" id="model-data">([\s\S]*?)</script>', html)
    if not embutido:
        falha("bloco de dados #model-data não encontrado no HTML")
    try:
        emb = json.loads(embutido.group(1))
    except Exception as e:  # noqa: BLE001
        falha(f"dados embutidos no HTML não são JSON válido: {e}")
    if emb.get("meta", {}).get("ate_rodada") != rod or len(emb.get("players", [])) != len(jog):
        falha("dados embutidos no HTML diferem do model_data.json")
    return rod, len(jog), tam


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", required=True)
    ap.add_argument("--site", required=True)
    ap.add_argument("--forcar", action="store_true")
    a = ap.parse_args()
    forcar = a.forcar or os.environ.get("FORCAR", "0") == "1"

    with open(os.path.join(a.build, "model_data.json"), encoding="utf-8") as f:
        bruto = f.read()
    data = json.loads(bruto)
    with open(os.path.join(a.build, "prancheta_cartola.html"), encoding="utf-8") as f:
        html = embrulhar(f.read())

    rod, njog, tam = validar(data, html)
    nscripts = checar_sintaxe_js(html)
    merc = (data.get("meta") or {}).get("mercado")
    api_ok = isinstance(merc, dict)

    extras = []
    for nome in ("app_template.html", "engine.js"):
        with open(os.path.join(a.build, nome), "rb") as f:
            extras.append(f.read())
    extras.append(CASCA.encode("utf-8"))
    imp = impressao(data, extras)

    antiga = None
    cam_versao = os.path.join(a.site, "versao.json")
    if os.path.exists(cam_versao):
        try:
            with open(cam_versao, encoding="utf-8") as f:
                antiga = json.load(f)
        except Exception as e:  # noqa: BLE001
            aviso(f"versao.json ilegível ({e}); tratando como primeira publicação")

    agora = int(time.time())
    motivo, publicar = "primeira publicação", True
    if antiga:
        if rod < int(antiga.get("ate_rodada", 0)):
            falha(f"regressão: build na rodada {rod}, site publicado na {antiga.get('ate_rodada')}")
        idade_h = (agora - int(antiga.get("publicado_ts", 0))) / 3600
        if rod > int(antiga.get("ate_rodada", 0)):
            motivo = f"rodada nova de scouts ({antiga.get('ate_rodada')} -> {rod})"
        elif forcar:
            motivo = "publicação forçada"
        elif not api_ok and antiga.get("mercado"):
            publicar, motivo = False, "API da Globo indisponível agora; mantido o último mercado oficial publicado"
        elif imp != antiga.get("impressao"):
            motivo = "dados ou painel mudaram"
        elif idade_h >= REFRESH_H:
            motivo = f"sem mudança, mas publicação com {idade_h:.0f} h (renova o carimbo)"
        else:
            publicar, motivo = False, f"sem mudança (publicação com {idade_h:.1f} h)"

    if not api_ok:
        if os.environ.get("USAR_API", "1") == "1":
            aviso("API da Globo não respondeu: build só com scouts (status/preços do último snapshot do caRtola)")
        else:
            print("USAR_API=0: build só com scouts, sem mercado oficial")

    linha_merc = (f"mercado oficial: {merc.get('n')} atletas, capturado {merc.get('capturado')}"
                  + (f", rodada em aberto {merc['rodada_alvo']}" if merc.get("rodada_alvo") else "")) if api_ok else "mercado oficial: NÃO aplicado"
    texto = f"R{rod} · {njog} jogadores · {'mercado ok' if api_ok else 'sem mercado'}"
    print(f"build: scouts até R{rod}, {njog} jogadores, HTML {tam/1024:.0f} KB, scripts ok: {nscripts}; {linha_merc}")
    print(("PUBLICA: " if publicar else "NÃO PUBLICA: ") + motivo)

    if publicar:
        os.makedirs(a.site, exist_ok=True)
        with open(os.path.join(a.site, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)
        with open(os.path.join(a.site, "model_data.json"), "w", encoding="utf-8") as f:
            f.write(bruto)
        versao = dict(impressao=imp, ate_rodada=rod, jogadores=njog, mercado=api_ok,
                      mercado_capturado=(merc or {}).get("capturado"),
                      publicado_ts=agora, publicado=time.strftime("%Y-%m-%d %H:%M %Z"), motivo=motivo)
        with open(cam_versao, "w", encoding="utf-8") as f:
            json.dump(versao, f, ensure_ascii=False, indent=1)
            f.write("\n")

    saida(mudou="true" if publicar else "false", api="ok" if api_ok else "falhou", rodada=rod, resumo=texto)
    resumo_md([
        "### Prancheta Cartola",
        f"- Scouts até a rodada **{rod}** · {njog} jogadores · HTML {tam/1024:.0f} KB",
        f"- {linha_merc}",
        f"- {'**Publicado**' if publicar else 'Não publicado'}: {motivo}",
    ])


if __name__ == "__main__":
    main()
