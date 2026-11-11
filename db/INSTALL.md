# Installation

Everything runs on one laptop, offline once installed. About 300 MB of disk:
the SurrealDB binary (~110 MB), Surrealist (~55 MB) and the demo data (~100 MB).

## What you need

| Tool | Version | Why |
|---|---|---|
| **SurrealDB** | **3.2.4** exactly | The version every test and measurement in this repo was run on |
| **Surrealist** | 3.x (we use 3.9.13) | Official SurrealDB GUI: queries, graph view, live queries |
| Python | 3.10 or newer | Demo and test scripts (tests use only the standard library) |
| [uv](https://docs.astral.sh/uv/) | any recent | Runs the scripts that need packages (SurrealDB SDK, numpy) without installing them globally |
| zsh, curl | any | The demo scripts are zsh; curl talks to the HTTP endpoint |

**Why pin 3.2.4.** The latest release is newer (3.3.x at the time of writing).
3.3 changes things this project depends on: it removes versioning from the
in-memory engine and adds query streaming. We have not re-run the tests on it,
so we do not claim it works.

## 1. SurrealDB 3.2.4

### macOS and Linux

The official installer, pinned to our version. The last argument is where the
binary goes; use a folder in your `PATH` that you can write to without `sudo`:

```sh
curl -sSf https://install.surrealdb.com | sh -s -- --version 3.2.4 ~/.local/bin
```

Do **not** use the Homebrew tap (`surrealdb/tap/surreal`): it is stuck at 1.0.0.

### Windows

Use **WSL 2** (Ubuntu) and follow the Linux steps inside it; the demo scripts are
zsh and will not run in PowerShell. In Ubuntu, install zsh first:
`sudo apt install zsh curl python3`.

### Docker (alternative for the database only)

The image exists for amd64 and arm64:

```sh
docker run --rm -p 8099:8000 -v "$PWD/dx-data:/data" \
  -e SURREAL_DATASTORE_VERSIONED=true -e SURREAL_DATASTORE_RETENTION=30d \
  surrealdb/surrealdb:v3.2.4 start --user root --pass root surrealkv:///data
```

Then load the data with `./db/demo/demo.sh studio-load` and `./db/demo/demo.sh stage`
(instead of `demo.sh up`, which starts a local binary). *We developed with the
native binary; this Docker path has not been through our test suite.*

### Check

```sh
surreal version
# 3.2.4+20260803.93ab219 for macos on aarch64   (platform part varies)
```

## 2. Surrealist

Download the desktop app for your system from the official page
(surrealdb.com/surrealist). On macOS it is a signed and notarised DMG; drag it
to Applications. Version used here: 3.9.13.

There is also a web version, but the desktop app is what we tested.

## 3. Python and uv

```sh
python3 --version     # 3.10 or newer
uv --version          # install: curl -LsSf https://astral.sh/uv/install.sh | sh
```

## 4. The repository

```sh
git clone https://github.com/Dominican-Express/dominican-ios.git
cd dominican-ios
```

Everything about the database lives in `db/`. The rest of the repo is the iOS app.

## 5. First start

```sh
./db/demo/demo.sh up
```

Expected (the first time it also loads the demo data, about one minute):

```
running on http://127.0.0.1:8099 (data in ~/.local/share/dominican-express)
first start: loading data (~1 min)…
bank:   5 customers, attack + sweep done
volume: 300 customers, 60 days, planted fraud, sweep done
live: 5 customers, no attack yet
connect Surrealist over WebSocket: ws://127.0.0.1:8099, root / root, namespace dx
remember: ./db/demo/demo.sh down when you finish
```

What it does: starts SurrealDB in the background **on disk** (SurrealKV engine,
with versioning on and 30 days of retention, for the time machine), bound to
`127.0.0.1` only, and loads three databases in namespace `dx`:

| Database | Content |
|---|---|
| `bank` | The 5-customer story with the attack and the sweep already done. Small: the graph fits on screen |
| `volume` | A generated bank: 300 customers, 60 days of normal life and planted fraud |
| `live` | The 5 customers, clean, for the live demo (`DEMO.md`) |

Optional: `./db/demo/demo.sh aml` adds `aml`, the IBM anti-money-laundering
sample (`DATASET.md`), in a few seconds.

Other commands: `./db/demo/demo.sh status`, `./db/demo/demo.sh down`.
Data survives between `down` and `up`. To start from zero, stop it and delete
`~/.local/share/dominican-express`.

## 6. Connect Surrealist

1. Open Surrealist and create a new connection:
   - protocol **`ws://`** (WebSocket), address **`127.0.0.1:8099`**;
   - authentication **Root**, user `root`, password `root`.
2. Open it. In the top bar, pick namespace **`dx`** and a database (`bank` to start).

Use WebSocket, not HTTP: the *Live* query mode only works over WebSocket.

**Credentials.** `root` / `root` is for this local demo only; the server listens
on `127.0.0.1` and nothing else. Demo app users (record access `banca`):

| User | Email | Password | PIN |
|---|---|---|---|
| Ana | ana@dominican.test | demo-ana | 1234 |
| Luis | luis@dominican.test | demo-luis | 5678 |
| Marta | marta@dominican.test | demo-marta | 2468 |

## 7. Verify everything (optional)

```sh
./db/demo/test_all.sh --quick   # the 6 test suites, ~15 s
./db/demo/test_all.sh           # plus the red-team runs, ~10 min
```

It starts its own temporary server on port 8098, so your demo data is not
touched. Expected last line: `ALL PASSED`. A red-team run breaks the schema on
purpose and checks that its test catches it (see `DECISIONS.md`).

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `did not start; see …/surreal.log` | Port 8099 in use, or wrong SurrealDB version. Check `surreal version` and `lsof -i :8099` |
| `The database 'x' does not exist` | In 3.x namespaces and databases are not created on the fly. Run `demo.sh up` (or `apply.sh`), which defines them |
| Surrealist shows no *Live* mode | The connection is HTTP. Make it `ws://` |
| Surrealist spins and the laptop heats up | A big result in **Graph** view (e.g. `SELECT * FROM account` on `volume` or `aml`). Quit Surrealist and always add `LIMIT` |
| Laptop warm after the demo | The server is still running: `./db/demo/demo.sh down` |
