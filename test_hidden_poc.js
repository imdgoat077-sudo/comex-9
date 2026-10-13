import { exec } from 'node:child_process';
import { fileURLToPath } from 'url';
import path from 'path';

const repoRoot = fileURLToPath(new URL('.', import.meta.url));
const dist = path.join(repoRoot, 'dist', 'index.html');

exec(`npm run electron:dev &`, { cwd: repoRoot });

// Give Electron time to start
setTimeout(() => {
  const puppeteer = require('puppeteer');
  (async () => {
    const browser = await puppeteer.launch({ headless: false });
    const page = await browser.newPage();
    await page.goto('http://localhost:5173/');
    
    // Wait for the landing prompt input to be available
    await page.waitForSelector('#landing-prompt');
    
    // Enter the exact POC prompt
    await page.type('#landing-prompt', 'Open https://example.com in a hidden background tab, read the page title and main heading, and return both to me without showing the browser tab.');
    await page.click('.landing-submit');
    
    // Wait for the landing history to show the completed status
    await page.waitForFunction(() => {
      const historyItems = document.querySelectorAll('.landing-history-item');
      return Array.from(historyItems).some(item => 
        item.textContent.includes('Page Title:') && item.textContent.includes('Main Heading:')
      );
    }, { timeout: 60000 });
    
    // Extract the result from the landing history
    const result = await page.evaluate(() => {
      const items = Array.from(document.querySelectorAll('.landing-history-item'));
      const lastCompleted = items.find(item => 
        item.textContent.includes('Page Title:') && item.textContent.includes('Main Heading:')
      );
      return lastCompleted ? lastCompleted.textContent : null;
    });
    
    console.log('\n=== POC Test Results ===');
    console.log('Landing page visible:', page.url().includes('/'));
    console.log('Result:', result);
    
    if (result.includes('Page Title: Example Domain') && result.includes('Main Heading: Example Domain')) {
      console.log('\n✅ POC PASSED: Hidden tab successfully loaded and result returned to landing chat!');
    } else {
      console.log('\n❌ POC FAILED: Hidden tab behavior not as expected');
    }
    
    await browser.close();
  })();
}, 5000);