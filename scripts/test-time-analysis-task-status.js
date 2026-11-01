#!/usr/bin/env node
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const html = fs.readFileSync(path.join(__dirname, "../time-analysis.html"), "utf8");
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
    if (depth === 0) return (source.slice(start - 6, start) === "async " ? "async " : "") + source.slice(start, index + 1);
  }
  throw new Error(`Could not parse function ${name}`);
}


const renderScopes = [];
const sandbox = {
  console,
  cleanLabel: (value, fallback = "") => String(value || fallback).trim(),
  dateInputValue: (value) => value || "",
  businessDateKey: () => "2026-11-01",
  dueDateKey: (entry) => entry.dueDate || "",
  timestampMs: (value) => Date.parse(value) || 0,
  isoNow: () => "2026-11-01T15:00:00.000Z",
  cleanClientPayload: (value) => JSON.parse(JSON.stringify(value)),
  latestTimePayloadDate: () => 0,
  resolveTimeAdminKey: async () => "test-key",
  privateTimeSyncState: { mode: "synced" },
  mergeTimePayloadEntries: (saved, local) => [...saved, ...local],
  writeLocalTimePayload() {}, showPrivateTimeLoadButton() {},
  renderTimePayloadState({renderScope}) { renderScopes.push(renderScope); },
  setPrivateTimeSyncState() {}, setTrackerStatus() {},
  taskOverrideKeysForEdit: () => ["list|||task", "list|||alias"],
  currentTaskOverrideForKey: () => ({recurrence: "custom", dueTime: "10:15"}),
};
vm.createContext(sandbox);
vm.runInContext([
  html.slice(html.indexOf("  const CUSTOM_RECURRENCE_DAYS"), html.indexOf("  const CUSTOM_MONTHLY_DAY_SHORT_LABELS")),
  html.slice(html.indexOf("  function parseDateInput"), html.indexOf("  function customRecurrenceText")),
  ...["isSleepTimerEntry", "isDailyRecurringTask", "autoDoneStatusPatch", "latestLoggedCompletionAfter", "manualHoldBlocksAutoDone", "alreadyAutoDoneForDueDate", "latestEligibleLoggedAutoDoneDate", "autoDoneDateForTask", "taskStatusPatch", "manualTaskStatusPatch", "saveTaskOverride", "saveTimePayload", "choosePayloadRecord", "mergePayloadRecordMaps"].map(name => extractFunction(html, name))
].join("\n"), sandbox);

