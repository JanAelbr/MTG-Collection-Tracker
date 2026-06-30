function formatRoi(profit, invested) {
    if (profit == null || invested == null || Number.isNaN(profit) || Number.isNaN(invested) || invested === 0) {
        return 'Unknown';
    }
    return `${((profit / invested) * 100).toFixed(1)}%`;
}

function formatCompletion(ownedCount, catalogCount) {
    if (!catalogCount) {
        return 'Unknown';
    }
    const percent = (ownedCount / catalogCount) * 100;
    return `${ownedCount} / ${catalogCount} (${percent.toFixed(1)}%)`;
}

function setStatValue(selector, value) {
    const element = document.querySelector(selector);
    if (element) {
        element.innerHTML = value;
    }
}

function formatUnknownCardLine(card) {
    const number = String(card.collector_number).padStart(3, '0');
    const name = displayName(card);
    return `${card.set_code} - ${number} - ${name} - ${card.art_style}`;
}

function positionUnknownCardsTooltip($tooltip, event) {
    const tooltipEl = $tooltip[0];
    const offset = 16;
    const padding = 8;
    const width = tooltipEl.offsetWidth;
    const height = tooltipEl.offsetHeight;
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    let left = event.clientX + offset;
    if (left + width + padding > viewportWidth) {
        left = event.clientX - width - offset;
    }
    left = Math.max(padding, Math.min(left, viewportWidth - width - padding));

    let top = event.clientY + offset;
    if (top + height + padding > viewportHeight) {
        top = event.clientY - height - offset;
    }
    top = Math.max(padding, Math.min(top, viewportHeight - height - padding));

    $tooltip.css({ left: left, top: top });
}

function initUnknownCardsTooltip(cards) {
    const card = document.querySelector('.unknown-card');
    $('.unknown-cards-tooltip').remove();
    if (card) {
        card.classList.remove('has-unknown-tooltip');
        $(card).off('.unknownTooltip');
    }
    if (!card || !cards || !cards.length) {
        return;
    }

    card.classList.add('has-unknown-tooltip');
    const listItems = cards.map((unknownCard) => (
        `<li>${escapeHtml(formatUnknownCardLine(unknownCard))}</li>`
    )).join('');
    const $tooltip = $(
        `<div class="unknown-cards-tooltip"><ul>${listItems}</ul></div>`
    ).appendTo('body');

    function moveTooltip(event) {
        positionUnknownCardsTooltip($tooltip, event);
    }

    $(card).on('mouseenter.unknownTooltip', function (event) {
        $tooltip.show();
        moveTooltip(event);
    });

    $(card).on('mousemove.unknownTooltip', moveTooltip);

    $(card).on('mouseleave.unknownTooltip', function () {
        $tooltip.hide();
    });
}

function artStyleFilterKey(setCode, artStyle) {
    return `${setCode}|${artStyle}`;
}

function parseArtStyleFilterKey(artKey) {
    const separator = artKey.indexOf('|');
    if (separator === -1) {
        return { setCode: '', artStyle: artKey };
    }
    return {
        setCode: artKey.slice(0, separator),
        artStyle: artKey.slice(separator + 1),
    };
}

function populateStatsArtFilter(pageStats, pageSet, selectedArtKey) {
    const select = document.getElementById('stats-art-filter');
    if (!select || !pageStats) {
        return;
    }

    if (pageSet === 'All') {
        select.innerHTML = '<option value="">All sets</option>';
        select.disabled = true;
        return;
    }

    select.disabled = false;
    const rows = pageStats.artStyles || [];
    const options = ['<option value="">All art styles</option>'];
    rows.forEach((row) => {
        const key = artStyleFilterKey(row.set_code, row.art_style);
        const label = pageSet === 'All'
            ? `${row.set_code} — ${row.art_style}`
            : row.art_style;
        const selected = key === selectedArtKey ? ' selected' : '';
        options.push(
            `<option value="${escapeHtml(key)}"${selected}>${escapeHtml(label)}</option>`,
        );
    });
    select.innerHTML = options.join('');
}

function resolveStatsView(pageStats, artKey) {
    if (!artKey || !pageStats.byArtStyle || !pageStats.byArtStyle[artKey]) {
        return pageStats;
    }
    return {
        ...pageStats.byArtStyle[artKey],
        artStyles: pageStats.artStyles,
        byArtStyle: pageStats.byArtStyle,
    };
}

