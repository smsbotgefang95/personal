const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync('smart-shopping.html', 'utf8');
const code = html.slice(html.indexOf('    async function fetchShoppingSync('), html.indexOf('    async function syncShoppingDevices('));
async function checkTimeout(bodyStalls) {
  let expire, cleared = false;
  const context = vm.createContext({
    AbortController, shoppingSyncApi: '/api/smart-shopping',
    window: { setTimeout(fn, ms) { assert.equal(ms, 15000); expire = fn; return 1; }, clearTimeout() { cleared = true; } },
    fetch: async (_, { signal }) => {
      const stalled = () => new Promise((resolve, reject) => signal.addEventListener('abort', () => reject(new Error('aborted')), { once: true }));
      if (!bodyStalls) return stalled();
      return { ok: true, status: 200, text: stalled };
    }
  });
  vm.runInContext(code, context);
  const request = context.fetchShoppingSync({});
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
  expire();
  await assert.rejects(request, /aborted/);
  assert.equal(cleared, true, 'timeout is cleaned up after a stalled request');
}
(async () => {
  await checkTimeout(false);
  await checkTimeout(true);
  let cleared = false;
  const context = vm.createContext({
    AbortController, shoppingSyncApi: '/api/smart-shopping',
    window: { setTimeout() { return 1; }, clearTimeout() { cleared = true; } },
    fetch: async () => ({ ok: true, status: 200, text: async () => '{"items":[]}' })
  });
  vm.runInContext(code, context);
  const response = await context.fetchShoppingSync({});
  assert.equal(response.json().items.length, 0);
  assert.equal(cleared, true, 'successful requests release timeout');
  console.log('PASS: stalled headers and body abort, successful JSON parses, timers cleaned up');
})().catch(error => { console.error(error); process.exitCode = 1; });
