/**
 * ux_probe.js — deterministic visual/UX measurement of a rendered page.
 *
 * Read-only: reads layout, computed styles, and paint order. It never mutates
 * the DOM, app state, or source. That is why it may run BEFORE the diagnosis
 * gate, unlike instrumentation (see reference/instrumentation.md).
 *
 * Scope is visual craft and interaction ergonomics. This is not an
 * accessibility audit and makes no compliance claim.
 *
 * Usage (Playwright):   await page.evaluate(fs.readFileSync('ux_probe.js','utf8'))
 * Usage (CDP):          Runtime.evaluate({ expression: <file contents>, returnByValue: true })
 *
 * Returns a JSON-serializable audit. Run once per viewport width and save each
 * result as evidence/round-N/ux_probe.<width>.json.
 */
(() => {
  const PROBE_VERSION = '1.0.0';

  const THRESHOLDS = {
    legibilityRatioNormal: 4.5,
    legibilityRatioLarge: 3.0,
    legibilityRatioIllegible: 3.0,
    // A miss within this fraction of the threshold is reported at minor
    // severity: the closer to the line, the weaker the claim.
    marginalBand: 0.05,
    largeTextPx: 24,
    minTargetPx: 24,
    criticalTargetPx: 16,
    minFontPx: 12,
    spacingGridPx: 4,
    spacingOffGridShare: 0.15,
    maxDistinctColors: 12,
    maxDistinctFontSizes: 8,
    maxDistinctFontFamilies: 3,
    maxDistinctRadii: 4,
    alignmentNearMissMinPx: 0.5,
    alignmentNearMissMaxPx: 3,
    maxElements: 3000,
    // One defect repeated across 16 sibling cards is one defect. Report a few
    // representatives; the true total stays in summary.by_rule.
    maxFindingsPerRule: 3,
  };

  const SEVERITY = { BLOCKER: 'blocker', MAJOR: 'major', MINOR: 'minor' };

  const INTERACTIVE_SELECTOR = [
    'button',
    'a[href]',
    'input:not([type="hidden"])',
    'select',
    'textarea',
    'summary',
    '[role="button"]',
    '[role="link"]',
    '[role="tab"]',
    '[role="switch"]',
    '[onclick]',
  ].join(',');

  const notes = [];
  const findings = [];

  // ---------------------------------------------------------------- utilities

  function cssPath(el) {
    if (!el || el.nodeType !== 1) return '<unknown>';
    if (el.id) return `#${el.id}`;
    const parts = [];
    let node = el;
    while (node && node.nodeType === 1 && parts.length < 4) {
      let part = node.tagName.toLowerCase();
      const cls = (node.getAttribute('class') || '').trim().split(/\s+/).filter(Boolean)[0];
      if (cls) part += `.${cls}`;
      const parent = node.parentElement;
      if (parent) {
        const siblings = [...parent.children].filter((c) => c.tagName === node.tagName);
        if (siblings.length > 1) part += `:nth-of-type(${siblings.indexOf(node) + 1})`;
      }
      parts.unshift(part);
      node = node.parentElement;
    }
    return parts.join(' > ');
  }

  function label(el) {
    const text = (el.textContent || '').trim().replace(/\s+/g, ' ');
    if (text) return text.slice(0, 60);
    const alt = el.getAttribute && (el.getAttribute('alt') || el.getAttribute('title'));
    return alt ? alt.slice(0, 60) : '';
  }

  function parseColor(value) {
    if (!value) return null;
    const match = value.match(/rgba?\(([^)]+)\)/);
    if (!match) return null;
    const parts = match[1].split(',').map((p) => parseFloat(p.trim()));
    if (parts.length < 3 || parts.some(Number.isNaN)) return null;
    return { r: parts[0], g: parts[1], b: parts[2], a: parts.length > 3 ? parts[3] : 1 };
  }

  function relativeLuminance({ r, g, b }) {
    const channel = (v) => {
      const s = v / 255;
      return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
    };
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
  }

  function contrastRatio(fg, bg) {
    const l1 = relativeLuminance(fg);
    const l2 = relativeLuminance(bg);
    const lighter = Math.max(l1, l2);
    const darker = Math.min(l1, l2);
    return (lighter + 0.05) / (darker + 0.05);
  }

  function blend(fg, bg) {
    const alpha = fg.a;
    return {
      r: fg.r * alpha + bg.r * (1 - alpha),
      g: fg.g * alpha + bg.g * (1 - alpha),
      b: fg.b * alpha + bg.b * (1 - alpha),
      a: 1,
    };
  }

  /** Walk ancestors for the first opaque background. Returns null if unknowable. */
  function effectiveBackground(el) {
    let node = el;
    let approximated = false;
    let accumulated = null;
    while (node && node.nodeType === 1) {
      const style = getComputedStyle(node);
      if (style.backgroundImage && style.backgroundImage !== 'none') approximated = true;
      const color = parseColor(style.backgroundColor);
      if (color && color.a > 0) {
        accumulated = accumulated ? blend(accumulated, color) : color;
        if (accumulated.a >= 1) return { color: accumulated, approximated };
      }
      node = node.parentElement;
    }
    const fallback = { r: 255, g: 255, b: 255, a: 1 };
    return { color: accumulated ? blend(accumulated, fallback) : fallback, approximated: true };
  }

  function isVisible(el, style, rect) {
    if (!rect || rect.width <= 0 || rect.height <= 0) return false;
    if (style.visibility === 'hidden' || style.display === 'none') return false;
    return parseFloat(style.opacity || '1') > 0.05;
  }

  function hasOwnText(el) {
    for (const node of el.childNodes) {
      if (node.nodeType === 3 && node.textContent.trim().length > 0) return true;
    }
    return false;
  }

  /**
   * Disabled controls are meant to look de-emphasised, and text hidden behind
   * `color: transparent` is usually a deliberate mechanic (a face-down card, a
   * reveal animation). Neither is a legibility defect.
   */
  function isDisabled(el) {
    if (el.disabled === true) return true;
    if (el.getAttribute && el.getAttribute('aria-disabled') === 'true') return true;
    return typeof el.closest === 'function' &&
      el.closest('[disabled], [aria-disabled="true"], fieldset:disabled') !== null;
  }

  function isDeliberatelyHidden(style) {
    const color = parseColor(style.color);
    return !color || color.a === 0;
  }

  /**
   * Handlers attached with addEventListener on a plain <div> are invisible to a
   * selector scan, and that is exactly how most generated UIs build cards,
   * tiles, and custom controls. `cursor: pointer` is the author's own signal
   * that something is clickable. Cursor inherits, so only credit the element
   * that introduces it, not every descendant.
   */
  function isPointerInteractive(el, style) {
    if (style.cursor !== 'pointer') return false;
    const parent = el.parentElement;
    if (!parent) return true;
    return getComputedStyle(parent).cursor !== 'pointer';
  }

  function addFinding(rule, severity, el, metric, actual, threshold, unit, detail, extra) {
    findings.push({
      rule,
      severity,
      selector: el ? cssPath(el) : ':root',
      label: el ? label(el) : '',
      detail,
      measurement: Object.assign(
        { metric, actual, threshold, unit },
        extra || {}
      ),
    });
  }

  function round(value, digits) {
    const factor = Math.pow(10, digits == null ? 2 : digits);
    return Math.round(value * factor) / factor;
  }

  // ------------------------------------------------------------- measurements

  const viewport = {
    width: window.innerWidth,
    height: window.innerHeight,
    device_pixel_ratio: window.devicePixelRatio || 1,
  };

  const allElements = [...document.querySelectorAll('body *')].slice(0, THRESHOLDS.maxElements);
  if (document.querySelectorAll('body *').length > THRESHOLDS.maxElements) {
    notes.push(`element scan capped at ${THRESHOLDS.maxElements} nodes`);
  }

  const visible = [];
  for (const el of allElements) {
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    if (isVisible(el, style, rect)) visible.push({ el, style, rect });
  }

  const palette = new Set();
  const fontSizes = new Set();
  const fontFamilies = new Set();
  const radii = new Set();
  const spacingValues = [];
  let offGridSpacing = 0;
  let approximatedBackgrounds = 0;

  function collectSpacing(style) {
    const props = [
      'marginTop', 'marginBottom', 'marginLeft', 'marginRight',
      'paddingTop', 'paddingBottom', 'paddingLeft', 'paddingRight',
      'gap',
    ];
    for (const prop of props) {
      const raw = style[prop];
      if (!raw || !raw.endsWith('px')) continue;
      const value = parseFloat(raw);
      if (!Number.isFinite(value) || value === 0) continue;
      spacingValues.push(value);
      const remainder = Math.abs(value % THRESHOLDS.spacingGridPx);
      const onGrid = remainder < 0.5 || Math.abs(remainder - THRESHOLDS.spacingGridPx) < 0.5;
      if (!onGrid) offGridSpacing += 1;
    }
  }

  // --- per-element rules
  for (const { el, style, rect } of visible) {
    const tag = el.tagName.toLowerCase();

    if (style.color) palette.add(style.color);
    if (style.backgroundColor && parseColor(style.backgroundColor)?.a > 0) {
      palette.add(style.backgroundColor);
    }
    if (style.fontFamily) fontFamilies.add(style.fontFamily.split(',')[0].trim().replace(/["']/g, ''));
    if (style.borderRadius && style.borderRadius !== '0px') radii.add(style.borderRadius);
    collectSpacing(style);

    const fontSize = parseFloat(style.fontSize);
    const textual = hasOwnText(el);
    if (textual && Number.isFinite(fontSize)) fontSizes.add(fontSize);

    // --- legibility + tiny text (text-bearing elements only)
    if (textual) {
      if (fontSize < THRESHOLDS.minFontPx) {
        addFinding(
          'tiny-text', SEVERITY.MAJOR, el, 'font_size', round(fontSize, 1),
          THRESHOLDS.minFontPx, 'px',
          'Body text is rendered below the comfortable reading floor.'
        );
      }

      const fg = parseColor(style.color);
      const bgInfo = effectiveBackground(el);
      const skipLegibility = isDeliberatelyHidden(style) || isDisabled(el);
      if (fg && bgInfo.color && !skipLegibility) {
        if (bgInfo.approximated) approximatedBackgrounds += 1;
        const resolvedFg = fg.a < 1 ? blend(fg, bgInfo.color) : fg;
        const ratio = contrastRatio(resolvedFg, bgInfo.color);
        const isLarge =
          fontSize >= THRESHOLDS.largeTextPx ||
          (fontSize >= 18.66 && parseInt(style.fontWeight, 10) >= 700);
        const threshold = isLarge
          ? THRESHOLDS.legibilityRatioLarge
          : THRESHOLDS.legibilityRatioNormal;
        if (ratio < threshold) {
          let severity;
          if (ratio < THRESHOLDS.legibilityRatioIllegible) {
            severity = SEVERITY.BLOCKER;
          } else if (ratio >= threshold * (1 - THRESHOLDS.marginalBand)) {
            severity = SEVERITY.MINOR;
          } else {
            severity = SEVERITY.MAJOR;
          }
          addFinding(
            'low-legibility', severity, el, 'contrast_ratio', round(ratio, 2),
            threshold, 'ratio',
            'Text does not separate enough from its background to read comfortably.',
            { approximated: bgInfo.approximated, font_size_px: round(fontSize, 1) }
          );
        }
      }
    }

    // --- clipped text
    const clipsX = style.overflowX === 'hidden' || style.overflowX === 'clip';
    const clipsY = style.overflowY === 'hidden' || style.overflowY === 'clip';
    const hasEllipsis = style.textOverflow === 'ellipsis';
    if (textual && !hasEllipsis) {
      if (clipsX && el.scrollWidth - el.clientWidth > 2) {
        addFinding(
          'text-clipped', SEVERITY.BLOCKER, el, 'overflow_x', el.scrollWidth - el.clientWidth,
          0, 'px', 'Text is cut off horizontally with no ellipsis and no way to scroll.'
        );
      } else if (clipsY && el.scrollHeight - el.clientHeight > 2) {
        addFinding(
          'text-clipped', SEVERITY.BLOCKER, el, 'overflow_y', el.scrollHeight - el.clientHeight,
          0, 'px', 'Text is cut off vertically with no way to reveal the rest.'
        );
      }
    }

    // --- element pushed outside the viewport
    if (rect.right > viewport.width + 1 || rect.left < -1) {
      const overhang = Math.max(rect.right - viewport.width, -rect.left);
      if (overhang > 4) {
        addFinding(
          'element-overflows-viewport', SEVERITY.MAJOR, el, 'overhang', round(overhang, 1),
          0, 'px', 'Element extends past the viewport edge at this width.'
        );
      }
    }

    // --- distorted images
    if (tag === 'img' && el.naturalWidth > 0 && el.naturalHeight > 0) {
      const naturalRatio = el.naturalWidth / el.naturalHeight;
      const renderedRatio = rect.width / rect.height;
      const drift = Math.abs(renderedRatio - naturalRatio) / naturalRatio;
      const objectFitCorrects = style.objectFit === 'cover' || style.objectFit === 'contain';
      if (drift > 0.02 && !objectFitCorrects) {
        addFinding(
          'image-aspect-distortion', SEVERITY.MAJOR, el, 'aspect_drift', round(drift * 100, 1),
          2, 'percent', 'Image is stretched or squashed relative to its natural aspect ratio.'
        );
      }
    }
  }

  // --- interactive element rules
  const interactive = visible.filter(
    ({ el, style }) => el.matches(INTERACTIVE_SELECTOR) || isPointerInteractive(el, style)
  );
  for (const { el, style, rect } of interactive) {
    if (isDisabled(el)) continue;

    const inlineInText =
      el.tagName.toLowerCase() === 'a' &&
      el.parentElement &&
      hasOwnText(el.parentElement);

    const smallest = Math.min(rect.width, rect.height);
    if (!inlineInText && smallest < THRESHOLDS.minTargetPx) {
      addFinding(
        'target-too-small',
        smallest < THRESHOLDS.criticalTargetPx ? SEVERITY.BLOCKER : SEVERITY.MAJOR,
        el, 'min_side', round(smallest, 1), THRESHOLDS.minTargetPx, 'px',
        'Control is smaller than a comfortable pointer or thumb target.',
        { width: round(rect.width, 1), height: round(rect.height, 1) }
      );
    }

    // occlusion: whatever paints at the control's center should be the control
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    if (cx >= 0 && cy >= 0 && cx <= viewport.width && cy <= viewport.height) {
      const hit = document.elementFromPoint(cx, cy);
      if (hit && hit !== el && !el.contains(hit) && !hit.contains(el)) {
        addFinding(
          'occluded-interactive', SEVERITY.BLOCKER, el, 'hit_test', 0, 1, 'boolean',
          'Another element paints on top of this control, so clicks never reach it.',
          { occluded_by: cssPath(hit) }
        );
      }
    }

    const formControl = ['input', 'textarea', 'select'].includes(el.tagName.toLowerCase());
    if (style.cursor !== 'pointer' && !formControl) {
      addFinding(
        'missing-hover-affordance', SEVERITY.MINOR, el, 'cursor', 0, 1, 'boolean',
        'Control does not signal that it is clickable on hover.',
        { cursor: style.cursor }
      );
    }

    // two-line clickable label — a Hallmark-style tell and a real hit-area problem
    const lineHeight = parseFloat(style.lineHeight);
    if (Number.isFinite(lineHeight) && lineHeight > 0 && label(el)) {
      const lines = Math.round(rect.height / lineHeight);
      const isBlockControl = ['button', 'a'].includes(el.tagName.toLowerCase());
      if (isBlockControl && lines >= 2 && rect.height < lineHeight * 4) {
        addFinding(
          'two-line-clickable', SEVERITY.MINOR, el, 'line_count', lines, 1, 'lines',
          'Clickable label wraps onto multiple lines, which reads as a layout break.'
        );
      }
    }
  }

  // --- document-level: horizontal scroll
  const docScrollWidth = document.documentElement.scrollWidth;
  if (docScrollWidth - viewport.width > 2) {
    addFinding(
      'viewport-overflow', SEVERITY.BLOCKER, null, 'horizontal_overflow',
      docScrollWidth - viewport.width, 0, 'px',
      'The page scrolls sideways at this width.'
    );
  }

  // --- design-system discipline (single summary findings, not per element)
  const distinctColors = palette.size;
  if (distinctColors > THRESHOLDS.maxDistinctColors) {
    addFinding(
      'palette-sprawl', SEVERITY.MINOR, null, 'distinct_colors', distinctColors,
      THRESHOLDS.maxDistinctColors, 'count',
      'The page uses more distinct colours than a coherent palette normally needs.'
    );
  }

  if (fontSizes.size > THRESHOLDS.maxDistinctFontSizes) {
    addFinding(
      'type-scale-sprawl', SEVERITY.MINOR, null, 'distinct_font_sizes', fontSizes.size,
      THRESHOLDS.maxDistinctFontSizes, 'count',
      'Type sizes do not follow a small, deliberate scale.'
    );
  }

  if (fontFamilies.size > THRESHOLDS.maxDistinctFontFamilies) {
    addFinding(
      'font-family-sprawl', SEVERITY.MINOR, null, 'distinct_font_families', fontFamilies.size,
      THRESHOLDS.maxDistinctFontFamilies, 'count',
      'More typefaces are in play than a display + body pairing.'
    );
  }

  if (radii.size > THRESHOLDS.maxDistinctRadii) {
    addFinding(
      'radius-sprawl', SEVERITY.MINOR, null, 'distinct_radii', radii.size,
      THRESHOLDS.maxDistinctRadii, 'count',
      'Corner rounding is inconsistent across components.'
    );
  }

  if (spacingValues.length > 0) {
    const share = offGridSpacing / spacingValues.length;
    if (share > THRESHOLDS.spacingOffGridShare) {
      addFinding(
        'spacing-off-scale', SEVERITY.MINOR, null, 'off_grid_share', round(share * 100, 1),
        THRESHOLDS.spacingOffGridShare * 100, 'percent',
        `Spacing values do not sit on a ${THRESHOLDS.spacingGridPx}px rhythm.`,
        { samples: spacingValues.length, off_grid: offGridSpacing }
      );
    }
  }

  // --- near-miss alignment between block siblings
  const alignmentOffenders = [];
  const containers = new Set(visible.map(({ el }) => el.parentElement).filter(Boolean));
  for (const container of containers) {
    const children = [...container.children]
      .map((child) => ({ child, rect: child.getBoundingClientRect() }))
      .filter(({ rect }) => rect.width > 0 && rect.height > 0);
    if (children.length < 2 || children.length > 24) continue;
    for (let i = 0; i < children.length - 1; i += 1) {
      const delta = Math.abs(children[i].rect.left - children[i + 1].rect.left);
      if (delta >= THRESHOLDS.alignmentNearMissMinPx && delta <= THRESHOLDS.alignmentNearMissMaxPx) {
        alignmentOffenders.push({
          a: cssPath(children[i].child),
          b: cssPath(children[i + 1].child),
          delta_px: round(delta, 2),
        });
      }
    }
  }
  if (alignmentOffenders.length > 0) {
    addFinding(
      'near-miss-alignment', SEVERITY.MINOR, null, 'near_miss_pairs', alignmentOffenders.length,
      0, 'count',
      'Sibling elements are almost aligned but off by a few pixels, which reads as sloppy.',
      { pairs: alignmentOffenders.slice(0, 10) }
    );
  }

  // --- unstyled browser defaults
  // `border-style: outset` is the user-agent button default and is effectively
  // never authored deliberately, so it is a more robust signal than matching
  // the default grey, which differs between browser versions.
  const bodyStyle = getComputedStyle(document.body);
  const bodyFamily = bodyStyle.fontFamily.toLowerCase();
  const defaultSerif = /times|serif/.test(bodyFamily) && !/sans-serif/.test(bodyFamily);
  const unstyledButtons = interactive.filter(
    ({ el, style }) =>
      el.tagName.toLowerCase() === 'button' &&
      !isDisabled(el) &&
      style.borderStyle === 'outset'
  ).length;
  if (defaultSerif || unstyledButtons > 0) {
    addFinding(
      'unstyled-default', SEVERITY.MAJOR, null, 'default_signals',
      (defaultSerif ? 1 : 0) + (unstyledButtons > 0 ? 1 : 0), 0, 'count',
      'The page still shows browser default styling, so it reads as unfinished.',
      { default_serif_body: defaultSerif, unstyled_buttons: unstyledButtons }
    );
  }

  if (approximatedBackgrounds > 0) {
    notes.push(
      `${approximatedBackgrounds} legibility measurements sat on an image or gradient ` +
      'background and are approximate — confirm visually before reporting.'
    );
  }

  const countsByRule = {};
  const countsBySeverity = {};
  for (const finding of findings) {
    countsByRule[finding.rule] = (countsByRule[finding.rule] || 0) + 1;
    countsBySeverity[finding.severity] = (countsBySeverity[finding.severity] || 0) + 1;
  }

  // Collapse repeats: the same rule firing on 16 sibling cards is one defect
  // with 16 instances, not 16 findings to triage.
  const perRuleSeen = {};
  const reported = [];
  for (const finding of findings) {
    const seen = perRuleSeen[finding.rule] || 0;
    if (seen < THRESHOLDS.maxFindingsPerRule) {
      reported.push(
        Object.assign({}, finding, { occurrences: countsByRule[finding.rule] })
      );
    }
    perRuleSeen[finding.rule] = seen + 1;
  }
  const suppressed = findings.length - reported.length;
  if (suppressed > 0) {
    notes.push(
      `${suppressed} repeated findings collapsed; see summary.by_rule for full counts.`
    );
  }

  return {
    probe_version: PROBE_VERSION,
    url: location.href,
    title: document.title,
    generated_at: new Date().toISOString(),
    viewport,
    thresholds: THRESHOLDS,
    findings: reported,
    summary: {
      total: findings.length,
      reported: reported.length,
      by_rule: countsByRule,
      by_severity: countsBySeverity,
      distinct_colors: distinctColors,
      distinct_font_sizes: fontSizes.size,
      distinct_font_families: [...fontFamilies],
      elements_scanned: visible.length,
    },
    notes,
  };
})();
