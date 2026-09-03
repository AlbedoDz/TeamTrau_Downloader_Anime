const fs = require('fs');
const vm = require('vm');

const reactCode = fs.readFileSync('src/ui/assets/react.production.min.js', 'utf-8');
const reactDomCode = fs.readFileSync('src/ui/assets/react-dom.production.min.js', 'utf-8');
const appCode = fs.readFileSync('src/ui/assets/app.js', 'utf-8');

const sandbox = {
  window: {},
  document: {
    getElementById: () => ({ appendChild: () => {} }),
    addEventListener: () => {},
  },
  navigator: { clipboard: { writeText: () => {} } },
  fetch: () => Promise.resolve({ ok: true, json: () => Promise.resolve({ tasks: [], counts: {} }) }),
  console: console,
  setInterval: () => 1,
  clearInterval: () => {},
  setTimeout: (fn) => fn(),
  clearTimeout: () => {},
};
sandbox.window = sandbox;
sandbox.self = sandbox;
sandbox.global = sandbox;

try {
  vm.createContext(sandbox);
  vm.runInContext(reactCode, sandbox);
  vm.runInContext(reactDomCode, sandbox);
  vm.runInContext(appCode, sandbox);
  console.log('SUCCESS: app.js parsed and executed without syntax error!');
} catch (err) {
  console.error('ERROR executing app.js:', err);
}
