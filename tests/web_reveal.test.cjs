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
    document, window: {addEventListener: (name, fn) => { windowEvents[name] = fn; }},
    fetch: async () => ({ok: true, json: async () => ({unlocked: false, labels: []})}),
    setTimeout(fn, delay) { timers.set(++timerId, {fn, delay}); return timerId; },
    clearTimeout(id) { timers.delete(id); }, setInterval() {},
  });
  vm.runInContext(source, context);
  await new Promise(setImmediate); // Finish the real script's initial status request.
  const run = code => vm.runInContext(code, context);
  run("state={unlocked:true,labels:['school'],name:'test.vault',vault_epoch:1};selected='school';");
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
