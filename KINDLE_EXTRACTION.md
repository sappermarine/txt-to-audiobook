# Kindle Book Text Extraction Guide

Extract text from Kindle books you own using Kindle Cloud Reader + automated screenshots + macOS Vision OCR.

## Why OCR?

Amazon's Kindle Web Reader uses server-side rendering with scrambled glyph fonts. There's no accessible text in the DOM — just rendered images. OCR is the only reliable way to extract the text.

## Prerequisites

- Kindle book purchased on your Amazon account
- macOS (for Vision framework OCR)
- [Playwright MCP](https://github.com/anthropics/playwright-mcp) or any browser automation tool
- Swift (comes with Xcode / Command Line Tools)
- Python 3

## Step-by-Step Process

### 1. Open the book in Kindle Cloud Reader

Navigate to `https://read.amazon.com/?asin=YOUR_BOOK_ASIN`

Find the ASIN on the Amazon product page URL (the 10-character alphanumeric code, e.g., `B0G27GW4RR`).

Log in if prompted. Navigate to the beginning of the book via the Table of Contents.

### 2. Capture screenshots of every page

The `browser_run_code` script below automates "Next page" clicks and screenshots. Key settings:

- **2.5s wait** between pages (shorter causes errors and duplicate pages)
- **Page change detection** — verifies the page actually advanced before screenshotting
- **5 retry attempts** per page navigation failure

Update `TOTAL_PAGES_HERE` with your book's page count (visible in the reader's bottom bar). Note: Kindle shows 2 book pages per screen, so actual screenshots needed ≈ total_pages / 2.

```javascript
async (page) => {
  const screenshotDir = '/path/to/screenshots';
  const totalPages = TOTAL_PAGES_HERE;
  let pageNum = 1;

  async function getPageId() {
    return await page.evaluate(() => {
      const ci = document.querySelector('[role="contentinfo"]');
      return ci ? ci.innerText.trim() : '';
    });
  }

  let prevPageId = await getPageId();
  await page.screenshot({
    path: `${screenshotDir}/page_${String(pageNum).padStart(4, '0')}.png`,
    type: 'png'
  });

  for (let i = 2; i <= totalPages; i++) {
    let advanced = false;
    for (let attempt = 0; attempt < 5; attempt++) {
      try {
        await page.getByRole('button', { name: 'Next page' }).click();
      } catch(e) {
        await page.waitForTimeout(2000);
        continue;
      }
      await page.waitForTimeout(2500);
      const newPageId = await getPageId();
      if (newPageId && newPageId !== prevPageId) {
        prevPageId = newPageId;
        advanced = true;
        break;
      }
      await page.waitForTimeout(1500);
    }
    if (!advanced) {
      const endCheck = await page.evaluate(() => {
        const btn = document.querySelector('[aria-label="Next page"]');
        return btn ? btn.disabled : true;
      });
      if (endCheck) break;
    }
    await page.screenshot({
      path: `${screenshotDir}/page_${String(i).padStart(4, '0')}.png`,
      type: 'png'
    });
    pageNum = i;
  }
  return { completed: pageNum };
}
```

### 3. OCR the screenshots

Run the Swift OCR script which uses macOS Vision framework:

```bash
swift ocr_pages.swift
```

This processes all PNG files in `screenshots/`, crops out UI chrome (header, footer, nav arrows), and outputs `book_raw.txt`.

### 4. Clean and deduplicate

```bash
python3 clean_book.py
python3 dedup_book.py
```

`clean_book.py` strips OCR artifacts (stray characters, UI text patterns, page numbers).

`dedup_book.py` removes duplicate pages (from navigation retries) using content fingerprinting.

### 5. Convert to audiobook

```bash
python generate_audiobook.py The_Book_Title.txt
```

See the main [README](README.md) for full audiobook generation options.

## Full pipeline timing

| Step | Time |
|------|------|
| Screenshots (~250 pages) | ~15 min |
| OCR | ~3 min |
| Clean + dedup | instant |
| Audiobook generation | ~3 min |
| **Total** | **~20 min** |

## Tips

- **Don't rush screenshots.** 2.5s wait is the minimum. Going faster causes the reader to error out and produce duplicate/missing pages.
- **Check page count** after screenshots. If you got significantly fewer than expected, some pages were skipped.
- **OCR accuracy** is typically ~97% for standard prose. Decorative headings, footnotes, and unusual formatting may have errors.
- **For future books**, clear old screenshots first: `rm screenshots/page_*.png`
