#!/usr/bin/env node
process.env.TZ = 'America/New_York';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync(require('node:path').join(__dirname, '../time-analysis.html'), 'utf8');
function source(name) {
  const start = html.indexOf(`  function ${name}(`);
  const end = html.indexOf('\n  function ', start + 1);
  assert.ok(start >= 0 && end > start, name);
  return html.slice(start, end);
}
const ctx = {
  Date, Map, Set, Number, DAY_TOTAL_AUDIT_TOLERANCE_MS: 60000,
  detailEntryKey: e => e.id, cleanLabel: (v, fallback = '') => v || fallback,
  dateInputValue: v => v,
};
vm.createContext(ctx);
vm.runInContext(['parseDateInput', 'addLocalDays', 'dateKeyBounds', 'entryHasExactDate',
  'entryDateOverlapMs', 'entryDateFilterMs', 'entryMatchesDate', 'dayAuditTimeLabel',
  'dayAuditRangeLabel', 'dayAuditSourceLabel', 'dayAuditEntryTitle', 'dayAuditWindow',
  'addDayAuditIssue', 'buildDayTotalAudit'].map(source).join('\n'), ctx);
function entry(id, start, stop) {
  return {id, taskName: id, start: new Date(start), stop: new Date(stop), sourceType: 'native'};
}
for (const [day, next, hours] of [
  ['2026-11-01', '2026-11-02', 25],
  ['2026-03-08', '2026-03-09', 23],
  ['2026-11-02', '2026-11-03', 24],
]) {
  const audit = ctx.buildDayTotalAudit([entry('full day', `${day}T00:00:00`, `${next}T00:00:00`)], day);
  assert.equal(audit.expectedMs, hours * 3600000);
  assert.equal(audit.isComplete, true, `${hours}-hour local day should be complete`);
  assert.equal(audit.issueEntries.length, 0);
}
const audit = ctx.buildDayTotalAudit([
  entry('day', '2026-11-02T00:00:00', '2026-11-03T00:00:00'),
  entry('duplicate hour', '2026-11-02T12:00:00', '2026-11-02T13:00:00'),
], '2026-11-02');
assert.equal(audit.deltaMs, 3600000);
assert.equal(audit.issueEntries.length, 2);
assert.ok(audit.issueEntries.every(e => e.reasons.some(r => r.type === 'overlap' && r.ms === 3600000)));
const missing = ctx.buildDayTotalAudit([{id: 'missing', date: '2026-11-02', durationMs: 3600000}], '2026-11-02');
assert.equal(missing.issueEntries[0].reasons[0].type, 'invalid');
for (const script of html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)) new vm.Script(script[1]);
console.log('Day audit: 25h fall-back, 23h spring-forward, 24h ordinary days, overlaps, missing timestamps, and script syntax passed.');
