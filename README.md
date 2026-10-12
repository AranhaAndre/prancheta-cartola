# Prancheta Cartola 2026 — site que se atualiza sozinho

Repositório que reconstrói o painel de 2 em 2 horas e publica a página quando há novidade.
Não precisa de servidor: o build roda no GitHub Actions e a página é um único `index.html`.

```
caRtola (scouts por rodada) ─┐
                             ├─> ci/build.sh ─> ci/publicar.py ─> site/index.html ─┬─> GitHub Pages
API oficial do Cartola ──────┘   (pipeline/)     (confere e decide)   (commit do bot) └─> Northflank (opcional)
(status, preços, partidas)
```

## O que tem aqui

| Pasta / arquivo | Para que serve |
|---|---|
| `pipeline/` | O modelo e o painel (os mesmos arquivos do artefato, com 2 ajustes — ver "O que mudou") |
| `ci/build.sh` | Caminho único de build: baixa os scouts, roda o pipeline, chama a conferência |
| `ci/publicar.py` | Confere o build e só publica em `site/` se estiver são e houver novidade |
| `site/` | A página pronta (`index.html`), os dados (`model_data.json`) e o carimbo (`versao.json`) |
| `.github/workflows/atualizar.yml` | Agenda, build, commit de `site/` e deploy no GitHub Pages |
| `Dockerfile`, `nginx/` | Só para hospedar no Northflank (nginx servindo `site/`) |
| `tests/` | Testes com a API da Globo simulada e teste do painel em navegador |

## Colocar no ar — GitHub Pages (caminho recomendado)

No plano grátis do GitHub, o Pages exige repositório **público**. Não há segredo nenhum neste repositório.

1. Em github.com → **New repository** → nome `prancheta-cartola` → **Public** → **sem** README/.gitignore/licença (tem de nascer vazio).
2. No PowerShell, dentro da pasta extraída do zip:

   ```powershell
   cd "CAMINHO\prancheta-cartola"
   git init
   git add .
   git commit -m "Prancheta Cartola: site automatico"
   git branch -M main
   git remote add origin https://github.com/SEU_USUARIO/prancheta-cartola.git
   git push -u origin main
   ```

3. No repositório: **Settings → Pages → Build and deployment → Source: GitHub Actions**.
4. **Actions → atualizar-prancheta → Run workflow** (branch `main`).
5. Quando os dois jobs ficarem verdes, o endereço aparece no job `deploy` e em Settings → Pages:
   `https://SEU_USUARIO.github.io/prancheta-cartola/`.

Se a aba Actions pedir para habilitar workflows, aceite. Se o push do bot falhar com erro de permissão,
confira **Settings → Actions → General → Workflow permissions** (o workflow já pede `contents: write`;
só uma política da conta/organização que force "somente leitura" bloqueia).

## Colocar no ar — Northflank (opcional, serve com repositório privado)

O Northflank não gera os dados: ele só serve a página que o GitHub Actions deixa em `site/`.
Cada commit do bot em `site/` é um push, então o CD do Northflank republica sozinho.

1. Suba o repositório como acima (pode ser **Private**; pule os passos 3–5 do Pages).
2. Northflank → **New service → Combined service** → conectar o GitHub App só a este repositório → branch `main`.
3. **Build type: Dockerfile** — path `/Dockerfile`, context `/`.
4. **Ports**: `8080`, protocolo **HTTP**, **Publicly exposed**.
5. **Health check**: HTTP, path `/health`, porta `8080`.
6. Sem volume e sem variáveis de ambiente: o serviço não guarda estado (a página vai dentro da imagem).

Ocupa 1 dos serviços do plano grátis (Sandbox). O cron do Northflank **não** é usado.

## Dia a dia

- Roda sozinho de 2 em 2 horas (minuto 23, horário UTC; o GitHub pode atrasar alguns minutos).
- Perto do fechamento do mercado, se quiser o dado do minuto: **Actions → atualizar-prancheta → Run workflow**.
- O topo da página mostra o estado: `Scouts até a R..`, `Mercado oficial · N atletas · data/hora` e `Fecha dd/mm hh:mm`.
  Se o selo virar `desatualizado`, o build parou há mais de 26 h — olhe a aba Actions.
- O botão "Atualizar escalações" continua funcionando para importar o mercado na mão; a importação manual
  vale até o próximo build automático mais novo que ela.
- Cada execução deixa um resumo na aba Actions (rodada, jogadores, se o mercado entrou, se publicou e por quê).

## Regras de publicação (`ci/publicar.py`)

1. Build inválido (HTML pequeno, erro de sintaxe em script, menos de 400 jogadores, clube desconhecido na tabela) → erro; o site antigo fica no ar.
2. Rodada de scouts menor que a publicada → erro.
3. API da Globo falhou agora, mas o site publicado já tem mercado oficial da mesma rodada → não publica.
4. Nada mudou e a publicação tem menos de 12 h → não publica.
5. Caso contrário → publica (commit em `site/` + deploy).

"Run workflow" com **forcar** marcado ignora as regras 3 e 4, nunca a 1 e a 2.

## Rodar na sua máquina

```bash
pip install -r requirements.txt
bash ci/build.sh                 # igual ao GitHub Actions (tenta a API da Globo)
USAR_API=0 bash ci/build.sh      # só scouts
python3 tests/testar.py          # API simulada (precisa de um build antes, para ter os CSV)
python3 tests/testar_painel.py   # opcional: painel em Chromium (pip install playwright)
```

No Windows, use o Git Bash ou o WSL para os comandos `bash`.

## O que mudou em relação ao pipeline do artefato

Sem `--api`, o `model_data.json` gerado aqui é idêntico byte a byte ao do artefato. As mudanças só agem com `--api`:

- `pipeline/atualizar_modelo.py` (bloco `--api`, linhas marcadas com `[repo]`):
  - tenta `api.cartola.globo.com` e, se falhar, `api.cartolafc.globo.com` (o host que o próprio caRtola usa no GitHub Actions);
  - código do clube vem dos CSV (campo `nome` da API), não de `abreviacao`;
  - quem saiu do mercado oficial sai do painel (mesma regra da importação manual);
  - grava em `meta.mercado`: `ts`, `rodada_alvo`, `status` e `fecha_ts`.
- `pipeline/app_template.html` (bloco marcado com `[repo]`, mais 2 linhas em `renderState` e `ingest`):
  - selo "Mercado oficial" quando o build já traz o mercado; alerta de "desatualizado"; selo de fechamento;
  - importação manual mais antiga que o build é descartada;
  - a rodada selecionada avança para a rodada em aberto.
- `ci/publicar.py` põe a casca do documento (`<!doctype>`, `<head>`), que no claude.ai é colocada na publicação.

## Limites conhecidos

- **Clima**: a previsão em `pipeline/wx.py` (`PREV_R31`, `KICKOFF`) é manual e só cobre a rodada 31 (horários até a 34). Não se atualiza sozinha.
- **Tabela**: rodadas 31–38 e datas estão fixas em `pipeline/fixtures.py`; as partidas válidas da rodada em aberto vêm da API.
- **API da Globo a partir do GitHub Actions**: o caRtola prova que `api.cartolafc.globo.com` responde de lá. Se um dia bloquearem, o site segue no ar só com scouts e a execução mostra um aviso amarelo.
- **Scouts**: dependem do caRtola publicar `rodada-N.csv` (o robô deles roda 1 vez por dia, às 10h de Brasília).
