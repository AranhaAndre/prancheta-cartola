#!/usr/bin/env bash
# Caminho único de build: é exatamente o que o GitHub Actions executa e o que se roda na máquina.
#
#   bash ci/build.sh                 # baixa os scouts, tenta a API da Globo, gera e (se houver novidade) publica em site/
#   USAR_API=0 bash ci/build.sh      # sem API da Globo (só scouts)
#   FORCAR=1 bash ci/build.sh        # publica mesmo sem mudança
#   CARTOLA_RAW=/caminho/01_raw/2026 bash ci/build.sh   # usa CSVs já baixados (não clona)
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TRAB="${TRAB:-$RAIZ/.trabalho}"
USAR_API="${USAR_API:-1}"
TEMPORADA="${TEMPORADA:-2026}"
DADOS_URL="${DADOS_URL:-https://github.com/henriquepgomide/caRtola}"

mkdir -p "$TRAB"

# 1) Scouts: clone esparso (só a pasta da temporada: ~6 MB em vez de ~120 MB)
if [ -z "${CARTOLA_RAW:-}" ]; then
  rm -rf "$TRAB/cartola"
  GIT_LFS_SKIP_SMUDGE=1 git clone --quiet --depth 1 --filter=blob:none --sparse "$DADOS_URL" "$TRAB/cartola"
  git -C "$TRAB/cartola" sparse-checkout set "data/01_raw/$TEMPORADA"
  CARTOLA_RAW="$TRAB/cartola/data/01_raw/$TEMPORADA"
fi
CARTOLA_RAW="$(cd "$CARTOLA_RAW" && pwd)"   # absoluto: o pipeline roda em outra pasta
export CARTOLA_RAW
N_CSV="$(find "$CARTOLA_RAW" -maxdepth 1 -name 'rodada-*.csv' | wc -l | tr -d ' ')"
[ "$N_CSV" -ge 1 ] || { echo "::error::nenhum rodada-N.csv em $CARTOLA_RAW"; exit 1; }
echo "scouts: $N_CSV arquivos em $CARTOLA_RAW"

# 2) Pipeline numa cópia limpa (as saídas nunca sujam pipeline/)
rm -rf "$TRAB/build"
cp -r "$RAIZ/pipeline" "$TRAB/build"
cd "$TRAB/build"
if [ "$USAR_API" = "1" ]; then
  python3 atualizar_modelo.py --api
else
  python3 atualizar_modelo.py
fi
python3 build_html.py

# 3) Conferência + publicação em site/ (só se estiver são e houver novidade)
python3 "$RAIZ/ci/publicar.py" --build "$TRAB/build" --site "$RAIZ/site"
