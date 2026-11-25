"""Genera presentation/dominican-express.pptx (22 diapositivas, notas del orador; el número de cada una se cuenta solo).

    uv run --with python-pptx --with matplotlib --with pillow --with qrcode --with networkx python presentation/build.py

Diseño: Brainstorm/slides-design.md en x-brain; cifras: db/*.md (ver README.md).
"""
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import qrcode
from pptx import Presentation
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches as I

import charts
from style import (BG, BOTTOM, CARD, H, LILAC, LINE, MARGIN, MONO, MUTED, PINK, TEXT, TOP,
                   VIOLET, W, arrow, box, frame, grid, picture, text)

REPO = "github.com/Dominican-Express/dominican-ios"


def qr_png():
    q = qrcode.QRCode(border=2, box_size=20)
    q.add_data("https://" + REPO)
    img = q.make_image(fill_color="#" + TEXT, back_color="#" + BG)
    path = HERE / "assets" / "gen" / "qr.png"
    img.save(path)
    return path


def app_icon():
    """Icono de la app con las esquinas redondeadas de iOS (radio 22,4 %)."""
    from PIL import Image, ImageDraw
    src = HERE.parent / "Project" / "Resources" / "Assets.xcassets" / "AppIcon.appiconset" / "AppIcon.png"
    im = Image.open(src).convert("RGBA")
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *im.size), radius=int(im.size[0] * 0.224), fill=255)
    im.putalpha(mask)
    path = HERE / "assets" / "gen" / "app-icon.png"
    im.save(path)
    return path


def cover(s):
    """Portada: el grafo real de transferencias de `volume`, anillos en violeta."""
    picture(s, charts.graph("graph-right", 6.6, 6.6), x=int(I(6.6)), y=int(I(0.45)),
            max_w=I(6.6), max_h=I(6.6))
    picture(s, app_icon(), x=int(MARGIN), y=int(I(1.05)), max_w=I(1.1), max_h=I(1.1))
    text(s, MARGIN, I(2.55), I(6.0), I(0.9), "Dominican Express", size=42, bold=True)
    text(s, MARGIN, I(3.5), I(6.0), I(0.6), "A bank built inside SurrealDB", size=24,
         color=MUTED)
    text(s, MARGIN, I(4.65), I(6.0), I(1.2), "Jorge Pérez\nXabier Ariznabarreta\nJavier Pérez",
         size=20)
    text(s, MARGIN, I(6.05), I(6.0), I(0.4), "Advanced Databases, UFV", size=18, color=MUTED)
    text(s, I(7.0), I(6.75), I(5.8), I(0.4), "2,827 transfers, 22 accounts in rings",
         size=18, color=MUTED, font=MONO, align=PP_ALIGN.RIGHT)


def commands(slide, lines, y=TOP + I(0.2)):
    """Chuleta de la demo: una línea por paso, número atenuado y orden en mono."""
    for i, (cmd, what) in enumerate(lines):
        yy = y + I(0.78) * i
        text(slide, MARGIN, yy, I(0.5), I(0.5), f"{i + 1}", size=22, color=MUTED, font=MONO)
        text(slide, MARGIN + I(0.6), yy, I(7.4), I(0.5), cmd, size=22, font=MONO)
        text(slide, MARGIN + I(8.2), yy + I(0.04), I(4.0), I(0.5), what, size=20, color=MUTED)


