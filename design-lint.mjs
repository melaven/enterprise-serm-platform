#!/usr/bin/env node
/**
 * Проверка дизайн-правил: падает (exit 1), если в исходниках есть запрещённое.
 * Tailwind-конфиг уже не генерирует такие утилиты; это страховка от «тихих»
 * нарушений: произвольные значения bg-[...], инлайн-стили, сторонний CSS.
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, extname } from 'node:path';

const RULES = [
  [/\bshadow(-|\b)/, 'тень (shadow-*)'],
  [/\bring(-|\b)/, 'ring-* (это box-shadow)'],
  [/\bdrop-shadow/, 'drop-shadow'],
  [/\bbackdrop-/, 'backdrop-* (стекло)'],
  [/\bblur(-|\b)/, 'blur'],
  [/\bbg-gradient|\bbg-linear|\bbg-radial|\bbg-conic|\b(from|via|to)-(plum|lime|chrome|ink|white)/, 'градиент'],
  [/\brounded-(md|lg|xl|2xl|3xl|full)\b/, 'скругление больше 2px'],
  [/\b(bg|text|border|fill|stroke)-\[#/, 'произвольный HEX мимо палитры'],
  [/box-shadow|text-shadow|linear-gradient|radial-gradient|backdrop-filter|filter:\s*blur/i, 'запрещённое CSS-свойство'],
  [/border-radius:\s*(?!0|1px|2px|0px)\S+/i, 'border-radius больше 2px'],
  [/\bneon\b/i, 'неон'],
];
// Допустимые исключения: в index.css есть защитное `box-shadow: none`, а в конфиге
// описание правил.
// LandingPage.tsx: публичный лендинг со своей спецификацией (скругления, радиальное свечение, hex-акценты).
const SKIP = new Set(['design-lint.mjs', 'tailwind.config.js', 'LandingPage.tsx']);

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) yield* walk(p);
    else if (['.ts', '.tsx', '.css', '.html'].includes(extname(p))) yield p;
  }
}

let failures = 0;
for (const root of ['src', 'index.html']) {
  const files = statSync(root).isDirectory() ? [...walk(root)] : [root];
  for (const file of files) {
    if (SKIP.has(file.split('/').pop())) continue;
    readFileSync(file, 'utf8').split('\n').forEach((line, i) => {
      if (/design-lint:ignore/.test(line)) return;
      if (/:\s*none\b/.test(line) && /shadow|filter/.test(line)) return; // `box-shadow: none` разрешён
      for (const [re, what] of RULES) {
        if (re.test(line)) {
          failures += 1;
          console.error(`${file}:${i + 1}  запрещено: ${what}\n    ${line.trim()}`);
        }
      }
    });
  }
}
if (failures) {
  console.error(`\ndesign-lint: нарушений ${failures}`);
  process.exit(1);
}
console.log('design-lint: ок');
