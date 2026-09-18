# Showwork — the next hour of coding (planned 2026-09-17 22:25, credits low)

Order matters. Each block is sized from tonight's pace (~15–20 min per verified feature).

## 0. Before the hour starts (Avery, no credits): the iPad pass
Add to Home Screen → open → Teach me… (kid, any topic) → write with the Pencil, palm down → Check my work →
Lasso something, move it → Insert › PDF (Gradescope PDF) → pinch-zoom → Export › this page → share sheet.
Write down the first three things that felt wrong. That list is what the first 10 minutes fix.

## 1. iPad fixes (≈10 min)
Whatever the pass surfaced. Likely suspects: palm rule too strict/loose, ribbon overflow in portrait,
text box keyboard pushing the canvas, Scribble grabbing Pencil strokes near text boxes.

## 2. Per-visitor cap on the shared key (≈25 min) — must land BEFORE the Handshake link goes public
- D1 table `checks(day, visitor_hash, n)`; visitor = hash(IP + UA) — no accounts needed.
- Worker: N free calls/day/visitor (start at 15), then 429 with the "add your own free key in ⚙" message
  the client already shows. Bring-your-own-key traffic never touches the Worker, so it's uncapped.
- Client: show "N checks left today" in the status line from the `checks_left` the Worker already returns.

## 3. Handshake submission (≈20 min)
- Tagline on the page (title, hero on first run): **"A free AI teacher that can see your notes."** (his words 21:39)
- Banner: a real screenshot — a handwritten wrong line struck through, the corrected work in amber, the plan on the
  board, chat open. 1200×630. Take it on the iPad, not Chrome.
- Write-up (~100 words): problem → what it does → the AI angle (Gemini; built with Claude Code).
  Live URL: https://showwork.avery-keller.net
- README.md in the repo (story-style, his house rules) — the public repo IS the portfolio artefact.

## 4. If he did the Azure step (≈5 min): verify OneNote import end to end
Register: portal.azure.com → App registrations → New → SPA redirect https://showwork.avery-keller.net/ →
Notes.Read + User.Read → paste the Application (client) ID into the import panel. Then import "calculus for data
science" and check Module 1 / Module 2 pages land as text.

## Parked (not an hour's work, or not yet asked for)
Accounts + sync (D1; the `store` seam is ready) · Mermaid for flowcharts · lasso-select for pictures ·
exam notes placed beside each problem · ink-to-shape · audio recording · translate.
