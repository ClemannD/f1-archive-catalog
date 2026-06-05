// ==UserScript==
// @name         F1TV Archive Scraper
// @namespace    f1-archive-catalog
// @version      1.4
// @description  Scrape F1TV archive pages and send data to local catalog server
// @match        https://f1tv.formula1.com/*
// @grant        GM_xmlhttpRequest
// @connect      localhost
// ==/UserScript==

(function() {
  'use strict';

  const SERVER = 'http://localhost:8484';

  // Floating scrape button
  const btn = document.createElement('button');
  btn.textContent = '🏎️ Scrape Page';
  btn.style.cssText = 'position:fixed;bottom:20px;right:20px;z-index:99999;padding:12px 20px;' +
    'background:#e10600;color:#fff;border:none;border-radius:8px;font-size:16px;font-weight:bold;' +
    'cursor:pointer;box-shadow:0 4px 12px rgba(0,0,0,0.4);';
  btn.addEventListener('mouseenter', () => btn.style.background = '#ff1801');
  btn.addEventListener('mouseleave', () => btn.style.background = '#e10600');
  document.body.appendChild(btn);

  const TYPE_MAP = {
    'replay': 'race',
    'race': 'race',
    'extended highlights': 'extended_highlights',
    'highlights': 'highlights',
    'season review': 'season_review',
    'season recap': 'season_review',
  };

  function parseVideoCard(link) {
    const titleEl = link.querySelector('.video-card-item-title');
    const descEl = link.querySelector('.race-description');
    if (!titleEl) return null;

    const fullTitle = titleEl.textContent.trim();
    const season = extractSeason(fullTitle);
    if (!season) return null;
    const name = fullTitle.replace(/^\d{4}\s+/, '');
    let duration = null;
    let type = 'race';

    if (descEl) {
      const parts = descEl.textContent.trim().split('|').map(s => s.trim());
      if (parts.length >= 1 && /^\d{2}:\d{2}:\d{2}$/.test(parts[0])) duration = parts[0];
      if (parts.length >= 2) type = TYPE_MAP[parts[parts.length - 1].toLowerCase()] || parts[parts.length - 1].toLowerCase();
    }

    const href = link.getAttribute('href');
    const url = href ? 'https://f1tv.formula1.com' + href.replace(/\?action=play$/, '') : null;
    return { season, round: null, name, type, duration, url };
  }

  function extractSeason(title) {
    const end = title.match(/\b((?:19|20)\d{2})\s*$/);
    if (end) return parseInt(end[1]);
    const start = title.match(/^(\d{4})\b/);
    if (start) return parseInt(start[1]);
    const any = title.match(/\b((?:19|20)\d{2})\b/);
    return any ? parseInt(any[1]) : null;
  }

  function extractGrandPrixName(title) {
    const gp = title.match(/([\w\s.'-]*\bGrand Prix)/i);
    if (gp) return gp[1].trim().replace(/\s+/g, ' ');
    const granPremio = title.match(/([\w\s.'-]*\bGran Premio[\w\s.'-]*)/i);
    if (granPremio) return granPremio[1].trim().replace(/\s+/g, ' ');
    const grandePremio = title.match(/([\w\s.'-]*\bGrande Pr[eê]mio[\w\s.'-]*)/i);
    if (grandePremio) return grandePremio[1].trim().replace(/\s+/g, ' ');
    return title
      .replace(/^\d{4}\s+/, '').replace(/\s*\d{4}$/, '')
      .replace(/\b(19|20)\d{2}\b/g, '')
      .replace(/^FORMULA\s*1\s*/i, '')
      .trim();
  }

  function isRaceEvent(title, round) {
    if (/pre[- ]?season|testing/i.test(title)) return false;
    if (round != null) return true;
    return /grand prix|gran premio|grande pr[eê]mio/i.test(title);
  }

  function getScrollTargets() {
    const targets = [document.documentElement, document.body];
    document.querySelectorAll('.wall-list-container, [class*="wall-list"]').forEach(el => {
      if (el.scrollHeight > el.clientHeight + 10) targets.push(el);
    });
    return [...new Set(targets)];
  }

  function collectVisibleCards(byHref, skipped) {
    const add = (link, parser, type) => {
      const href = link.getAttribute('href');
      if (!href || byHref.has(href)) return;
      const entry = parser(link);
      if (entry) {
        byHref.set(href, entry);
      } else {
        skipped.push({ type, title: link.textContent.trim().slice(0, 80) });
      }
    };

    document.querySelectorAll('a.video-card-item').forEach(link => add(link, parseVideoCard, 'video-card'));
    document.querySelectorAll('a.bundle-card-item').forEach(link => add(link, parseBundleCard, 'bundle-card'));
  }

  async function scrapeAllCards() {
    const byHref = new Map();
    const skipped = [];
    const targets = getScrollTargets();
    const saved = targets.map(el =>
      el === document.documentElement || el === document.body ? window.scrollY : el.scrollTop
    );

    // Walk the page top-to-bottom, collecting cards at each position.
    // F1TV virtualizes the wall list — cards unmount when scrolled away,
    // so we must capture href+metadata while each card is visible.
    const steps = 30;
    for (let i = 0; i <= steps; i++) {
      const frac = i / steps;
      window.scrollTo(0, frac * document.documentElement.scrollHeight);
      targets.forEach(el => {
        if (el === document.documentElement || el === document.body) return;
        el.scrollTop = frac * el.scrollHeight;
      });
      await new Promise(r => setTimeout(r, 200));
      collectVisibleCards(byHref, skipped);
    }

    // Restore scroll position
    window.scrollTo(0, saved[0] || 0);
    targets.forEach((el, i) => {
      if (el === document.documentElement || el === document.body) return;
      el.scrollTop = saved[i] || 0;
    });

    return { entries: [...byHref.values()], skipped, uniqueHrefs: byHref.size };
  }

  function parseBundleCard(link) {
    const titleEl = link.querySelector('.bundle-card-item-title');
    if (!titleEl) return null;

    const fullTitle = titleEl.textContent.trim();
    const season = extractSeason(fullTitle);
    if (!season) return null;

    let round = null;
    const roundEl = link.querySelector('.bundle-card-item-round-indicator');
    if (roundEl) {
      const roundMatch = roundEl.textContent.match(/(\d+)/);
      if (roundMatch) round = parseInt(roundMatch[1]);
    }

    if (!isRaceEvent(fullTitle, round)) return null;

    const titleName = extractGrandPrixName(fullTitle);
    const countryEl =
      link.querySelector('.bundle-card-item-country-container .line-clamp') ||
      link.querySelector('.bundle-card-item-country-container');

    let name;
    if (/grand prix|gran premio|grande pr[eê]mio/i.test(titleName)) {
      name = titleName;
    } else if (countryEl) {
      const country = countryEl.textContent.trim();
      name = /grand prix/i.test(country) ? country : country + ' Grand Prix';
    } else {
      name = titleName;
    }

    const href = link.getAttribute('href');
    const url = href ? 'https://f1tv.formula1.com' + href : null;
    return { season, round, name, type: 'race', duration: null, url };
  }

  btn.addEventListener('click', async () => {
    btn.textContent = '⏳ Loading cards...';
    btn.style.background = '#555';
    btn.disabled = true;

    const { entries, skipped, uniqueHrefs } = await scrapeAllCards();

    if (skipped.length) console.warn(`F1TV Scraper: skipped ${skipped.length} cards`, skipped);
    console.log(`F1TV Scraper: collected ${entries.length} unique cards by href`);

    if (entries.length === 0) {
      btn.disabled = false;
      // Dump diagnostic info into a floating panel
      const panel = document.createElement('div');
      panel.style.cssText = 'position:fixed;top:10px;right:10px;z-index:999999;background:#111;color:#0f0;' +
        'padding:16px;border-radius:8px;font-family:monospace;font-size:12px;max-height:80vh;overflow:auto;' +
        'max-width:600px;white-space:pre-wrap;box-shadow:0 4px 20px rgba(0,0,0,0.8);';
      const close = document.createElement('button');
      close.textContent = '✕';
      close.style.cssText = 'position:absolute;top:4px;right:8px;background:none;border:none;color:#f00;font-size:16px;cursor:pointer;';
      close.onclick = () => panel.remove();
      panel.appendChild(close);

      let info = '=== F1TV Scraper Debug ===\n\n';
      info += `Unique hrefs collected: ${uniqueHrefs}\n`;
      info += `Visible in DOM now: ${document.querySelectorAll('a.bundle-card-item, a.video-card-item').length}\n\n`;
      info += 'Tried selectors:\n';
      info += `  a.video-card-item: ${document.querySelectorAll('a.video-card-item').length}\n`;
      info += `  a.bundle-card-item: ${document.querySelectorAll('a.bundle-card-item').length}\n\n`;
      info += 'Searching for links with titles...\n';
      const allLinks = document.querySelectorAll('a[href*="/detail/"]');
      info += `  a[href*="/detail/"]: ${allLinks.length}\n\n`;
      if (allLinks.length > 0) {
        info += 'First 5 detail links:\n';
        [...allLinks].slice(0, 5).forEach((a, i) => {
          info += `\n[${i}] class="${a.className}"\n`;
          info += `    href="${a.getAttribute('href')}"\n`;
          info += `    text: ${a.textContent.trim().substring(0, 120)}\n`;
          info += `    children classes: ${[...a.querySelectorAll('[class]')].map(el => el.className).join(', ').substring(0, 300)}\n`;
        });
      }
      panel.appendChild(document.createTextNode(info));
      document.body.appendChild(panel);

      btn.textContent = '🔍 See debug panel ↗';
      btn.style.background = '#666';
      setTimeout(() => { btn.textContent = '🏎️ Scrape Page'; btn.style.background = '#e10600'; }, 5000);
      return;
    }

    btn.textContent = `⏳ Sending ${entries.length}...`;

    GM_xmlhttpRequest({
      method: 'POST',
      url: SERVER + '/add',
      headers: { 'Content-Type': 'application/json' },
      data: JSON.stringify(entries),
      onload: function(resp) {
        const res = JSON.parse(resp.responseText);
        const skipNote = skipped.length ? `, ${skipped.length} skipped` : '';
        btn.textContent = `✅ found ${entries.length}, +${res.added}${skipNote}`;
        btn.style.background = '#1a8d1a';
        btn.disabled = false;
        setTimeout(() => { btn.textContent = '🏎️ Scrape Page'; btn.style.background = '#e10600'; }, 5000);
      },
      onerror: function(err) {
        btn.textContent = '❌ Server error';
        btn.style.background = '#e10600';
        btn.disabled = false;
        console.error('F1TV Scraper error:', err);
        setTimeout(() => { btn.textContent = '🏎️ Scrape Page'; btn.style.background = '#e10600'; }, 3000);
      }
    });
  });
})();
