const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const html = fs.readFileSync('smart-shopping.html', 'utf8');
const context = vm.createContext({ document: { createElement: () => ({ setAttribute() {} }) } });
vm.runInContext(html.slice(html.indexOf('    function prepareItemPhotos('), html.indexOf('    function median(')), context);
function image(complete = false, naturalWidth = 0, source = 'https://photos.anylist.com/backup.jpg') {
  return {
    dataset: { photoSource: source, photoFallback: '🥚' }, complete, naturalWidth,
    loading: 'lazy', src: 'missing.jpg', handlers: {},
    addEventListener(event, handler) { this.handlers[event] = handler; },
    replaceWith(element) { this.replacement = element; }
  };
}
const images = Array.from({ length: 13 }, () => image());
context.prepareItemPhotos({ querySelectorAll: () => images });
assert.equal(images[0].loading, 'eager');
assert.equal(images[11].loading, 'eager');
assert.equal(images[12].loading, 'lazy');
images[0].handlers.error();
assert.equal(images[0].src, images[0].dataset.photoSource);
images[0].handlers.error();
assert.equal(images[0].replacement.textContent, '🥚');
const cached = image(true);
const healthy = image(true, 1024);
const custom = image(true, 0, '');
context.prepareItemPhotos({ querySelectorAll: () => [cached, healthy, custom] });
assert.equal(cached.src, cached.dataset.photoSource);
assert.equal(healthy.src, 'missing.jpg');
assert.equal(custom.replacement.textContent, '🥚');
assert.match(html, /prepareItemPhotos\(els\.importedList\)/);
console.log('Photo loading, cached errors, backup and final fallback passed.');
