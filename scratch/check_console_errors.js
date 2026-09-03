const { spawn } = require('child_process');

async function run() {
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
    console.log('Connected to tab:', pageTab.title, pageTab.url);

    const ws = new WebSocket(pageTab.webSocketDebuggerUrl);
    ws.onopen = () => {
      ws.send(JSON.stringify({ id: 1, method: 'Runtime.enable' }));
      ws.send(JSON.stringify({ id: 2, method: 'Log.enable' }));

      setTimeout(() => {
        const script = '(() => {' +
          '  const buttons = Array.from(document.querySelectorAll(\"button\"));' +
          '  const tasksBtn = buttons.find(b => b.textContent && b.textContent.includes(\"Tác vụ\"));' +
          '  if (tasksBtn) {' +
          '    tasksBtn.click();' +
          '    return \"CLICKED TÁC VỤ TAB SUCCESS\";' +
          '  }' +
          '  return \"NO BUTTON FOUND: \" + buttons.map(b => b.textContent).slice(0, 5).join(\" | \");' +
          '})()';

        ws.send(JSON.stringify({
          id: 3,
          method: 'Runtime.evaluate',
          params: { expression: script, returnByValue: true }
        }));
      }, 1500);

      setTimeout(() => {
        ws.send(JSON.stringify({
          id: 4,
          method: 'Runtime.evaluate',
          params: { expression: 'document.getElementById(\"root\").innerHTML', returnByValue: true }
        }));
      }, 3000);

      setTimeout(() => {
        edge.kill();
        process.exit(0);
      }, 4500);
    };

    ws.onmessage = (evt) => {
      const msg = JSON.parse(evt.data);
      if (msg.method === 'Runtime.consoleAPICalled') {
        console.log('[BROWSER CONSOLE]', msg.params.type, msg.params.args.map(a => a.value || a.description).join(' '));
      } else if (msg.method === 'Runtime.exceptionThrown') {
        console.error('[BROWSER UNCAUGHT EXCEPTION]', JSON.stringify(msg.params.exceptionDetails, null, 2));
      } else if (msg.id === 3) {
        console.log('[CLICK RESULT]', msg.result?.result?.value);
      } else if (msg.id === 4) {
        console.log('[ROOT HTML LENGTH AFTER CLICK]', msg.result?.result?.value?.length);
      }
    };
  } catch (err) {
    console.error('Edge debug connection error:', err);
    edge.kill();
  }
}
run();
