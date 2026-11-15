// alexa-voice-announcer: make an Echo or the Alexa app speak any text, free and unlimited, from your own server.
//
// Sign in once through the local login proxy (http://localhost:3456, reach it over an SSH tunnel); the session is saved
// in cookie.json (mode 600) and refreshed automatically. Local HTTP API on 127.0.0.1:8095 (never expose it):
//
//   GET  /status              -> {ready, login}
//   GET  /devices             -> speakers on the account (Echo devices and Alexa app instances)
//   GET  /devices/all         -> everything on the account, with device types
//   GET  /routines            -> your Alexa routines (to see how other tools trigger devices)
//   POST /speak {text, device?, mode?, skill?}
//        mode "announcement" (default) : Alexa announcement with chime (Echo devices)
//        mode "speak"                  : plain text-to-speech (Echo devices)
//        mode "launch"                 : opens your skill on the device (works on Echo AND the Alexa phone app);
//                                        your skill then speaks whatever you queued for it (see ../skill)
const fs = require('fs');
const path = require('path');
const http = require('http');
const Alexa = require('alexa-remote2');

const HERE = __dirname;
const COOKIE = path.join(HERE, 'cookie.json');
const env = { ...process.env };
try {
    for (const l of fs.readFileSync(path.join(HERE, 'echo.env'), 'utf8').split('\n')) {
        const m = l.match(/^\s*([A-Z_]+)\s*=\s*(.*?)\s*$/);
        if (m && !l.trim().startsWith('#')) env[m[1]] = m[2];
    }
} catch (e) { /* echo.env is optional */ }

const PAGE = env.AMAZON_PAGE || 'amazon.com';          // your Alexa region: amazon.com, amazon.in, amazon.co.uk, amazon.de ...
const BASE = env.BASE_AMAZON_PAGE || 'amazon.com';     // sign-in host; amazon.com works for most regions (amazon.co.jp for Japan)
const LANG = env.ACCEPT_LANGUAGE || 'en-US';
const LOCALE = env.LOCALE || LANG;
const DEVICE = env.ECHO_DEVICE || '';                  // device name or serial; empty = first online speaker
const MODE = env.DEFAULT_MODE || 'announcement';
const SKILL = env.SKILL_ID || '';                      // your custom skill's ID, for mode "launch"
const PORT = Number(env.PORT || 8095);
const PROXY_PORT = Number(env.PROXY_PORT || 3456);

let ready = false;
let loginMsg = '';
let saved = null;
try { saved = JSON.parse(fs.readFileSync(COOKIE, 'utf8')); } catch (e) { /* first run: sign in through the proxy */ }

const alexa = new Alexa();
alexa.on('cookie', () => {
    try {
        fs.writeFileSync(COOKIE, JSON.stringify(alexa.cookieData || {}), { mode: 0o600 });
        console.log('session saved');
    } catch (e) { console.log('could not save the session:', e.message); }
});

alexa.init({
    cookie: saved || undefined,
    proxyOnly: true,
    proxyOwnIp: 'localhost',
    proxyPort: PROXY_PORT,
    proxyListenBind: '127.0.0.1',
    proxyLogLevel: 'warn',
    amazonPage: PAGE,
    baseAmazonPage: BASE,
    acceptLanguage: LANG,
    amazonPageProxyLanguage: LANG.replace('-', '_'),
    useWsMqtt: false,
    usePushConnection: false,
    // log outcomes only: never cookies, headers or authorization codes
    logger: (m) => { m = String(m); if (/SUCCESS|error|fail/i.test(m) && !/cookie[:=]|catched|Headers|authorization/i.test(m)) console.log(m.slice(0, 200)); },
}, (err) => {
    if (err) {
        loginMsg = String(err.message || err);
        console.log(`sign-in needed: open http://localhost:${PROXY_PORT} (through an SSH tunnel) and sign in to Amazon`);
        return;
    }
    ready = true;
    loginMsg = '';
    console.log('ready');
});

