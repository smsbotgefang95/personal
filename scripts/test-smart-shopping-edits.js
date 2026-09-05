const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const html = fs.readFileSync('smart-shopping.html', 'utf8');
const code = html.slice(html.indexOf('    const priceHistoryStorageKey ='), html.indexOf('    function normalizeStoredItem('));
const id = '橱柜::主食::Organic Light Brown Rice 有机糙米 (1 × 1袋)';
const server = { data: { itemEdits: { [id]: { name: '糙米', facts: { price: '$16.69' } } } } };
function device(storage = new Map(), limit = Infinity) {
  const localStorage = { getItem: k => storage.get(k) || null, setItem: (k, v) => {
    const next = new Map(storage); next.set(k, v);
    if ([...next.values()].reduce((n, value) => n + value.length, 0) > limit) {
      const error = new Error('Storage full'); error.name = 'QuotaExceededError'; throw error;
    }
    storage.set(k, v);
  }, removeItem: k => storage.delete(k) };
  const context = vm.createContext({ localStorage, window: { localStorage, setTimeout: () => 1, clearTimeout() {} },
    document: { getElementById: () => ({}) }, render() {},
    fetch: async (_, options) => {
      if (options.method === 'POST') {
        if (server.fail) return { ok: false, status: 503 };
        server.data = JSON.parse(options.body);
        if (server.onPost) server.onPost();
        return { ok: true };
      }
      return { ok: true, json: async () => JSON.parse(JSON.stringify(server.data)) };
    }
  });
  vm.runInContext(code + '\nshoppingSyncKey="test";', context);
  return {
    storage,
    persist: () => context.persistItemEditState(),
    photo: () => vm.runInContext(`itemEdits[${JSON.stringify(id)}]?.photo`, context),
    edit(price) { vm.runInContext(`itemEdits[${JSON.stringify(id)}] = {name:'糙米',facts:{price:${JSON.stringify(price)}}}; pendingEdits[${JSON.stringify(id)}] = itemEdits[${JSON.stringify(id)}]; savePendingEdits(); saveItemEdits();`, context); },
    sync: () => context.syncShoppingDevices(),
    pending: () => { const saved = JSON.parse(storage.get('smart-shopping-item-edits-v1')); return Object.fromEntries(saved.pendingKeys.map(key => [key, saved.items[key]])); },
    price: () => vm.runInContext(`itemEdits[${JSON.stringify(id)}]?.facts.price`, context)
  };
}
(async () => {
  // A nearly full browser can save an existing photo without duplicating it
  // into a pending outbox. Legacy unsynced data remains authoritative on reload.
  const photo = 'data:image/png;base64,' + 'a'.repeat(10000);
  const oldItem = { name: 'Yeast', facts: { price: '$7.691' }, photo };
  const unsynced = { ...oldItem, facts: { price: '$7.691', weight: '2lb' } };
  const legacy = new Map([
    ['smart-shopping-item-edits-v1', JSON.stringify({ [id]: oldItem })],
    ['smart-shopping-pending-edits-v1', JSON.stringify({ [id]: unsynced })],
  ]);
  const migrated = device(legacy, 22000);
  assert.equal(migrated.photo(), photo);
  migrated.persist();
  assert.equal(legacy.has('smart-shopping-pending-edits-v1'), false);
  assert.equal((legacy.get('smart-shopping-item-edits-v1').match(/data:image/g) || []).length, 1);
  assert.equal(migrated.pending()[id].facts.weight, '2lb');
  const offlineReload = device(legacy, 12000);
  offlineReload.persist();
  assert.equal(offlineReload.photo(), photo);
  assert.equal(offlineReload.pending()[id].facts.weight, '2lb');
  const before = new Map(legacy);
  const full = device(legacy, 100);
  assert.throws(() => full.persist(), { name: 'QuotaExceededError' });
  assert.deepEqual(legacy, before);
  console.log('PASS: legacy migration, photo stored once, offline reload, atomic quota failure');
  const phone = device();
  await phone.sync();
  phone.edit('$18.99');
  await phone.sync();
  assert.equal(phone.price(), '$18.99');
  assert.equal(server.data.itemEdits[id].facts.price, '$18.99');
  assert.deepEqual(phone.pending(), {});
  const laptop = device();
  await laptop.sync();
  assert.equal(laptop.price(), '$18.99');
  phone.edit('$19.99');
  server.fail = true;
  await phone.sync();
  assert.equal(phone.pending()[id].facts.price, '$19.99');
  const reloaded = device(phone.storage);
  assert.equal(reloaded.price(), '$19.99');
  server.fail = false;
  await reloaded.sync();
  assert.equal(server.data.itemEdits[id].facts.price, '$19.99');
  reloaded.edit('$20.99');
  server.onPost = () => reloaded.edit('$21.99');
  await reloaded.sync();
  assert.equal(reloaded.pending()[id].facts.price, '$21.99');
  server.onPost = null;
  await reloaded.sync();
  assert.equal(server.data.itemEdits[id].facts.price, '$21.99');
  await laptop.sync();
  assert.equal(laptop.price(), '$21.99');
  console.log('PASS: stale server edit, second device, failed upload/reload, edit during upload, subsequent remote update');
})().catch(error => { console.error(error); process.exitCode = 1; });
