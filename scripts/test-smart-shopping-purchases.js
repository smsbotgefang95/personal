#!/usr/bin/env node
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '..', 'smart-shopping.html'), 'utf8');
const code = html.slice(html.indexOf('    const priceHistoryStorageKey ='), html.indexOf('    function normalizeStoredItem('));
const purchaseKey = 'smart-shopping-item-purchases-v1';
const pendingKey = 'smart-shopping-pending-purchases-v1';
const chicken = { sourceList: '买菜', key: '熟食::Roast chicken' };
const walnuts = { sourceList: '买菜', key: '零食::Walnuts' };
const key = (item) => `${item.sourceList}::${item.key}`;

function device(server, storage = new Map(), viewItems = [chicken, walnuts]) {
  const localStorage = { getItem: (k) => storage.get(k) || null, setItem: (k, v) => storage.set(k, v) };
  const context = vm.createContext({
    localStorage, window: { localStorage, confirm: () => { throw new Error('Reset must not depend on browser confirmation'); }, setTimeout: () => 1, clearTimeout() {} },
    document: { getElementById: () => ({ textContent: '', showModal() {}, close() {} }) },
    render() {}, showToast() {}, displayItemName: (item) => item.key,
    getViewItems: () => viewItems, isAllList: () => true,
    AbortController,
    fetch: async (_, options) => {
      if (options.method === 'POST') {
        if (server.fail) return { ok: false, status: 503, text: async () => '' };
        server.data = JSON.parse(options.body);
        if (server.onPost) await server.onPost();
        return { ok: true, text: async () => '' };
      }
      return { ok: true, text: async () => JSON.stringify(server.data) };
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
    status: (item) => context.shoppingStatus(item),
    weekly: (item) => context.isWeeklyStaple(item),
    setWeekly: (item, weekly) => context.setWeeklyStaple(item, weekly),
    plan: (item, status) => context.saveShoppingState(item, status),
    pending: () => JSON.parse(storage.get(pendingKey) || '{}')
  };
}

(async () => {
  const server = { data: { itemPurchases: { [key(chicken)]: true, [key(walnuts)]: true } } };
  const first = device(server);
  assert.equal(first.status(walnuts), "saved", "unselected catalog items are Saved");
  for (const name of ["Eggs", "Free range organic grade a medium egg 有机鸡蛋", "Bananas 香蕉", "Organic bananas bunch 有机香蕉", "Roast chicken 烤鸡"]) {
    assert.equal(first.weekly({ sourceList: "买菜", key: name, name }), true, name);
  }
  for (const name of ["Eggplant 茄子", "Stewed quail eggs 鹌鹑蛋", "Chicken breast"]) {
    assert.equal(first.weekly({ sourceList: "买菜", key: name, name }), false, name);
  }
  await first.sync();
  assert.equal(first.purchased(chicken), true);
  first.set(chicken, false);
  await first.sync();
  assert.equal(first.purchased(chicken), false, 'stale GET must not recheck item');
  assert.equal(server.data.itemPurchases[key(chicken)].status, "to-buy", 'upload explicit unchecked value');
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
  assert.equal(server.data.itemPurchases[key(chicken)].status, "to-buy");
  assert.equal(server.data.itemPurchases[key(walnuts)].status, "saved", 'bulk reset syncs');
  assert.equal(first.status(chicken), "to-buy", "weekly staple ready for next week");
  assert.equal(first.status(walnuts), "saved", "ordinary purchase goes to Saved");
  await second.sync();
  assert.equal(second.status(walnuts), "saved", "second device receives Saved");
  assert.equal(second.weekly(chicken), true);
  first.setWeekly(chicken, false);
  first.set(chicken, true);
  first.reset(); first.confirmReset();
  assert.equal(first.status(chicken), "saved", "explicit opt-out overrides weekly default");
  first.plan(walnuts, "to-buy");
  assert.equal(first.status(walnuts), "to-buy", "Buy again selects a saved item");
  first.setWeekly(walnuts, true);
  await first.sync(); await second.sync();
  assert.equal(second.weekly(walnuts), true, "custom weekly preference syncs");
  first.setWeekly(chicken, true);

  server.fail = true;
  first.set(chicken, true);
  await first.sync();
  assert.equal(first.pending()[key(chicken)].status, "purchased", 'failed upload retains pending value');
  const reloaded = device(server, first.storage);
  server.fail = false;
  await reloaded.sync();
  assert.equal(server.data.itemPurchases[key(chicken)].status, "purchased", 'reload retries pending change');
  assert.deepEqual(reloaded.pending(), {});

  reloaded.set(chicken, false);
  server.onPost = async () => {
    reloaded.set(chicken, true);
    await reloaded.sync(); // Must not start an overlapping request.
  };
  await reloaded.sync();
  assert.equal(reloaded.pending()[key(chicken)].status, "purchased", 'change during POST is not acknowledged early');
  server.onPost = null;
  await reloaded.sync();
  assert.equal(server.data.itemPurchases[key(chicken)].status, "purchased");
  assert.deepEqual(reloaded.pending(), {});
  const scopedServer = { data: { itemPurchases: { [key(chicken)]: true, [key(walnuts)]: true } } };
  const scoped = device(scopedServer, new Map(), [chicken]);
  await scoped.sync(); scoped.reset(); scoped.confirmReset(); await scoped.sync();
  assert.equal(scopedServer.data.itemPurchases[key(walnuts)], true, "trip completion stays in selected collection");
  assert.equal(scopedServer.data.itemPurchases[key(chicken)].status, "to-buy");
  console.log('PASS: weekly defaults/opt-out, Saved/To buy, scoped finish, and uncheck, recheck, bulk reset, second device, failed sync/reload, and change during upload');
})().catch((error) => { console.error(error); process.exitCode = 1; });