function speakers() {
    return Object.values(alexa.serialNumbers || {}).filter((d) =>
        (d.capabilities || []).length && !/^(THIRD_PARTY|WHA|AMAZON_ONE)/.test(d.deviceFamily || ''));
}

function pick(name) {
    const want = String(name || DEVICE).toLowerCase();
    const list = speakers();
    if (want) {
        const d = list.find((x) => (x.serialNumber || '').toLowerCase() === want || (x.accountName || '').toLowerCase() === want)
            || list.find((x) => (x.accountName || '').toLowerCase().includes(want));
        if (d) return d;
    }
    return list.find((x) => x.online) || list[0];
}

function launchSequence(d, skill) {
    return {
        '@type': 'com.amazon.alexa.behaviors.model.Sequence',
        'startNode': {
            '@type': 'com.amazon.alexa.behaviors.model.OpaquePayloadOperationNode',
            'type': 'Alexa.Operation.SkillConnections.Launch',
            'skillId': skill,
            'operationPayload': {
                'locale': LOCALE,
                'customerId': d.deviceOwnerCustomerId,
                'targetDevice': { 'deviceType': d.deviceType, 'deviceSerialNumber': d.serialNumber },
                'connectionRequest': { 'uri': `connection://AMAZON.Launch/${skill}`, 'input': {} },
            },
        },
    };
}

function send(res, code, obj) {
    res.writeHead(code, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(obj));
}

http.createServer((req, res) => {
    if (req.method === 'GET' && req.url === '/status') return send(res, 200, { ready, login: ready ? '' : (loginMsg || 'starting') });
    if (!ready) return send(res, 503, { ok: false, error: 'not signed in yet' });
    if (req.method === 'GET' && req.url === '/devices') {
        return send(res, 200, speakers().map((d) => ({ name: d.accountName, serial: d.serialNumber, family: d.deviceFamily, online: d.online })));
    }
    if (req.method === 'GET' && req.url === '/devices/all') {
        return send(res, 200, Object.values(alexa.serialNumbers || {}).map((d) => ({
            name: d.accountName, serial: d.serialNumber, family: d.deviceFamily, type: d.deviceType, online: d.online })));
    }
    if (req.method === 'GET' && req.url === '/routines') {
        return alexa.getAutomationRoutines((err, r) => {
            if (err) return send(res, 502, { ok: false, error: String(err.message || err) });
            send(res, 200, (r || []).map((x) => ({ name: x.name, status: x.status, triggers: x.triggers, sequence: x.sequence })));
        });
    }
    if (req.method === 'POST' && req.url === '/speak') {
        let body = '';
        req.on('data', (c) => { body += c; if (body.length > 20000) req.destroy(); });
        req.on('end', () => {
            let j;
            try { j = JSON.parse(body || '{}'); } catch (e) { return send(res, 400, { ok: false, error: 'bad json' }); }
            const mode = j.mode || MODE;
            const text = String(j.text || '').trim().slice(0, 1000);
            if (!text && mode !== 'launch') return send(res, 400, { ok: false, error: 'no text' });
            const d = pick(j.device);
            if (!d) return send(res, 404, { ok: false, error: 'no Echo or Alexa app found on this account' });
            let command = mode === 'speak' ? 'speak' : 'announcement';
            if (mode === 'launch') {
                const skill = String(j.skill || SKILL);
                if (!skill) return send(res, 400, { ok: false, error: 'mode launch needs SKILL_ID' });
                command = launchSequence(d, skill);
            }
            try {
                alexa.sendSequenceCommand(d.serialNumber, command, text || 'launch', (err) => {
                    if (err) return send(res, 502, { ok: false, error: String(err.message || err) });
                    send(res, 200, { ok: true, device: d.accountName, mode });
                });
            } catch (e) { send(res, 500, { ok: false, error: e.message }); }
        });
        return;
    }
    send(res, 404, { ok: false, error: 'not found' });
}).listen(PORT, '127.0.0.1', () => console.log(`alexa-voice-announcer on 127.0.0.1:${PORT}`));
