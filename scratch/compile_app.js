const fs = require('fs');
const path = require('path');
const Babel = require('./babel.min.js');

const htmlPath = path.join(__dirname, '..', 'src', 'ui', 'index.html');
const outPath = path.join(__dirname, '..', 'src', 'ui', 'assets', 'app.js');

const html = fs.readFileSync(htmlPath, 'utf-8');
const startTag = '<script type="text/babel">';
const endTag = '</script>';
const startIndex = html.indexOf(startTag);
const endIndex = html.indexOf(endTag, startIndex);

if (startIndex === -1 || endIndex === -1) {
  console.error('No script found');
  process.exit(1);
}

const jsx = html.substring(startIndex + startTag.length, endIndex);
const res = Babel.transform(jsx, {
  presets: [['react', { runtime: 'classic' }]]
});
const finalCode = res.code;
fs.writeFileSync(outPath, finalCode, 'utf-8');
const stat = fs.statSync(outPath);
console.log('SUCCESS: Precompiled classic app.js written, size: ' + stat.size + ' bytes');