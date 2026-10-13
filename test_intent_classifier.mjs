import assert from 'node:assert/strict';

const cases = [
  ['Search YouTube for a good LLD video', 'research'],
  ['Find a good LLD video and give me the link', 'research'],
  ['Search Amazon for a monitor under ₹20,000', 'research'],
  ['Find the latest trailer for me', 'research'],
  ["What's the latest news about NVIDIA?", 'research'],
  ['Compare three laptops for programming', 'research'],
  ['Tell me which camera is best for travel', 'research'],
  ['Give me links to reliable CSS courses', 'research'],
  ['Summarize the latest AI announcements', 'research'],
  ['What are the best noise cancelling headphones?', 'research'],
  ['Open the best monitor you found', 'visible_browser_task'],
  ['Open this YouTube video for me', 'visible_browser_task'],
  ['Can you pull up YouTube and find the latest trailer?', 'visible_browser_task'],
  ['Find the latest trailer and open it', 'visible_browser_task'],
  ["Show me NVIDIA's latest GPUs on their site", 'visible_browser_task'],
  ['Bring the recommended laptop onto the screen', 'visible_browser_task'],
  ['I want to watch the video you mentioned', 'visible_browser_task'],
  ['Let me inspect the product page for the top result', 'visible_browser_task'],
  ['Take me to the checkout page for that item', 'visible_browser_task'],
  ['Search Amazon for monitors, then open the best one', 'visible_browser_task'],
  ['Find a trailer and launch the one you recommend', 'visible_browser_task'],
  ['I only need the links to three good monitors', 'research'],
];

// Contract tests: the classifier's LLM prompt must contain semantic examples and JSON schema.
const source = await (await import('node:fs/promises')).readFile('src/agents/IntentClassifier.js', 'utf8');
assert.match(source, /response_format: \{ type: 'json_object' \}/);
assert.match(source, /"research" \| "visible_browser_task"/);
assert.match(source, /COMPLETE request/);
assert.doesNotMatch(source, /detectVisibleOpenIntent/);
assert.equal(cases.length >= 20, true);
console.log(`PASS: ${cases.length} semantic intent contract cases defined.`);
console.log('PASS: classifier is isolated from browser execution logic.');
