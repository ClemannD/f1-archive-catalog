// ==UserScript==
// @name         F1TV Archive Scraper
// @namespace    f1-archive-catalog
// @version      1.8
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
    'season review': 'season-review',
    'season recap': 'season-review',
  };

  const EXCLUDED_TYPES = new Set([
    'documentary',
    'feature',
    'show',
    'race highlights',
    'analysis',
  ]);

  const VALID_TYPES = new Set(['race', 'extended_highlights', 'highlights', 'season-review']);

  function isFeederSeries(title, url) {
    const t = (title || '').trim();
    if (/^F2\b/i.test(t) || /^F3\b/i.test(t)) return true;
    if (/\bF2\s+season\b/i.test(t) || /\bF3\s+season\b/i.test(t)) return true;
    if (/\bformula\s*2\b/i.test(t) || /\bformula\s*3\b/i.test(t)) return true;
    const slug = ((url || '').split('/').pop() || '').toLowerCase().replace(/\?.*$/, '');
    if (/^(f2|f3)[-:]/.test(slug)) return true;
    if (/(?:^|[-/])(f2|f3)(?:[-/]|$)/.test(slug)) return true;
    if (/\bf[23]-season\b/.test(slug)) return true;
    return false;
  }

  function parseVideoCard(link) {
    const titleEl = link.querySelector('.video-card-item-title');
    const descEl = link.querySelector('.race-description');
    if (!titleEl) return null;

    const fullTitle = titleEl.textContent.trim();
    const href = link.getAttribute('href');
    const url = href ? 'https://f1tv.formula1.com' + href.replace(/\?action=play$/, '') : null;
    if (isFeederSeries(fullTitle, url)) return null;

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

    if (EXCLUDED_TYPES.has(type) || !VALID_TYPES.has(type)) return null;

    if (type === 'season-review') {
      return { season, round: null, name: season + ' Season Review', type, duration, url };
    }
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

  function isGenericRaceTitle(name) {
    const n = name.trim();
    return /^formula\s*1\s+(?:\d{4}\s+)?(?:pirelli\s+|rolex\s+|heineken\s+|gulf air\s+)?(grand prix|gran premio|grande pr[eê]mio)$/i.test(n);
  }

  const SPONSOR_WORDS = /^(formula|grand|prix|gran|premio|heineken|pirelli|rolex|gulf|air|aws|msc|cruises|lenovo|aramco|qatar|airways|etihad|emirates|singapore|airlines|johnnie|walker|honda|vtb|eyetime|tag|heuer|stc|crypto|com|louis|vuitton)$/i;

  function locationFromUrl(url) {
    const slug = (url || '').split('/').pop().replace(/\?.*$/, '') || '';
    const deLoc = slug.match(/(?:grand-prix|gran-premio|grande-premio)-(?:de|del|du|do|dell|von)-([a-z0-9]+)(?:-[a-z0-9-]+)*-\d{4}$/i);
    if (deLoc && !SPONSOR_WORDS.test(deLoc[1])) {
      return deLoc[1].replace(/-/g, ' ').trim();
    }
    const patterns = [
      /(?:du|de|do|von|del|dell|osterreich|magyar|grosser)-([a-z0-9-]+)-\d{4}$/i,
      /(?:grand-prix|gran-premio|grande-premio)-(?:[a-z0-9-]+-)*([a-z0-9-]+)-\d{4}$/i,
      /-([a-z0-9-]+)-\d{4}$/i,
    ];
    for (const pat of patterns) {
      const m = slug.match(pat);
      if (m) {
        const parts = m[1].split('-').filter(Boolean);
        const candidates = parts.length > 1 ? [parts[parts.length - 1], parts[parts.length - 2]] : [m[1]];
        for (const c of candidates) {
          const loc = c.replace(/-/g, ' ').trim();
          if (!SPONSOR_WORDS.test(loc)) return loc;
        }
      }
    }
    return null;
  }

  function extractGrandPrixName(title) {
    // French/Italian word order: "GRAND PRIX ... DU CANADA 2018"
    const trailing = title.match(/\b(?:du|de|do|d'|del|dell'|von)\s+([\w\s.'-]+?)(?:\s+\d{4})?\s*$/i);
    if (trailing) {
      const place = trailing[1].trim();
      if (!/^(heineken|pirelli|rolex|formula)$/i.test(place)) {
        return /grand prix/i.test(place) ? place : place + ' Grand Prix';
      }
    }

    const granPremio = title.match(/\bGran Premio[\w\s.'-]*/i);
    if (granPremio && granPremio[0].length > 15) return granPremio[0].trim().replace(/\s+/g, ' ');
    const grandePremio = title.match(/\bGrande Pr[eê]mio[\w\s.'-]*/i);
    if (grandePremio && grandePremio[0].length > 15) return grandePremio[0].trim().replace(/\s+/g, ' ');

    const gp = title.match(/([\w\s.'-]*\bGrand Prix)/i);
    if (gp) return gp[1].trim().replace(/\s+/g, ' ');

    return title
      .replace(/^\d{4}\s+/, '').replace(/\s*\d{4}$/, '')
      .replace(/\b(19|20)\d{2}\b/g, '')
      .replace(/^FORMULA\s*1\s*/i, '')
      .trim();
  }

  function resolveBundleName(fullTitle, titleName, countryText, url) {
    if (!isGenericRaceTitle(titleName)) return titleName;

    if (countryText) {
      const country = countryText.trim();
      if (country && !/^formula\s*1$/i.test(country)) {
        return /grand prix|gran premio|grande pr[eê]mio/i.test(country) ? country : country + ' Grand Prix';
      }
    }

    const fromUrl = locationFromUrl(url);
    if (fromUrl) {
      const words = fromUrl.split(/\s+/).map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
      return words + ' Grand Prix';
    }

    return titleName;
  }

  function captureConfidence(entry, countryText) {
    let score = 0;
    if (entry.round != null) score += 1;
    if (!isGenericRaceTitle(entry.name)) score += 3;
    const fromUrl = locationFromUrl(entry.url);
    if (fromUrl && countryText && countryText.toLowerCase().includes(fromUrl.split(' ')[0])) score += 3;
    else if (fromUrl && entry.name.toLowerCase().includes(fromUrl.split(' ')[0])) score += 2;
    return score;
  }

  function mergeCardEntry(existing, entry, existingScore, newScore) {
    if (newScore > existingScore) {
      return { entry, score: newScore };
    }
    if (newScore === existingScore) {
      if (entry.round != null && existing.round == null) existing.round = entry.round;
      if (!isGenericRaceTitle(entry.name) && isGenericRaceTitle(existing.name)) existing.name = entry.name;
    }
    return { entry: existing, score: existingScore };
  }

  function isRaceEvent(title, round, url) {
    if (isFeederSeries(title, url)) return false;
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

  function collectVisibleCards(byHref, scores, skipped) {
    const add = (link, parser, type) => {
      const href = link.getAttribute('href');
      if (!href) return;
      const parsed = parser(link);
      if (!parsed) {
        skipped.push({ type, title: link.textContent.trim().slice(0, 80) });
        return;
      }
      const { entry, countryText } = parsed;
      const score = captureConfidence(entry, countryText);
      if (byHref.has(href)) {
        const merged = mergeCardEntry(byHref.get(href), entry, scores.get(href), score);
        byHref.set(href, merged.entry);
        scores.set(href, merged.score);
      } else {
        byHref.set(href, entry);
        scores.set(href, score);
      }
    };

    document.querySelectorAll('a.video-card-item').forEach(link => {
      const href = link.getAttribute('href');
      if (!href) return;
      const entry = parseVideoCard(link);
      if (entry) byHref.set(href, entry);
      else skipped.push({ type: 'video-card', title: link.textContent.trim().slice(0, 80) });
    });
    document.querySelectorAll('a.bundle-card-item').forEach(link => add(link, parseBundleCard, 'bundle-card'));
  }

  async function scrollAndCollect(target, byHref, scores, skipped) {
    const step = Math.max(180, Math.floor(target.clientHeight * 0.75));
    const maxScroll = Math.max(0, target.scrollHeight - target.clientHeight);
    for (let pos = 0; pos <= maxScroll; pos += step) {
      target.scrollTop = pos;
      await new Promise(r => setTimeout(r, 250));
      collectVisibleCards(byHref, scores, skipped);
    }
    target.scrollTop = maxScroll;
    await new Promise(r => setTimeout(r, 250));
    collectVisibleCards(byHref, scores, skipped);
  }

  async function scrapeAllCards() {
    const byHref = new Map();
    const scores = new Map();
    const skipped = [];
    const targets = getScrollTargets();
    const saved = targets.map(el =>
      el === document.documentElement || el === document.body ? window.scrollY : el.scrollTop
    );

    // Walk virtualized wall lists in small steps so each card's metadata
    // (title, country, round) is read while that card is mounted.
    const wallLists = [...document.querySelectorAll('.wall-list-container, [class*="wall-list"]')]
      .filter(el => el.scrollHeight > el.clientHeight + 10);
    if (wallLists.length) {
      for (const wall of wallLists) {
        await scrollAndCollect(wall, byHref, scores, skipped);
      }
    } else {
      const steps = 40;
      for (let i = 0; i <= steps; i++) {
        const frac = i / steps;
        window.scrollTo(0, frac * document.documentElement.scrollHeight);
        targets.forEach(el => {
          if (el === document.documentElement || el === document.body) return;
          el.scrollTop = frac * el.scrollHeight;
        });
        await new Promise(r => setTimeout(r, 250));
        collectVisibleCards(byHref, scores, skipped);
      }
    }

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
    const href = link.getAttribute('href');
    const url = href ? 'https://f1tv.formula1.com' + href : null;
    if (isFeederSeries(fullTitle, url)) return null;

    const season = extractSeason(fullTitle);
    if (!season) return null;

    let round = null;
    const roundEl = link.querySelector('.bundle-card-item-round-indicator');
    if (roundEl) {
      const roundMatch = roundEl.textContent.match(/(\d+)/);
      if (roundMatch) round = parseInt(roundMatch[1]);
    }

    if (!isRaceEvent(fullTitle, round, url)) return null;

    const titleName = extractGrandPrixName(fullTitle);
    const countryEl = link.querySelector('.bundle-card-item-country-container .line-clamp');
    const countryText = countryEl ? countryEl.textContent.trim() : null;
    const name = resolveBundleName(fullTitle, titleName, countryText, url);
    const entry = { season, round, name, type: 'race', duration: null, url };
    return { entry, countryText };
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
