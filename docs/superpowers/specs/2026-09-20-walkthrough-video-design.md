# Showwork walkthrough video — design (approved 2026-09-20 15:17)

**Audience:** people deciding whether to try Showwork (Handshake reviewers, students, LinkedIn).
**Length:** ~75s · 1920×1080 · 30fps.
**Voice:** Kokoro TTS, local (HyperFrames `tts`), voice picked by Avery from two samples.
**Footage:** hybrid — real UI captured from showwork.avery-keller.net (ribbon, panels,
dialogs) with ink, strikes and tutor responses animated on top as deterministic SVG (the v2 method).
**Music:** happy-beats vol-9, ducked ~0.12 under voice, up in gaps, out over the last 1.5s.
**Toolchain:** HyperFrames (`~/projects/showwork/walkthrough/composition`), gate = `hyperframes check` 0 errors.
**Output:** `walkthrough/showwork-walkthrough.mp4` + poster `.jpg` + `share-copy.txt`.

## Beats and narration (every claim from README.md)

1. **Check my work — 0–14s.** Cold open on the strike. *This is Showwork. You write the way you would on paper. A tutor that can see the page checks it — finds the first thing that's wrong, crosses out just that, writes the correction underneath in its own colour, and tells you why. One mistake at a time. That's how people learn.*
2. **Teach me… — 14–30s.** Two quick questions, plan on the board, fraction bars drawn live. *Say "teach me" anything. It asks two quick questions to find out what you know, puts a plan on the board, and walks you through it one step at a time — drawing on your page as it goes.*
3. **Your textbook — 30–41s.** Attach a chapter; tutor cites the page. *Attach your course's textbook. The tutor follows its definitions and notation, and cites the page. Your course, not a generic one.*
4. **Practice & Review — 41–52s.** Fresh page, five questions, tutor locked; Review oldest-first. *Practice exam: five questions on a fresh page, tutor locked until you say you're done. Review walks your notebook oldest-first and asks you to recall what you'd otherwise forget.*
5. **Reading mode · push to talk · free — 52–75s.** *Reading mode swaps in OpenDyslexic and wider spacing. Push to talk — hold the mic, speak, let go. Nothing listens on its own. It's free: one HTML file, no account, Gemini's free tier — or paste your own key and it never touches this server. Showwork. A free AI teacher that can see your notes.*

Scene durations flex to the generated narration (measure each WAV, set `data-duration` from it).

## Rules
- Only claims that appear in README.md. No invented stats.
- `--ai-ink #c2410c` is never used for student ink.
- Reading floor: captions ≥0.3s/word; labels ≥0.8s settled.
- Never tween layout properties; transforms + opacity only.
