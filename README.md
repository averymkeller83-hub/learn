# Learn

**L**ook · **E**xplain · **A**ttempt · **R**evise · **N**ext — the loop the letters spell, and the way the tutor works: read the problem, ask it to teach with a `?`, write one step in ink, let Check mark the slip in the margin, then the next step.

**A free AI teacher that can see your notes.**

Live: https://learn.avery-keller.net  (the old showwork.avery-keller.net still answers)

You handwrite (or type, or import) on a page. A tutor that can see the page
checks your work, crosses out the exact bit that's wrong, writes the corrected
line under it, and explains *why* in the chat. Ask it to teach you anything and
it finds out what you know, puts a plan on the board, and walks you through it
one step at a time — drawing diagrams, plotting graphs, writing examples, all in
its own colour so its work never blurs into yours.

It looks like OneNote on purpose: notebooks › sections › pages, the Home ·
Insert · Draw · View ribbon, Microsoft's own icon set. Students already know
where everything is.

## What it does

**Check my work** — reads your handwriting, finds the *first* mistake, crosses
it out where it sits, writes the corrected work on the page, and explains why in
the chat. One mistake at a time; that's how people learn.

**Teach me…** — say a topic and your level (kid → adult). Two quick questions to
find out what you know, a plan on the board, then one step per turn. It remembers
what each learner has mastered and where they struggled, per notebook.

**A tutor with a whiteboard** — it talks in the chat and *shows* on the page:
shapes, arrows, labels, exact plots of any expression, and SVG diagrams for
anything with many parts. Ten subject personas — math, chemistry, physics,
biology, code, writing, history, language, study skills — each carrying that
subject's method, notation, the mistakes it produces, and how people who do the
work actually work.

**Sources** — attach the course's textbook chapters or links; the tutor follows
*their* definitions and notation and cites the page. Your course, not a generic one.

**Practice exams and Review** — five questions on your topic on a fresh page, the
tutor locked until you say you're done. Review goes further: it walks the notebook
oldest-first and asks you to recall what you'd otherwise be forgetting.

**Progress** — pages, topics, days studied, how the graded work went, and what the
tutor has noticed about how you work.

**Everything OneNote has** — notebooks › sections › pages, the Home · Insert ·
Draw · View ribbon with Microsoft's own icon set, pens, highlighter, eraser, lasso
(move / copy / cut / paste / delete), text, tables, pictures, camera, PDFs to write
on, ten kinds of paper, symbols, dictation, read-aloud, a calculator (`3*(4+5) =`
+ Enter) that can be switched off, export to PNG/PDF via the share sheet, import
from OneNote, zoom, undo/redo. Installable as an app.

**Reading mode** — OpenDyslexic, wider spacing, a warmer page, and the tutor's
handwriting in a plain face instead of a cursive one.

**Push to talk** — hold the mic, speak, let go. Nothing listens on its own.

## How it works

One HTML file is the whole app (`index.html`). Pages live in the browser's
IndexedDB. Nothing leaves the device until you ask the tutor something — then a
JPEG of the page (your ink, never the tutor's) goes to the model.

```
browser ──► Cloudflare Worker (worker/worker.js) ──► Gemini
   │              holds the shared key
   └────────────► Gemini directly, with YOUR free key (⚙ Settings)
```

- **Bring your own AI.** Gemini (free), Anthropic Claude, OpenAI, or Ollama on
  your own machine. Paste a key in ⚙ and every call goes straight from your
  browser to that provider — it never touches this server. Only vision models are
  offered: reading handwriting is the product.
- **The shared key is capped** at 15 checks per visitor per day (counted in D1,
  by a hash of IP and user agent — no accounts, nobody identified), so one busy
  day can't leave the next visitor with a broken app.
- **The prompts are in one file** — `prompts.json` — read by the Worker, the
  local dev server *and* the browser, so they can't drift.
- **Why the read-back step exists.** On day one, two of three readers (me, the
  model, and the truth) disagreed about one handwritten fraction. So the tutor
  never corrects a reading it flagged as doubtful without asking you first.

## Run it

```
export GEMINI_API_KEY=...        # a free key from aistudio.google.com/apikey
python3 server.py                # then open http://localhost:8000
```

Deploy your own:

```
cd worker
npx wrangler deploy
npx wrangler secret put GEMINI_API_KEY
```

Edit `routes` in `worker/wrangler.toml` for your domain.

## House rules

1. Secrets never touch the code, and never reach the browser. The key lives in
   the Worker (or in the student's own browser, for their own key).
2. Every file reads like a story: a plain-English map at the top, banners on
   sections, a memo on every move. If you can't read it, I broke a rule.
3. The model proposes; the code decides. The tutor's ink is on its own layer
   and never modifies the student's strokes. The student is the authority on
   what they wrote.
4. No button that only pretends. Audio/video recording, meeting details, email,
   translate and stickers are left out until they can be real.

## Credits

Built by Avery Keller with Claude Code, September 2026, as an Indiana
University CS student who needed exactly this.

Icons: [Fluent UI System Icons](https://github.com/microsoft/fluentui-system-icons)
(Microsoft, MIT). PDFs: [pdf.js](https://mozilla.github.io/pdf.js/) (Apache-2.0).
PDF export: [jsPDF](https://github.com/parallax/jsPDF) (MIT). Model: Google Gemini.

## License

MIT — see `LICENSE`. Free means free.
