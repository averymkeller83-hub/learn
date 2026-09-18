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
import json
import os
import urllib.error
import urllib.request
from http.server import HTTPServer, SimpleHTTPRequestHandler

# ============================================================
# THE BRAIN — same swappable seam as agent-from-scratch.
# Changing models touches these three lines and nothing else.
# ============================================================
MODEL = "gemini-3.5-flash"
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
def ask_vision(prompt, img_bytes, mime="image/png"):
    """Send one image and one question. Get words back."""

    # ---- the picture rides as base64 text inside the JSON ----
    body = json.dumps({"contents": [{"parts": [
        {"text": prompt},
        {"inline_data": {"mime_type": mime,
                         "data": base64.b64encode(img_bytes).decode()}},
    ]}]})

    req = urllib.request.Request(ASK_URL, data=body.encode(), headers={
        "Content-Type": "application/json", "x-goog-api-key": API_KEY})

    with urllib.request.urlopen(req, timeout=60) as resp:
        answer = json.loads(resp.read())

    # ---- dig the words out of Gemini's nesting ----
    return answer["candidates"][0]["content"]["parts"][0]["text"]


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
        if self.path in ("/", "/index.html"):
            self.path = "/index.html"
            return super().do_GET()
        self.send_error(404)

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
        if self.path not in ("/transcribe", "/check"):
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

        # ---- read the request: {"image": "data:image/png;base64,..."} ----
        length = int(self.headers.get("Content-Length", 0))
        try:
            data = json.loads(self.rfile.read(length))
            head, b64 = data["image"].split(",", 1)          # "data:image/jpeg;base64"
            mime = head[5:].split(";")[0] or "image/png"      # the board sends JPEG now
            png = base64.b64decode(b64)
        except (ValueError, KeyError, IndexError) as e:
            return self.reply(400, {"error": "bad_request", "message": str(e)})

        Board.checks_used += 1

        # ---- what the student says they're working on, if anything. It goes ----
        # ---- in FRONT of either prompt so the model isn't reading blind.      ----
        ctx = (data.get("context") or "").strip()[:300]
        note = PROMPTS["context_note"].replace("{context}", ctx) if ctx else ""

        try:
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

            raw = ask_vision(note + CHECK_PROMPT.replace("{work}", work), png, mime)

            # ---- the model was asked for JSON. If it obliged, pass it ----
            # ---- through. If it rambled, hand the ramble over rather  ----
            # ---- than pretending we got nothing.                      ----
            try:
                verdict = json.loads(strip_fence(raw))
            except ValueError:
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
