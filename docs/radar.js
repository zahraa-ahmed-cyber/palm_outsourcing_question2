/**
 * Same rules as radar/names.py + radar/pipeline.py.
 * Runs in the browser so an account lead never opens a terminal.
 */

const STRIP_TOKENS = new Set([
  "inc", "incorporated", "llc", "ltd", "limited", "co", "company",
  "corp", "corporation", "plc", "lp", "pllc", "pc",
]);
const STRIP_LEADING = new Set(["the"]);
const CONFIRMED = 100;
const REVIEW_FLOOR = 72;
const WINDOW_DAYS = 45;

function normalizeName(name) {
  if (!name) return "";
  let s = name.toLowerCase().replaceAll("&", " and ");
  s = s.replace(/[^a-z0-9]+/g, " ").trim();
  const tokens = s.split(/\s+/).filter(Boolean);
  while (tokens.length && STRIP_LEADING.has(tokens[0])) tokens.shift();
  while (tokens.length && STRIP_TOKENS.has(tokens[tokens.length - 1])) tokens.pop();
  return tokens.join(" ");
}

function compact(name) {
  return normalizeName(name).replaceAll(" ", "");
}

function findLongestMatch(a, b, alo, ahi, blo, bhi) {
  const idx = {};
  for (let i = blo; i < bhi; i++) {
    (idx[b[i]] ||= []).push(i);
  }
  let besti = alo;
  let bestj = blo;
  let bestsize = 0;
  let j2len = {};
  for (let i = alo; i < ahi; i++) {
    const newj2len = {};
    for (const j of idx[a[i]] || []) {
      const k = (j2len[j - 1] || 0) + 1;
      newj2len[j] = k;
      if (k > bestsize) {
        besti = i - k + 1;
        bestj = j - k + 1;
        bestsize = k;
      }
    }
    j2len = newj2len;
  }
  return [besti, bestj, bestsize];
}

function sequenceRatio(a, b) {
  if (!a && !b) return 100;
  if (!a || !b) return 0;
  let matches = 0;
  const queue = [[0, a.length, 0, b.length]];
  while (queue.length) {
    const [alo, ahi, blo, bhi] = queue.pop();
    const [i, j, k] = findLongestMatch(a, b, alo, ahi, blo, bhi);
    if (k) {
      matches += k;
      if (alo < i && blo < j) queue.push([alo, i, blo, j]);
      if (i + k < ahi && j + k < bhi) queue.push([i + k, ahi, j + k, bhi]);
    }
  }
  return Math.round((2 * matches) / (a.length + b.length) * 100);
}

function nameScore(left, right) {
  const na = normalizeName(left);
  const nb = normalizeName(right);
  if (!na || !nb) return [0, "empty name"];
  if (na === nb) {
    return [100, "same after normalising case, punctuation and legal suffix"];
  }
  const ca = na.replaceAll(" ", "");
  const cb = nb.replaceAll(" ", "");
  if (ca === cb) return [96, "same letters once spaces are ignored"];
  const [shorter, longer] = na.length <= nb.length ? [na, nb] : [nb, na];
  if (shorter.length >= 8 && longer.startsWith(shorter + " ")) {
    const extra = longer.slice(shorter.length).trim();
    if (extra && !STRIP_TOKENS.has(extra)) {
      return [90, `one name is the other plus '${extra}'`];
    }
  }
  const seq = sequenceRatio(na, nb);
  const tokenSort = sequenceRatio(
    na.split(" ").sort().join(" "),
    nb.split(" ").sort().join(" ")
  );
  const compactR = sequenceRatio(ca, cb);
  return [Math.max(seq, tokenSort, compactR), "fuzzy (sequence / token-sort / compact)"];
}

function classifyScore(score) {
  if (score >= CONFIRMED) return "matched";
  if (score >= REVIEW_FLOOR) return "review";
  return "unmatched";
}

function parseDate(value) {
  const v = (value || "").trim();
  return v ? v : null;
}

function addMonths(iso, months) {
  if (!iso) return null;
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1 + months, 1));
  const last = new Date(Date.UTC(dt.getUTCFullYear(), dt.getUTCMonth() + 1, 0)).getUTCDate();
  const day = Math.min(d, last);
  const mm = String(dt.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(day).padStart(2, "0");
  return `${dt.getUTCFullYear()}-${mm}-${dd}`;
}

