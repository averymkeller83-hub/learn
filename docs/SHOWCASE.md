# Handshake AI Showcase — the submission

Live URL: **https://showwork.avery-keller.net**
Repo: **https://github.com/averymkeller83-hub/showwork**

## Title
Showwork

## Tagline (for the banner image)
**A free AI teacher that can see your notes.**

## Description (~100 words — the field on Handshake)
Showwork is a notebook with a teacher inside it. You handwrite your work the way
you would on paper; it reads your handwriting, crosses out the first thing that's
wrong, writes the correction on the page, and explains why in the chat. Say
"teach me" anything and it asks what you already know, puts a plan on the board,
and teaches one step at a time — drawing diagrams and plotting graphs as it goes.
Attach your own textbook and it follows your course's definitions. Built with
Claude Code over one long night; it runs on Gemini's free tier, or your own key.

## Banner
1200×630. A real screenshot from the iPad, showing in one frame:
- a handwritten line with the wrong part struck through in amber
- the corrected work written underneath in the tutor's hand
- a plan or diagram on the board
- the chat open with the explanation

Take it on the iPad, not in Chrome — the Pencil strokes look like a person's.

## Why it should interest an engineer who clicks through
- One HTML file, no build step, no framework.
- A provider layer: Gemini, Claude, OpenAI or a local Ollama behind one call shape.
- Prompts live in one file read by the Worker, the dev server *and* the browser,
  so they cannot drift.
- Retrieval over the student's own textbook, cited back.
- The read-back step: the tutor never corrects a reading it flagged as doubtful
  without asking first — because on day one, two of three readers misread the
  same handwritten fraction.
