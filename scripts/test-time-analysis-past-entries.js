#!/usr/bin/env node
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync(require('node:path').join(__dirname, '../time-analysis.html'), 'utf8');
function source(name) {
  const start = html.indexOf(`function ${name}(`);
  const body = html.indexOf('{', html.indexOf(') {', start));
  let depth = 0;
  for (let i = body; i < html.length; i++) {
    if (html[i] === '{') depth++;
    if (html[i] === '}' && --depth === 0) return html.slice(start, i + 1);
  }
  throw new Error(name);
}
let fail = false, writes = 0;
const active = {id: 'running', taskName: 'Other task'};
const context = {
  Date, privateTimeSyncState: {mode: "synced"}, LIST_NAME_MAP: {}, timePayload: {entries: [], activeEntry: active}, pastEntryTaskKey: 'sleep',
  cleanLabel: (v, fallback = '') => String(v || fallback),
  parseDateInput: v => v ? new Date(`${v}T00:00:00`) : null,
  timeInputValue: v => v, nativeId: () => `manual-${writes}`, taskIdFor: () => 'sleep',
  listNameForId: () => 'Survival', normalizeTaskCategory: v => v, inferRecurrence: () => 'daily',
  timestampMs: v => new Date(v).getTime(), formatDuration: ms => String(ms),
  setTrackerStatus: () => {}, showTrackerToast: () => {},
  autoMarkTimeLoggedTasksDone: async () => {},
  saveTimePayload: async payload => {
    if (fail) throw new Error('offline');
    writes++;
    context.timePayload = payload;
  }
};
vm.createContext(context);
vm.runInContext([
  ...['localDateTimeFromInputs', 'isSleepTimerEntry', 'sleepSplitBoundaryFor', 'completedTimerEntry', 'completedTimerEntries'].map(source),
  'async ' + source('savePastTimeEntry')
].join('\n'), context);
const task = {taskId: 'sleep', taskName: '🛏️ Sleep', listId: 'survival'};
function editor(start, end) {
  const values = {'[data-past-date]': '2026-10-27', '[data-past-start]': start, '[data-past-end]': end};
  return {querySelector: key => ({value: values[key]})};
}
(async () => {
  await context.savePastTimeEntry(task, editor('22:30', '23:59'));
  assert.equal(context.timePayload.entries[0].durationMs, 89 * 60000);
  assert.equal(context.timePayload.activeEntry, active, 'past logging must preserve the running timer');
  await context.savePastTimeEntry(task, editor('22:30', '23:59'));
  assert.equal(writes, 1, 'retrying the same interval must not duplicate it');
  context.timePayload.entries = [];
  await context.savePastTimeEntry(task, editor('22:30', '06:30'));
  assert.equal(context.timePayload.entries.length, 2, 'overnight Sleep must split at midnight');
  assert.equal(context.timePayload.entries.reduce((sum, e) => sum + e.durationMs, 0), 8 * 3600000);
  assert.equal(new Date(context.timePayload.entries[0].stop).getHours(), 6);
  context.pastEntryTaskKey = 'sleep';
  fail = true;
  await assert.rejects(context.savePastTimeEntry(task, editor('10:00', '11:00')), /offline/);
  assert.equal(context.pastEntryTaskKey, 'sleep', 'a failed save must preserve the open editor');
  // A stalled request must release the sync queue, including a stalled response body.
  for (const stallBody of [false, true]) {
    let expire, cleared = false;
    const apiContext = {
      AbortController, TIME_ENTRIES_API: '/api/time-entries',
      ensureTimeAdminKey: async () => '', clearTimeAdminKey: () => {},
      window: {
        setTimeout: callback => { expire = callback; return 1; },
        clearTimeout: () => { cleared = true; }
      },
      fetch: async (url, {signal}) => {
        const stalled = () => new Promise((resolve, reject) => {
          signal.addEventListener('abort', () => reject(new Error('aborted')));
          queueMicrotask(expire);
        });
        return stallBody ? {status: 200, ok: true, json: stalled} : stalled();
      }
    };
    vm.createContext(apiContext);
    vm.runInContext('async ' + source('timeApi'), apiContext);
    await assert.rejects(apiContext.timeApi('POST', {}), /sync timed out/);
    assert.equal(cleared, true, 'request timeout must be cleaned up');
  }
  console.log('Past-entry save and sync-timeout regression tests passed.');
})().catch(error => { console.error(error); process.exitCode = 1; });
