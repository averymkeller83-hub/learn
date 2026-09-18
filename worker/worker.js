/*  Showwork — the Cloudflare Worker. The dev server (../server.py), ported.

    THE WHOLE PROGRAM IN THREE STEPS:
      1. GET  /            -> hand over the board (index.html, bundled in).
      2. POST /transcribe  -> "what does this say?"      -> the words back.
      3. POST /check       -> "where is the FIRST mistake?" -> one verdict back.

    The key is a Worker secret (wrangler secret put GEMINI_API_KEY). It is
    never in this file and never reaches the browser.

    Not here yet: the per-visitor check cap. That needs D1 or KV to count
    across requests, and it is weekend two. Until then, when Gemini says the
    daily quota is gone we say so plainly instead of failing quietly.        */

import html    from "../index.html";   // the board, as text — one copy, no assets dir
import prompts from "../prompts.json"; // the two prompts — same file server.py reads

// ============================================================
// THE BRAIN — the swappable seam. Change the model here, nowhere else.
// ============================================================
const MODEL   = "gemini-3.5-flash";
const ASK_URL = `https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent`;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // ---- the board. GET serves index.html and NOTHING else. ----
    if (request.method === "GET") {
      if (url.pathname === "/" || url.pathname === "/index.html") {
        return new Response(html, { headers: { "Content-Type": "text/html; charset=utf-8" } });
      }
      return json(404, { error: "not_found" });
    }

    if (request.method !== "POST" || !["/transcribe", "/check"].includes(url.pathname)) {
      return json(404, { error: "no such endpoint" });
    }

    // ---- the guard rail: no key, no calls, and SAY so ----
    if (!env.GEMINI_API_KEY) {
      return json(503, { error: "no_key", message: "GEMINI_API_KEY is not set on the server." });
    }

    // ---- read {"image": "data:image/png;base64,...", "work"?: "..."} ----
    let data;
    try { data = await request.json(); } catch { return json(400, { error: "bad_request", message: "not JSON" }); }
    const b64 = (data.image || "").split(",", 2)[1];
    if (!b64) return json(400, { error: "bad_request", message: "no image" });

    try {
      // ============================================
      // /transcribe — "what does this say?"
      // ============================================
      if (url.pathname === "/transcribe") {
        const text = await askVision(env, prompts.transcribe, b64);
        return json(200, { transcription: text.trim(), checks_left: null });
      }

      // ============================================
      // /check — "where is the FIRST mistake?"
      // The confirmed reading goes in; we trust it over
      // the model's own second look at the picture.
      // ============================================
      const work = (data.work || "").trim();
      if (!work) return json(400, { error: "no_work", message: "Confirm the transcription first." });

      const raw = await askVision(env, prompts.check.replace("{work}", work), b64);

      // asked for JSON; if it obliged pass it through, if it rambled hand the ramble over
      let verdict;
      try { verdict = JSON.parse(stripFence(raw)); }
      catch { verdict = { line: "", problem: raw.trim(), nudge: "", all_correct: false }; }
      verdict.checks_left = null;
      return json(200, verdict);

    } catch (e) {
      // Gemini's own 429 = the shared daily quota is gone. Say it out loud.
      if (e.status === 429) return json(429, { error: "out_of_checks",
        message: "Out of checks for today. The board still works." });
      return json(502, { error: "model_error", message: String(e.message).slice(0, 300) });
    }
  },
};

// ============================================================
// askVision — the phone line to the brain, with a picture attached.
// IN: env (for the key), a prompt, the PNG as base64.  OUT: words.
// ============================================================
async function askVision(env, prompt, b64) {
  const res = await fetch(ASK_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json", "x-goog-api-key": env.GEMINI_API_KEY },
    body: JSON.stringify({ contents: [{ parts: [
      { text: prompt },
      { inline_data: { mime_type: "image/png", data: b64 } },
    ]}]}),
  });
  if (!res.ok) {
    const err = new Error(`Gemini ${res.status}: ${(await res.text()).slice(0, 200)}`);
    err.status = res.status;
    throw err;
  }
  const answer = await res.json();
  return answer.candidates[0].content.parts[0].text;   // dig the words out of the nesting
}

// the model likes to wrap JSON in ```json fences — take them off
function stripFence(text) {
  let t = text.trim();
  if (t.startsWith("```")) {
    t = t.includes("\n") ? t.slice(t.indexOf("\n") + 1) : t;
    t = t.slice(0, t.lastIndexOf("```"));
  }
  return t.trim();
}

// every answer leaves through here, so the headers are written once
function json(status, payload) {
  return new Response(JSON.stringify(payload), {
    status, headers: { "Content-Type": "application/json" } });
}
