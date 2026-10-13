import React, { useMemo, useState } from 'react';
import { Copy, Check, Table2 } from 'lucide-react';

/*
 * Markdown for assistant replies: headings, paragraphs, nested lists, quotes,
 * fenced code, GitHub-style tables and inline bold/italic/strike/code/links.
 * Output is React elements only (never raw HTML), and links are limited to
 * http(s)/mailto so model output can't inject script URLs.
 */

const FENCE = /^\s*```\s*([\w+-]*)\s*$/;
const TABLE_SEP = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/;
const HEADING = /^(#{1,6})\s+(.*?)\s*#*\s*$/;
const LIST_ITEM = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/;
const HR = /^\s*([-*_])(\s*\1){2,}\s*$/;
const QUOTE = /^\s*>\s?(.*)$/;

export function hasMarkdownTable(text) {
  if (!text) return false;
  const lines = text.split('\n');
  return lines.some((line, i) => line.includes('|') && TABLE_SEP.test(lines[i + 1] || ''));
}

function splitRow(line) {
  let row = line.trim();
  if (row.startsWith('|')) row = row.slice(1);
  if (row.endsWith('|') && !row.endsWith('\\|')) row = row.slice(0, -1);
  return row.split(/(?<!\\)\|/).map((cell) => cell.trim().replace(/\\\|/g, '|'));
}

function parseList(lines) {
  // Nest by indentation: deeper items become children of the previous item.
  const root = { items: [], ordered: false, start: 1, indent: null };
  const stack = [root];
  for (const line of lines) {
    const m = LIST_ITEM.exec(line);
    let top = stack[stack.length - 1];
    if (!m) {
      const last = top.items[top.items.length - 1];
      if (last) last.text += ` ${line.trim()}`;
      continue;
    }
    const indent = m[1].replace(/\t/g, '  ').length;
    const ordered = /\d/.test(m[2]);
    const start = parseInt(m[2], 10) || 1;
    if (top.indent === null) {
      Object.assign(top, { indent, ordered, start });
    } else if (indent > top.indent && top.items.length) {
      const child = { items: [], ordered, start, indent };
      top.items[top.items.length - 1].children = child;
      stack.push(child);
      top = child;
    } else {
      while (stack.length > 1 && indent < top.indent) {
        stack.pop();
        top = stack[stack.length - 1];
      }
    }
    top.items.push({ text: m[3] });
  }
  return root;
}

export function parseBlocks(content) {
  const lines = content.replace(/\r\n?/g, '\n').split('\n');
  const blocks = [];
  let i = 0;

  const isBlockStart = (line, next) => FENCE.test(line) || HEADING.test(line) || HR.test(line)
    || QUOTE.test(line) || LIST_ITEM.test(line) || (line.includes('|') && TABLE_SEP.test(next || ''));

  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }

    const fence = FENCE.exec(line);
    if (fence) {
      const body = [];
      i++;
      while (i < lines.length && !/^\s*```\s*$/.test(lines[i])) body.push(lines[i++]);
      i++;
      blocks.push({ type: 'code', language: fence[1] || 'text', code: body.join('\n') });
      continue;
    }

    if (line.includes('|') && TABLE_SEP.test(lines[i + 1] || '')) {
      const header = splitRow(line);
      const align = splitRow(lines[i + 1]).map((c) => (c.startsWith(':') && c.endsWith(':') ? 'center' : c.endsWith(':') ? 'right' : null));
      const rows = [];
      i += 2;
      while (i < lines.length && lines[i].includes('|') && lines[i].trim()) rows.push(splitRow(lines[i++]));
      blocks.push({ type: 'table', header, align, rows });
      continue;
    }

    const heading = HEADING.exec(line);
    if (heading) { blocks.push({ type: 'heading', level: heading[1].length, text: heading[2] }); i++; continue; }

    if (HR.test(line)) { blocks.push({ type: 'hr' }); i++; continue; }

    if (QUOTE.test(line)) {
      const body = [];
      while (i < lines.length && QUOTE.test(lines[i])) body.push(QUOTE.exec(lines[i++])[1]);
      blocks.push({ type: 'quote', blocks: parseBlocks(body.join('\n')) });
      continue;
    }

    if (LIST_ITEM.test(line)) {
      const body = [];
      while (i < lines.length) {
        const l = lines[i];
        if (LIST_ITEM.test(l) || (l.trim() && /^\s+/.test(l) && !FENCE.test(l))) { body.push(l); i++; continue; }
        // a single blank line inside a list keeps the list going if another item follows
        if (!l.trim() && LIST_ITEM.test(lines[i + 1] || '')) { i++; continue; }
        break;
      }
      blocks.push({ type: 'list', list: parseList(body) });
      continue;
    }

    const para = [line.trim()];
    i++;
    while (i < lines.length && lines[i].trim() && !isBlockStart(lines[i], lines[i + 1])) para.push(lines[i++].trim());
    blocks.push({ type: 'paragraph', text: para.join(' ') });
  }
  return blocks;
}