def build():
    g = charts.all_charts()
    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H
    num = iter(range(1, 100))  # número de diapositiva: se cuenta solo al insertar una

    # ------------------------------------------------------------------ Jorge
    s = frame(prs, next(num), None, notes="""
JORGE. Good morning. We are Jorge, Xabier and Javier, and this is Dominican Express:
a digital bank. The deliverable of this course is the database, and in our project the
database is not just storage: the whole backend, from payments to fraud detection,
lives inside it. On the right, real data from our test bank: 2,827 transfers between
300 customers over 60 days. The violet ones are the 22 accounts the database itself
found moving money in rings.
I will start with the product and why we chose this database. Then Xabier shows the
architecture and how it behaves when we break it, and Javier closes with a critical look.""")
    cover(s)

    # ------------------------------------------------------------------ Jorge
    s = frame(prs, next(num), "The product", "iOS app in SwiftUI, talking to the database", notes="""
JORGE. The product is a mobile bank: accounts, transfers, Bizum between customers,
cards, shared accounts. This is our iOS app, written in SwiftUI. On the left, the home
screen: the total balance, buttons to send money or make a Bizum, and the recent
activity. On the right, the card screen, with the monthly spending limit. The app started
on mock data. Now it reads and pays against the real database, with no server in
between.""")
    shots = HERE.parent / "docs" / "screenshots"
    picture(s, shots / "home.png", x=int(W / 2 - I(3.0)), max_w=I(2.8))
    picture(s, shots / "cards.png", x=int(W / 2 + I(0.2)), max_w=I(2.8))

    # ------------------------------------------------------------------ Jorge
    s = frame(prs, next(num), "Inside the app", "One protocol, two data sources", notes="""
JORGE. I built the app. It uses SwiftUI with MVVM and async/await, in Swift 6. The views
read everything through one protocol, BankRepository, which has two implementations. The
mock one has fixed demo data and is the default. The SurrealDB one makes real HTTP
calls. Four launch arguments in Xcode switch between them, and the views do not change.
Two details matter for a bank. Money is a Decimal in the app and travels as text, never
as a floating point number. And every payment attempt carries a new UUID, so if the same
order arrives twice, the database pays it once.""")
    box(s, I(2.65), TOP + I(0.1), I(8.0), I(0.95), "SwiftUI views and view models",
        sub="MVVM, async/await, Swift 6", size=22)
    arrow(s, I(6.65), TOP + I(1.05), I(6.65), TOP + I(1.6))
    box(s, I(3.9), TOP + I(1.6), I(5.5), I(0.95), "BankRepository", sub="one protocol",
        accent=True, font=MONO, size=22)
    for i, (name, sub) in enumerate([("MockBankRepository", "demo data, the default"),
                                     ("SurrealBankRepository", "URLSession, real database")]):
        x = I(1.45) + i * I(5.65)
        box(s, x, TOP + I(3.25), I(4.8), I(1.3), name, sub=sub, font=MONO, size=22)
        arrow(s, I(6.65), TOP + I(2.55), x + I(2.4), TOP + I(3.25))

    # ------------------------------------------------------------------ Jorge
    s = frame(prs, next(num), "What SurrealDB is", "NoSQL, multi-model. Looks like SQL, has no JOINs",
              notes="""
JORGE. SurrealDB is a NoSQL, multi-model database. One engine, one query language called
SurrealQL, and one transaction cover three ways of storing data. Documents: a customer
or an account is a JSON-like record. Graph: a relation, like "this customer owns this
account", is itself a record and can carry fields. And underneath, everything is stored
as keys in an ordered key-value store. It looks like SQL, but it is not relational:
records link to each other by ID, there are no JOINs.""")
    top = box(s, I(2.65), TOP + I(0.3), I(8.0), I(0.95),
              "One engine, one language, one transaction", accent=True, size=22)
    cols = [("Documents", "customer, account"), ("Graph", "owns, transfer"),
            ("Key-value", "storage layer")]
    for i, (name, sub) in enumerate(cols):
        x = I(1.45) + i * I(3.75)
        box(s, x, TOP + I(2.4), I(3.1), I(1.5), name, sub=sub, size=24)
        arrow(s, I(6.65), TOP + I(1.25), x + I(1.55), TOP + I(2.4))

    # ------------------------------------------------------------------ Jorge
    s = frame(prs, next(num), "One engine instead of several",
              "Ledger, graph and permissions in one transaction", notes="""
JORGE. A common way to build this is with several pieces: an application server between
the app and the database, a database for the money, and for fraud a separate graph
database, fed by an ETL process. Two systems can diverge, and sign-in and permissions end
up written in two places. In SurrealDB the ledger, the transfer graph and
the permissions live in one database and commit in one transaction. A transfer writes the
accounting entries and the graph edge together. And the same path, from a customer
through owns to an account, decides what you can see and feeds the fraud detectors.""")
    for i, (head, items, acc) in enumerate([
            ("Separate systems", ["An application server in front", "A database for the money",
                                  "A graph database fed by ETL"], False),
            ("One engine", ["API inside the database", "Ledger and graph, one transaction",
                            "Permissions are graph paths"], True)]):
        x = MARGIN + I(0.3) + i * I(6.1)
        box(s, x, TOP + I(0.2), I(5.6), I(0.85), head, accent=acc, size=24)
        for j, item in enumerate(items):
            box(s, x, TOP + I(1.35) + j * I(1.05), I(5.6), I(0.85), item, size=20)

    # ------------------------------------------------------------------ Jorge
    s = frame(prs, next(num), "Why a bank needs it", "Typical fits: fraud and risk, social data, access control",
              notes="""
JORGE. Why this database for a bank? A bank needs three things at once. Money that
never goes out of balance: that needs transactions over several records. Fraud is a
graph problem: rings of accounts, phones shared by strangers. And the data is sensitive,
so each customer must only see their own records, and some fields like the card number
only after a PIN. Of the engines we compared, SurrealDB is the one that gives all three
in one place.
Typical scenarios for it: fraud and risk analysis, social and recommendation data,
access-control models that are graphs, and small or medium applications that want the
API, sign-in and real-time updates inside the database. Now Xabier will show you the
whole system, from the phone to the disk.""")
    rows = [("Money never out of balance", "Multi-record ACID", False),
            ("Fraud is a graph", "Native graph", True),
            ("Sensitive data", "Per-record, per-field permissions", False)]
    for i, (need, cap, acc) in enumerate(rows):
        y = TOP + I(0.25) + i * I(1.65)
        box(s, I(1.2), y, I(4.6), I(1.15), need, size=22)
        arrow(s, I(5.8), y + I(0.575), I(7.4), y + I(0.575))
        box(s, I(7.4), y, I(4.7), I(1.15), cap, accent=acc, size=22)

    # ------------------------------------------------------------------ Xabier
    s = frame(prs, next(num), "The path of a request", "One address for the app. No backend in between", notes="""
XABIER. This is the whole system, and the path of one request through it. The iPhone app
talks to one address: HAProxy, our load balancer. Step 1, sign in: the app gets a token
that carries only that customer's permissions, never database credentials. Step 2, read:
a plain SurrealQL query; HAProxy sends it to node A or B, and the database itself filters
it, so Ana only gets her own account. Step 3, pay: a POST to an endpoint defined inside
the database, with an order id generated by the app. Step 4: the SurrealDB node turns it
into a distributed transaction; PD says which TiKV nodes hold those keys, and the write
commits when two of the three copies have it, through Raft. Step 5: 201 Created comes back
the same way. The SurrealDB nodes keep nothing, so any of them can serve any request, and
that is what makes the load balancer possible.""")
    y0 = TOP + I(0.55)
    box(s, I(0.5), y0 + I(0.75), I(1.75), I(1.0), "iPhone app", size=20)
    box(s, I(2.85), y0 + I(0.75), I(1.95), I(1.0), "HAProxy", sub=":8100", accent=True, size=20)
    box(s, I(5.45), y0, I(1.85), I(0.9), "Node A", size=20)
    box(s, I(5.45), y0 + I(1.6), I(1.85), I(0.9), "Node B", size=20)
    box(s, I(7.95), y0 + I(0.75), I(1.5), I(1.0), "PD", size=20)
    box(s, I(10.1), y0 + I(0.75), I(2.7), I(1.0), "TiKV x3", sub="Raft 2 of 3", size=20)
    arrow(s, I(2.25), y0 + I(1.25), I(2.85), y0 + I(1.25))
    arrow(s, I(4.8), y0 + I(1.25), I(5.45), y0 + I(0.45))
    arrow(s, I(4.8), y0 + I(1.25), I(5.45), y0 + I(2.05))
    arrow(s, I(7.3), y0 + I(0.45), I(7.95), y0 + I(1.25))
    arrow(s, I(7.3), y0 + I(2.05), I(7.95), y0 + I(1.25))
    arrow(s, I(9.45), y0 + I(1.25), I(10.1), y0 + I(1.25))
    steps = [("1", "/signin", "customer token"), ("2", "/sql", "read, filtered"),
             ("3", "/api/bizum", "pay, order id"), ("4", "Raft", "2 of 3 copies"),
             ("5", "201", "back to the app")]
    for i, (n, what, sub) in enumerate(steps):
        x = I(0.5) + i * I(2.5)
        text(s, x, y0 + I(3.0), I(0.4), I(0.5), n, size=22, color=LILAC, font=MONO, bold=True)
        text(s, x + I(0.4), y0 + I(3.0), I(2.05), I(0.45), what, size=18, font=MONO)
        text(s, x + I(0.4), y0 + I(3.45), I(2.05), I(0.45), sub, size=18, color=MUTED)

    # ------------------------------------------------------------------ Xabier
    s = frame(prs, next(num), "Why a load balancer", "Check the node, not what every node shares", notes="""
XABIER. Why a load balancer? Because the SurrealDB nodes are stateless: without one, the
app would need the list of nodes and its own failover. With HAProxy the app has one
address, the load is spread, and a dead node is taken out before the app notices. We chose
HAProxy because it checks every node actively, once a second; free nginx only notices
when a real request fails. We measured it. Killing node A in the middle of 40 payments:
40 of 40 OK, three times, because HAProxy retries on the other node only when the
connection failed, so a payment is never sent twice. And a mistake we found: our first
health check also tested the storage. When a storage node died, both SurrealDB nodes
failed the check, HAProxy removed both, and 22 of 40 writes failed, more than with no
balancer at all. Checking only the node itself: 6 and 7, all from the storage election.""")
    grid(s, MARGIN + I(0.3), TOP + I(0.35), [I(6.6), I(5.0)], I(0.95), [
        ["Experiment, 40 writes through HAProxy", "Failed writes"],
        ["SurrealDB node A killed (3 runs)", "0 of 40"],
        ["TiKV leader killed, health check /health", "22 of 40"],
        ["TiKV leader killed, health check /status", "6 and 7 of 40"],
    ], size=22, first_col_bold=False, highlight_row=1)

    # ------------------------------------------------------------------ Xabier
    s = frame(prs, next(num), "One record, two models", "The role lives on the edge, not in a join table",
              notes="""
XABIER. Here is the data model in one query. Ana's account is a document. Who owns it is
a graph: the edge "owns" goes from customer to account, and it carries a field, the role.
Ana is the holder, Luis the co-holder. No join table. And the same traversal,
"my customer, owns, account", is both the permission rule (you see an account if it
hangs from one of your owns edges) and the input of the fraud detectors. We use a strict
schema where money is, and free-form fields where each detector writes different
details.""")
    box(s, MARGIN, TOP + I(0.2), W - 2 * MARGIN, I(1.0),
        "SELECT <-owns<-customer.name AS holders, <-owns.role AS roles FROM account:ana;",
        font=MONO, size=20, fill=CARD)
    for i, (name, role, acc) in enumerate([("Ana García", "titular", True),
                                          ("Luis Romero", "cotitular", False)]):
        y = TOP + I(2.0) + i * I(1.45)
        box(s, I(1.4), y, I(3.0), I(1.0), name, size=22)
        arrow(s, I(4.4), y + I(0.5), I(8.7), y + I(0.5))
        text(s, I(4.95), y + I(0.05), I(3.5), I(0.4), f"owns  role: {role}", size=18,
             font=MONO, color=LILAC if acc else MUTED, align=PP_ALIGN.CENTER)
    box(s, I(8.7), TOP + I(2.0), I(3.2), I(2.45), "account:ana", sub="document", accent=True,
        font=MONO, size=22)

    # ------------------------------------------------------------------ Xabier
    s = frame(prs, next(num), "Consistency under a race", "10 simultaneous full-balance transfers, 20 rounds",
              notes="""
XABIER. Consistency. Our first design was a pure ledger: the balance is the sum of the
entries. We fired ten transfers of the whole balance at the same time, twenty rounds.
The unsafe version ended in an overdraft in 11 to 16 of the 20 rounds. Why: SurrealDB
uses snapshot isolation, which only detects a conflict when two transactions write the
same record, and two transfers insert different ledger entries. The fix: every transfer
also updates the account's balance field. That write is the conflict point; one of the
two transactions is undone entirely. Result: zero overdrafts, every time. We only found
this by testing it.""")
    picture(s, g["race"])

    # ------------------------------------------------------------------ Xabier
    s = frame(prs, next(num), "Compute apart from storage", "3 copies, Raft majority 2 of 3: CP", notes="""
XABIER. Architecture. SurrealDB separates compute from storage. The same binary runs on
memory, on disk, or on TiKV, a distributed key-value store. With TiKV, SurrealDB nodes
are stateless: any node serves any request. TiKV splits the data in ranges called
regions, and keeps every region on three nodes, kept in agreement by the Raft protocol.
A write commits when two of three have it. Under a network partition the minority side
refuses writes: in CAP terms it is CP, consistency first. For a bank, the right side.
We built this cluster, and in the video you will see us break it.""")
    nb_y, pd_y, kv_y = TOP + I(0.1), TOP + I(1.75), TOP + I(3.4)
    for x, label in [(I(3.4), "Node A"), (I(7.0), "Node B")]:
        box(s, x, nb_y, I(2.6), I(0.95), label, size=22)
        arrow(s, x + I(1.3), nb_y + I(0.95), I(6.0), pd_y)
    box(s, I(4.85), pd_y, I(2.3), I(0.95), "PD", size=22)
    for i in range(3):
        x = I(2.45) + i * I(3.0)
        box(s, x, kv_y, I(2.5), I(0.95), f"TiKV {i + 1}", accent=(i == 0), size=22)
        arrow(s, I(6.0), pd_y + I(0.95), x + I(1.25), kv_y)
    for y, label in [(nb_y, "stateless"), (pd_y, "placement"),
                     (kv_y, "3 copies each")]:
        text(s, I(11.2), y + I(0.25), I(1.9), I(0.5), label, size=18, color=MUTED)
    text(s, I(2.45), kv_y + I(1.05), I(2.5), I(0.4), "leader", size=18, color=LILAC,
         align=PP_ALIGN.CENTER)

    # ------------------------------------------------------------------ Xabier
    s = frame(prs, next(num), "How it scales", "Scale compute and storage separately", notes="""
XABIER. How this grows. Compute and storage scale separately. More users: add SurrealDB
nodes behind HAProxy; they keep no state, so a new node serves traffic as soon as it
passes the health check. More data: add TiKV nodes; the data is split in ranges called
regions, regions split when they grow, and PD moves them to the new node on its own.
The limits we know: PD needs a majority, so three of them in production; a region that
everyone writes to, like one very busy account, is a hot spot no number of nodes fixes;
and live queries only see their own node, so a fraud dashboard listens on every node.
On a laptop this shows the mechanism; throughput across machines we did not measure.""")
    cols = [("More users", "add SurrealDB nodes", "stateless, behind HAProxy", True),
            ("More data", "add TiKV nodes", "regions split, PD moves them", False),
            ("Limits", "PD quorum, hot regions", "LIVE sees one node", False)]
    for i, (head_, line1, line2, acc) in enumerate(cols):
        x = MARGIN + I(0.1) + i * I(4.1)
        box(s, x, TOP + I(0.5), I(3.7), I(0.9), head_, accent=acc, size=24)
        box(s, x, TOP + I(1.65), I(3.7), I(1.1), line1, size=20)
        box(s, x, TOP + I(3.0), I(3.7), I(1.1), line2, size=18, font=MONO)

    # ------------------------------------------------------------------ Xabier
    s = frame(prs, next(num), "Streaming in and out with Kafka", "Why Kafka and not Redis Streams", notes="""
XABIER. The app's payments go straight into SurrealDB, but a bank also receives payments
from outside: the card network, other banks. Those arrive as a stream, so they come in
through Kafka. The key of each message is the account, so the payments of one account
stay in order. A consumer applies them, and Kafka delivers every message at least once:
if the consumer dies after paying and before confirming, the same payment comes again.
So each message carries an id, recorded in the same transaction as the payment, and the
second copy is not charged. We killed the consumer in the middle: 60 of 60 applied once.
Without the id, 61; confirming before paying, 59. Alerts leave through a second topic,
so every dashboard sees the alerts of every node. Why not Redis Streams? Redis keeps the
stream in memory and copies it to replicas asynchronously, so it can lose a write it
already acknowledged. For a notification that is fine; for a payment it is not. Kafka
keeps it on disk, we can read it again like our ledger, and it splits one stream over
many nodes by account.""")
    y0 = TOP + I(0.25)
    flow = [("Card network, banks", None, False), ("payments", "key = account", True),
            ("SurrealDB", "pays once", False), ("fraud-alerts", "every node", True),
            ("Dashboards", None, False)]
    for i, (title_, sub_, acc) in enumerate(flow):
        x = MARGIN + i * I(2.5)
        box(s, x, y0, I(2.05), I(0.95), title_, sub=sub_, accent=acc, size=18)
        if i:
            arrow(s, x - I(0.45), y0 + I(0.47), x, y0 + I(0.47))
    grid(s, MARGIN + I(0.3), y0 + I(1.35), [I(4.0), I(3.9), I(3.9)], I(0.62), [
        ["", "Kafka", "Redis Streams"],
        ["An accepted payment", "on disk, on replicas", "in memory, async copies"],
        ["Read it again", "rewind the offset", "until it is trimmed"],
        ["One stream, many nodes", "partitions by account", "one key, one node"],
    ], size=19, first_col_bold=False)
    text(s, MARGIN + I(0.3), y0 + I(4.05), I(11.8), I(0.5),
         "Killed mid-stream: 60 of 60 once. No id: 61. Commit first: 59",
         size=18, color=MUTED, font=MONO)

    # ------------------------------------------------------------------ Xabier
    s = frame(prs, next(num), "Install, access, query", "HTTP, WebSocket, Surrealist, Python SDK", notes="""
XABIER. Installing it is one command; we pin version 3.2.4 because 3.3 changes features
we depend on. Our demo script starts the database on disk and loads three databases in
about a minute, and the six test suites run in fifteen seconds. You talk to it over HTTP
for queries and our API, over WebSocket for the SDKs and live queries, with Surrealist,
the official GUI, and from Python with the official SDK. Everything is in the public
repo, step by step, so another student can reproduce it.""")
    picture(s, g["install"])

    # ------------------------------------------------------------------ Xabier
    s = frame(prs, next(num), "The system under attack", "Recorded on this laptop, nothing staged", notes="""
XABIER (video, 4 minutes 40; narrate over it).
1. Surrealist, live alerts: a mule ring forms, six alerts arrive on their own, the ring is
   frozen in proportion, Marta tries to erase the trail and cannot.
2. The cluster: HAProxy's health checks and the TiKV stores in view, SurrealDB node A
   killed during payments (every payment still OK), then a TiKV leader killed (a few
   seconds of errors, nothing lost).
3. Python with the official SDK: create, read, update, delete; a retried payment charged
   once.""")
    video = HERE / "assets" / "video" / "demo.mp4"
    if video.exists():
        poster = HERE / "assets" / "video" / "poster.png"
        # 16:9 exacto dentro de la zona de imagen, centrado: si no, se estira.
        vh = BOTTOM - TOP
        vw = int(vh * 16 / 9)
        s.shapes.add_movie(str(video), int((W - vw) / 2), TOP, vw, vh,
                           poster_frame_image=str(poster) if poster.exists() else None,
                           mime_type="video/mp4")
    else:
        commands(s, [("live alerts", "a ring is frozen"),
                     ("kill node A", "payments continue"),
                     ("kill a TiKV", "nothing lost"),
                     ("Python SDK", "insert, query, update, delete")])

    # ------------------------------------------------------------------ Xabier
    s = frame(prs, next(num), "The model, a race and real data", "Recorded on this laptop, part two", notes="""
XABIER (video 2, 5 minutes 17; narrate over it).
5. The model in Surrealist: customers are documents, owns is an edge with the role on it,
   the Designer, one query in each direction, and the mule ring as a graph.
6. Concurrency: ten clients send the whole balance at once, twenty rounds. The real
   transfer function never overdraws; the unsafe one did in 13 of 20.
7. Permissions: the script signs in as Ana and Luis, never as root, and every attack is
   refused.
8. IBM's dataset: the sample loads in about a second, the sweep flags 20 accounts in
   strict rings, and IBM's own labels confirm that all of them launder.""")
    video = HERE / "assets" / "video" / "demo2.mp4"
    if video.exists():
        poster = HERE / "assets" / "video" / "poster2.png"
        vh = BOTTOM - TOP
        vw = int(vh * 16 / 9)
        s.shapes.add_movie(str(video), int((W - vw) / 2), TOP, vw, vh,
                           poster_frame_image=str(poster) if poster.exists() else None,
                           mime_type="video/mp4")
    else:
        commands(s, [("the model", "documents and edges"),
                     ("demo.sh race", "0 of 20 overdrafts"),
                     ("demo.sh access", "every attack refused"),
                     ("demo.sh aml", "20 rings, all labelled")])

    # ------------------------------------------------------------------ Xabier
    s = frame(prs, next(num), "Tested on data we did not make", "Calibrated on one set, validated untouched on another",
              notes="""
XABIER. The ring in the demo we planted ourselves, so it can only confirm our own design.
So we ran the detector on IBM's public anti-money-laundering dataset, where the answer
is known. First result: 6 of 54 laundering cycles. We had assumed a mule keeps a
commission, so the amount shrinks; on IBM's data it grows half the time. We fixed the
method before looking, calibrated on one set, 33 of 54, and validated on another set we
had not touched: 8 of 12. At 87 percent precision, freezing would hit one innocent in
eight, so two tiers: strict rings freeze, wide ones go to an analyst. And a cheap
filter first: 4.5 million transfers down to 381, without losing a single ring.""")
    picture(s, g["ibm"])

    # ------------------------------------------------------------------ Xabier
    s = frame(prs, next(num), "What the cluster gives, what it costs",
              "The cluster proves failover. Time travel needs one node", notes="""
XABIER. What we measured. Killing a follower: nothing visible. Killing the leader of the
region being written: 9 to 12 seconds of errors, and not one write lost or half applied.
The node comes back and catches up in about ten seconds. It costs about 1.1 GB of RAM
on this laptop. And two features do not cross nodes: time travel only exists on the
single-node engine, and live queries only see changes made on their own node; across
nodes it is an Enterprise feature. So the alert demo and the time machine run on one
node, and the cluster proves the failover. Javier will now step back and judge the whole thing.""")
    grid(s, MARGIN + I(0.3), TOP + I(0.2), [I(5.8), I(5.8)], I(0.78), [
        ["Gives", "Costs"],
        ["Every write on 3 nodes", "About 1.1 GB of RAM"],
        ["SurrealDB node killed: 0 of 40 failed", "HAProxy: a single point here"],
        ["TiKV leader killed: 9 to 12 s of errors", "No time travel on TiKV"],
        ["0 writes lost or half applied", "Live queries: one node only"],
        ["5 of 6 test suites pass", "One laptop: mechanics, not speed"],
    ], size=20, first_col_bold=False)

    # ------------------------------------------------------------------ Javier
    s = frame(prs, next(num), "Don't trust the tool, test it", "74 of 74 deliberate breaks caught", notes="""
JAVIER. Now a critical look. Our main method: a test you have never seen fail is not
watching anything. So every protection was broken on purpose, and its test had to
catch it: 74 of 74 caught. Testing like this found real problems in SurrealDB: a
time-travel bug that brought deleted records back, which could produce false evidence
against an innocent; live notifications lost silently when two clients listen; and a
query planner that ignored our index, 72 milliseconds against 1.2. Every one became a
design decision. SurrealDB is powerful, but young. The red teams also found weak tests:
some passed with the bug still in place, and some crashed instead of failing.""")
    picture(s, g["redteam"])

    # ------------------------------------------------------------------ Javier
    s = frame(prs, next(num), "Lessons from building it",
              "Found by running, measuring or breaking it", notes="""
JAVIER. Building the project taught us some lessons about the engine. Functions were renamed between
3.x versions, so we pinned 3.2.4 and test everything on it. The time-travel bug only
appears on the disk engine, SurrealKV. In memory, that red team caught only 6 of 10
breaks, so our tests run on SurrealKV, where it catches 10 of 10. A write conflict comes
back as HTTP 400, which looks like a client error. Our client recognises it and retries
with the same order id. And a .map that ran a query for every item grew quadratically:
the IBM ring sweep took 54 seconds. Rewritten with SELECT VALUE, it takes one second.""")
    grid(s, MARGIN + I(0.3), TOP + I(0.2), [I(5.8), I(5.8)], I(0.9), [
        ["What we found", "How we handled it"],
        ["Renames between 3.x versions", "Pinned 3.2.4, tested on it"],
        ["Time-travel bug only on disk", "Tests on SurrealKV: 10 of 10, not 6"],
        ["Write conflict as HTTP 400", "Retry with the same order id"],
        ["IBM ring sweep: 54 s", "SELECT VALUE: 1.0 s"],
    ], size=20, first_col_bold=False)

    # ------------------------------------------------------------------ Javier
    s = frame(prs, next(num), "Against the alternatives", "From the documentation. Speed not measured",
              notes="""
JAVIER. How it compares, from each vendor's documentation, not measured: we do not claim
it is faster than any of them. MongoDB also has multi-document transactions; what
separates them is the graph, limited to 100 MB, and permissions per field only through
views. Cassandra keeps transactions inside one partition. Neo4j is the strongest graph,
but property permissions are Enterprise only. ArangoDB was the serious alternative,
rejected for permissions. PostgreSQL is not NoSQL, which the course requires, but it is
still the fair comparison. It is far more mature: SELECT FOR UPDATE, serializable
isolation, row-level security and decades of tooling. With it we would lose the graph
shared by permissions and fraud detection, the API inside the database, and time travel.
SurrealDB is the only one of these with queries into the past inside the language.""")
    grid(s, MARGIN, TOP + I(0.05), [I(2.35), I(2.4), I(2.4), I(2.5), I(2.45)], I(0.74), [
        ["", "Transactions", "Graph", "Field permissions", "Query the past"],
        ["MongoDB", "multi-document", "100 MB limit", "views only", "about 5 min"],
        ["Cassandra", "one partition", "no", "column masking", "no"],
        ["Neo4j", "yes", "native", "Enterprise only", "no"],
        ["ArangoDB", "single server", "native", "per collection", "no"],
        ["PostgreSQL", "yes, not NoSQL", "recursive CTE", "row-level", "no system time"],
        ["SurrealDB", "multi-record", "native", "per field", "VERSION, beta"],
    ], size=18, highlight_row=6)

    # ------------------------------------------------------------------ Javier
    s = frame(prs, next(num), "Where SurrealDB fits", "Strengths we measured, limits we hit", notes="""
JAVIER. So, when would we use it? When documents, a graph and fine-grained permissions
meet, like fraud, risk or access control; for small and medium systems where a small
team benefits from having the API, authentication and real-time updates inside the
database; and for prototypes and teaching. Not yet for a system that needs a long,
proven operational record: we hit renames between versions, a bug and lost live events.
Not for real-time across nodes without the Enterprise licence. And legal evidence must
still be copied out to write-once storage.""")
    for i, (head, items, acc) in enumerate([
            ("Good fit", ["Documents + graph + permissions", "Small team, logic in the database",
                          "Prototypes and teaching"], True),
            ("Not yet", ["Long proven operational record", "Real-time across nodes, free",
                         "Legal evidence storage"], False)]):
        x = MARGIN + I(0.3) + i * I(6.1)
        box(s, x, TOP + I(0.2), I(5.6), I(0.85), head, accent=acc, size=24)
        for j, item in enumerate(items):
            box(s, x, TOP + I(1.35) + j * I(1.05), I(5.6), I(0.85), item, size=20)

    # ------------------------------------------------------------------ Javier
    s = frame(prs, next(num), "What we would do next", "What we would change, what is still missing",
              notes="""
JAVIER. If we started again, we would test as an app user and on the real engine from day
one, as our final test suites do. We would also measure every engine feature before
building on it. For production, apps should not send free queries: permissions limit what
a customer sees, not the CPU a query costs. Then the next steps. A write-once copy of the audit log,
because the law asks for five to ten years and versioning keeps 30 days. A limit on
password attempts: today only the PIN locks, after three failures. And a measured
comparison of our ring detector against a recursive query in PostgreSQL.""")
    for i, (head, items, acc) in enumerate([
            ("Do differently", ["Test as an app user from day one",
                                "Measure each feature first", "No free queries from apps"], True),
            ("Next steps", ["Write-once copy of the audit log", "Limit on login attempts",
                            "Ring detector against PostgreSQL"], False)]):
        x = MARGIN + I(0.3) + i * I(6.1)
        box(s, x, TOP + I(0.2), I(5.6), I(0.85), head, accent=acc, size=24)
        for j, item in enumerate(items):
            box(s, x, TOP + I(1.35) + j * I(1.05), I(5.6), I(0.85), item, size=20)

    # ------------------------------------------------------------------ Javier
    s = frame(prs, next(num), None, notes="""
JAVIER. To finish: every number you saw is in the public repository, with the steps to
reproduce it. The code was written with AI help; what we did was decide what to build,
measure it, and break it on purpose. Thank you. Questions?""")
    text(s, MARGIN, I(2.2), I(7), I(1.0), "Decisions, measured", size=48, bold=True)
    text(s, MARGIN, I(3.4), I(7), I(1.0), "Every number on these slides\nis in the repository.",
         size=24, color=MUTED)
    text(s, MARGIN, I(5.2), I(7), I(0.5), REPO, size=20, font=MONO, color=LILAC)
    picture(s, qr_png(), x=int(I(8.6)), y=int(I(1.8)), max_w=I(3.8), max_h=I(3.8))

    out = HERE / "dominican-express.pptx"
    prs.save(out)
    return out


if __name__ == "__main__":
    print(build())
