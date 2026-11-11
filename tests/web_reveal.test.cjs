// Execute the shipped frontend with controlled network timing and a minimal DOM.
// This covers async privacy logic, not full browser layout or browser APIs.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../hakimino/web/app.js'), 'utf8');
const MASK = '••••••••••••••••';

async function fixture() {
  const nodes = new Map(), events = {}, windowEvents = {}, timers = new Map();
  let timerId = 0, reply, calls = 0, payload;
  function node(id) {
    if (!nodes.has(id)) nodes.set(id, {
      textContent: '', innerHTML: '', content: 'synthetic-csrf', value: '',
      focus() {}, querySelector() { return node('dialog-button'); },
    });
    return nodes.get(id);
  }
  const buttons = ['reveal', 'hide'].map(action => ({dataset: {action}, disabled: false}));
  const document = {
    hidden: false, getElementById: node, querySelector: node,
    querySelectorAll: () => buttons,
    addEventListener: (name, fn) => { events[name] = fn; },
  };
  const context = vm.createContext({
    FormData: class { constructor(form) { return form.testFields; } },
    document, window: {addEventListener: (name, fn) => { windowEvents[name] = fn; }},
    fetch: async () => ({ok: true, json: async () => ({unlocked: false, labels: []})}),
    setTimeout(fn, delay) { timers.set(++timerId, {fn, delay}); return timerId; },
    clearTimeout(id) { timers.delete(id); }, setInterval() {},
  });
  vm.runInContext(source, context);
  await new Promise(setImmediate); // Finish the real script's initial status request.
  const run = code => vm.runInContext(code, context);
  run("state={unlocked:true,labels:['school'],name:'test.vault',vault_epoch:1,vault_revision:'original-revision'};selected='school';");
  context.fetch = (_, options) => {
    calls++;
    payload = JSON.parse(options.body);
    return new Promise(resolve => { reply = resolve; });
  };
  return {
    node, nodes, run, document, events, windowEvents, timers, buttons,
    get calls() { return calls; },
    get payload() { return payload; },
    reply(data = {password: 'synthetic-test-password'}, ok = true) {
      reply({ok, json: async () => data});
    },
  };
}

test('an explicit visible reveal succeeds and expires after 15 seconds', async () => {
  const f = await fixture();
  const pending = f.run("act('reveal')");
  f.reply(); await pending;
  assert.equal(f.node('visible-password').textContent, 'synthetic-test-password');
  const timeout = [...f.timers.values()].find(timer => timer.delay === 15000);
  assert.ok(timeout);
  timeout.fn();
  assert.equal(f.node('visible-password').textContent, MASK);
});

const interruptions = {
  'tab hidden': f => { f.document.hidden = true; f.events.visibilitychange(); },
  'tab hidden then visible before reply': f => {
    f.document.hidden = true; f.events.visibilitychange();
    f.document.hidden = false; f.events.visibilitychange();
  },
  'page hidden': f => f.windowEvents.pagehide(),
  'manual hide while request is busy': f => {
    assert.equal(f.buttons.find(b => b.dataset.action === 'hide').disabled, false);
    f.run("act('hide')");
  },
  'vault locked and view rendered': f => f.run("state={unlocked:false,labels:[]};render()"),
  'entry changed': f => f.run("selected='different-entry'"),
  'same vault revision changed': f => f.run("state.vault_revision='replacement-revision'"),
  'same vault reopened': f => f.run("state.vault_epoch=2"),
  'password view replaced': f => f.nodes.set('visible-password', {textContent: MASK}),
};
for (const [name, interrupt] of Object.entries(interruptions)) {
  test(`ignore a delayed reveal after ${name}`, async () => {
    const f = await fixture();
    const original = f.node('visible-password');
    const pending = f.run("act('reveal')");
    interrupt(f);
    f.reply(); await pending;
    assert.equal(original.textContent, MASK);
    assert.equal(f.node('visible-password').textContent, MASK);
    assert.equal([...f.timers.values()].some(timer => timer.delay === 15000), false);
  });
}

