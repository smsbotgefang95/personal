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
  const paramsStart = source.indexOf("(", start);
  let paramsDepth = 0;
  let bodySearchStart = -1;
  for (let index = paramsStart; index < source.length; index += 1) {
    if (source[index] === "(") paramsDepth += 1;
    if (source[index] === ")") paramsDepth -= 1;
    if (paramsDepth === 0) {
      bodySearchStart = index + 1;
      break;
    }
  }
  const bodyStart = source.indexOf("{", bodySearchStart);
  let depth = 0;
  for (let index = bodyStart; index < source.length; index += 1) {
    if (source[index] === "{") depth += 1;
    if (source[index] === "}") depth -= 1;
    if (depth === 0) return source.slice(start, index + 1);
  }
  throw new Error(`Could not parse function ${name}`);
}

function extractConst(source, name) {
  const match = source.match(new RegExp(`const ${name} = .*?;`));
  if (!match) throw new Error(`Could not find const ${name}`);
  return match[0];
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

const catalogOrderFallback = sandbox.recentTrackedTasks([
  entry("Later catalog item", "", { sourceIndex: 3 }),
  entry("Earlier catalog item", "", { sourceIndex: 1 })
]);
assert.deepStrictEqual(
  Array.from(catalogOrderFallback, (item) => item.taskName),
  ["Earlier catalog item", "Later catalog item"],
  "catalog-backed recent tasks should preserve catalog order when timestamps are missing"
);

console.log("Recent task ordering checks passed.");

const analyticsSandbox = {
  cleanLabel(value, fallback = "") {
    const text = value == null ? "" : String(value).trim();
    return text || fallback;
  }
};

vm.createContext(analyticsSandbox);
vm.runInContext([
  extractFunction(html, "normalizedAnalyticsTaskName"),
  extractFunction(html, "consolidatedAnalyticsTaskRows")
].join("\n\n"), analyticsSandbox);

assert.strictEqual(
  analyticsSandbox.normalizedAnalyticsTaskName("🤖 Run AI agent_Work"),
  "run ai agent work",
  "analytics task normalization should ignore emoji and underscore separators"
);

const mergedAnalyticsRows = analyticsSandbox.consolidatedAnalyticsTaskRows([
  {
    taskId: "clickup-run-ai-agent",
    taskName: "🤖 Run AI agent_Work",
    totalHours: 197,
    weekHours: new Map([["W27", 1], ["W26", 25.1]])
  },
  {
    taskId: "native-run-ai-agent-work",
    taskName: "Run Ai agent_work",
    totalHours: 2.83,
    weekHours: new Map([["W27", 0], ["W26", 1.6]])
  }
], ["W27", "W26"]);

assert.strictEqual(
  mergedAnalyticsRows.length,
  1,
  "analytics task rows should merge equivalent AI-agent labels"
);

assert.ok(
  Math.abs(mergedAnalyticsRows[0].totalHours - 199.83) < 1e-9,
  "merged analytics row should combine total hours"
);

assert.ok(
  Math.abs(mergedAnalyticsRows[0].weekHours.get("W26") - 26.7) < 1e-9,
  "merged analytics row should combine weekly hours"
);

console.log("Analytics task merge checks passed.");

const breakAlarmSandbox = {
  cleanLabel(value, fallback = "") {
    const text = value == null ? "" : String(value).trim();
    return text || fallback;
  }
};

vm.createContext(breakAlarmSandbox);
vm.runInContext([
  extractFunction(html, "normalizedBreakAlarmTaskName"),
  extractFunction(html, "isAiAgentBreakAlarmTask")
].join("\n\n"), breakAlarmSandbox);

[
  { taskName: "Run AI Agent" },
  { taskName: "Run AI Agent Life" },
  { taskName: "Run AI Agent", taskCategory: "Life", listName: "🌈 Personal" },
  { taskName: "Run AI Agent_Work" },
  { taskName: "🤖 Run AI Agent_Work" },
  { taskName: "Run Ai Agent_work" },
  { taskName: "Run AI Agent Work" },
  { taskName: "Run AI Agent-Work" },
  {
    taskId: "86agzhyhy",
    taskName: "🤖 Run AI agent",
    listId: "900601952633",
    listName: "🚀 On Business",
    taskCategory: "🙂 Work"
  },
  {
    taskName: "Run AI agent",
    listId: "900601952633",
    listName: "🚀 On Business",
    taskCategory: "Work"
  }
].forEach((entry) => {
  assert.strictEqual(
    breakAlarmSandbox.isAiAgentBreakAlarmTask(entry),
    false,
    `${entry.taskName} should not trigger the 30-minute AI-agent break alarm`
  );
});

console.log("AI-agent break alarm checks passed.");

const autoDoneSandbox = {
  cleanLabel(value, fallback = "") {
    const text = value == null ? "" : String(value).trim();
    return text || fallback;
  },
  effectiveTaskId(taskId, taskName) {
    const id = autoDoneSandbox.cleanLabel(taskId, "");
    if (id) return id;
    return autoDoneSandbox.cleanLabel(taskName, "")
      .toLowerCase()
      .replace(/^[^a-z0-9]+/, "")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
  },
  taskOverrideKey(entry) {
    return [
      autoDoneSandbox.cleanLabel(entry?.listId, ""),
      autoDoneSandbox.effectiveTaskId(entry?.taskId, entry?.taskName)
    ].filter(Boolean).join("::");
  }
};

vm.createContext(autoDoneSandbox);
vm.runInContext([
  extractFunction(html, "normalizeLoggedTaskTargetName"),
  extractConst(html, "AUTO_DONE_EXCLUDED_TASK_IDS"),
  extractConst(html, "AUTO_DONE_EXCLUDED_TASK_NAMES"),
  extractConst(html, "AUTO_DONE_EXCLUDED_AI_AGENT_TASK_NAMES"),
  extractFunction(html, "normalizeAutoDoneAiAgentTaskName"),
  extractFunction(html, "isAutoDoneExcludedAiAgentTask"),
  extractFunction(html, "isAutoDoneExcludedTask"),
  extractFunction(html, "autoDoneTaskTargets")
].join("\n\n"), autoDoneSandbox);

function autoDoneEntry(taskName, overrides = {}) {
  return {
    listId: "list-main",
    listName: "Main",
    taskId: "",
    taskName,
    start: "2026-06-12T08:00:00.000-04:00",
    stop: "2026-06-12T09:00:00.000-04:00",
    dueDate: "2026-06-12",
    recurrence: "daily",
    ...overrides
  };
}

[
  "Run AI Agent_Life",
  "Run AI Agent_Work",
  "🤖 Run AI Agent_Life",
  "Run AI Agent Work",
  "Run AI Agent-Work"
].forEach((taskName) => {
  assert.strictEqual(
    autoDoneSandbox.autoDoneTaskTargets(autoDoneEntry(taskName)).length,
    0,
    `${taskName} should be excluded from logged-time auto-done`
  );
});

[
  autoDoneEntry("🌷Grow flowers and plants", { taskId: "86adrww47" }),
  autoDoneEntry("Grow flowers and plants")
].forEach((entry) => {
  assert.strictEqual(
    autoDoneSandbox.autoDoneTaskTargets(entry).length,
    0,
    `${entry.taskName} should be excluded from logged-time auto-done`
  );
});

assert.notStrictEqual(
  autoDoneSandbox.autoDoneTaskTargets(autoDoneEntry("Run AI Agent")).length,
  0,
  "base Run AI Agent should not be excluded by the Life/Work-specific rule"
);

assert.notStrictEqual(
  autoDoneSandbox.autoDoneTaskTargets(autoDoneEntry("Talk to Matt")).length,
  0,
  "normal logged tasks should still produce auto-done targets"
);

console.log("AI Agent auto-done exclusion checks passed.");

const autoDoneGuardSandbox = {
  dateInputValue(value) {
    return /^\d{4}-\d{2}-\d{2}$/.test(String(value || "")) ? String(value) : "";
  },
  isDailyRecurringTask(entry) {
    return entry?.recurrence === "daily";
  }
};

vm.createContext(autoDoneGuardSandbox);
vm.runInContext(extractFunction(html, "alreadyAutoDoneForDueDate"), autoDoneGuardSandbox);

assert.strictEqual(
  autoDoneGuardSandbox.alreadyAutoDoneForDueDate(
    { recurrence: "daily", status: "todo", autoDoneDate: "2026-06-18" },
    "2026-06-18"
  ),
  false,
  "daily todo tasks stuck on their auto-done date should be eligible to advance"
);

assert.strictEqual(
  autoDoneGuardSandbox.alreadyAutoDoneForDueDate(
    { recurrence: "daily", status: "done", autoDoneDate: "2026-06-18" },
    "2026-06-18"
  ),
  true,
  "completed daily tasks should still be treated as already auto-done"
);

console.log("Auto-done recovery guard checks passed.");

const sleepStatusSandbox = {
  cleanLabel(value, fallback = "") {
    const text = value == null ? "" : String(value).trim();
    return text || fallback;
  },
  dateInputValue(value) {
    return /^\d{4}-\d{2}-\d{2}$/.test(String(value || "")) ? String(value) : "";
  },
  parseDateInput(value) {
    const text = sleepStatusSandbox.dateInputValue(value);
    if (!text) return null;
    const [year, month, day] = text.split("-").map((part) => Number(part));
    const date = new Date(year, month - 1, day);
    return date.getFullYear() === year && date.getMonth() === month - 1 && date.getDate() === day ? date : null;
  },
  formatDateInput(date) {
    if (!(date instanceof Date) || Number.isNaN(date.getTime())) return "";
    return [
      date.getFullYear(),
      String(date.getMonth() + 1).padStart(2, "0"),
      String(date.getDate()).padStart(2, "0")
    ].join("-");
  },
  addLocalDays(date, days) {
    const next = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    next.setDate(next.getDate() + days);
    return next;
  },
  addLocalMonths(date, months) {
    const targetMonth = date.getMonth() + months;
    const firstOfTarget = new Date(date.getFullYear(), targetMonth, 1);
    const lastDayOfTarget = new Date(firstOfTarget.getFullYear(), firstOfTarget.getMonth() + 1, 0).getDate();
    return new Date(firstOfTarget.getFullYear(), firstOfTarget.getMonth(), Math.min(date.getDate(), lastDayOfTarget));
  },
  isoNow() {
    return "2026-07-14T12:00:00.000Z";
  }
};

vm.createContext(sleepStatusSandbox);
vm.runInContext([
  extractFunction(html, "inferRecurrence"),
  extractFunction(html, "isSleepTimerEntry"),
  extractFunction(html, "nextRecurringDueDate"),
  extractFunction(html, "taskStatusPatch")
].join("\n\n"), sleepStatusSandbox);

assert.deepStrictEqual(
  { ...sleepStatusSandbox.taskStatusPatch(
    { taskName: "Sleep", dueDate: "2026-07-14", recurrence: "none" },
    "done"
  ) },
  { dueDate: "2026-07-15", dueDateManaged: true, dueDateManualHold: "", status: "todo" },
  "marking Sleep done should advance the due date and keep it TO DO even without explicit daily recurrence"
);

assert.deepStrictEqual(
  { ...sleepStatusSandbox.taskStatusPatch(
    { taskName: "One-off task", dueDate: "2026-07-14", recurrence: "none" },
    "done"
  ) },
  { dueDateManualHold: "", status: "done" },
  "nonrecurring non-sleep tasks should still stay DONE"
);

console.log("Sleep status recurrence checks passed.");
