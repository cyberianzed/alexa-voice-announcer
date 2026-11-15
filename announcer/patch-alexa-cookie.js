// Runs after `npm install`. alexa-cookie2's login proxy looks for Amazon's final sign-in redirect in
// proxyRes.socket.parser.outgoing, which is empty on Node 20+, so the sign-in "succeeds" but is never caught
// (you land on an Amazon "page not found"). This adds the request URL to the places it checks. Idempotent.
const fs = require('fs');
const path = require('path');

const file = path.join(__dirname, 'node_modules', 'alexa-cookie2', 'lib', 'proxy.js');
if (!fs.existsSync(file)) {
    console.log('patch: alexa-cookie2 not installed yet, skipped');
    process.exit(0);
}
let s = fs.readFileSync(file, 'utf8');
if (s.includes('url, // alexa-voice-announcer patch')) {
    console.log('patch: already applied');
    process.exit(0);
}
const anchor = '        const successUrl = [\n';
if (!s.includes(anchor)) {
    console.log('patch: anchor not found (alexa-cookie2 changed?); sign-in may still work, skipping');
    process.exit(0);
}
s = s.replace(anchor, anchor + '            url, // alexa-voice-announcer patch: Node 20+ has no parser.outgoing here\n');
fs.writeFileSync(file, s);
console.log('patch: applied to alexa-cookie2/lib/proxy.js');
