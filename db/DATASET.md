# Dataset: IBM Transactions for Anti Money Laundering

We test our mule-ring detector against data we did not generate ourselves and
whose answer is known. Our own scenario (`demo/01_seed.surql`, `gen_volume.py`)
can only confirm what we designed; an independent dataset can show where the
design is wrong. It did (see [Findings](#findings)).

## Source and licence

- **IBM, "Transactions for Anti Money Laundering (AML)"**, Kaggle:
  `ealtman2019/ibm-transactions-for-anti-money-laundering-aml` (version 8).
- Paper: E. Altman et al., *Realistic Synthetic Financial Transactions for
  Anti-Money Laundering Models*, arXiv:2306.16424 (2023).
- Licence of the data: **CDLA-Sharing-1.0** (github.com/IBM/AML-Data). The
  sample in `data/ibm-aml/` is a subset of it, distributed under the same
  licence: `data/ibm-aml/LICENSE-CDLA-Sharing-1.0.txt`.

The data is **synthetic**: a simulated world of banks, people and companies,
some of whom launder money. It is not real customers anonymised. Each
transaction carries an `Is Laundering` label, and a separate file lists 370
laundering attempts by typology (fan-in, fan-out, cycle, scatter-gather,
gather-scatter, bipartite, stack, random).

## What is in the repo

`data/ibm-aml/HI-Small-sample_*` (6.5 MB), same format as the original:

| File | Content |
|---|---|
| `_Trans.csv` | 23,256 of the 5,078,345 HI-Small transactions |
| `_accounts.csv` | the 35,435 accounts that appear in them, with owner |
| `_Patterns.txt` | the full list of 370 labelled laundering attempts |
| `_rates.json` | EUR exchange rates computed from the **full** set |

The 23,256 rows are:

1. the **381 candidates** of the lossless prefilter (everything that can be part
   of a ring, see below);
2. **every row of the labelled attempts** (the known answer);
3. ~20,000 **ordinary transactions** as background, picked by a fixed hash of the
   row number, so the sample is the same every time.

The exchange rates travel with the sample because recomputing them from a
subset changes the amounts in EUR, and with them which hops pass the rule.

**The sample gives exactly the same results as the full set**: 381 candidates,
7 strict rings over 20 accounts, 36 wide rings over 211 accounts, in SurrealDB
and in the Python reference. Checked when the sample was built.

## Reproduce

Requirements: SurrealDB 3.2.4 running (see `INSTALL.md`), Python 3, and
[uv](https://docs.astral.sh/uv/) for the scripts that use numpy.

**From the sample in the repo** (seconds):

```sh
# load into database dx/aml (only core, graph and detectors: an analytics copy)
SURREAL_URL=http://127.0.0.1:8099 python3 db/demo/aml_load.py \
    --data db/data/ibm-aml --set HI-Small-sample --db aml

# sweep September 2022 with both tiers
curl -s -u root:root -H 'surreal-ns: dx' -H 'surreal-db: aml' -H 'Accept: application/json' \
  http://127.0.0.1:8099/sql --data-binary \
  "RETURN fn::detect_rings_between(d'2022-08-31T00:00:00Z', d'2022-09-20T00:00:00Z', 12);
   SELECT kind, count() AS n FROM fraud_alert GROUP BY kind;"
# expected: 20 mule_ring, 191 possible_ring

# calibration table (Python reference, no database)
uv run --with numpy python db/demo/aml_prefilter.py --data db/data/ibm-aml --set HI-Small-sample
uv run --with numpy python db/demo/aml_eval.py --data db/data/ibm-aml --set HI-Small-sample \
    --rows HI-Small-sample_candidates_0.8_1.2_72h.txt
```

**From the full set** (~510 MB download, ~3 min of CPU for the prefilter):

```sh
DIR=$(./db/demo/aml_fetch.sh HI-Small)          # no Kaggle account needed
uv run --with numpy python db/demo/aml_prefilter.py --data "$DIR" --set HI-Small
uv run --with numpy python db/demo/aml_eval.py --data "$DIR" --set HI-Small \
    --rows HI-Small_candidates_0.8_1.2_72h.txt
python3 db/demo/aml_sample.py --data "$DIR" --rows HI-Small_candidates_0.8_1.2_72h.txt   # rebuilds the sample
```

## How the data is mapped

| IBM | Dominican Express | Why |
|---|---|---|
| bank + account | `account:⟨bank_account⟩` | The transactions file writes the bank with leading zeros (`021174`), the accounts file without: they must be normalised or no account matches |
| entity | `customer`, linked by `owns` | |
| amount paid, currency | `transfer.amount` in EUR | Hops of one ring are in different currencies; the rule compares amounts. Rates: median of the ~72,000 cross-currency transactions in the set |
| (none) | IBAN `ES` + 22 digits from a hash | The schema requires a unique Spanish IBAN |
| `Is Laundering`, pattern | table `aml_truth`, apart | The detector must not see the label, not even by accident |
| self-transfers (591,212) | dropped | Not a movement between accounts; in a graph, a loop with no meaning |

It goes into a **separate database** (`aml`) with only `01_core`, `02_graph` and
`05_detectors`: an analytics copy. Importing 5 million rows through the payments
API would fire the audit trail and alerts for every one.

## Why the full set never reaches SurrealDB

Our detector starts a search from every transfer. On one day of IBM data
(200,000 transfers) that kept the CPU at 100 % for minutes on a fanless laptop.
A bank does the same thing we did: a cheap filter first, the expensive graph
analysis only on what is suspicious.

`demo/aml_prefilter.py` removes, in one linear pass repeated until nothing
changes, every transfer that **cannot** be part of a ring under the most
permissive rule we test (amount 0.80–1.20, 72 h):

1. a ring hop always has a previous hop **or** a next one under the rule (the
   first hop has no previous, the closing one has no next: requiring both
   loses every ring);
2. the accounts of a ring form a cycle, so they lie in the same strongly
   connected component, of at least 3 accounts.

HI-Small: **4,487,133 → 381 transfers** (256 accounts); LI-Small: 6,119,572 → 158.
Of the 381, 323 are labelled laundering (85 %, against 0.1 % in the set).

**Lossless, checked**: `demo/aml_rings.py` re-implements `fn::ring_from` in
Python. On the first 500,000 and 1,500,000 rows it finds exactly the same rings
from all transfers as from the candidates only. Red test: changing *or* to
*and* in step 1 loses all of them, and the comparison catches it.

## Findings

**1. Our rule was nearly blind on independent data.** We assumed a mule keeps a
commission, so each hop moves *less* money (85–100 %). In IBM's cycles the
amount after currency conversion moves ±9 % and **grows half the time**. The
strict rule found **6 of 54** cycles.

**2. Calibration, method fixed in advance** (`demo/aml_eval.py`): grid
lo ∈ {0.80, 0.85, 0.90} × hi ∈ {1.00 … 1.20} × gap ∈ {24, 48, 72} h, up to 12
hops. Pick the rule that recovers most labelled cycles with precision ≥ 95 %;
ties go to the strictest. Then apply it untouched to a second set.

| | strict (0.85–1.00, 48 h) | wide (0.90–1.20, 72 h) |
|---|---|---|
| HI-Small, calibration | 6/54 cycles, precision 100 % | **33/54, 98.6 %** (3 innocent of 211) |
| LI-Small, held out | 1/12, 100 % | **8/12, 86.9 %** (8 innocent of 61) |

Precision is the share of flagged accounts that take part in some labelled
laundering transaction. A cycle counts as found when the detector returns a
ring made only of transfers of that attempt.

Recall holds on unseen data (61 % → 67 %). Precision drops because LI has less
laundering: the rarer the fraud, the more the false alarms weigh. We do not
recalibrate on LI; that would be grading our own exam.

**3. Two tiers instead of one rule.** Freezing on the wide rule would freeze 1
innocent in 8. So (`05_detectors`, `10_controls`):

- strict ring → `mule_ring` → **freeze** (100 % precision on both sets);
- ring that only the wide rule sees → `possible_ring` → **review** by an analyst.

**4. What no forwarding rule can catch.** Of the 54 cycles, 19 are out of reach:
14 have only 2 accounts (A→B→A, excluded on purpose: friends paying each other
back), 2 break the permissive rule (a 79 h hop, an amount ×2.88), and 3 are
**not in time order**: an account sends the money on *before* receiving it. IBM's
generator does not enforce causality, so "the same money goes round" does not
describe them.

**5. Rings are one typology of eight.** The detector targets cycles; it is not
meant to catch fan-in, fan-out and the rest, and it does not.

## Limitations

- Synthetic data. Real banks see more legitimate forwarding (payroll agents,
  marketplaces), so real precision would be lower than here.
- Precision as defined above credits an account that launders through another
  typology; it is the account-level question an analyst would ask, not a
  ring-level one.
- Exchange rates are one median per currency for the whole month.
- The search found a SurrealDB performance trap on the way: see README.es.md,
  "Trampas de SurrealQL" (`.map` calling a function that queries is quadratic).
