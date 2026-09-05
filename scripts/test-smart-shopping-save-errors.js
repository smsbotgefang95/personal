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
