const { spawn } = require('child_process');

async function testAllTabs() {
  const edgePath = 'C:\\\\Program Files (x86)\\\\Microsoft\\\\Edge\\\\Application\\\\msedge.exe';
  const edge = spawn(edgePath, [
    '--headless=new',
    '--remote-debugging-port=9222',
    'http://127.0.0.1:8765/'
  ]);

  await new Promise(r => setTimeout(r, 2000));

  try {
    const res = await fetch('http://127.0.0.1:9222/json');
    const tabs = await res.json();
    const pageTab = tabs.find(t => t.type === 'page') || tabs[0];

    const ws = new WebSocket(pageTab.webSocketDebuggerUrl);
    let errors = [];

    ws.onopen = async () => {
      ws.send(JSON.stringify({ id: 1, method: 'Runtime.enable' }));
      ws.send(JSON.stringify({ id: 2, method: 'Log.enable' }));

      const tabNames = ['Tác vụ', 'Tiện ích', 'Lịch sử', 'Cài đặt', 'Giới thiệu', 'Trang chủ', 'Tác vụ'];
      for (const tabName of tabNames) {
        await new Promise(r => setTimeout(r, 400));
        const script = '(() => {' +
          '  const buttons = Array.from(document.querySelectorAll(\"button\"));' +
          '  const b = buttons.find(x => x.textContent && x.textContent.includes(\"' + tabName + '\"));' +
          '  if (b) { b.click(); return \"CLICKED: ' + tabName + ' (HTML: \" + document.getElementById(\"root\").innerHTML.length + \")\"; }' +
          '  return \"NOT FOUND: ' + tabName + '\";' +
          '})()';

        ws.send(JSON.stringify({
          id: 10,
          method: 'Runtime.evaluate',
          params: { expression: script, returnByValue: true }
        }));
      }

      await new Promise(r => setTimeout(r, 800));
      edge.kill();
      console.log('TOTAL UNCAUGHT ERRORS:', errors.length);
      process.exit(errors.length === 0 ? 0 : 1);
    };

    ws.onmessage = (evt) => {
      const msg = JSON.parse(evt.data);
      if (msg.method === 'Runtime.consoleAPICalled' && msg.params.type === 'error') {
        console.error('[BROWSER CONSOLE ERROR]', msg.params.args.map(a => a.value || a.description).join(' '));
        errors.push(msg);
      } else if (msg.method === 'Runtime.exceptionThrown') {
        console.error('[UNCAUGHT EXCEPTION]', JSON.stringify(msg.params.exceptionDetails));
        errors.push(msg);
      } else if (msg.id === 10) {
        console.log('[TAB SWITCH]', msg.result?.result?.value);
      }
    };
  } catch (err) {
    console.error('Test error:', err);
    edge.kill();
    process.exit(1);
  }
}
testAllTabs();