test('a hidden page cannot start a reveal request', async () => {
  const f = await fixture();
  f.document.hidden = true;
  await f.run("act('reveal')");
  assert.equal(f.calls, 0);
  assert.equal(f.node('visible-password').textContent, MASK);
});

test('returning to the tab requires a fresh explicit reveal', async () => {
  const f = await fixture();
  let pending = f.run("act('reveal')");
  f.document.hidden = true; f.events.visibilitychange();
  f.document.hidden = false; f.events.visibilitychange();
  f.reply(); await pending;
  assert.equal(f.node('visible-password').textContent, MASK);
  pending = f.run("act('reveal')");
  f.reply(); await pending;
  assert.equal(f.node('visible-password').textContent, 'synthetic-test-password');
});

test('a stale reveal carries its original unlock and clears the old view', async () => {
  const f = await fixture();
  const pending = f.run("act('reveal')");
  assert.equal(f.payload.vault_epoch, 1);
  f.reply({unlocked: false, kind: 'access', error: 'The open vault changed.'}, false);
  await pending;
  assert.equal(f.run('state.unlocked'), false);
  assert.equal(f.node('visible-password').textContent, MASK);
});

test('status polling clears the old view when a different unlock is active', async () => {
  const f = await fixture();
  f.node('visible-password').textContent = 'synthetic-test-password';
  const pending = f.run('refreshStatus()');
  f.reply({unlocked: true, name: 'another.vault', labels: ['school'], vault_epoch: 2});
  await pending;
  assert.equal(f.run('state.unlocked'), false);
  assert.equal(f.node('visible-password').textContent, MASK);
});


test('reveal sends the viewed ciphertext revision', async () => {
  const f = await fixture();
  const pending = f.run("act('reveal')");
  assert.equal(f.payload.vault_revision, 'original-revision');
  f.reply(); await pending;
});

test('delete preserves the revision captured before confirmation', async () => {
  const f = await fixture();
  f.run("window.confirm=()=>{state.vault_revision='replacement-revision';return true}");
  const pending = f.run("act('delete')");
  assert.equal(f.payload.vault_revision, 'original-revision');
  assert.equal(f.payload.label, 'school');
  f.reply({unlocked:false,kind:'access',error:'The vault changed.'}, false);
  await pending;
  assert.equal(f.run('state.unlocked'), false);
  assert.equal(f.node('visible-password').textContent, MASK);
});

test('polling masks and clears a same-unlock changed revision', async () => {
  const f = await fixture();
  f.node('visible-password').textContent = 'synthetic-test-password';
  const pending = f.run('refreshStatus()');
  f.reply({unlocked:true,labels:['school'],vault_epoch:1,vault_revision:'replacement-revision'});
  await pending;
  assert.equal(f.run('state.unlocked'), false);
  assert.equal(f.node('visible-password').textContent, MASK);
});

test('unchanged polling does not disrupt the selected entry', async () => {
  const f = await fixture();
  const pending = f.run('refreshStatus()');
  f.reply({unlocked:true,labels:['school'],vault_epoch:1,vault_revision:'original-revision'});
  await pending;
  assert.equal(f.run('state.unlocked'), true);
  assert.equal(f.run('selected'), 'school');
});


for (const [count, expected] of [[0, '0 entries'], [1, '1 entry'], [2, '2 entries']]) {
  test(`workspace count uses correct English for ${count} records`, async () => {
    const f = await fixture();
    f.run(`state.labels=Array(${count}).fill('school');render()`);
    assert.ok(f.node('screen').innerHTML.includes(` · ${expected}</span>`));
  });
}

