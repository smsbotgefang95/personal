const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const html = fs.readFileSync('smart-shopping.html', 'utf8');
const code = html.slice(html.indexOf('    function reportItemSaveError('), html.indexOf('    function saveItemEdit('));
const status = { textContent: '' };
let closed = false;
let failing = true;
const context = vm.createContext({
  editDirty: true, photoLoading: false,
  document: { getElementById: () => status }, showToast() {},
  editSession: { mode: 'edit' },
  els: { editModal: { classList: { remove() { closed = true; } } }, photoInput: {} },
  setStoreOptionsOpen() {}, setPhotoPreview() {},
  saveItemEdit() {
    if (failing) return context.reportItemSaveError('Browser storage is full.');
    return true;
  },
});
vm.runInContext(code, context);
context.closeItemEditor();
assert.equal(status.textContent, 'Browser storage is full.');
assert.equal(closed, false);
assert.equal(context.editDirty, true);
failing = false;
context.closeItemEditor();
assert.equal(closed, true);
assert.equal(context.editDirty, false);
assert.equal(status.textContent, 'Saved in this browser.');
console.log('PASS: storage error persists, failed editor stays open and dirty, retry saves and closes');

const persistenceCode = html.slice(html.indexOf('    function persistItemEditState('), html.indexOf('    function savePendingEdits('));
const writes = [];
const persistenceContext = vm.createContext({
  itemEdits: {
    synced: { name: 'Already synced', photo: 'data:image/jpeg;base64,' + 'x'.repeat(1000) },
    pending: { name: 'Needs upload', photo: 'data:image/jpeg;base64,small' },
  },
  pendingEdits: { pending: { name: 'Needs upload' } },
  localStorage: {
    setItem(key, value) { writes.push([key, value]); },
    removeItem() {},
  },
  itemEditsStorageKey: 'edits',
  pendingEditsStorageKey: 'legacy',
});
vm.runInContext(persistenceCode, persistenceContext);
persistenceContext.persistItemEditState();
const persisted = JSON.parse(writes[0][1]);
assert.deepEqual(Object.keys(persisted.items), ['pending']);
assert.deepEqual(persisted.pendingKeys, ['pending']);
assert.equal(persisted.items.synced, undefined);
console.log('PASS: synced edits and their photos are not duplicated in localStorage');
