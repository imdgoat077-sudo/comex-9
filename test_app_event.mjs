import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

async function runTest() {
  const source = await readFile('src/App.jsx', 'utf8');

  // Extract the contents of the try/catch block inside handleSearch
  // We want the part starting from `const result = await classifyIntent(prompt);`
  // up to the end of the catch block.
  const tryCatchMatch = source.match(/try\s*\{\s*const result = await classifyIntent\(prompt\);([\s\S]*?)\}\s*catch\s*\(err\)\s*\{([\s\S]*?)\}/);
  assert.ok(tryCatchMatch, "Could not find the intent handling logic in App.jsx");

  const tryBlock = `const result = await classifyIntent(prompt);\n` + tryCatchMatch[1];

  let dispatchedEvents = [];

  // Mock DOM and React environment
  const env = {
    window: {
      dispatchEvent: (event) => {
        dispatchedEvents.push(event);
      },
      nexusNative: {}
    },
    CustomEvent: class {
      constructor(type, options) {
        this.type = type;
        this.detail = options?.detail;
      }
    },
    requestAnimationFrame: (cb) => cb(),
    setTabs: () => {},
    setActiveTabId: () => {},
    setIsChatOpen: () => {},
    getTitleFromUrl: (url) => url,
    console: { error: () => {} }
  };

  async function executeLogic(prompt, mockResult) {
    dispatchedEvents = [];
    const classifyIntent = async () => mockResult;
    
    // We execute the extracted logic in an AsyncFunction with our mocked globals
    const AsyncFunction = Object.getPrototypeOf(async function(){}).constructor;
    const fn = new AsyncFunction(
      'prompt', 'classifyIntent', 
      'window', 'CustomEvent', 'requestAnimationFrame', 
      'setTabs', 'setActiveTabId', 'setIsChatOpen', 'getTitleFromUrl', 'console',
      tryBlock
    );
    
    await fn(
      prompt, classifyIntent,
      env.window, env.CustomEvent, env.requestAnimationFrame,
      env.setTabs, env.setActiveTabId, env.setIsChatOpen, env.getTitleFromUrl, env.console
    );
    
    return dispatchedEvents;
  }

  // Test Case A: Research classification
  let events = await executeLogic("Some research task", { intent: 'research', confidence: 0.9 });
  assert.equal(events.length, 1, "Should dispatch exactly one event for research");
  assert.equal(events[0].type, 'comex-landing-prompt');
  assert.equal(events[0].detail.intent, 'research', "Event detail should contain intent: 'research'");

  // Test Case B: Visible browser task classification
  events = await executeLogic("Open browser", { intent: 'visible_browser_task', confidence: 0.9 });
  assert.equal(events.length, 1, "Should dispatch exactly one event for visible browser task");
  assert.equal(events[0].type, 'comex-landing-prompt');
  assert.equal(events[0].detail.intent, 'visible_browser_task', "Event detail should contain intent: 'visible_browser_task'");

  // Test fallback logic
  events = await executeLogic("Some task", null); // Error or undefined intent
  assert.equal(events.length, 1);
  assert.equal(events[0].detail.intent, undefined, "Event detail intent should be undefined on fallback");

  console.log("PASS: Frontend intent dispatch logic verified for both 'research' and 'visible_browser_task' cases.");
}

runTest().catch(err => {
  console.error("Test failed:", err);
  process.exit(1);
});
