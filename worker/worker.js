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
import manifest from "../app/manifest.webmanifest";   // installable app: manifest, worker, icons
import sw       from "../app/sw.js";
import icon192  from "../app/icon-192.png";
import icon512  from "../app/icon-512.png";

// ============================================================
// THE BRAIN — the swappable seam. Change the model here, nowhere else.
// ============================================================
const MODEL   = "gemini-3.5-flash-lite";  // 2026-09-17: ~10x faster than flash here, passed both check tests
const ASK_URL = `https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent`;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // ---- the board. GET serves index.html and NOTHING else. ----
    if (request.method === "GET") {
      if (url.pathname === "/" || url.pathname === "/index.html") {
        return new Response(html, { headers: { "Content-Type": "text/html; charset=utf-8" } });
      }
      if (url.pathname === "/prompts.json") {     // the browser needs them for bring-your-own-key
        return new Response(JSON.stringify(prompts), { headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
      }
      if (url.pathname === "/fetch") return fetchPage(url.searchParams.get("url") || "");
      if (url.pathname === "/manifest.webmanifest") return new Response(manifest, { headers: { "Content-Type": "application/manifest+json" } });
      if (url.pathname === "/sw.js") return new Response(sw, { headers: { "Content-Type": "application/javascript", "Cache-Control": "no-cache" } });
      if (url.pathname === "/icon-192.png") return new Response(icon192, { headers: { "Content-Type": "image/png", "Cache-Control": "public, max-age=86400" } });
      if (url.pathname === "/icon-512.png") return new Response(icon512, { headers: { "Content-Type": "image/png", "Cache-Control": "public, max-age=86400" } });
      return json(404, { error: "not_found" });
    }

    if (request.method !== "POST" || !["/transcribe", "/check", "/chat"].includes(url.pathname)) {
      return json(404, { error: "no such endpoint" });
    }

    // ---- the guard rail: no key, no calls, and SAY so ----
    if (!env.GEMINI_API_KEY) {
      return json(503, { error: "no_key", message: "GEMINI_API_KEY is not set on the server." });
    }

    // ---- the shared key's daily allowance. Students who bring their own key
    // ---- never get here, so they are never capped. ----
    const quota = await spend(env, request);
    if (quota && quota.over) {
      return json(429, { error: "out_of_checks", checks_left: 0, message:
        `That's ${DAILY_FREE} free checks today on Showwork's shared key. Add your own free Gemini key in Settings (⚙) ` +
        `for unlimited use - it takes one tap at aistudio.google.com/apikey - or come back tomorrow. The board still works.` });
    }
    const left = quota ? quota.left : null;

    // ---- read {"image": "data:image/png;base64,...", "work"?: "..."} ----
    let data;
    try { data = await request.json(); } catch { return json(400, { error: "bad_request", message: "not JSON" }); }
    // the picture is required for transcribe/check, optional for chat
    const [head, b64] = (data.image || "").split(",", 2);   // "data:image/jpeg;base64"
    if (!b64 && url.pathname !== "/chat") return json(400, { error: "bad_request", message: "no image" });
    const mime = b64 ? (head.slice(5).split(";")[0] || "image/png") : "image/png";

    // what the student says they're working on — goes in FRONT of either prompt
    const ctx  = String(data.context || "").trim().slice(0, 300);
    let note = ctx ? prompts.context_note.replace("{context}", ctx) : "";
    // excerpts from the student's own textbooks, picked by the browser
    const src = String(data.sources || "").trim().slice(0, 9000);
    if (src) note += prompts.sources_note.replace("{sources}", src);
    // the calculator setting: may the tutor do the numbers, or must the student?
    if (data.calc === "on" || data.calc === "off") note += prompts[data.calc === "on" ? "calc_on_note" : "calc_off_note"];
    // the subject persona: teach like someone who does this work
    const subj = (prompts.subjects || {})[String(data.subject || "")];
    if (subj) note += prompts.subject_note.replace("{subject}", subj.prompt);

    // who the learner is: their level, and what the tutor has learned about them
    if (String(data.level || "").trim()) note += prompts.level_note.replace("{level}", String(data.level).trim().slice(0, 40));
    if (String(data.learner || "").trim()) note += prompts.learner_note.replace("{learner}", String(data.learner).trim().slice(0, 3000));

    try {
      // ============================================
      // /chat — the tutor, looking at the page. Asks for
      // JSON {say, board}; a ramble becomes what it says.
      // ============================================
      if (url.pathname === "/chat") {
        const msgs = (Array.isArray(data.messages) ? data.messages : []).slice(-16);
        if (!msgs.length) return json(400, { error: "no_message", message: "Say something first." });
        const raw = await askGemini(env, chatBody(note + prompts.chat, msgs, b64, mime));
        let say = raw.trim(), board = "", remember = "";
        const out = looseJson(raw);
        if (out) { say = String(out.say || ""); board = out.board ?? ""; remember = String(out.remember || "").slice(0, 200); }
        return json(200, { say, board, remember, checks_left: left });
      }

      // ============================================
      // /transcribe — "what does this say?"
      // ============================================
      if (url.pathname === "/transcribe") {
        const text = await askVision(env, note + prompts.transcribe, b64, mime);
        return json(200, { transcription: text.trim(), checks_left: left });
      }

      // ============================================
      // /check — "where is the FIRST mistake?"
      // The confirmed reading goes in; we trust it over
      // the model's own second look at the picture.
      // ============================================
      const work = (data.work || "").trim();
      if (!work) return json(400, { error: "no_work", message: "Confirm the transcription first." });

      // an exam page asks to be GRADED whole, not checked for one error
      const prompt = data.mode === "grade"
        ? prompts.grade.replace("{work}", work).replace(/\{n\}/g, String(parseInt(data.n) || 5))
        : prompts.check.replace("{work}", work);
      const raw = await askVision(env, note + prompt, b64, mime, true);

      // asked for JSON; if it obliged pass it through, if it rambled hand the ramble over
      let verdict = looseJson(raw);
      if (!verdict) verdict = { line: "", problem: raw.trim(), nudge: "", all_correct: false };
      verdict.checks_left = left;
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
// Gemini's JSON mode: the answer IS valid JSON - no fences, no bracket slips.
// Used wherever we parse the reply (check, grade, chat). Not transcribe.
const JSON_MODE = { response_mime_type: "application/json" };

async function askVision(env, prompt, b64, mime = "image/png", wantJson = false) {
  const body = { contents: [{ parts: [
    { text: prompt },
    { inline_data: { mime_type: mime, data: b64 } },
  ]}]};
  if (wantJson) body.generationConfig = JSON_MODE;
  return askGemini(env, body);
}

// a conversation: alternating user/model turns, the page's picture on the
// LAST turn, the tutor's standing instructions as system_instruction
function chatBody(system, messages, b64, mime) {
  const contents = messages.slice(0, -1).map(m => ({
    role: m.role === "model" ? "model" : "user", parts: [{ text: String(m.text || "") }] }));
  const last = messages[messages.length - 1] || { text: "" };
  const parts = [{ text: String(last.text || "") }];
  if (b64) parts.push({ inline_data: { mime_type: mime, data: b64 } });
  contents.push({ role: "user", parts });
  return { system_instruction: { parts: [{ text: system }] }, contents, generationConfig: JSON_MODE };
}

// ============================================================
// THE DAILY ALLOWANCE — how many calls one visitor may make on the
// SHARED key. A visitor is a hash of IP + user agent + a salt: enough
// to tell people apart, never enough to identify anyone, and it needs
// no accounts. If D1 isn't bound (local dev), there is no cap.
// ============================================================
const DAILY_FREE = 15;

async function spend(env, request) {
  if (!env.DB) return null;                       // no database bound: don't cap
  try {
    const who = await visitorHash(request);
    const day = new Date().toISOString().slice(0, 10);
    // count first, then decide: one statement, so two quick taps can't both slip through
    await env.DB.prepare(
      "INSERT INTO checks (day, who, n) VALUES (?1, ?2, 1) " +
      "ON CONFLICT(day, who) DO UPDATE SET n = n + 1").bind(day, who).run();
    const row = await env.DB.prepare("SELECT n FROM checks WHERE day = ?1 AND who = ?2").bind(day, who).first();
    const used = row ? row.n : 1;
    return { over: used > DAILY_FREE, left: Math.max(0, DAILY_FREE - used) };
  } catch (e) {
    console.warn("quota unavailable", e);         // never let the counter break the tutor
    return null;
  }
}

async function visitorHash(request) {
  const ip = request.headers.get("CF-Connecting-IP") || "";
  const ua = request.headers.get("User-Agent") || "";
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(ip + "|" + ua + "|showwork"));
  return [...new Uint8Array(buf)].slice(0, 16).map(b => b.toString(16).padStart(2, "0")).join("");
}

// a linked web page as readable text: the browser can't read other sites
// (CORS), so we do. http(s) only, no private hosts, capped, tags stripped.
async function fetchPage(target) {
  let t;
  try { t = new URL(target); } catch { return json(400, { error: "bad_url", message: "That is not a link." }); }
  const host = t.hostname.toLowerCase();
  if (!/^https?:$/.test(t.protocol) || host === "localhost" || /^(127\.|10\.|192\.168\.|169\.254\.|0\.)/.test(host) || host.endsWith(".local"))
    return json(400, { error: "bad_url", message: "Only public http(s) links can be added." });
  let raw;
  try {
    const res = await fetch(t.href, { headers: { "User-Agent": "Mozilla/5.0 (Showwork source fetch)" }, redirect: "follow" });
    if (!res.ok) return json(502, { error: "fetch_failed", message: `That page answered ${res.status}.` });
    raw = (await res.text()).slice(0, 1_500_000);
  } catch (e) { return json(502, { error: "fetch_failed", message: String(e.message).slice(0, 200) }); }
  const title = (raw.match(/<title[^>]*>([\s\S]*?)<\/title>/i) || [])[1];
  let text = raw.replace(/<(script|style|noscript)[^>]*>[\s\S]*?<\/\1>/gi, " ").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
  const unesc = s => s.replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&nbsp;/g, " ");
  return json(200, { title: title ? unesc(title.trim()) : target, text: unesc(text).slice(0, 400_000) });
}

// the one place that actually talks to Gemini
async function askGemini(env, body) {
  const res = await fetch(ASK_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json", "x-goog-api-key": env.GEMINI_API_KEY },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = new Error(`Gemini ${res.status}: ${(await res.text()).slice(0, 200)}`);
    err.status = res.status;
    throw err;
  }
  const answer = await res.json();
  return answer.candidates[0].content.parts[0].text;   // dig the words out of the nesting
}

// the model's JSON, read the way a person would: strict parse, then the
// widest {...} in the text, then null. Raw JSON must never reach the student.
// ---- a lone backslash (the model writing \frac despite the rules) breaks JSON.parse;
//      make every illegal escape a literal backslash before parsing ----
function repairEscapes(t) {

  let out = '';

  for (let i = 0; i < t.length; i++) {
    const ch = t[i];

    /* ordinary character: copy it */
    if (ch !== '\\') { out += ch; continue; }

    const rest = t.slice(i + 1), next = rest[0] || '';

    /* an escaped backslash: keep the pair, skip its partner */
    if (next === '\\') { out += '\\\\'; i++; continue; }

    /* a real JSON escape (\n, \", \uXXXX ...) - unless it is the start of a LaTeX word like \frac or \neq */
    const legal = '"/bfnrtu'.includes(next);
    const latexWord = /^[a-zA-Z]{2,}/.test(rest) && !/^u[0-9a-fA-F]{4}/.test(rest);
    if (legal && !latexWord) { out += '\\'; continue; }

    /* anything else: the model meant a literal backslash */
    out += '\\\\';
  }

  return out;
}

function looseJson(text) {
  const t = repairEscapes(stripFence(text));
  try { return JSON.parse(t); } catch {}
  const a = t.indexOf("{"), b = t.lastIndexOf("}");
  if (a >= 0 && b > a) for (let end = b; end > a; end = t.lastIndexOf("}", end - 1)) {
    try { return JSON.parse(t.slice(a, end + 1)); } catch {}
  }
  return null;
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