function assertLockedFilename(f, expected) {
  const html = f.node('screen').innerHTML;
  assert.ok(html.includes(`name="name" value="${expected}"`));
  const masterInput = html.match(/<input id="master"[^>]*>/)[0];
  assert.ok(masterInput.includes('type="password"'));
  assert.equal(/\bvalue=/.test(masterInput), false);
  assert.equal(html.includes('synthetic-master-only'), false);
}

test('successful explicit lock retains only the last filename', async () => {
  const f = await fixture();
  f.run("state.name='presentation.vault';render()");
  const pending = f.run("act('lock')");
  f.reply({unlocked:false,labels:[],name:null}); await pending;
  assertLockedFilename(f, 'presentation.vault');
});

for (const action of ['unlock', 'create']) {
  test(`failed ${action} retains the attempted filename without the passphrase`, async () => {
    const f = await fixture();
    const pending = f.run(`act('${action}',{name:'attempted.vault',master:'synthetic-master-only'})`);
    f.reply({unlocked:false,kind:'access',error:'Cannot open this vault.'}, false);
    await pending;
    assertLockedFilename(f, 'attempted.vault');
    assert.equal(f.run('state.unlocked'), false);
  });
}

test('status expiry remembers the viewed vault rather than another client vault', async () => {
  const f = await fixture();
  f.run("state.name='intended.vault';render()");
  const pending = f.run('refreshStatus()');
  f.reply({unlocked:true,labels:[],name:'another.vault',vault_epoch:2,vault_revision:'other'});
  await pending;
  assertLockedFilename(f, 'intended.vault');
});

test('network failure retains the filename while clearing the unlocked view', async () => {
  const f = await fixture();
  f.run("state.name='offline.vault';render()");
  const pending = f.run("act('lock')");
  f.reply({}, false); await pending;
  assertLockedFilename(f, 'offline.vault');
  assert.equal(f.run('state.unlocked'), false);
});

test('server expiry retains the last filename', async () => {
  const f = await fixture();
  f.run("state.name='expired.vault';render()");
  const pending = f.run('refreshStatus()');
  f.reply({unlocked:false,labels:[],name:null}); await pending;
  assertLockedFilename(f, 'expired.vault');
});

test('successful unlock updates the remembered filename for the next lock', async () => {
  const f = await fixture();
  const pending = f.run("act('unlock',{name:'second.vault',master:'synthetic-master-only'})");
  f.reply({unlocked:true,labels:[],name:'second.vault',vault_epoch:2,vault_revision:'new'});
  await pending;
  f.run("state={unlocked:false,labels:[],name:null};render()");
  assertLockedFilename(f, 'second.vault');
});

test('a rejected filename is escaped before rendering into an attribute', async () => {
  const f = await fixture();
  const pending = f.run(`act('unlock',{name:'bad"<>&.vault',master:'synthetic-master-only'})`);
  f.reply({unlocked:false,kind:'input',error:'Invalid filename.'}, false); await pending;
  assertLockedFilename(f, 'bad&quot;&lt;&gt;&amp;.vault');
  assert.equal(f.node('screen').innerHTML.includes('value="bad"<>&.vault"'), false);
});

test('form submission clears the password field before sending the request', async () => {
  const f = await fixture();
  f.node('master').value = 'synthetic-master-only';
  f.events.submit({preventDefault() {}, target:{id:'unlock-form',testFields:[
    ['name','submitted.vault'],['master','synthetic-master-only'],
  ]},submitter:{value:'unlock'}});
  assert.equal(f.node('master').value, '');
  assert.equal(f.payload.name, 'submitted.vault');
  f.reply({unlocked:false,kind:'access',error:'Incorrect password.'}, false);
  await new Promise(setImmediate);
  assertLockedFilename(f, 'submitted.vault');
});

test('a fresh page starts with the default filename, not a persisted credential', async () => {
  const first = await fixture();
  first.run("vaultName='previous-page.vault'");
  const second = await fixture();
  assert.equal(second.run('vaultName'), 'ui-test.vault');
  // The fixture exposes no localStorage/sessionStorage. Any use would fail.
});
