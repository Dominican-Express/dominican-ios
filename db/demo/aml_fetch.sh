#!/bin/zsh
# Descarga un conjunto completo del dataset de IBM (no hace falta cuenta de
# Kaggle: kagglehub baja los públicos sin credenciales). HI-Small son ~510 MB.
#
# uso: ./db/demo/aml_fetch.sh [HI-Small|LI-Small] [carpeta]
# imprime la carpeta donde quedan <set>_Trans.csv, _accounts.csv y _Patterns.txt
set -e
SET=${1:-HI-Small}
OUT=${2:-$HOME/.cache/domex-aml}
mkdir -p "$OUT"
KAGGLEHUB_CACHE="$OUT/kh" uvx --quiet --from kagglehub python -I -c "
import kagglehub, os
for f in ['${SET}_Patterns.txt', '${SET}_accounts.csv', '${SET}_Trans.csv']:
    p = kagglehub.dataset_download('ealtman2019/ibm-transactions-for-anti-money-laundering-aml', path=f)
print(os.path.dirname(p))"