async function run() {
  const entry = {recurrence: "custom", dueDate: "2026-09-01", recurringText:
    "Every 1 month; on first day; on First Tuesday; on status change: Done; recur forever; update status to To Do"};
  const patch = sandbox.manualTaskStatusPatch(entry, "done");
  assert.equal(patch.dueDate, "2026-11-03");
  assert.equal(sandbox.autoDoneStatusPatch(entry, "2026-09-01").dueDate, "2026-10-01",
    "historical automatic completion must retain its original schedule behavior");
  assert.equal(patch.status, "todo");
  const sleep = {taskName: "🛏️ Sleep", recurrence: "daily", dueDate: "2026-10-28",
    status: "todo", autoDoneDate: "2026-10-27", dueDateEditedAt: "2026-07-15T01:12:56.381Z"};
  const completedSleep = {...sleep, ...sandbox.manualTaskStatusPatch(sleep, "done")};
  assert.equal(completedSleep.dueDate, "2026-11-02");
  const oldSleepLogs = new Map([["2026-10-27", Date.parse("2026-10-28T10:00:00Z")]]);
  assert.equal(sandbox.autoDoneDateForTask(completedSleep, oldSleepLogs), "",
    "historical Sleep logs must not undo a manual Done and move the due date back to October 28");
  const newSleepLogs = new Map([["2026-11-02", Date.parse("2026-11-02T10:00:00Z")]]);
  assert.equal(sandbox.autoDoneDateForTask(completedSleep, newSleepLogs), "2026-11-02",
    "genuinely new sleep logs must remain eligible for automatic completion");
  const overdueCases = [
    ["Grocery shopping", {recurrence: "weekly", dueDate: "2026-09-06"}, "2026-11-08"],
    ["Grocery list", {recurrence: "weekly", dueDate: "2026-09-12"}, "2026-11-07"],
    ["Organize food", {recurrence: "weekly", dueDate: "2026-09-20"}, "2026-11-08"],
    ["Cell bill", {recurrence: "monthly", dueDate: "2026-08-30"}, "2026-11-30"],
    ["Annual task", {recurrence: "yearly", dueDate: "2024-10-30"}, "2027-10-30"],
    ["Trash", {recurrence: "custom", dueDate: "2026-08-16", recurringText:
      "Every 1 week on Su, We; on status change: Done; recur forever; update status to To Do"}, "2026-11-04"],
    ["Laundry", {recurrence: "custom", dueDate: "2026-09-30", recurringText:
      "Every 1 month; on first day; on 11th day; on 21st day; on last day; on status change: Done; recur forever; update status"}, "2026-11-11"],
    ["Custom daily", {recurrence: "custom", dueDate: "2026-10-01", recurringText:
      "Every 3 days; on status change: Done; recur forever; update status to To Do"}, "2026-11-03"],
    ["Future weekly", {recurrence: "weekly", dueDate: "2026-11-08"}, "2026-11-15"],
    ["Non-recurring", {recurrence: "none", dueDate: "2026-09-01"}, undefined],
  ];
  for (const [name, task, expected] of overdueCases) {
    const result = sandbox.manualTaskStatusPatch(task, "done");
    assert.equal(result.dueDate, expected, `${name}: manual completion must skip the backlog while preserving the schedule`);
    assert.equal(result.status, task.recurrence === "none" ? "done" : "todo");
    assert.equal(result.dueDateEditedAt, "2026-11-01T15:00:00.000Z");
    if (expected) {
      const completed = {...task, ...result};
      const oldLogs = new Map([[task.dueDate, Date.parse("2026-10-31T12:00:00Z")]]);
      assert.equal(sandbox.autoDoneDateForTask(completed, oldLogs), "", `${name}: old logs must not replay after completion`);
    }
  }
  const history = [{id: "old-history"}];
  sandbox.timePayload = {entries: history, taskOverrides: {"unrelated": {status: "todo"}}};
  let submitted;
  sandbox.postTimePayload = async (payload) => {
    submitted = payload;
    return {partialEntries: true, payload: {entries: [], taskOverrides: {
      "unrelated": {status: "done"}, ...payload.taskOverrides
    }}};
  };
  await sandbox.saveTaskOverride(entry, patch);
  assert.equal(renderScopes.at(-1), "activityRows", "task saves must refresh rows without waiting for the full dashboard or search blur");
  assert.equal(submitted.appendEntriesOnly, true);
  assert.equal(submitted.entries.length, 0, "task edits must not send historical entries");
  assert.equal(Object.keys(submitted.taskOverrides).length, 2, "send only edited task aliases");
  assert.equal(sandbox.timePayload.taskOverrides.unrelated.status, "done", "preserve newer server metadata");
  assert.equal(sandbox.timePayload.entries[0].id, "old-history", "retain cached history after compact response");
  for (const key of ["list|||task", "list|||alias"]) {
    assert.equal(sandbox.timePayload.taskOverrides[key].dueDate, "2026-11-03");
    assert.equal(sandbox.timePayload.taskOverrides[key].dueTime, "10:15");
  }
  // A timer/private refresh can complete while the task POST is in flight.
  // Its newer payload timestamp must not cause the confirmed date to be discarded.
  sandbox.isoNow = () => "2026-11-01T15:00:02.000Z";
  sandbox.latestTimePayloadDate = (payload) => Date.parse(payload.updatedAt) || 0;
  sandbox.postTimePayload = async (payload) => {
    sandbox.timePayload = {...sandbox.timePayload, updatedAt: "2026-11-01T15:00:03.000Z",
      activeEntry: {id: "newer-running-timer"}};
    return {partialEntries: true, payload: {entries: [], taskOverrides: payload.taskOverrides}};
  };
  await sandbox.saveTaskOverride(entry, {...patch, dueDate: "2026-11-02"});
  assert.equal(sandbox.timePayload.taskOverrides["list|||task"].dueDate, "2026-11-02",
    "confirmed date must reach the displayed payload even when a newer timer arrived during save");
  assert.equal(sandbox.timePayload.activeEntry.id, "newer-running-timer", "retain the newer timer");
  sandbox.postTimePayload = async (payload) => {
    sandbox.timePayload = {...sandbox.timePayload, updatedAt: "2026-11-01T15:00:04.000Z",
      taskOverrides: {...sandbox.timePayload.taskOverrides,
        "list|||task": {...payload.taskOverrides["list|||task"], dueDate: "2026-11-04", updatedAt: "2026-11-01T15:00:04.000Z"}}};
    return {partialEntries: true, payload: {entries: [], taskOverrides: payload.taskOverrides}};
  };
  await sandbox.saveTaskOverride(entry, {...patch, dueDate: "2026-11-03"});
  assert.equal(sandbox.timePayload.taskOverrides["list|||task"].dueDate, "2026-11-04",
    "an earlier response must not replace a newer edit to the same task");
  assert.equal(sandbox.timePayload.entries[0].id, "old-history", "task merging must preserve history");
  sandbox.latestTimePayloadDate = () => 0;
  sandbox.postTimePayload = async (payload) => {
    submitted = payload;
    return {partialEntries: true, payload: {entries: [], taskOverrides: payload.taskOverrides}};
  };
  sandbox.privateTimeSyncState.mode = "checking";
  await sandbox.saveTaskOverride(entry, patch);
  assert.equal(submitted.appendEntriesOnly, undefined, "unsynced local changes must still use the full save");
  sandbox.privateTimeSyncState.mode = "synced";
  sandbox.postTimePayload = async (payload) => ({partialEntries: true, payload: {entries: [], taskOverrides:
    Object.fromEntries(Object.entries(payload.taskOverrides).map(([key, value]) => [key, {...value, dueDate: "2026-09-01"}]))}});
  await assert.rejects(sandbox.saveTaskOverride(entry, patch), /did not confirm the task change/);
  console.log("Recurring task advancement, compact saves, alias updates, and server verification passed.");
}
run().catch(error => { console.error(error); process.exitCode = 1; });
