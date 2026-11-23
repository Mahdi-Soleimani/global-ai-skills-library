#!/usr/bin/env node
"use strict";
// Dependency-free browser-DOM simulation for GASL Explorer's main user path.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

class Element {
  constructor(tag = "div", id = null) {
    this.tag = tag;
    this.id = id;
    this.children = [];
    this.listeners = {};
    this.style = {};
    this.value = "";
    this.textContent = "";
    this.disabled = false;
    this.hidden = false;
    this.checked = false;
    this.className = "";
    this.attributes = {};
  }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = [...nodes]; }
  setAttribute(key, value) { this.attributes[key] = value; }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  scrollIntoView() {}
}
function descendants(root, predicate) {
  const found = [];
  for (const child of root.children) {
    if (typeof child === "object") {
      if (predicate(child)) found.push(child);
      found.push(...descendants(child, predicate));
    }
  }
  return found;
}
const ids = [
  "query", "recommendButton", "searchButton", "results", "count",
  "recommendationNotice", "comparePanel", "compareButton", "compareBody",
  "compareStatus", "selectionPanel", "selectionBody", "detail", "detailBody",
  "detailTitle", "closeDetail", "searchForm", "apiToken", "engineStatus",
  "domain", "agent", "limit", "publicOnly", "contentOnly"
];
const nodes = Object.fromEntries(ids.map(id => [id, new Element("div", id)]));
nodes.query.value = "security audit api";
nodes.limit.value = "10";
nodes.agent.value = "codex";
nodes.domain.value = "";
nodes.publicOnly.checked = false;
nodes.contentOnly.checked = false;
nodes.comparePanel.hidden = true;
nodes.selectionPanel.hidden = true;
const calls = [];
const candidates = [
  {
    source_record_id: "GASL-SRC-a1", skill_name: "API audit",
    description: "Review Python APIs for vulnerabilities",
    repository: "example/audit", license_spdx: "MIT",
    security_status: "not_scanned",
    source_url: "https://github.com/example/audit",
    relevance_score: 5.5, inferred_domains: []
  },
  {
    source_record_id: "GASL-SRC-b2", skill_name: "API defense",
    description: "Inspect API authentication flows",
    repository: "example/defense", license_spdx: "Apache-2.0",
    security_status: "manual_review_required",
    source_url: "javascript:alert(1)",
    relevance_score: 4.5, inferred_domains: []
  },
  {
    source_record_id: "GASL-SRC-c3", skill_name: "Other security",
    description: "Review cloud security",
    repository: "example/other", license_spdx: null,
    security_status: "not_scanned",
    source_url: null, relevance_score: 2.1, inferred_domains: []
  }
];
const fetchMock = async (url, options = {}) => {
  calls.push({ url, method: options.method || "GET" });
  let data;
  if (url === "/health") {
    data = { source_record_count: 4431, semantic_search_enabled: false };
  } else if (url === "/v1/domains") {
    data = { domains: [] };
  } else if (url === "/v1/route") {
    assert.equal(options.method, "POST");
    const body = JSON.parse(options.body);
    assert.equal(body.task, "security audit api");
    assert.equal(body.agent, "codex");
    data = { results: candidates, returned_count: 3, routing_decision: "undetermined" };
  } else if (url.startsWith("/v1/search?")) {
    data = { results: candidates, count: 3, search_mode: "lexical" };
  } else if (url === "/v1/compare") {
    assert.equal(options.method, "POST");
    const body = JSON.parse(options.body);
    assert.deepEqual(body.ids, ["GASL-SRC-a1", "GASL-SRC-b2"]);
    data = {
      count: 2, source_record_ids: body.ids,
      different_fields: ["license_spdx", "security_status", "repository"],
      items: candidates.slice(0, 2).map(item => ({
        ...item, source_path: "skills/SKILL.md", content_status: "not_scanned",
        license_assessment: "unknown", compatibility: "codex",
        commit_sha: "a".repeat(40)
      })),
      note: "No quality winner."
    };
  } else {
    throw Error("Unexpected network request: " + url);
  }
  return { ok: true, status: 200, json: async () => data };
};
const doc = {
  getElementById: id => {
    assert(nodes[id], "Unexpected DOM ID: " + id);
    return nodes[id];
  },
  createElement: tag => new Element(tag),
};
const raw = fs.readFileSync(path.join(__dirname, "..", "web", "index.html"), "utf8");
const source = raw.split("<script>")[1].split("</script>")[0];
const context = { document: doc, fetch: fetchMock, navigator: { clipboard: { writeText: async () => {} } },
                  URL, URLSearchParams, console };
