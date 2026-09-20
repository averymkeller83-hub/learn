"""Showwork — the dev server. Small on purpose.

THE WHOLE PROGRAM IN FOUR STEPS:
  1. Serve index.html (the board) to the browser.
  2. Board sends a picture of itself to /transcribe. We ask the vision
     model ONLY "what does this say?" and hand the words back.
  3. The student fixes the reading if we got it wrong.
  4. Board sends the picture + the CORRECTED reading to /check. Now we
     ask "where is the FIRST mistake?" and hand that back.

Steps 2 and 4 are deliberately two separate calls to the model. One
combined call would bury the reading inside the verdict, and the student
would never get the chance to correct it. On 2026-09-17 two of three
readers misread the same handwritten fraction — that is the whole
reason this program is shaped like this.

The key lives HERE and never goes to the browser.

Run:  GEMINI_API_KEY=... python3 server.py     then open localhost:8000
"""

# ============================================================
# IMPORTS — all built into Python, nothing to install
# ============================================================
import base64
import html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from http.server import HTTPServer, SimpleHTTPRequestHandler

# ============================================================
# THE BRAIN — same swappable seam as agent-from-scratch.
# Changing models touches these three lines and nothing else.
# ============================================================
MODEL = "gemini-3.5-flash-lite"   # 2026-09-17: ~10x faster than flash on this task, passed both check tests
BASE = "https://generativelanguage.googleapis.com/v1beta/models"
ASK_URL = f"{BASE}/{MODEL}:generateContent"

# ---- The key is read from the environment, NEVER written here. ----
# ---- A key in this file is a key published the second I push.  ----
API_KEY = os.environ.get("GEMINI_API_KEY")

PORT = 8000

# How many checks one visitor gets. On the real thing this lives in the
# database, per person. Here it is one number, because there is one of me.
CHECK_BUDGET = 40


# ============================================================
# THE TWO PROMPTS — the heart of the product — live in prompts.json,
# because the Cloudflare Worker reads the SAME file. Two copies would
# drift; one file can't. Transcribe is forbidden from judging: the
# moment it starts correcting, it stops reporting what is on the page.
# ============================================================
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts.json")) as f:
    PROMPTS = json.load(f)
TRANSCRIBE_PROMPT = PROMPTS["transcribe"]
CHECK_PROMPT = PROMPTS["check"]          # contains {work}, filled in below


# ============================================================
# ask_vision — the phone line to the brain, with a picture attached.
# IN:  a prompt, and the board as PNG bytes
# OUT: whatever the model said, as text
# ============================================================
def ask_vision(prompt, img_bytes, mime="image/png", want_json=False):
    """Send one image and one question. Get words back (valid JSON if asked)."""

    # ---- the picture rides as base64 text inside the JSON ----
    body = {"contents": [{"parts": [
        {"text": prompt},
        {"inline_data": {"mime_type": mime,
                         "data": base64.b64encode(img_bytes).decode()}},
    ]}]}
    if want_json:
        body["generationConfig"] = JSON_MODE
    return ask(body)


# Gemini's JSON mode: the answer IS valid JSON, no fences, no bracket slips.
# Used wherever we parse the reply - check, grade and chat. Not transcribe.
JSON_MODE = {"response_mime_type": "application/json"}


def ask(body):
    """The one place that actually talks to Gemini. IN: a request body. OUT: words."""
    req = urllib.request.Request(ASK_URL, data=json.dumps(body).encode(), headers={
        "Content-Type": "application/json", "x-goog-api-key": API_KEY})

    with urllib.request.urlopen(req, timeout=60) as resp:
        answer = json.loads(resp.read())

    # ---- dig the words out of Gemini's nesting ----
    return answer["candidates"][0]["content"]["parts"][0]["text"]


# ============================================================
# chat_body — a conversation, not a single question. Gemini wants
# turns that alternate user / model; ours do, because the board only
# stores what was said. The page's picture rides with the LAST turn,
# and the tutor's standing instructions go in system_instruction.
# IN: the system prompt, [{role, text}], and maybe an image.
# ============================================================
def chat_body(system, messages, img_bytes=None, mime="image/png"):
    contents = []
    for m in messages[:-1]:
        role = "model" if m.get("role") == "model" else "user"
        contents.append({"role": role, "parts": [{"text": m.get("text", "")}]})
    last = messages[-1] if messages else {"text": ""}
    parts = [{"text": last.get("text", "")}]
    if img_bytes:
        parts.append({"inline_data": {"mime_type": mime,
                                      "data": base64.b64encode(img_bytes).decode()}})
    contents.append({"role": "user", "parts": parts})
    return {"system_instruction": {"parts": [{"text": system}]}, "contents": contents,
            "generationConfig": JSON_MODE}


