function getFallersForPage(data, compareDate, filters) {
    return applyPageSizeLimit(
        applyRankedCardFilters(data.cards, filters, data)
            .map((card) => enrichCardWithSnapshot(card, compareDate, data.snapshots || {}))
            .filter((card) => card.price_change != null && card.price_change < 0)
            .sort((left, right) => {
                if (left.price_change !== right.price_change) {
                    return left.price_change - right.price_change;
                }
                return (right.current_value || 0) - (left.current_value || 0);
            }),
        filters.pageSize,
    );
}

function ensureTopImagesContainer() {
    let container = document.querySelector('.top-card-images');
    if (container) {
        return container;
    }
    const panel = document.querySelector('.top-cards-panel');
    if (!panel) {
        return null;
    }
    container = document.createElement('div');
    container.className = 'top-card-images';
    panel.insertBefore(container, panel.firstChild);
    return container;
}

function renderTopImages(fallers) {
    const container = ensureTopImagesContainer();
    if (!container) {
        return;
    }

    const figures = fallers.slice(0, 5).map((card, index) => {
        if (!card.image_uri) {
            return '';
        }
        return (
            `<figure class="top-card-image">` +
            `<img src="${escapeHtml(card.image_uri)}" alt="${escapeHtml(displayName(card))}" loading="lazy">` +
            `<figcaption>` +
            `<span class="top-card-rank">#${index + 1}</span>` +
            `<span class="top-card-name">${escapeHtml(displayName(card))}</span>` +
            `<span class="top-card-value">${escapeHtml(formatEuro(card.current_value))}</span>` +
            `</figcaption></figure>`
        );
    }).filter(Boolean);

    if (!figures.length) {
        container.innerHTML = '';
        return;
    }

    container.innerHTML = figures.join('');
}

function renderFallersTable(fallers, compareLabel, compareDate, ownedFilter) {
    updateChangeHeader('#cardsTable', 5, compareLabel, compareDate);

    if ($.fn.DataTable.isDataTable('#cardsTable')) {
        $('#cardsTable').DataTable().destroy();
    }

    const showUnownedBadge = ownedFilter === 'all';
    const tbody = document.querySelector('#cardsTable tbody');
    tbody.innerHTML = fallers.map((card, index) => (
        '<tr>' +
        `<td>${index + 1}</td>` +
        `<td>${buildCardLabel(card, !showUnownedBadge)}</td>` +
        `<td>${escapeHtml(card.art_style)}</td>` +
        `<td>${buildCurrentValueCell(card)}</td>` +
        `<td>${formatPriceChange(card.price_change, card.previous_value)}</td>` +
        `<td>${formatGainLoss(card.profit_loss, card.purchase_value)}</td>` +
        '</tr>'
    )).join('');

    initCardsDataTable();
}

function initCardsDataTable() {
    $('#cardsTable').DataTable({
        paging: false,
        searching: false,
        info: false,
        order: [[0, 'asc']],
        columnDefs: [
            {
                targets: 0,
                render: function(data, type) {
                    if (type === 'sort' || type === 'type') {
                        return parseInt(String(data), 10) || data;
                    }
                    return data;
                }
            },
            {
                targets: 1,
                render: function(data, type) {
                    if (type === 'sort' || type === 'type') {
                        const match = String(data).match(/^\s*0*(\d+)\s*-\s*/);
                        return match ? parseInt(match[1], 10) : data;
                    }
                    return data;
                }
            },
            {
                targets: [3, 4, 5],
                render: function(data, type) {
                    if (type === 'sort' || type === 'type') {
                        return parseEuroNumber(data);
                    }
                    return data;
                }
            }
        ]
    });
}

function renderFallersForCompareDate(data, compareDate, compareLabel, filters) {
    const fallers = getFallersForPage(data, compareDate, filters);
    renderFallersTable(fallers, compareLabel, compareDate, filters.ownedFilter);
    renderTopImages(fallers);
}

function initFallersReport() {
    const data = window.FALLERS_DATA;
    if (!data) {
        return;
    }

    let compareDate = getSelectedCompareDate(data);
    let compareLabel = getComparePreset(getSelectedComparePreset(data)).label;
    let filters = {
        setCode: getCurrentSet(),
        artStyle: '',
        ownedFilter: getStoredOwnedFilter(),
        foilFilter: getStoredFoilFilter(),
        pageSize: getStoredPageSize(data.defaultPageSize),
    };
    let filterControls = null;

    function renderCurrentSet() {
        renderFallersForCompareDate(data, compareDate, compareLabel, filters);
    }

    function initCompareNav() {
        initPriceCompareNav(data, (nextCompareDate, preset) => {
            compareDate = nextCompareDate;
            compareLabel = preset.label;
            renderCurrentSet();
        });
    }

    filterControls = initRankedReportFilters(data, (nextFilters) => {
        filters = nextFilters;
        renderCurrentSet();
    });
    filters = {
        setCode: getCurrentSet(),
        artStyle: document.getElementById('report-art-filter')?.value || '',
        ownedFilter: getOwnedFilterValue(),
        foilFilter: getFoilFilterValue(),
        pageSize: getStoredPageSize(data.defaultPageSize),
    };

    initSetNav(function () {
        filterControls.refreshArtStyles(getCurrentSet());
        filterControls.notify();
    });
    initCompareNav();
    initCardImageTooltip();
}

$(document).ready(initFallersReport);