function getInitialStatsArtKey(pageSet, pageStats) {
    if (!pageStats) {
        return '';
    }
    const { setCode, artStyle } = parseCollectionUrlFilters();
    if (!artStyle) {
        return '';
    }

    const match = (pageStats.artStyles || []).find((row) => {
        if (row.art_style !== artStyle) {
            return false;
        }
        if (pageSet === 'All') {
            return !setCode || row.set_code === setCode;
        }
        return row.set_code === pageSet;
    });
    return match ? artStyleFilterKey(match.set_code, match.art_style) : '';
}

function syncStatsUrlParams(pageSet, artKey, foilFilter) {
    const params = new URLSearchParams(window.location.search);
    if (pageSet && pageSet !== 'All') {
        params.set('set', pageSet);
    } else {
        params.delete('set');
    }

    if (artKey) {
        const { setCode, artStyle } = parseArtStyleFilterKey(artKey);
        if (pageSet === 'All' && setCode) {
            params.set('set', setCode);
        }
        params.set('art', artStyle);
    } else {
        params.delete('art');
    }

    if (foilFilter && foilFilter !== 'all') {
        params.set('foil', foilFilter);
    } else {
        params.delete('foil');
    }

    const query = params.toString();
    window.history.replaceState({}, '', query ? `${window.location.pathname}?${query}` : window.location.pathname);
}

function aggregateArtStylesBySet(artStyles) {
    const grouped = new Map();
    for (const row of artStyles || []) {
        const key = row.set_code || row.setCode;
        if (!key) {
            continue;
        }
        const prev = grouped.get(key) || {
            set_code: key,
            count: 0,
            current: null,
            invested: null,
            profit: null,
        };
        prev.count += row.count || 0;
        prev.current = (prev.current ?? 0) + (row.current ?? 0);
        prev.invested = (prev.invested ?? 0) + (row.invested ?? 0);
        prev.profit = (prev.profit ?? 0) + (row.profit ?? 0);
        grouped.set(key, prev);
    }
    return [...grouped.values()].sort((a, b) => String(a.set_code).localeCompare(String(b.set_code)));
}

function resolveSetBreakdownRows(stats) {
    if (stats?.setBreakdown?.length) {
        return stats.setBreakdown;
    }
    return aggregateArtStylesBySet(stats?.artStyles || []);
}

function renderSetTable(setBreakdown) {
    const thead = document.querySelector('#artStyleTableHead');
    const tbody = document.querySelector('#artStyleTable tbody');
    const heading = document.querySelector('.art-style-card h3');
    if (!tbody || !thead) {
        return;
    }

    if (heading) {
        heading.textContent = 'Value by set';
    }

    thead.innerHTML = '<th>Set</th><th>Cards</th><th>Value</th><th>Invested</th><th>Profit / Loss</th>';

    if (!setBreakdown || !setBreakdown.length) {
        tbody.innerHTML = '<tr><td colspan="5">No data</td></tr>';
        return;
    }

    tbody.innerHTML = setBreakdown.map((row) => {
        const setCode = row.set_code || row.setCode;
        return (
        `<tr>` +
        `<td>${escapeHtml(setCode)}</td>` +
        `<td>${row.count}</td>` +
        `<td>${formatEuro(row.current)}</td>` +
        `<td>${formatInvested(row.invested)}</td>` +
        `<td>${formatProfit(row.profit, 'Unknown')}</td>` +
        '</tr>'
        );
    }).join('');
}

function renderArtStyleTable(artStyles, selectedArtKey) {
    const thead = document.querySelector('#artStyleTableHead');
    const tbody = document.querySelector('#artStyleTable tbody');
    const heading = document.querySelector('.art-style-card h3');
    if (!tbody || !thead) {
        return;
    }

    const pageSet = getCurrentSet();
    if (pageSet === 'All') {
        return;
    }

    if (heading) {
        heading.textContent = 'Value by art style';
    }

    if (!artStyles || !artStyles.length) {
        tbody.innerHTML = '<tr><td colspan="4">No data</td></tr>';
        return;
    }

    thead.innerHTML = '<th>Art style</th><th>Cards</th><th>Value</th><th>Profit / Loss</th>';

    tbody.innerHTML = artStyles.map((row) => {
        const setCode = pageSet;
        const rowKey = artStyleFilterKey(row.set_code, row.art_style);
        const rowClass = rowKey === selectedArtKey ? ' class="stats-art-row-selected"' : '';
        const artStyleLink = (
            `<a href="${escapeHtml(collectionReportUrl(setCode, row.art_style, true))}" ` +
            `class="stats-art-style-link">${escapeHtml(row.art_style)}</a>`
        );
        return (
            `<tr${rowClass}>` +
            `<td>${artStyleLink}</td>` +
            `<td>${row.count}</td>` +
            `<td>${formatEuro(row.current)}</td>` +
            `<td>${formatProfit(row.profit, 'Unknown')}</td>` +
            '</tr>'
        );
    }).join('');
}

