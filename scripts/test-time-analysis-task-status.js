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


const sandbox = {
  console,
  cleanLabel: (value, fallback = "") => String(value || fallback).trim(),
  dateInputValue: (value) => value || "",
  isSleepTimerEntry: () => false,
  isoNow: () => "2026-11-01T15:00:00.000Z",
  cleanClientPayload: (value) => JSON.parse(JSON.stringify(value)),
  latestTimePayloadDate: () => 0,
  resolveTimeAdminKey: async () => "test-key",
  privateTimeSyncState: { mode: "synced" },
  mergeTimePayloadEntries: (saved, local) => [...saved, ...local],
  writeLocalTimePayload() {}, showPrivateTimeLoadButton() {},
  renderTimePayloadState() {}, setPrivateTimeSyncState() {}, setTrackerStatus() {},
  taskOverrideKeysForEdit: () => ["list|||task", "list|||alias"],
  currentTaskOverrideForKey: () => ({recurrence: "custom", dueTime: "10:15"}),
};
vm.createContext(sandbox);
vm.runInContext([
  html.slice(html.indexOf("  const CUSTOM_RECURRENCE_DAYS"), html.indexOf("  const CUSTOM_MONTHLY_DAY_SHORT_LABELS")),
  html.slice(html.indexOf("  function parseDateInput"), html.indexOf("  function customRecurrenceText")),
  ...["taskStatusPatch", "manualTaskStatusPatch", "saveTaskOverride", "saveTimePayload"].map(name => extractFunction(html, name))
].join("\n"), sandbox);

async function run() {
  const entry = {recurrence: "custom", dueDate: "2026-09-01", recurringText:
    "Every 1 month; on first day; on First Tuesday; on status change: Done; recur forever; update status to To Do"};
  const patch = sandbox.manualTaskStatusPatch(entry, "done");
  assert.equal(patch.dueDate, "2026-10-01");
  assert.equal(patch.status, "todo");
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
  assert.equal(submitted.appendEntriesOnly, true);
  assert.equal(submitted.entries.length, 0, "task edits must not send historical entries");
  assert.equal(Object.keys(submitted.taskOverrides).length, 2, "send only edited task aliases");
  assert.equal(sandbox.timePayload.taskOverrides.unrelated.status, "done", "preserve newer server metadata");
  assert.equal(sandbox.timePayload.entries[0].id, "old-history", "retain cached history after compact response");
  for (const key of ["list|||task", "list|||alias"]) {
    assert.equal(sandbox.timePayload.taskOverrides[key].dueDate, "2026-10-01");
    assert.equal(sandbox.timePayload.taskOverrides[key].dueTime, "10:15");
  }
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