function daysBetween(fromIso, toIso) {
  const a = Date.parse(fromIso + "T00:00:00Z");
  const b = Date.parse(toIso + "T00:00:00Z");
  return Math.round((b - a) / 86400000);
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = "";
  let i = 0;
  let inQuotes = false;
  const src = text.replace(/^\uFEFF/, "");
  while (i < src.length) {
    const ch = src[i];
    if (inQuotes) {
      if (ch === '"') {
        if (src[i + 1] === '"') {
          cell += '"';
          i += 2;
          continue;
        }
        inQuotes = false;
        i += 1;
        continue;
      }
      cell += ch;
      i += 1;
      continue;
    }
    if (ch === '"') {
      inQuotes = true;
      i += 1;
      continue;
    }
    if (ch === ",") {
      row.push(cell);
      cell = "";
      i += 1;
      continue;
    }
    if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && src[i + 1] === "\n") i += 1;
      row.push(cell);
      if (row.some((c) => c !== "")) rows.push(row);
      row = [];
      cell = "";
      i += 1;
      continue;
    }
    cell += ch;
    i += 1;
  }
  if (cell !== "" || row.length) {
    row.push(cell);
    if (row.some((c) => c !== "")) rows.push(row);
  }
  if (!rows.length) return [];
  const headers = rows[0].map((h) => h.trim());
  return rows.slice(1).map((vals) => {
    const obj = {};
    headers.forEach((h, idx) => {
      obj[h] = (vals[idx] || "").trim();
    });
    return obj;
  });
}

function loadBilling(rows) {
  return rows.map((raw) => ({
    client_name: (raw.client_name || "").trim(),
    retainer_start: parseDate(raw.retainer_start),
    retainer_end: parseDate(raw.retainer_end),
    monthly_retainer_usd: parseInt(raw.monthly_retainer_usd, 10) || 0,
    package: (raw.package || "").trim(),
    account_lead: (raw.account_lead || "").trim(),
    billing_contact: (raw.billing_contact || "").trim(),
  }));
}

function loadProjects(rows) {
  return rows.map((raw) => ({
    brand_name: (raw.brand_name || "").trim(),
    current_scope: (raw.current_scope || "").trim(),
    last_delivery: parseDate(raw.last_delivery),
    deliveries_this_term: parseInt(raw.deliveries_this_term, 10) || 0,
    health: (raw.health || "").trim(),
    account_lead: (raw.account_lead || "").trim(),
    notes: (raw.notes || "").trim(),
  }));
}

function collapseResigns(billing) {
  const groups = new Map();
  for (const row of billing) {
    const key = normalizeName(row.client_name) || compact(row.client_name);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(row);
  }
  const current = [];
  const superseded = [];
  for (const [key, rows] of groups) {
    const ordered = [...rows].sort((a, b) =>
      (b.retainer_start || "").localeCompare(a.retainer_start || "")
    );
    const winner = { ...ordered[0], normalized: key };
    winner.prior_terms = ordered.slice(1).map((r) => ({
      start: r.retainer_start,
      end: r.retainer_end,
      monthly_retainer_usd: r.monthly_retainer_usd,
    }));
    current.push(winner);
    for (const r of ordered.slice(1)) {
      superseded.push({
        ...r,
        normalized: key,
        superseded_by_start: winner.retainer_start,
      });
    }
  }
  return [current, superseded];
}

function pairProjects(current, projects) {
  const scored = [];
  current.forEach((b, bi) => {
    projects.forEach((p, pi) => {
      const [score, why] = nameScore(b.client_name, p.brand_name);
      scored.push([score, bi, pi, why]);
    });
  });
  scored.sort((a, b) => b[0] - a[0]);
  const usedB = new Set();
  const usedP = new Set();
  const attached = {};
  const possible = {};
  const reviews = [];
  for (const [score, bi, pi, why] of scored) {
    const kind = classifyScore(score);
    if (kind === "unmatched") continue;
    if (usedB.has(bi) || usedP.has(pi)) continue;
    usedB.add(bi);
    usedP.add(pi);
    if (kind === "review") {
      possible[bi] = [pi, score, why];
      reviews.push({
        billing_name: current[bi].client_name,
        project_name: projects[pi].brand_name,
        score,
        why,
      });
      continue;
    }
    attached[bi] = [pi, score, why];
  }
  const unmatchedBilling = current
    .map((r, i) => (usedB.has(i) ? null : r.client_name))
    .filter(Boolean);
  const unmatchedProjects = projects
    .map((r, i) => (usedP.has(i) ? null : r.brand_name))
    .filter(Boolean);
  return [attached, possible, reviews, unmatchedBilling, unmatchedProjects];
}