# ============================================================
# strip_fence — the model likes to wrap JSON in ```json fences.
# IN: text that might be fenced.  OUT: text that isn't.
# ============================================================
def strip_fence(text):
    """Pull the JSON out of a markdown code fence, if there is one."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t     # drop the ```json line
        t = t.rsplit("```", 1)[0]                        # drop the closing fence
    return t.strip()


# ============================================================
# loose_json — the model's JSON, read the way a person would. Even in
# JSON mode a reply occasionally carries a fence, a stray trailing
# brace, or a sentence after the object. Strict parse, then the widest
# {...} in the text, then None. Raw JSON must never reach the student.
# ============================================================
def repair_escapes(t):
    """A lone backslash - the model writing \\frac despite the rules - is an
    illegal JSON escape and sinks the whole reply. Make it a literal one."""

    return re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', t)


def loose_json(text):
    # ---- strip the fence, mend the backslashes, then try the strict parse ----
    t = repair_escapes(strip_fence(text))

    try:
        return json.loads(t)
    except ValueError:
        pass
    a, b = t.find("{"), t.rfind("}")
    while a >= 0 and b > a:
        try:
            return json.loads(t[a:b + 1])
        except ValueError:
            b = t.rfind("}", a, b)
    return None


# ============================================================
# Board — the web server. Two real endpoints, everything else
# is just handing over files.
# ============================================================
class Board(SimpleHTTPRequestHandler):

    # one budget, shared by this process. The real one is per-person in D1.
    checks_used = 0

    # --------------------------------------------------------
    # do_GET — serve the board and NOTHING else. The default
    # handler hands out the whole directory, which would make a
    # stray .env one URL away. House rule 1: secrets never leave.
    # --------------------------------------------------------
    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path      # drop "?t=3" and the like
        if path in ("/", "/index.html"):
            self.path = "/index.html"
            return super().do_GET()
        if path == "/prompts.json":                        # the browser needs them for bring-your-own-key
            raw = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts.json"), "rb").read()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")   # a cached copy would drop new subjects
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            return self.wfile.write(raw)
        if path in ("/manifest.webmanifest", "/sw.js", "/icon-192.png", "/icon-512.png"):   # the installable-app files
            self.path = "/app" + path
            return super().do_GET()
        if path == "/fetch":                               # a linked web page, as readable text
            return self.fetch_page(urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get("url", [""])[0])
        self.send_error(404)

    # --------------------------------------------------------
    # fetch_page — the browser can't read other sites (CORS), so
    # we fetch a linked page here and hand back its text. http(s)
    # only, no private hosts, capped, tags stripped.
    # --------------------------------------------------------
    def fetch_page(self, url):
        u = urllib.parse.urlsplit(url)
        host = (u.hostname or "").lower()
        if u.scheme not in ("http", "https") or not host or host in ("localhost",) or \
           host.startswith(("127.", "10.", "192.168.", "169.254.", "0.")) or host.endswith(".local"):
            return self.reply(400, {"error": "bad_url", "message": "Only public http(s) links can be added."})
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Showwork source fetch)"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read(1_500_000).decode("utf-8", "replace")
        except Exception as e:                      # noqa: BLE001 - surface it
            return self.reply(502, {"error": "fetch_failed", "message": str(e)[:200]})
        title = re.search(r"<title[^>]*>(.*?)</title>", raw, re.I | re.S)
        text = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", raw, flags=re.I | re.S)
        text = re.sub(r"<[^>]+>", " ", text)
        text = html.unescape(re.sub(r"\s+", " ", text)).strip()
        return self.reply(200, {"title": html.unescape(title.group(1)).strip() if title else url, "text": text[:400_000]})

    def log_message(self, fmt, *args):
        """Quieter log — one line per real request, not per favicon."""
        if "/transcribe" in self.path or "/check" in self.path:
            print(f"  {self.path}  {fmt % args}")

    # --------------------------------------------------------
    # reply — every answer leaves through here, so the JSON
    # headers and the error shape are written down once.
    # --------------------------------------------------------
    def reply(self, status, payload):
        raw = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        if self.path not in ("/transcribe", "/check", "/chat"):
            return self.reply(404, {"error": "no such endpoint"})

        # ---- the guard rail: no key, no calls, and SAY so. A demo ----
        # ---- that fails silently is worse than one that refuses.  ----
        if not API_KEY:
            return self.reply(503, {
                "error": "no_key",
                "message": "GEMINI_API_KEY is not set on the server."})

        # ---- the budget. When it is gone the board still draws; ----
        # ---- only the checking stops, and it stops out loud.     ----
        if Board.checks_used >= CHECK_BUDGET:
            return self.reply(429, {
                "error": "out_of_checks",
                "message": "Out of checks for now. The board still works."})

        # ---- read the request: {"image": "data:image/jpeg;base64,...", ...} ----
        # ---- the picture is required for transcribe/check, optional for chat ----
        length = int(self.headers.get("Content-Length", 0))
        try:
            data = json.loads(self.rfile.read(length))
            png, mime = None, "image/png"
            if data.get("image"):
                head, b64 = data["image"].split(",", 1)      # "data:image/jpeg;base64"
                mime = head[5:].split(";")[0] or "image/png"  # the board sends JPEG
                png = base64.b64decode(b64)
            elif self.path != "/chat":
                raise KeyError("image")
        except (ValueError, KeyError, IndexError) as e:
            return self.reply(400, {"error": "bad_request", "message": str(e)})

        Board.checks_used += 1

        # ---- what the student says they're working on, if anything. It goes ----
        # ---- in FRONT of either prompt so the model isn't reading blind.      ----
        ctx = (data.get("context") or "").strip()[:300]
        note = PROMPTS["context_note"].replace("{context}", ctx) if ctx else ""
        # ---- excerpts from the student's own textbooks, picked by the browser. They go ----
        # ---- right after the topic, so the model teaches THEIR course, not a generic one. ----
        src = (data.get("sources") or "").strip()[:9000]
        if src:
            note += PROMPTS["sources_note"].replace("{sources}", src)
        # ---- the calculator setting: may the tutor do the numbers, or must the student? ----
        if data.get("calc") in ("on", "off"):
            note += PROMPTS["calc_on_note" if data["calc"] == "on" else "calc_off_note"]
        # ---- the subject persona: teach like someone who does this work ----
        subj = PROMPTS.get("subjects", {}).get(str(data.get("subject") or ""), None)
        if subj:
            note += PROMPTS["subject_note"].replace("{subject}", subj["prompt"])

        # ---- who the learner is: their level, and what the tutor has learned about them ----
        if (data.get("level") or "").strip():
            note += PROMPTS["level_note"].replace("{level}", str(data["level"]).strip()[:40])
        if (data.get("learner") or "").strip():
            note += PROMPTS["learner_note"].replace("{learner}", str(data["learner"]).strip()[:3000])

        try:
            # ============================================
            # /chat — the tutor, looking at the page.
            # Asks for JSON {say, board}; if the model rambles,
            # the ramble becomes what it says.
            # ============================================
            if self.path == "/chat":
                msgs = [m for m in (data.get("messages") or []) if isinstance(m, dict)][-16:]
                if not msgs:
                    return self.reply(400, {"error": "no_message", "message": "Say something first."})
                raw = ask(chat_body(note + PROMPTS["chat"], msgs, png, mime))
                out = loose_json(raw)
                if isinstance(out, dict):
                    say, board = str(out.get("say", "")), out.get("board", "") or ""   # a string or a list of steps
                    remember = str(out.get("remember", "") or "")[:200]
                else:
                    say, board, remember = raw.strip(), "", ""
                return self.reply(200, {"say": say, "board": board, "remember": remember,
                                        "checks_left": CHECK_BUDGET - Board.checks_used})

            # ============================================
            # /transcribe — "what does this say?"
            # ============================================
            if self.path == "/transcribe":
                text = ask_vision(note + TRANSCRIBE_PROMPT, png, mime)
                return self.reply(200, {
                    "transcription": text.strip(),
                    "checks_left": CHECK_BUDGET - Board.checks_used})

            # ============================================
            # /check — "where is the FIRST mistake?"
            # The confirmed reading goes in; we trust it over
            # the model's own second look at the picture.
            # ============================================
            work = data.get("work", "").strip()
            if not work:
                return self.reply(400, {
                    "error": "no_work",
                    "message": "Confirm the transcription first."})

            # ---- an exam page asks to be GRADED whole, not checked for one error ----
            if data.get("mode") == "grade":
                n = str(int(data.get("n") or 5))
                prompt = PROMPTS["grade"].replace("{work}", work).replace("{n}", n)
            else:
                prompt = CHECK_PROMPT.replace("{work}", work)
            raw = ask_vision(note + prompt, png, mime, want_json=True)

            # ---- the model was asked for JSON. If it obliged, pass it ----
            # ---- through. If it rambled, hand the ramble over rather  ----
            # ---- than pretending we got nothing.                      ----
            verdict = loose_json(raw)
            if not isinstance(verdict, dict):
                verdict = {"line": "", "problem": raw.strip(),
                           "nudge": "", "all_correct": False}

            verdict["checks_left"] = CHECK_BUDGET - Board.checks_used
            return self.reply(200, verdict)

        except urllib.error.HTTPError as e:
            detail = e.read().decode()[:300]
            return self.reply(502, {"error": "model_error", "message": detail})
        except Exception as e:                      # noqa: BLE001 - surface it
            return self.reply(500, {"error": "server_error", "message": str(e)})


# ============================================================
# Start it up.
# ============================================================
if __name__ == "__main__":
    if not API_KEY:
        print("!! GEMINI_API_KEY is not set — the board will draw, but")
        print("!! checking will refuse instead of failing quietly.\n")

    print(f"Showwork on http://localhost:{PORT}  ({CHECK_BUDGET} checks)")
    HTTPServer.allow_reuse_address = True      # stop/start without the TIME_WAIT sulk
    HTTPServer(("", PORT), Board).serve_forever()
