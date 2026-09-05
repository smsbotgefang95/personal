#!/usr/bin/env node
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '..', 'smart-shopping.html'), 'utf8');
const code = html.slice(html.indexOf('    const itemEditsStorageKey ='), html.indexOf('    function normalizeStoredItem('));
const purchaseKey = 'smart-shopping-item-purchases-v1';
const pendingKey = 'smart-shopping-pending-purchases-v1';
const chicken = { sourceList: '买菜', key: '熟食::Roast chicken' };
const walnuts = { sourceList: '买菜', key: '零食::Walnuts' };
const key = (item) => `${item.sourceList}::${item.key}`;

function device(server, storage = new Map()) {
  const localStorage = { getItem: (k) => storage.get(k) || null, setItem: (k, v) => storage.set(k, v) };
  const context = vm.createContext({
    localStorage, window: { localStorage, confirm: () => { throw new Error('Reset must not depend on browser confirmation'); }, setTimeout: () => 1, clearTimeout() {} },
    document: { getElementById: () => ({ textContent: '', showModal() {}, close() {} }) },
    render() {}, showToast() {}, displayItemName: (item) => item.key,
    getViewItems: () => [chicken, walnuts], isAllList: () => true,
    fetch: async (_, options) => {
      if (options.method === 'POST') {
        if (server.fail) return { ok: false, status: 503 };
        server.data = JSON.parse(options.body);
        if (server.onPost) await server.onPost();
        return { ok: true };
      }
      return { ok: true, json: async () => JSON.parse(JSON.stringify(server.data)) };
    }
  });
  vm.runInContext(code + '\nshoppingSyncKey = "test-only";', context);
  return {
    storage,
    set: (item, value) => context.setItemPurchased(item, value),
    reset: () => context.resetPurchasedItems(),
    confirmReset: () => context.confirmResetPurchasedItems(),
    sync: () => context.syncShoppingDevices(),
    purchased: (item) => context.isItemPurchased(item),
    pending: () => JSON.parse(storage.get(pendingKey) || '{}')
  };
}

(async () => {
  const server = { data: { itemPurchases: { [key(chicken)]: true, [key(walnuts)]: true } } };
  const first = device(server);
  await first.sync();
  assert.equal(first.purchased(chicken), true);
  first.set(chicken, false);
  await first.sync();
  assert.equal(first.purchased(chicken), false, 'stale GET must not recheck item');
  assert.equal(server.data.itemPurchases[key(chicken)], false, 'upload explicit unchecked value');
  assert.deepEqual(first.pending(), {});
  assert.equal(first.purchased(walnuts), true, 'unrelated purchases preserved');

  const second = device(server, new Map([[purchaseKey, JSON.stringify({ [key(chicken)]: true })]]));
  await second.sync();
  assert.equal(second.purchased(chicken), false, 'another device receives unchecked value');
  first.set(chicken, true);
  await first.sync();
  assert.equal(first.purchased(chicken), true, 'checking works too');
  first.reset();
  assert.equal(first.purchased(chicken), true, 'opening confirmation must not change purchases');
  first.confirmReset();
  await first.sync();
  assert.equal(server.data.itemPurchases[key(chicken)], false);
  assert.equal(server.data.itemPurchases[key(walnuts)], false, 'bulk reset syncs');

  server.fail = true;
  first.set(chicken, true);
  await first.sync();
  assert.equal(first.pending()[key(chicken)], true, 'failed upload retains pending value');
  const reloaded = device(server, first.storage);
  server.fail = false;
  await reloaded.sync();
  assert.equal(server.data.itemPurchases[key(chicken)], true, 'reload retries pending change');
  assert.deepEqual(reloaded.pending(), {});

  reloaded.set(chicken, false);
  server.onPost = async () => {
    reloaded.set(chicken, true);
    await reloaded.sync(); // Must not start an overlapping request.
  };
  await reloaded.sync();
  assert.equal(reloaded.pending()[key(chicken)], true, 'change during POST is not acknowledged early');
  server.onPost = null;
  await reloaded.sync();
  assert.equal(server.data.itemPurchases[key(chicken)], true);
  assert.deepEqual(reloaded.pending(), {});
  console.log('PASS: uncheck, recheck, bulk reset, second device, failed sync/reload, and change during upload');
})().catch((error) => { console.error(error); process.exitCode = 1; });
