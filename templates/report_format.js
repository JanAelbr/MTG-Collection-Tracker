function escapeHtml(text) {
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function formatEuro(value) {
    if (value == null || Number.isNaN(value)) {
        return 'Unknown';
    }
    const parts = Number(value).toFixed(2).split('.');
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    return `€ ${parts.join('.')}`;
}

function formatInvested(value) {
    if (value == null || Number.isNaN(value)) {
        return formatEuro(0);
    }
    return formatEuro(value);
}

function formatPurchaseValue(value) {
    if (value == null || Number.isNaN(value)) {
        return '';
    }
    return formatEuro(value);
}

function formatProfit(value, unknownLabel) {
    if (value == null || Number.isNaN(value)) {
        return unknownLabel || '';
    }
    if (value >= 0) {
        return `<span class="profit-cell">🟢 ${formatEuro(value)}</span>`;
    }
    return `<span class="loss-cell">🔴 ${formatEuro(value)}</span>`;
}

function hasPurchasePrice(purchaseValue) {
    return purchaseValue != null && !Number.isNaN(purchaseValue) && purchaseValue !== 0;
}

function formatGainLoss(profitLoss, purchaseValue, unknownLabel = '') {
    if (!hasPurchasePrice(purchaseValue)) {
        return unknownLabel || '';
    }
    if (profitLoss == null || Number.isNaN(profitLoss)) {
        return unknownLabel || '';
    }
    return formatProfit(profitLoss, unknownLabel);
}

function collectorSortKey(collectorNumber) {
    const str = String(collectorNumber);
    const match = str.match(/^(\d+)(.*)$/);
    if (!match) {
        return [Number.MAX_SAFE_INTEGER, str.toLowerCase()];
    }
    return [parseInt(match[1], 10), match[2].toLowerCase()];
}

function sortCardsByCollectorNumber(cards) {
    return [...cards].sort((left, right) => {
        const a = collectorSortKey(left.collector_number);
        const b = collectorSortKey(right.collector_number);
        if (a[0] !== b[0]) {
            return a[0] - b[0];
        }
        return String(a[1]).localeCompare(String(b[1]));
    });
}

function formatPercentChange(change, previousValue) {
    if (change == null || Number.isNaN(change) || previousValue == null || Number.isNaN(previousValue) || previousValue === 0) {
        return '';
    }
    const percent = (change / previousValue) * 100;
    const formatted = `${Math.abs(percent).toFixed(1)}%`;
    if (percent > 0) {
        return ` (+${formatted})`;
    }
    if (percent < 0) {
        return ` (-${formatted})`;
    }
    return ' (0.0%)';
}

function formatPriceChange(value, previousValue) {
    if (value == null || Number.isNaN(value)) {
        return '—';
    }
    if (value === 0) {
        return 'No changes';
    }
    const suffix = formatPercentChange(value, previousValue);
    if (value > 0) {
        return `<span class="profit-cell">🟢 +${formatEuro(value)}${suffix}</span>`;
    }
    return `<span class="loss-cell">🔴 ${formatEuro(value)}${suffix}</span>`;
}

function hasDeckPrint(card) {
    return Boolean(card.set_code && card.collector_number);
}

function buildDeckCardNameHtml(card, options = {}) {
    const {
        linkClass = 'card-name-link',
        showSetInName = false,
        showNotOwnedBadge = true,
    } = options;

    if (!hasDeckPrint(card)) {
        return escapeHtml(resolveCardName(card));
    }

    const ref = {
        set_code: card.set_code,
        collector_number: card.collector_number,
        name: resolveCardName(card),
        foil: card.foil,
        image_uri: card.image_uri,
        cardmarket_url: card.cardmarket_url,
    };
    const number = String(ref.collector_number).padStart(3, '0');
    const name = displayName(ref);
    let nameHtml;
    if (card.in_catalog) {
        const setSuffix = showSetInName ? ` (${escapeHtml(card.set_code)})` : '';
        nameHtml = (
            `<a href="${cardDetailUrl(ref, card.foil)}" class="${linkClass}">` +
            `${escapeHtml(name)}${setSuffix}</a>`
        );
    } else {
        const setSuffix = showSetInName ? ` (${escapeHtml(card.set_code)})` : '';
        nameHtml = `${escapeHtml(name)}${setSuffix}`;
    }

    let labelHtml = `${escapeHtml(number)} - ${nameHtml}`;
    if (showNotOwnedBadge && card.owned_qty <= 0) {
        labelHtml += ' <span class="unowned-badge">Not owned</span>';
    }
    return wrapCardPreview(labelHtml, ref.image_uri);
}

function formatDeckUnknownCardLine(card) {
    if (!hasDeckPrint(card)) {
        return resolveCardName(card);
    }
    const number = String(card.collector_number).padStart(3, '0');
    const name = resolveCardName(card);
    return `${card.set_code} - ${number} - ${name} - ${formatFinish(card.foil)}`;
}

function coerceCardText(value) {
    if (value == null) {
        return '';
    }
    if (typeof value === 'number' && Number.isNaN(value)) {
        return '';
    }
    const text = String(value).trim();
    if (!text || text.toLowerCase() === 'nan' || text.toLowerCase() === 'undefined' || text.toLowerCase() === 'null') {
        return '';
    }
    return text;
}

function resolveCardName(card) {
    const name = coerceCardText(card?.name)
        || coerceCardText(card?.catalog_name)
        || coerceCardText(card?.card_name);
    if (name) {
        return name;
    }
    if (card?.set_code && card?.collector_number) {
        return `${card.set_code} #${card.collector_number}`;
    }
    return 'Unknown';
}

function displayName(card) {
    const name = resolveCardName(card);
    if (Number(card?.foil) === 1) {
        return `✨ ${name}`;
    }
    return name;
}

function formatFinish(foil) {
    return Number(foil) === 1 ? 'Foil' : 'Non-foil';
}

function wrapCardPreview(labelHtml, imageUri) {
    if (!imageUri) {
        return labelHtml;
    }
    return `<span class="card-preview" data-image="${escapeHtml(imageUri)}">${labelHtml}</span>`;
}

function cardDetailUrl(card, finish) {
    const params = new URLSearchParams({
        set: card.set_code,
        number: card.collector_number,
    });
    const resolvedFinish = finish ?? (Number(card.foil ?? 0) === 1 ? '1' : '0');
    if (resolvedFinish === '1') {
        params.set('finish', '1');
    }
    return `card.html?${params.toString()}`;
}

function collectionReportUrl(setCode, artStyle, ownedOnly, foilFilter) {
    return topReportUrl(setCode, {
        artStyle,
        ownedFilter: ownedOnly ? 'owned' : 'all',
        foilFilter,
    });
}

function topReportUrl(setCode, options = {}) {
    const params = new URLSearchParams();
    if (setCode) {
        params.set('set', setCode);
    }
    const artStyle = options.artStyle;
    if (artStyle) {
        params.set('art', artStyle);
    }
    const ownedFilter = options.ownedFilter;
    if (ownedFilter && ownedFilter !== 'owned') {
        params.set('owned', ownedFilter);
    }
    const foilFilter = options.foilFilter;
    if (foilFilter && foilFilter !== 'all') {
        params.set('foil', foilFilter);
    }
    const query = params.toString();
    return query ? `collection_top.html?${query}` : 'collection_top.html';
}

function topReportSetUrl(setCode) {
    return topReportUrl(setCode);
}

function buildSetLinkCell(setCode) {
    if (!setCode) {
        return '—';
    }
    return (
        `<a href="${escapeHtml(topReportSetUrl(setCode))}" class="stats-art-style-link">` +
        `${escapeHtml(setCode)}</a>`
    );
}

function parseCollectionUrlFilters() {
    const params = new URLSearchParams(window.location.search);
    const owned = params.get('owned');
    let ownedFilter = null;
    if (owned === 'owned' || owned === 'all' || owned === 'unowned') {
        ownedFilter = owned;
    }
    const foil = params.get('foil');
    let foilFilter = null;
    if (foil === 'all' || foil === 'nonfoil' || foil === 'foil') {
        foilFilter = foil;
    }
    return {
        setCode: params.get('set'),
        artStyle: params.get('art'),
        ownedFilter,
        foilFilter,
    };
}

function getInitialSet(availableSets, includeAll = true) {
    const { setCode } = parseCollectionUrlFilters();
    if (setCode === 'All' && includeAll) {
        return 'All';
    }
    if (setCode && availableSets.includes(setCode)) {
        return setCode;
    }
    return getStoredSet(availableSets, includeAll);
}

function buildCardLabel(card, ownedOnly) {
    const number = String(card.collector_number).padStart(3, '0');
    const nameLink = (
        `<a href="${cardDetailUrl(card)}" class="card-name-link">` +
        `${escapeHtml(displayName(card))}</a>`
    );
    let labelHtml = `${escapeHtml(number)} - ${nameLink}`;
    if (!ownedOnly && (card.purchase_value == null || Number.isNaN(card.purchase_value))) {
        labelHtml += ' <span class="unowned-badge">Not owned</span>';
    }
    return wrapCardPreview(labelHtml, card.image_uri);
}

function buildCurrentValueCell(card) {
    const text = formatEuro(card.current_value);
    if (!card.cardmarket_url) {
        return text;
    }
    const safeUrl = escapeHtml(card.cardmarket_url);
    return (
        `<a href="${safeUrl}" target="_blank" rel="noopener noreferrer" class="price-link">${text}</a>`
    );
}

function parseEuroNumber(value) {
    if (value == null) {
        return NaN;
    }

    const text = String(value)
        .replace(/<[^>]*>/g, '')
        .replace(/[€\s]/g, '')
        .replace(/,/g, '')
        .replace(/^[^\d+-]*/g, '');

    const match = text.match(/([-+]?\d+(?:\.\d+)?)/);
    return match ? parseFloat(match[1]) : NaN;
}

function cardKey(card) {
    return `${card.set_code}|${card.collector_number}|${card.foil}`;
}

function getCurrentSet() {
    return document.body.dataset.currentSet || 'All';
}

const CURRENT_SET_KEY = 'reportCurrentSet';
const PRICE_COMPARE_KEY = 'priceComparePreset';
const LEGACY_PRICE_COMPARE_KEY = 'priceCompareDate';

const COMPARE_PRESETS = [
    { id: '1d', label: 'Yesterday', days: 1 },
    { id: '7d', label: '7 days ago', days: 7 },
    { id: '30d', label: '30 days ago', days: 30 },
    { id: '60d', label: '60 days ago', days: 60 },
    { id: '90d', label: '90 days ago', days: 90 },
    { id: '180d', label: '180 days ago', days: 180 },
    { id: '365d', label: '1 year ago', days: 365 },
    { id: 'start', label: 'Since the beginning', days: null },
];

function getStoredSet(availableSets, includeAll = true) {
    const stored = localStorage.getItem(CURRENT_SET_KEY);
    if (includeAll && stored === 'All') {
        return 'All';
    }
    if (stored && availableSets.includes(stored)) {
        return stored;
    }
    if (includeAll) {
        return 'All';
    }
    return availableSets[0] || '';
}

function setCurrentSet(setCode) {
    document.body.dataset.currentSet = setCode;
    localStorage.setItem(CURRENT_SET_KEY, setCode);
}

function getAvailableSetsFromSelect(select) {
    return Array.from(select.options)
        .filter((option) => !option.disabled && option.value && option.value !== 'All')
        .map((option) => option.value);
}

function syncSetUrlParam(setCode) {
    const params = new URLSearchParams(window.location.search);
    const artStyle = params.get('art');
    const owned = params.get('owned');
    const foil = params.get('foil');
    if (setCode && setCode !== 'All') {
        params.set('set', setCode);
    } else {
        params.delete('set');
    }
    if (artStyle) {
        params.set('art', artStyle);
    }
    if (owned) {
        params.set('owned', owned);
    }
    if (foil && foil !== 'all') {
        params.set('foil', foil);
    } else {
        params.delete('foil');
    }
    const query = params.toString();
    const nextUrl = query ? `${window.location.pathname}?${query}` : window.location.pathname;
    window.history.replaceState({}, '', nextUrl);
}

function getSetSelectItems(select) {
    return Array.from(select.options).map((option) => ({
        value: option.value,
        label: option.textContent.trim(),
        separator: option.disabled && option.classList.contains('report-set-separator'),
        selectable: !option.disabled && Boolean(option.value),
    }));
}

function filterSetSelectItems(items, query) {
    const normalized = query.trim().toLowerCase();
    if (!normalized) {
        return items.filter((item) => item.separator || item.selectable);
    }
    return items.filter((item) => (
        item.selectable
        && (item.label.toLowerCase().includes(normalized)
            || item.value.toLowerCase().includes(normalized))
    ));
}

function getSetSelectOptionLabel(select) {
    const option = select.options[select.selectedIndex];
    return option ? option.textContent.trim() : '';
}

function enhanceSearchableSetSelect(select) {
    if (!select || select.dataset.searchable === 'true') {
        return select?._setCombobox || null;
    }

    select.dataset.searchable = 'true';
    const allItems = getSetSelectItems(select);

    const wrapper = document.createElement('div');
    wrapper.className = 'report-set-combobox-inner';

    const input = document.createElement('input');
    input.type = 'text';
    input.id = 'report-set-select-filter';
    input.className = 'report-set-combobox-input report-set-select';
    input.placeholder = 'Search sets...';
    input.autocomplete = 'off';
    input.spellcheck = false;
    input.setAttribute('role', 'combobox');
    input.setAttribute('aria-autocomplete', 'list');
    input.setAttribute('aria-controls', 'report-set-select-list');
    input.setAttribute('aria-expanded', 'false');

    const list = document.createElement('ul');
    list.id = 'report-set-select-list';
    list.className = 'report-set-combobox-list';
    list.setAttribute('role', 'listbox');
    list.hidden = true;

    select.classList.add('report-set-select-native');
    select.tabIndex = -1;
    select.setAttribute('aria-hidden', 'true');

    const label = document.querySelector('label[for="report-set-select"]');
    if (label) {
        label.setAttribute('for', 'report-set-select-filter');
    }

    select.parentNode.insertBefore(wrapper, select);
    wrapper.appendChild(input);
    wrapper.appendChild(select);
    wrapper.appendChild(list);

    let isOpen = false;
    let highlightIndex = -1;

    function renderList(items) {
        list.innerHTML = '';
        items.forEach((item) => {
            if (item.separator) {
                const separator = document.createElement('li');
                separator.className = 'report-set-combobox-separator';
                separator.textContent = item.label;
                separator.setAttribute('role', 'separator');
                list.appendChild(separator);
                return;
            }

            const option = document.createElement('li');
            option.className = 'report-set-combobox-option';
            if (item.value === select.value) {
                option.classList.add('active');
            }
            option.textContent = item.label;
            option.dataset.value = item.value;
            option.setAttribute('role', 'option');
            option.setAttribute('aria-selected', item.value === select.value ? 'true' : 'false');
            option.addEventListener('mousedown', (event) => {
                event.preventDefault();
                chooseValue(item.value);
            });
            list.appendChild(option);
        });
    }

    function getSelectableOptions() {
        return Array.from(list.querySelectorAll('.report-set-combobox-option'));
    }

    function updateHighlight() {
        const options = getSelectableOptions();
        options.forEach((option, index) => {
            option.classList.toggle('highlighted', index === highlightIndex);
        });
        const highlighted = options[highlightIndex];
        if (highlighted) {
            highlighted.scrollIntoView({ block: 'nearest' });
        }
    }

    function syncDisplay() {
        if (!isOpen) {
            input.value = getSetSelectOptionLabel(select);
        }
    }

    function openCombobox() {
        if (isOpen) {
            return;
        }
        isOpen = true;
        highlightIndex = -1;
        input.setAttribute('aria-expanded', 'true');
        list.hidden = false;
        renderList(filterSetSelectItems(allItems, ''));
    }

    function closeCombobox() {
        if (!isOpen) {
            syncDisplay();
            return;
        }
        isOpen = false;
        highlightIndex = -1;
        input.setAttribute('aria-expanded', 'false');
        list.hidden = true;
        syncDisplay();
    }

    function chooseValue(value) {
        closeCombobox();
        if (select.value !== value) {
            select.value = value;
            select.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }

    input.addEventListener('focus', () => {
        openCombobox();
        input.select();
    });

    input.addEventListener('input', () => {
        if (!isOpen) {
            openCombobox();
        }
        highlightIndex = -1;
        renderList(filterSetSelectItems(allItems, input.value));
    });

    input.addEventListener('keydown', (event) => {
        const options = getSelectableOptions();
        if (event.key === 'ArrowDown') {
            event.preventDefault();
            if (!isOpen) {
                openCombobox();
            }
            if (options.length) {
                highlightIndex = Math.min(highlightIndex + 1, options.length - 1);
                updateHighlight();
            }
        } else if (event.key === 'ArrowUp') {
            event.preventDefault();
            if (!isOpen) {
                openCombobox();
            }
            if (options.length) {
                highlightIndex = Math.max(highlightIndex - 1, 0);
                updateHighlight();
            }
        } else if (event.key === 'Enter') {
            if (!isOpen) {
                return;
            }
            event.preventDefault();
            if (highlightIndex >= 0 && options[highlightIndex]) {
                chooseValue(options[highlightIndex].dataset.value);
            } else if (options.length === 1) {
                chooseValue(options[0].dataset.value);
            }
        } else if (event.key === 'Escape') {
            event.preventDefault();
            closeCombobox();
            input.blur();
        }
    });

    input.addEventListener('blur', () => {
        window.setTimeout(() => closeCombobox(), 150);
    });

    const combobox = { syncDisplay, close: closeCombobox };
    select._setCombobox = combobox;
    syncDisplay();
    return combobox;
}

function initSetNav(onSetChange, options = {}) {
    const select = document.getElementById('report-set-select');
    if (!select) {
        onSetChange(getCurrentSet());
        return;
    }

    const combobox = enhanceSearchableSetSelect(select);
    const includeAll = options.includeAll !== false;
    const availableSets = getAvailableSetsFromSelect(select);
    const initialSet = getInitialSet(availableSets, includeAll);
    select.value = initialSet;
    combobox?.syncDisplay();
    setCurrentSet(initialSet);
    syncSetUrlParam(initialSet);
    onSetChange(initialSet);

    select.addEventListener('change', function () {
        const setCode = select.value;
        combobox?.syncDisplay();
        setCurrentSet(setCode);
        syncSetUrlParam(setCode);
        onSetChange(setCode);
    });
}

function parseIsoDate(iso) {
    const parts = String(iso).split('-').map(Number);
    return new Date(parts[0], parts[1] - 1, parts[2]);
}

function subtractDays(date, days) {
    const copy = new Date(date.getTime());
    copy.setDate(copy.getDate() - days);
    return copy;
}

function findClosestCompareDate(compareDates, targetDate) {
    if (!compareDates.length) {
        return null;
    }

    let best = compareDates[0];
    let bestDiff = Math.abs(parseIsoDate(best) - targetDate);
    for (let index = 1; index < compareDates.length; index += 1) {
        const candidate = compareDates[index];
        const diff = Math.abs(parseIsoDate(candidate) - targetDate);
        if (diff < bestDiff) {
            best = candidate;
            bestDiff = diff;
        }
    }
    return best;
}

function getComparePreset(presetId) {
    return COMPARE_PRESETS.find((preset) => preset.id === presetId) || COMPARE_PRESETS[0];
}

function resolveCompareDate(data, presetId) {
    const compareDates = data.compareDates || [];
    if (!compareDates.length) {
        return null;
    }

    const preset = getComparePreset(presetId);
    if (preset.days == null) {
        return compareDates[compareDates.length - 1];
    }

    const anchor = data.currentDate
        ? parseIsoDate(data.currentDate)
        : parseIsoDate(compareDates[0]);
    const targetDate = subtractDays(anchor, preset.days);
    return findClosestCompareDate(compareDates, targetDate);
}

function findPresetIdForDate(data, date) {
    for (const preset of COMPARE_PRESETS) {
        if (resolveCompareDate(data, preset.id) === date) {
            return preset.id;
        }
    }

    let bestId = '1d';
    let bestDiff = Infinity;
    for (const preset of COMPARE_PRESETS) {
        const resolved = resolveCompareDate(data, preset.id);
        if (!resolved) {
            continue;
        }
        const diff = Math.abs(parseIsoDate(resolved) - parseIsoDate(date));
        if (diff < bestDiff) {
            bestDiff = diff;
            bestId = preset.id;
        }
    }
    return bestId;
}

function getSelectedComparePreset(data) {
    const stored = localStorage.getItem(PRICE_COMPARE_KEY);
    if (stored && COMPARE_PRESETS.some((preset) => preset.id === stored)) {
        return stored;
    }

    const legacyDate = localStorage.getItem(LEGACY_PRICE_COMPARE_KEY);
    if (legacyDate && data.compareDates && data.compareDates.includes(legacyDate)) {
        return findPresetIdForDate(data, legacyDate);
    }

    return '1d';
}

function getSelectedCompareDate(data) {
    return resolveCompareDate(data, getSelectedComparePreset(data));
}

function saveComparePreset(presetId) {
    localStorage.setItem(PRICE_COMPARE_KEY, presetId);
}

function updateCompareNavActive(nav, presetId) {
    nav.querySelectorAll('[data-preset]').forEach((button) => {
        button.classList.toggle('active', button.dataset.preset === presetId);
    });
}

function initPriceCompareNav(data, onCompareChange) {
    const nav = document.getElementById('price-compare-nav');
    if (!nav || !data.compareDates || !data.compareDates.length) {
        return;
    }

    let selectedPresetId = getSelectedComparePreset(data);

    nav.innerHTML = COMPARE_PRESETS.map((preset) => {
        const resolvedDate = resolveCompareDate(data, preset.id);
        const active = preset.id === selectedPresetId ? ' active' : '';
        const title = resolvedDate
            ? ` title="${escapeHtml(resolvedDate)}"`
            : '';
        return (
            `<button type="button" class="report-compare-link${active}"` +
            ` data-preset="${preset.id}"${title}>${escapeHtml(preset.label)}</button>`
        );
    }).join('');

    nav.addEventListener('click', (event) => {
        const button = event.target.closest('[data-preset]');
        if (!button) {
            return;
        }

        const presetId = button.dataset.preset;
        if (presetId === selectedPresetId) {
            return;
        }

        selectedPresetId = presetId;
        saveComparePreset(presetId);
        updateCompareNavActive(nav, presetId);
        onCompareChange(resolveCompareDate(data, presetId), getComparePreset(presetId));
    });
}

function enrichCardWithSnapshot(card, compareDate, snapshots) {
    const snapshot = snapshots[compareDate] || {};
    const previousValue = snapshot[cardKey(card)];
    const priceChange = (
        previousValue != null && card.current_value != null
    ) ? card.current_value - previousValue : null;
    return {
        ...card,
        previous_value: previousValue ?? null,
        price_change: priceChange,
    };
}

function updateChangeHeader(tableSelector, columnIndex, compareLabel, compareDate) {
    const header = document.querySelector(`${tableSelector} thead th:nth-child(${columnIndex})`);
    if (!header) {
        return;
    }

    if (compareLabel) {
        header.textContent = `Change (${compareLabel})`;
        if (compareDate) {
            header.title = compareDate;
        } else {
            header.removeAttribute('title');
        }
        return;
    }

    header.textContent = 'Change';
    header.removeAttribute('title');
}

function csvEscape(value) {
    const text = value == null ? '' : String(value);
    if (/[",;\n]/.test(text)) {
        return `"${text.replace(/"/g, '""')}"`;
    }
    return text;
}

function buildCsvContent(headers, rows) {
    const lines = [headers.map(csvEscape).join(';')];
    rows.forEach((row) => {
        lines.push(row.map(csvEscape).join(';'));
    });
    return `\ufeff${lines.join('\n')}`;
}

function downloadCsv(filename, headers, rows) {
    const blob = new Blob([buildCsvContent(headers, rows)], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
    URL.revokeObjectURL(link.href);
}

const CARD_CSV_HEADERS = [
    'set_code',
    'art_style',
    'collector_number',
    'name',
    'foil',
    'current_value',
    'price_change',
    'purchase_value',
    'profit_loss',
];

const SUMMARY_CSV_HEADERS = [
    'set_code',
    'art_style',
    'cards',
    'current_value',
    'price_change',
    'profit_loss',
];

const PORTFOLIO_CSV_HEADERS = ['date', 'value', 'invested'];

const UNKNOWN_CARD_CSV_HEADERS = [
    'set_code',
    'collector_number',
    'name',
    'art_style',
    'foil',
];

function finishLabel(finish) {
    return Number(finish) === 1 ? 'Foil' : 'Non-foil';
}

function cardsToCsvRows(cards) {
    return cards.map((card) => ([
        card.set_code,
        card.art_style,
        card.collector_number,
        card.name,
        finishLabel(card.foil),
        card.current_value,
        card.price_change,
        card.purchase_value,
        card.profit_loss,
    ]));
}

function summaryToCsvRows(summaryRows) {
    return summaryRows.map((row) => ([
        row.set_code,
        row.art_style,
        row.cards,
        row.current_value,
        row.price_change,
        row.profit_loss,
    ]));
}

function portfolioHistoryToCsvRows(history) {
    return (history || []).map((point) => ([
        point.date,
        point.value,
        point.invested,
    ]));
}

function unknownCardsToCsvRows(cards) {
    return (cards || []).map((card) => ([
        card.set_code,
        card.collector_number,
        card.name,
        card.art_style,
        finishLabel(card.foil),
    ]));
}

function aggregateSummaryChanges(cards, summaryRows) {
    const changes = {};
    const previousTotals = {};
    cards.forEach((card) => {
        if (card.price_change == null || Number.isNaN(card.price_change)) {
            if (card.previous_value != null && !Number.isNaN(card.previous_value)) {
                const key = `${card.set_code}|${card.art_style}`;
                previousTotals[key] = (previousTotals[key] || 0) + card.previous_value;
            }
            return;
        }
        const key = `${card.set_code}|${card.art_style}`;
        changes[key] = (changes[key] || 0) + card.price_change;
        if (card.previous_value != null && !Number.isNaN(card.previous_value)) {
            previousTotals[key] = (previousTotals[key] || 0) + card.previous_value;
        }
    });

    return summaryRows.map((row) => ({
        ...row,
        price_change: changes[`${row.set_code}|${row.art_style}`] ?? null,
        previous_total: previousTotals[`${row.set_code}|${row.art_style}`] ?? null,
    }));
}

const PAGE_SIZE_KEY = 'reportPageSize';
const OWNED_FILTER_KEY = 'reportOwnedFilter';
const FOIL_FILTER_KEY = 'reportFoilFilter';
const DEFAULT_RANKED_PAGE_SIZE = 25;

function getStoredOwnedFilter() {
    const stored = localStorage.getItem(OWNED_FILTER_KEY);
    if (stored === 'owned' || stored === 'all' || stored === 'unowned') {
        return stored;
    }
    return 'owned';
}

function getStoredFoilFilter() {
    const stored = localStorage.getItem(FOIL_FILTER_KEY);
    if (stored === 'all' || stored === 'nonfoil' || stored === 'foil') {
        return stored;
    }
    return 'all';
}

function cardMatchesFoilFilter(card, foilFilter) {
    if (!foilFilter || foilFilter === 'all') {
        return true;
    }
    const target = foilFilter === 'foil' ? 1 : 0;
    return Number(card.foil) === target;
}

function applyFoilFilter(cards, foilFilter) {
    if (!foilFilter || foilFilter === 'all') {
        return cards;
    }
    return cards.filter((card) => cardMatchesFoilFilter(card, foilFilter));
}

function applyManagerFoilFilter(cards, foilFilter) {
    if (!foilFilter || foilFilter === 'all') {
        return cards;
    }
    if (foilFilter === 'foil') {
        return cards.filter((card) => card.has_foil);
    }
    return cards.filter((card) => card.has_nonfoil);
}

function summarizeDeckCards(cards) {
    const deckSize = cards.reduce((sum, card) => sum + (Number(card.qty) || 0), 0);
    const trackedRows = cards.filter((card) => card.in_catalog);
    const trackedQty = trackedRows.reduce((sum, card) => sum + (Number(card.qty) || 0), 0);
    const priced = cards.filter((card) => card.in_catalog && card.current_value != null && !Number.isNaN(card.current_value));
    const ownedRows = cards.filter((card) => Number(card.owned_qty) > 0);
    const current = priced.reduce((sum, card) => sum + (Number(card.current_value) || 0), 0);
    const invested = ownedRows.reduce((sum, card) => sum + (Number(card.invested) || 0), 0);
    const profit = ownedRows.reduce((sum, card) => sum + (Number(card.profit_loss) || 0), 0);
    const ownedQty = ownedRows.reduce((sum, card) => sum + (Number(card.owned_qty) || 0), 0);
    const unknownRows = cards.filter((card) => card.current_value == null || Number.isNaN(card.current_value));
    const winners = ownedRows.filter((card) => Number(card.profit_loss) > 0).length;
    const losers = ownedRows.filter((card) => Number(card.profit_loss) < 0).length;
    const averageValues = priced.map((card) => Number(card.unit_value)).filter((value) => !Number.isNaN(value));

    return {
        current: priced.length ? current : null,
        invested: ownedRows.length ? invested : null,
        profit: ownedRows.length ? profit : null,
        deckSize,
        trackedQty,
        ownedQty,
        missingQty: Math.max(deckSize - ownedQty, 0),
        trackedCoverage: deckSize ? Math.round((trackedQty / deckSize) * 1000) / 10 : null,
        ownedCoverage: deckSize ? Math.round((ownedQty / deckSize) * 1000) / 10 : null,
        average: averageValues.length
            ? averageValues.reduce((sum, value) => sum + value, 0) / averageValues.length
            : null,
        unknownQty: unknownRows.reduce((sum, card) => sum + (Number(card.qty) || 0), 0),
        unknownCount: unknownRows.length,
        winners,
        losers,
        cards,
    };
}

function resolveStatsPageStats(pageStats, foilFilter) {
    if (!pageStats) {
        return pageStats;
    }
    if (!foilFilter || foilFilter === 'all') {
        return pageStats;
    }
    const finishKey = foilFilter === 'foil' ? '1' : '0';
    const foilStats = pageStats.byFoil?.[finishKey];
    if (!foilStats) {
        return {
            ...pageStats,
            current: 0,
            invested: 0,
            profit: 0,
            ownedCount: 0,
            average: null,
            unknownInvested: 0,
            unknownCount: 0,
            unknownCards: [],
            winners: 0,
            losers: 0,
            portfolioHistory: [],
            setBreakdown: [],
            artStyles: [],
            byArtStyle: {},
            byFoil: pageStats.byFoil || {},
        };
    }
    return {
        ...foilStats,
        byFoil: pageStats.byFoil || {},
    };
}

const DECK_BROWSE_PAGE = 'collection_decks.html';
const DECK_STATS_PAGE = 'collection_deck_stats.html';
const STORAGE_PAGE = 'collection_storage.html';
const DECK_BROWSE_STORAGE_KEY = 'reportCurrentBrowseDeck';
const DECK_STATS_STORAGE_KEY = 'reportCurrentDeck';

function deckReportUrl(page, deckId) {
    const params = new URLSearchParams();
    if (deckId && deckId !== 'All') {
        params.set('deck', deckId);
    }
    const query = params.toString();
    return query ? `${page}?${query}` : page;
}

function storageReportUrl(locationSlug) {
    const params = new URLSearchParams();
    if (locationSlug) {
        params.set('location', locationSlug);
    }
    const query = params.toString();
    return query ? `${STORAGE_PAGE}?${query}` : STORAGE_PAGE;
}

function locationReportUrl(location) {
    if (!location?.slug) {
        return STORAGE_PAGE;
    }
    if (location.locationType === 'deck') {
        const deckSlug = location.slug.replace(/^deck:/, '');
        return deckReportUrl(DECK_BROWSE_PAGE, deckSlug);
    }
    return storageReportUrl(location.slug);
}

function syncDeckReportLinks(deckId) {
    const statsLink = document.getElementById('deck-stats-link');
    const browseLink = document.getElementById('deck-browse-link');
    if (statsLink) {
        statsLink.href = deckReportUrl(DECK_STATS_PAGE, deckId);
    }
    if (browseLink) {
        browseLink.href = deckReportUrl(
            DECK_BROWSE_PAGE,
            deckId === 'All' ? null : deckId,
        );
    }
}

function persistDeckSelection(deckId) {
    if (deckId === 'All') {
        localStorage.setItem(DECK_STATS_STORAGE_KEY, 'All');
        return;
    }
    if (deckId) {
        localStorage.setItem(DECK_BROWSE_STORAGE_KEY, deckId);
        localStorage.setItem(DECK_STATS_STORAGE_KEY, deckId);
    }
}

function getInitialDeckSelection(availableDecks, options = {}) {
    const allowAll = options.allowAll === true;
    const defaultDeck = options.defaultDeck
        || (allowAll ? 'All' : String(availableDecks[0]?.id || ''));

    const params = new URLSearchParams(window.location.search);
    const fromUrl = params.get('deck');
    if (fromUrl === 'All' && allowAll) {
        return 'All';
    }
    if (fromUrl && availableDecks.some((deck) => String(deck.id) === fromUrl)) {
        return fromUrl;
    }

    for (const key of [DECK_STATS_STORAGE_KEY, DECK_BROWSE_STORAGE_KEY]) {
        const stored = localStorage.getItem(key);
        if (stored === 'All' && allowAll) {
            return 'All';
        }
        if (stored && availableDecks.some((deck) => String(deck.id) === stored)) {
            return stored;
        }
    }

    return defaultDeck;
}

function applyDeckPageFoilFilter(pageStats, foilFilter) {
    if (!pageStats) {
        return pageStats;
    }
    const cards = applyFoilFilter(pageStats.cards || [], foilFilter);
    if (!foilFilter || foilFilter === 'all') {
        return pageStats;
    }
    return {
        ...pageStats,
        ...summarizeDeckCards(cards),
        portfolioHistory: pageStats.portfolioHistory || [],
    };
}

function getStoredPageSize(defaultSize) {
    const stored = parseInt(localStorage.getItem(PAGE_SIZE_KEY), 10);
    if (Number.isFinite(stored) && stored > 0) {
        return stored;
    }
    return defaultSize || DEFAULT_RANKED_PAGE_SIZE;
}

function applyRankedCardFilters(cards, filters) {
    let result = cards;
    const setCode = filters.setCode || getCurrentSet();
    if (setCode && setCode !== 'All') {
        result = result.filter((card) => card.set_code === setCode);
    }
    if (filters.artStyle) {
        result = result.filter((card) => card.art_style === filters.artStyle);
    }
    if (filters.foilFilter && filters.foilFilter !== 'all') {
        result = applyFoilFilter(result, filters.foilFilter);
    }
    const ownedFilter = filters.ownedFilter || 'owned';
    if (ownedFilter === 'owned') {
        result = result.filter((card) => card.purchase_value != null && !Number.isNaN(card.purchase_value));
    } else if (ownedFilter === 'unowned') {
        result = result.filter((card) => card.purchase_value == null || Number.isNaN(card.purchase_value));
    }
    return result;
}

function cardRankKey(card) {
    return `${card.set_code}|${card.collector_number}|${card.foil}`;
}

function isOwnedCard(card) {
    return card.purchase_value != null && !Number.isNaN(card.purchase_value);
}

function isUnpricedCard(card) {
    return card.current_value == null || Number.isNaN(card.current_value);
}

function compareRankedByCurrentValue(left, right) {
    const leftPriced = !isUnpricedCard(left);
    const rightPriced = !isUnpricedCard(right);
    if (leftPriced && rightPriced) {
        return right.current_value - left.current_value;
    }
    if (leftPriced !== rightPriced) {
        return leftPriced ? -1 : 1;
    }
    const setCompare = String(left.set_code).localeCompare(String(right.set_code));
    if (setCompare !== 0) {
        return setCompare;
    }
    return String(left.collector_number).localeCompare(
        String(right.collector_number),
        undefined,
        { numeric: true },
    );
}

function applyPageSizeLimit(cards, pageSize, options = {}) {
    const limit = parseInt(pageSize, 10);
    if (!Number.isFinite(limit) || limit <= 0 || limit >= cards.length) {
        return cards;
    }

    if (options.includeUnpricedOwned) {
        const unpricedOwned = cards.filter((card) => isOwnedCard(card) && isUnpricedCard(card));
        const pricedOrUnowned = cards.filter((card) => !(isOwnedCard(card) && isUnpricedCard(card)));
        const limited = pricedOrUnowned.slice(0, limit);
        const seen = new Set(limited.map(cardRankKey));
        unpricedOwned.forEach((card) => {
            const key = cardRankKey(card);
            if (!seen.has(key)) {
                limited.push(card);
                seen.add(key);
            }
        });
        return limited;
    }

    return cards.slice(0, limit);
}

function uniqueArtStyles(cards, setCode) {
    const scoped = setCode && setCode !== 'All'
        ? cards.filter((card) => card.set_code === setCode)
        : cards;
    return [...new Set(scoped.map((card) => card.art_style).filter(Boolean))].sort();
}

function populateArtStyleFilter(cards, setCode, selectedArtStyle) {
    const select = document.getElementById('report-art-filter');
    if (!select) {
        return;
    }
    const styles = uniqueArtStyles(cards, setCode);
    const options = ['<option value="">All art styles</option>'];
    styles.forEach((style) => {
        const selected = style === selectedArtStyle ? ' selected' : '';
        options.push(`<option value="${escapeHtml(style)}"${selected}>${escapeHtml(style)}</option>`);
    });
    select.innerHTML = options.join('');
}

function getFoilFilterValue() {
    const checked = document.querySelector('input[name="report-foil-filter"]:checked');
    return checked ? checked.value : getStoredFoilFilter();
}

function setFoilFilterValue(value) {
    document.querySelectorAll('input[name="report-foil-filter"]').forEach((input) => {
        input.checked = input.value === value;
    });
}

function initFoilFilterRadios(onChange) {
    const initial = parseCollectionUrlFilters().foilFilter || getStoredFoilFilter();
    setFoilFilterValue(initial);
    document.querySelectorAll('input[name="report-foil-filter"]').forEach((input) => {
        input.addEventListener('change', onChange);
    });
}

function getOwnedFilterValue() {
    const checked = document.querySelector('input[name="report-owned-filter"]:checked');
    return checked ? checked.value : getStoredOwnedFilter();
}

function setOwnedFilterValue(value) {
    document.querySelectorAll('input[name="report-owned-filter"]').forEach((input) => {
        input.checked = input.value === value;
    });
}

function initOwnedFilterRadios(onChange) {
    const initial = parseCollectionUrlFilters().ownedFilter || getStoredOwnedFilter();
    setOwnedFilterValue(initial);
    document.querySelectorAll('input[name="report-owned-filter"]').forEach((input) => {
        input.addEventListener('change', onChange);
    });
}

function syncReportUrlParams(setCode, artStyle, ownedFilter, foilFilter) {
    const params = new URLSearchParams(window.location.search);
    if (setCode && setCode !== 'All') {
        params.set('set', setCode);
    } else {
        params.delete('set');
    }
    if (artStyle) {
        params.set('art', artStyle);
    } else {
        params.delete('art');
    }
    if (ownedFilter && ownedFilter !== 'owned') {
        params.set('owned', ownedFilter);
    } else {
        params.delete('owned');
    }
    if (foilFilter && foilFilter !== 'all') {
        params.set('foil', foilFilter);
    } else {
        params.delete('foil');
    }
    params.delete('deck');
    const query = params.toString();
    window.history.replaceState({}, '', query ? `${window.location.pathname}?${query}` : window.location.pathname);
}

function initRankedReportFilters(data, onFiltersChange) {
    const artSelect = document.getElementById('report-art-filter');
    const urlFilters = parseCollectionUrlFilters();

    let artStyle = urlFilters.artStyle || '';
    const setForArtFilter = (
        urlFilters.setCode
        && urlFilters.setCode !== 'All'
        && getAvailableSetsFromSelect(document.getElementById('report-set-select') || { options: [] }).includes(urlFilters.setCode)
    ) ? urlFilters.setCode : getCurrentSet();

    populateArtStyleFilter(data.cards, setForArtFilter, artStyle);
    if (artSelect && artStyle) {
        artSelect.value = artStyle;
    }

    function currentFilters() {
        return {
            setCode: getCurrentSet(),
            artStyle: artSelect ? artSelect.value : artStyle,
            ownedFilter: getOwnedFilterValue(),
            foilFilter: getFoilFilterValue(),
            pageSize: getStoredPageSize(data.defaultPageSize),
        };
    }

    function notify() {
        const filters = currentFilters();
        localStorage.setItem(OWNED_FILTER_KEY, filters.ownedFilter);
        localStorage.setItem(FOIL_FILTER_KEY, filters.foilFilter);
        if (filters.pageSize > 0) {
            localStorage.setItem(PAGE_SIZE_KEY, String(filters.pageSize));
        }
        syncReportUrlParams(
            filters.setCode,
            filters.artStyle,
            filters.ownedFilter,
            filters.foilFilter,
        );
        onFiltersChange(filters);
    }

    initOwnedFilterRadios(notify);
    initFoilFilterRadios(notify);
    if (artSelect) {
        artSelect.addEventListener('change', notify);
    }

    return {
        refreshArtStyles(setCode) {
            artStyle = artSelect ? artSelect.value : artStyle;
            populateArtStyleFilter(data.cards, setCode, artStyle);
            if (artSelect && artStyle && !Array.from(artSelect.options).some((option) => option.value === artStyle)) {
                artSelect.value = '';
                artStyle = '';
            }
        },
        notify,
    };
}
