# Showwork — design

*Work the problem. It watches you.* — provisional. Flagged: checking is
on-demand, so "watches" oversells it. Needs a tagline that promises what the
product does. Decide before the banner is made.

Written 2026-09-17. Author: Avery Keller.

---

## The map

A whiteboard you handwrite math on. You ask it to check your work; it reads your
handwriting, shows you what it read so you can correct the read, then marks the
**first** place you went wrong — drawing on the board in its own ink, stroke by
stroke, the way a tutor writes beside you.

Built for the Handshake AI Showcase. A submission there is four things: a banner
image, a title, ~100 words, and **one live URL a stranger can open and understand
in five seconds.** Every design decision below serves that last part.

---

## Why the transcription step exists

On 2026-09-17 we ran a feasibility spike: Avery's real handwritten M220 work,
rendered from PDF, through Gemini vision. It transcribed nearly the whole page
correctly, including a name the handwriting renders as "Iceller".

Then three readers looked at one fraction:

| Reader | Read it as |
|---|---|
| Claude | `dx/dy` |
| Gemini | `dy/du` |
| Truth | `∂y/∂x` |

Two of three were wrong, and both were confident. **That is the central problem of
this product.** A tutor that confidently misreads your work and then corrects you
for an error you did not make is worse than no tutor at all — most of all for a
student who cannot easily tell that it is wrong.

So the product never tutors on an unconfirmed read. It shows its transcription
first. The student is the authority on what they wrote.

---

## The loop

1. Student handwrites the problem and their work on the board.
2. Student hits **check my work**. Nothing happens until they ask — see *Cost*.
3. Canvas is snapshotted and sent to the Worker.
4. The Worker asks the vision model to **transcribe** the work.
5. The transcription is shown back: *"here is what I read."* Student confirms or fixes.
6. Only on confirmation, the Worker asks for the **first error** — one, not all.
7. The answer is drawn onto the board in the AI's reserved ink, animated stroke by
   stroke, beside the line it refers to.
8. Student fixes that one line and checks again.

**One error at a time is a design rule, not a limitation.** It is how a person
actually learns, and it is the same rule that worked on Avery's Java this morning:
one bracket at a time, compile, next.

---

## The pieces

Four units. Each does one thing, and can be understood without reading the others.

### 1. The board (browser)

Infinite canvas, OneNote-feel: pick up a pen and write, no modes to learn.

- **Pen and mouse draw. Fingers do not.** `PointerEvent.pointerType === "pen"`
  (or `"mouse"`) draws; `"touch"` pans and zooms. This is real palm rejection —
  you can rest your hand on the screen while writing.
- Student ink: several colors, their choice.
- **AI ink: one reserved color, never available to the student.** Its marks can
  never be mistaken for theirs.
- Undo, clear.
- Knows nothing about AI or the database. It only calls the Worker.

### 2. The Worker (Cloudflare)

The only thing that holds a key or touches the database. The browser never sees
either.

- `POST /transcribe` — image in, transcription out.
- `POST /check` — image + confirmed transcription in, first error out.
- Enforces the per-visitor check cap.

### 3. The vision call (Gemini)

Two distinct prompts, deliberately separate:

- **Transcribe:** write out every line exactly as written. No judgement.
- **First error:** given the confirmed transcription, find the *first* place the
  student goes wrong, mathematically or in notation. If nothing is wrong, say so.
  Do not list every issue.

Splitting these is what makes step 5 possible. One combined call would bury the
read inside the verdict, and the student could never correct it.

### 4. D1 (SQLite)

- `users` — accounts.
- `boards` — saved work, per user.
- `checks` — per-visitor counts, for the cap.

---

## Rendering the AI's ink

The response is converted to stroke paths and animated in with
`stroke-dashoffset`, so the handwriting appears progressively rather than
popping into place.

This is not decoration. It is the difference between "a chatbot with a canvas
attached" and something that feels like a person writing beside you — and it is
the five-second clip that goes on the showcase banner.

---

## Accounts, and the stranger problem

Notes live in a real backend with accounts, so they persist across devices.

The risk this creates: a showcase visitor who must sign up before seeing anything
leaves. Most of them leave.

**The fix:** the showcase URL opens a **demo board**, already populated with a
sample problem, fully working, no account. Sign up only to *keep* something. Most
visitors never sign up, and that is fine — they still watched it work.

---

## Cost

Gemini's free tier is capped **per key, per day** — not per user. A key sitting in
the Worker serving everyone is one shared quota.

Three defenses:

1. **On-demand only.** Nothing is sent until the student hits check. Continuous
   watching was considered and rejected: at roughly one call per written line, a
   single study session would exhaust a day's quota in minutes.
2. **Per-visitor cap**, counted in D1. Enough checks to feel the product work.
3. **Graceful empty.** When the quota is gone, the board still draws and says so
   plainly. It never fails silently — the person who sees a broken demo is exactly
   the person you were trying to impress.

Verify the current free-tier daily limits before building against a number; Google
changes them.

---

## House rules carried over from `agent-from-scratch`

1. Secrets never touch the code, and never reach the browser. The key lives in the
   Worker only.
2. Every file reads like a story: a map at the top, banners on sections, a memo on
   every move.
3. **The model proposes; the code decides.** The AI's ink is drawn on a layer of
   its own and never modifies the student's strokes. Nothing is auto-saved over
   their work.

---

## Not in v1

Named explicitly, because these are what kill a first version:

- No multi-page notebooks — one board.
- No sharing or collaboration.
- No mobile app — the web page works on a tablet, that is enough.
- No subjects beyond math.
- No voice.
- No auto-watching. (Revisit once real quota headroom is known.)

---

## Scope

- **Weekend one:** canvas with pen-only input, snapshot, transcribe, confirm,
  first-error, AI ink drawn on the board. A working v1.
- **Weekend two:** accounts, D1, demo board, quota cap, banner and write-up.

The canvas input and the two-stage transcription are the real work. The Worker and
D1 halves follow patterns already built in `jarvis-cloud`.

---

## Open risk

The spike read a **clean, high-contrast PDF export**. A photo of paper under bad
kitchen lighting is a harder problem, and it has not been tested. If recognition
collapses on real-world photos, the confirm-the-transcription step is what keeps
the product usable — the student fixes the read and still gets correct tutoring.
That is the fallback, and it is already in the design.