function renderStatsBreakdownTable(stats, selectedArtKey) {
    const pageSet = getCurrentSet();
    if (pageSet === 'All') {
        const rows = resolveSetBreakdownRows(stats);
        if (rows.length) {
            renderSetTable(rows);
        }
        return;
    }
    renderArtStyleTable(stats.artStyles, selectedArtKey);
}

function renderStatsPage(stats, selectedArtKey) {
    setStatValue('[data-stat="current"]', formatEuro(stats.current));
    setStatValue('[data-stat="invested"]', formatInvested(stats.invested));
    setStatValue('[data-stat="profit"]', formatProfit(stats.profit, 'Unknown'));
    setStatValue('[data-stat="roi"]', formatRoi(stats.profit, stats.invested));
    setStatValue('[data-stat="owned"]', String(stats.ownedCount));
    setStatValue('[data-stat="completion"]', formatCompletion(stats.ownedCount, stats.catalogCount));
    setStatValue('[data-stat="average"]', formatEuro(stats.average));
    setStatValue('[data-stat="unknown"]', formatEuro(stats.unknownInvested));
    setStatValue('[data-stat="unknown-count"]', `${stats.unknownCount} cards`);
    setStatValue('[data-stat="winners"]', String(stats.winners));
    setStatValue('[data-stat="losers"]', String(stats.losers));
    renderStatsBreakdownTable(stats, selectedArtKey);
    initUnknownCardsTooltip(stats.unknownCards);
    return stats;
}

function initStatsReport() {
    const data = window.STATS_DATA;
    if (!data) {
        return;
    }

    let currentStats = null;
    let selectedArtKey = '';
    let foilFilter = getStoredFoilFilter();
    const artSelect = document.getElementById('stats-art-filter');

    function renderCurrentView() {
        const pageSet = getCurrentSet();
        const pageStats = data.pages[pageSet];
        if (!pageStats) {
            return;
        }

        const scopedStats = resolveStatsPageStats(pageStats, foilFilter);
        populateStatsArtFilter(scopedStats, pageSet, selectedArtKey);
        if (selectedArtKey && !scopedStats.byArtStyle?.[selectedArtKey]) {
            selectedArtKey = '';
            if (artSelect) {
                artSelect.value = '';
            }
        }

        const viewStats = resolveStatsView(scopedStats, selectedArtKey);
        currentStats = renderStatsPage(viewStats, selectedArtKey);
    }

    if (artSelect) {
        artSelect.addEventListener('change', function () {
            selectedArtKey = artSelect.value;
            syncStatsUrlParams(getCurrentSet(), selectedArtKey, foilFilter);
            renderCurrentView();
        });
    }

    initFoilFilterRadios(function () {
        foilFilter = getFoilFilterValue();
        selectedArtKey = '';
        if (artSelect) {
            artSelect.value = '';
        }
        syncStatsUrlParams(getCurrentSet(), '', foilFilter);
        renderCurrentView();
    });
    foilFilter = getFoilFilterValue();

    const exportUnknownButton = document.getElementById('export-unknown-csv');
    if (exportUnknownButton) {
        exportUnknownButton.addEventListener('click', function () {
            if (!currentStats) {
                return;
            }
            const page = getCurrentSet();
            const filename = page === 'All'
                ? 'unknown_value.csv'
                : `unknown_value_${page.toLowerCase()}.csv`;
            downloadCsv(
                filename,
                UNKNOWN_CARD_CSV_HEADERS,
                unknownCardsToCsvRows(currentStats.unknownCards),
            );
        });
    }

    initSetNav(function () {
        selectedArtKey = '';
        syncStatsUrlParams(getCurrentSet(), '', foilFilter);
        renderCurrentView();
    });

    selectedArtKey = getInitialStatsArtKey(getCurrentSet(), data.pages[getCurrentSet()]);
    syncStatsUrlParams(getCurrentSet(), selectedArtKey, foilFilter);
    renderCurrentView();
}

$(document).ready(initStatsReport);
