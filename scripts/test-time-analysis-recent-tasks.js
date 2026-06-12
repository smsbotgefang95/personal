#!/usr/bin/env node

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const repoRoot = path.resolve(__dirname, "..");
const html = fs.readFileSync(path.join(repoRoot, "time-analysis.html"), "utf8");

function extractFunction(source, name) {
  const start = source.indexOf(`function ${name}(`);
  if (start === -1) throw new Error(`Could not find function ${name}`);
  const bodyStart = source.indexOf("{", start);
  let depth = 0;
  for (let index = bodyStart; index < source.length; index += 1) {
    if (source[index] === "{") depth += 1;
    if (source[index] === "}") depth -= 1;
    if (depth === 0) return source.slice(start, index + 1);
  }
  throw new Error(`Could not parse function ${name}`);
}

const sandbox = {
  DEFAULT_RECENT_TASK_EXCLUDED_NAMES: new Set(),
  cleanLabel(value, fallback = "") {
    const text = value == null ? "" : String(value).trim();
    return text || fallback;
  },
  rawHiddenRecentTaskKeys() {
    return [];
  },
  hiddenRecentTaskRecordKey() {
    return "";
  },
  hiddenRecentTaskRecordHiddenAt() {
    return 0;
  },
  isRecentTaskHidden() {
    return false;
  }
};

vm.createContext(sandbox);
vm.runInContext([
  extractFunction(html, "recentTaskKey"),
  extractFunction(html, "recentTaskDateMs"),
  extractFunction(html, "recentTaskCompletedMs"),
  extractFunction(html, "compareRecentTasksByRecency"),
  extractFunction(html, "normalizedRecentTaskName"),
  extractFunction(html, "isDefaultRecentTaskExcluded"),
  extractFunction(html, "recentTrackedTasks")
].join("\n\n"), sandbox);

function entry(taskName, stop, overrides = {}) {
  return {
    listId: "list-main",
    listName: "Main",
    taskId: taskName.toLowerCase().replace(/\s+/g, "-"),
    taskName,
    start: "2026-06-01T08:00:00.000Z",
    stop,
    ...overrides
  };
}

const newestFirst = sandbox.recentTrackedTasks([
  entry("Oldest", "2026-06-01T09:00:00.000Z"),
  entry("Newest", "2026-06-03T09:00:00.000Z"),
  entry("Middle", "2026-06-02T09:00:00.000Z")
]);
assert.deepStrictEqual(
  Array.from(newestFirst, (item) => item.taskName),
  ["Newest", "Middle", "Oldest"],
  "recent tasks should render newest completion on the left"
);

const duplicateNewestWins = sandbox.recentTrackedTasks([
  entry("Duplicate", "2026-06-01T09:00:00.000Z", { taskId: "same-task" }),
  entry("Other", "2026-06-02T09:00:00.000Z"),
  entry("Duplicate", "2026-06-03T09:00:00.000Z", { taskId: "same-task" })
]);
assert.deepStrictEqual(
  Array.from(duplicateNewestWins, (item) => `${item.taskName}:${item.stop}`),
  [
    "Duplicate:2026-06-03T09:00:00.000Z",
    "Other:2026-06-02T09:00:00.000Z"
  ],
  "deduped recent tasks should keep the newest completion for a task key"
);

const tiedTasks = sandbox.recentTrackedTasks([
  entry("Bravo", ""),
  entry("Alpha", "")
]);
assert.deepStrictEqual(
  Array.from(tiedTasks, (item) => item.taskName),
  ["Alpha", "Bravo"],
  "recent task order should be deterministic when timestamps tie"
);

console.log("Recent task ordering checks passed.");