function bucket(end, asOf) {
  if (!end) return "no_date";
  const windowEnd = addDays(asOf, WINDOW_DAYS);
  if (end < asOf) return "lapsed";
  if (end <= windowEnd) return "upcoming";
  return "later";
}

function addDays(iso, n) {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d + n));
  const mm = String(dt.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(dt.getUTCDate()).padStart(2, "0");
  return `${dt.getUTCFullYear()}-${mm}-${dd}`;
}

function runRadar(billing, projects, asOf) {
  const [current, superseded] = collapseResigns(billing);
  const [attached, possible, reviews, unmatchedB, unmatchedP] = pairProjects(
    current,
    projects
  );
  const records = [];
  const missingEnd = [];
  current.forEach((b, bi) => {
    let inferred = false;
    let end = b.retainer_end;
    if (!end) {
      end = addMonths(b.retainer_start, 3);
      inferred = true;
      missingEnd.push(b.client_name);
    }
    let project = null;
    let score = null;
    let why = null;
    let matchKind = "unmatched";
    let possibleMatch = null;
    if (attached[bi]) {
      const [pi, sc, w] = attached[bi];
      project = projects[pi];
      score = sc;
      why = w;
      matchKind = "matched";
    } else if (possible[bi]) {
      const [pi, sc, w] = possible[bi];
      const cand = projects[pi];
      score = sc;
      why = w;
      matchKind = "review";
      possibleMatch = {
        project_name: cand.brand_name,
        score: sc,
        why: w,
        scope: cand.current_scope,
        last_delivery: cand.last_delivery,
        notes: cand.notes,
        health: cand.health,
        account_lead: cand.account_lead,
      };
    }
    const status = bucket(end, asOf);
    const days = end ? daysBetween(asOf, end) : null;
    records.push({
      display_name: project ? project.brand_name : b.client_name,
      billing_name: b.client_name,
      project_name: project ? project.brand_name : null,
      match_score: score,
      match_why: why,
      match_kind: matchKind,
      possible_match: possibleMatch,
      start: b.retainer_start,
      end,
      end_inferred: inferred,
      days,
      status,
      monthly_retainer_usd: b.monthly_retainer_usd,
      package: b.package,
      account_lead: project ? project.account_lead : b.account_lead,
      scope: project ? project.current_scope : null,
      last_delivery: project ? project.last_delivery : null,
      deliveries_this_term: project ? project.deliveries_this_term : null,
      health: project ? project.health : null,
      notes: project ? project.notes : null,
      prior_terms: b.prior_terms || [],
      billing_contact: b.billing_contact,
    });
  });
  const sortKey = (r) => (r.days === null ? 10000 : r.days);
  const upcoming = records.filter((r) => r.status === "upcoming").sort((a, b) => sortKey(a) - sortKey(b));
  const lapsed = records.filter((r) => r.status === "lapsed").sort((a, b) => sortKey(a) - sortKey(b));
  const later = records.filter((r) => r.status === "later").sort((a, b) => sortKey(a) - sortKey(b));
  const recentLapsed = lapsed.filter((r) => r.days !== null && r.days >= -60);
  return {
    as_of: asOf,
    window_days: WINDOW_DAYS,
    window_end: addDays(asOf, WINDOW_DAYS),
    upcoming,
    lapsed: recentLapsed,
    later,
    records,
    needs_review: reviews,
    unmatched_billing: unmatchedB,
    unmatched_projects: unmatchedP,
    superseded: superseded.map((r) => ({
      client_name: r.client_name,
      start: r.retainer_start,
      end: r.retainer_end,
      superseded_by_start: r.superseded_by_start,
    })),
    missing_end_dates: missingEnd,
    counts: {
      billing_rows: billing.length,
      project_rows: projects.length,
      current_retainers: current.length,
      upcoming: upcoming.length,
      lapsed: recentLapsed.length,
      later: later.length,
    },
  };
}

window.RelayRadar = {
  parseCsv,
  loadBilling,
  loadProjects,
  runRadar,
  WINDOW_DAYS,
};