vm.runInNewContext(source, context, { filename: "explorer-inline.js" });

(async () => {
  await nodes.recommendButton.listeners.click();
  assert.match(nodes.recommendationNotice.textContent, /قطعی نیست/);
  const direct = descendants(nodes.results, n => n.tag === "button" &&
    n.textContent === "انتخاب برای بررسی");
  assert.equal(direct.length, 3);
  direct[0].listeners.click();
  assert.equal(nodes.selectionPanel.hidden, false);
  assert.match(descendants(nodes.selectionBody, n => n.tag === "code")[0].textContent,
    /install-plan --id GASL-SRC-a1/);

  const boxes = descendants(nodes.results, n => n.tag === "input" && n.type === "checkbox");
  assert.equal(boxes.length, 3);
  boxes[0].checked = true;
  boxes[0].listeners.change();
  boxes[1].checked = true;
  boxes[1].listeners.change();
  assert.equal(nodes.comparePanel.hidden, false);
  assert.equal(nodes.compareButton.disabled, false);
  await nodes.compareButton.listeners.click();
  const table = descendants(nodes.compareBody, n => n.tag === "table");
  assert.equal(table.length, 1);
  const selections = descendants(nodes.compareBody, n => n.tag === "button" &&
    n.textContent === "بررسی این گزینه");
  assert.equal(selections.length, 2);
  selections[0].listeners.click();
  assert.equal(nodes.selectionPanel.hidden, false);
  const command = descendants(nodes.selectionBody, n => n.tag === "code")[0];
  assert.match(command.textContent, /install-plan --id GASL-SRC-a1 --agent codex --scope project/);
  const interactive = descendants(nodes.selectionBody, n => n.tag === "code")
    .find(n => n.textContent.includes("codex-install-wizard"));
  assert(interactive, "Selected Codex Skill must show exact terminal-only installation handoff");
  assert.match(interactive.textContent,
    /codex-install-wizard --id GASL-SRC-a1 --selected-root "\$GASL_SELECTED_PROJECT" --action install --download-if-missing/);
  assert(descendants(nodes.selectionBody, n => n.tag === "code")
    .some(n => n.textContent.includes("export GASL_SELECTED_PROJECT=")));
  for (const host of ["cursor", "claude-code"]) {
    nodes.agent.value = host;
    selections[0].listeners.click();
    const command = descendants(nodes.selectionBody, n => n.tag === "code")
      .find(n => n.textContent.includes("host-project-wizard"));
    assert(command, "Explorer must display the project-only local TTY wizard for " + host);
    assert(command.textContent.includes("--host " + host + " --id GASL-SRC-a1"));
    assert(command.textContent.includes("--selected-root \"$GASL_SELECTED_PROJECT\""));
    assert(command.textContent.includes("--action install --download-if-missing"));
  }
  for (const host of ["codex", "cursor", "claude-code"]) {
    nodes.agent.value = host;
    selections[0].listeners.click();
    const global = descendants(nodes.selectionBody, n => n.tag === "code")
      .find(n => n.textContent.includes("user-profile-wizard"));
    assert(global, "User-scope local TTY wizard must be visible for " + host);
    assert(global.textContent.includes("--host " + host + " --id GASL-SRC-a1"));
    assert(global.textContent.includes('--selected-home "$HOME"'));
    assert(global.textContent.includes("--action install --download-if-missing"));
    const explanation = descendants(nodes.selectionBody, n => n.tag === "p")
      .map(n => n.textContent).join(" ");
    assert(explanation.includes("User Profile"));
    if (host === "cursor") assert(explanation.includes("Cloud Agents"));
  }
  nodes.agent.value = "codex";
  assert.equal(calls.filter(c => c.url === "/v1/compare").length, 1);
  assert.equal(calls.filter(c => c.url.startsWith("/v1/install")).length, 0);
  assert.equal(descendants(nodes.results, n => n.tag === "a" && n.href?.startsWith("javascript:")).length, 0);

  // A new search must clear the previous selection and comparison.
  await nodes.searchForm.listeners.submit({ preventDefault() {} });
  assert.equal(nodes.compareButton.disabled, true);
  assert.equal(nodes.selectionPanel.hidden, true);
  assert.equal(nodes.compareBody.children.length, 0);
  assert.match(nodes.count.textContent, /جست‌وجو/);
  console.log("EXPLORER_NEED_COMPARE_SELECT_WORKFLOW=PASS");
})().catch(error => { console.error(error); process.exitCode = 1; });