const INLINE = /(`[^`]+`)|(\*\*[^*]+?\*\*|__[^_]+?__)|(~~[^~]+?~~)|(\*[^*\s][^*]*?\*)|(\[[^\]]+\]\([^)\s]+(?:\s+"[^"]*")?\))|(https?:\/\/[^\s<>()]+[^\s<>().,;:!?'"])/g;

function safeHref(url) {
  return /^(https?:|mailto:)/i.test(url) ? url : null;
}

function renderInline(text, keyPrefix = 'i') {
  const out = [];
  let last = 0;
  let m;
  INLINE.lastIndex = 0;
  const re = new RegExp(INLINE.source, 'g');
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const key = `${keyPrefix}-${m.index}`;
    const tok = m[0];
    if (m[1]) out.push(<code key={key} className="md-code-inline">{tok.slice(1, -1)}</code>);
    else if (m[2]) out.push(<strong key={key} className="md-strong">{renderInline(tok.slice(2, -2), key)}</strong>);
    else if (m[3]) out.push(<del key={key}>{renderInline(tok.slice(2, -2), key)}</del>);
    else if (m[4]) out.push(<em key={key}>{renderInline(tok.slice(1, -1), key)}</em>);
    else if (m[5]) {
      const lm = /^\[([^\]]+)\]\(([^)\s]+)/.exec(tok);
      const href = safeHref(lm[2]);
      out.push(href
        ? <a key={key} href={href} target="_blank" rel="noopener noreferrer" className="md-link" title={href}>{renderInline(lm[1], key)}</a>
        : lm[1]);
    } else if (m[6]) {
      let host = tok;
      try { host = new URL(tok).hostname.replace(/^www\./, ''); } catch { /* keep the raw text */ }
      out.push(<a key={key} href={tok} target="_blank" rel="noopener noreferrer" className="md-link md-link-bare" title={tok}>{host}</a>);
    }
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

const NUMERIC_CELL = /^[-+]?[₹$€£¥]?\s?\d[\d,]*(\.\d+)?\s?(%|[kKmMbB]|x|ms|s)?$/;

function MarkdownTable({ block }) {
  const [copied, setCopied] = useState(false);
  const columns = block.header.length;
  // Right-align columns whose cells are all numbers, unless the author set an alignment.
  const align = block.header.map((_, c) => {
    if (block.align[c]) return block.align[c];
    const cells = block.rows.map((r) => (r[c] || '').replace(/\*\*/g, '')).filter(Boolean);
    return cells.length && cells.every((v) => NUMERIC_CELL.test(v)) ? 'right' : null;
  });

  const copyTable = () => {
    const tsv = [block.header, ...block.rows]
      .map((r) => r.map((cell) => cell.replace(/\*\*|`/g, '').replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')).join('\t'))
      .join('\n');
    navigator.clipboard.writeText(tsv);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  return (
    <figure className="md-table-card">
      <div className="md-table-bar">
        <span className="md-table-meta"><Table2 size={13} /> {block.rows.length} {block.rows.length === 1 ? 'row' : 'rows'}</span>
        <button type="button" className="md-mini-btn" onClick={copyTable} aria-label="Copy table for a spreadsheet">
          {copied ? <Check size={12} /> : <Copy size={12} />}
          <span>{copied ? 'Copied' : 'Copy'}</span>
        </button>
      </div>
      <div className="md-table-scroll" tabIndex={0} role="region" aria-label="Table">
        <table className="md-table">
          <thead>
            <tr>
              {block.header.map((cell, c) => (
                <th key={c} style={{ textAlign: align[c] || 'left' }}>{renderInline(cell, `h${c}`)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {block.rows.map((row, r) => (
              <tr key={r} style={{ '--row': Math.min(r, 14) }}>
                {Array.from({ length: columns }, (_, c) => (
                  <td key={c} className={align[c] === 'right' ? 'md-num' : undefined} style={{ textAlign: align[c] || 'left' }}>
                    {renderInline(row[c] || '', `r${r}c${c}`)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </figure>
  );
}

function CodeBlock({ block }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(block.code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };
  return (
    <div className="md-code-card">
      <div className="md-table-bar">
        <span className="md-table-meta">{block.language}</span>
        <button type="button" className="md-mini-btn" onClick={copy} aria-label="Copy code">
          {copied ? <Check size={12} /> : <Copy size={12} />}
          <span>{copied ? 'Copied' : 'Copy'}</span>
        </button>
      </div>
      <pre className="md-pre"><code>{block.code}</code></pre>
    </div>
  );
}

function ListView({ list, depth = 0 }) {
  const Tag = list.ordered ? 'ol' : 'ul';
  return (
    <Tag className={`md-list ${list.ordered ? 'md-ol' : 'md-ul'}`} start={list.ordered ? list.start : undefined} data-depth={depth}>
      {list.items.map((item, idx) => (
        <li key={idx} className="md-li">
          {renderInline(item.text, `l${depth}-${idx}`)}
          {item.children && <ListView list={item.children} depth={depth + 1} />}
        </li>
      ))}
    </Tag>
  );
}

function Block({ block }) {
  switch (block.type) {
    case 'heading': {
      const level = Math.min(block.level + 1, 5);
      const Tag = `h${level}`;
      return <Tag className={`md-h md-h${block.level}`}>{renderInline(block.text, 'h')}</Tag>;
    }
    case 'paragraph': return <p className="md-p">{renderInline(block.text, 'p')}</p>;
    case 'list': return <ListView list={block.list} />;
    case 'quote': return <blockquote className="md-quote">{block.blocks.map((b, i) => <Block key={i} block={b} />)}</blockquote>;
    case 'hr': return <hr className="md-hr" />;
    case 'code': return <CodeBlock block={block} />;
    case 'table': return <MarkdownTable block={block} />;
    default: return null;
  }
}

export default function MarkdownRenderer({ content, animate = false }) {
  const blocks = useMemo(() => (content ? parseBlocks(content) : []), [content]);
  if (!blocks.length) return null;
  return (
    <div className={`md ${animate ? 'md-animate' : ''}`}>
      {blocks.map((block, i) => (
        <div key={i} className={`md-block md-block-${block.type}`} style={{ '--i': Math.min(i, 16) }}>
          <Block block={block} />
        </div>
      ))}
    </div>
  );
}
