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
  renderActivityRows: () => {},
  timeLoggedTaskOverrideUpdates: () => ({sleep: {status: "done"}}),
  saveTimePayload: async (payload, options) => {
    assert.ok(options.appendEntries.length <= 2, "only the new intervals should be sent");
    assert.equal(options.taskOverrideUpdates.sleep.status, "done", "completion must be included in the same save");
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
  context.pastEntryTaskKey = 'sleep';
  await context.savePastTimeEntry(task, editor('22:30', '23:59'));
  assert.equal(writes, 1, 'retrying the same interval must not duplicate it');
  assert.equal(context.pastEntryTaskKey, '', 'an already-saved interval must close the editor');
  context.timePayload.entries = [];
  await context.savePastTimeEntry(task, editor('22:30', '06:30'));
  assert.equal(context.timePayload.entries.length, 2, 'overnight Sleep must split at midnight');
  assert.equal(context.timePayload.entries.reduce((sum, e) => sum + e.durationMs, 0), 8 * 3600000);
  assert.equal(new Date(context.timePayload.entries[0].stop).getHours(), 6);
  context.pastEntryTaskKey = 'sleep';
  fail = true;
  await assert.rejects(context.savePastTimeEntry(task, editor('10:00', '11:00')), /offline/);
  assert.equal(context.pastEntryTaskKey, 'sleep', 'a failed save must preserve the open editor');
  // Exercise the real save transport with a large cached history and compact
  // server response. New intervals and completion updates share one request.
  let sent, requestCount = 0, localFallback;
  const history = Array.from({length: 6000}, (_, i) => ({id: `old-${i}`, start: '2026-01-01', stop: '2026-01-02'}));
  const candidate = {id: 'manual-new', start: '2026-10-29T10:00:00Z', stop: '2026-10-29T11:00:00Z'};
  const saveContext = {
    privateTimeSyncState: {mode: "synced"},
    timePayload: {entries: history}, isoNow: () => '2026-10-29T12:00:00Z',
    cleanClientPayload: p => p,
    timeEntrySaveMatches: (a, b) => a?.id === b.id && a?.stop === b.stop,
    latestTimePayloadDate: p => Date.parse(p.updatedAt || '2026-01-01'),
    resolveTimeAdminKey: async () => 'test-key',
    postTimePayload: async p => {
      sent = p; requestCount++;
      return {partialEntries: true, payload: {
        entries: [{...candidate, id: 'manual-canonical'}], activeEntry: active,
        taskOverrides: p.taskOverrides, updatedAt: '2026-10-29T12:00:00Z'
      }};
    },
    mergeTimePayloadEntries: (a, b) => [...a, ...b],
    writeLocalTimePayload: () => {}, showPrivateTimeLoadButton: () => {},
    scheduleDeferredTimePayloadRender: () => {}, renderTimePayloadState: () => {},
    setPrivateTimeSyncState: () => {}, setTrackerStatus: () => {},
    shouldFallbackToLocalTimeSave: () => true, localTimeSaveFallbackMessage: () => 'offline',
    saveTimePayloadLocally: p => { localFallback = p; }
  };
  vm.createContext(saveContext);
  vm.runInContext('async ' + source('saveTimePayload'), saveContext);
  const pending = {entries: [candidate, ...history], activeEntry: active, taskOverrides: {sleep: {status: 'done'}}};
  const options = {appendEntries: [candidate], taskOverrideUpdates: pending.taskOverrides, deferRender: true};
  await saveContext.saveTimePayload(pending, options);
  assert.equal(requestCount, 1);
  assert.equal(sent.appendEntriesOnly, true);
  assert.equal(sent.entries.length, 1);
  assert.ok(JSON.stringify(sent).length < 1000, 'request size must not grow with cached history');
  assert.equal(saveContext.timePayload.entries.length, 6001, 'compact response must preserve local history');
  assert.equal(saveContext.timePayload.entries[0].id, 'manual-canonical', 'retry must use the canonical server ID');
  assert.equal(saveContext.timePayload.activeEntry, active);
  const editOptions = {...options, requireServer: true, verifyEntry: candidate};
  // A compact response must confirm the actual edited ID/time; the submitted
  // draft must never stand in for a missing or stale server acknowledgement.
  saveContext.postTimePayload = async p => { sent = p; return {partialEntries: true, payload: {...pending, entries: [candidate]}}; };
  await saveContext.saveTimePayload(pending, editOptions);
  assert.equal(sent.entries.length, 1, 'manual edit must send just the edited entry');
  assert.equal(saveContext.timePayload.entries.length, 6001);
  for (const entries of [[], [{...candidate, stop: '2026-10-29T10:30:00Z'}]]) {
    saveContext.postTimePayload = async () => ({partialEntries: true, payload: {...pending, entries}});
    await assert.rejects(saveContext.saveTimePayload(pending, editOptions), /did not confirm/);
  }
  saveContext.postTimePayload = async () => { throw new Error('offline'); };
  await assert.rejects(saveContext.saveTimePayload(pending, editOptions), /offline/);
  assert.equal(localFallback, undefined, 'manual edit must never report local-only persistence as server success');
  saveContext.privateTimeSyncState.mode = 'local-only';
  saveContext.postTimePayload = async p => { sent = p; return {payload: p}; };
  await saveContext.saveTimePayload(pending, options);
  assert.equal(sent.entries.length, 6001, 'reconnecting must upload older unsynced entries too');
  assert.equal(sent.appendEntriesOnly, undefined);
  saveContext.privateTimeSyncState.mode = 'synced';
  saveContext.postTimePayload = async () => { throw new Error('offline'); };
  await saveContext.saveTimePayload(pending, options);
  assert.equal(localFallback.entries.length, 6001, 'offline fallback must save the full history, not the transport delta');
  const syncContext = {
    privateTimeSyncState: {mode: 'synced', lastSuccessAt: '2026-07-02T10:59:00Z'},
    isoNow: () => '2026-10-28T11:00:00Z',
    cleanPrivateTimeSyncState: value => value,
    writePrivateTimeSyncState: () => {}, renderPrivateTimeSyncState: () => {}
  };
  vm.createContext(syncContext);
  vm.runInContext(source('setPrivateTimeSyncState'), syncContext);
  syncContext.setPrivateTimeSyncState('synced');
  assert.equal(syncContext.privateTimeSyncState.lastSuccessAt, '2026-10-28T11:00:00Z', 'each successful sync must refresh its timestamp');
  syncContext.setPrivateTimeSyncState('error');
  assert.equal(syncContext.privateTimeSyncState.lastSuccessAt, '2026-10-28T11:00:00Z', 'failed sync must preserve the last successful timestamp');
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
