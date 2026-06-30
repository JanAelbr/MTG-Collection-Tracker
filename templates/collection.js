function filterBySet(rows, page) {
    if (page === 'All') {
        return rows;
    }
    return rows.filter((row) => row.set_code === page);
}

function renderSummaryTable(summaryRows) {
    const tbody = document.querySelector('#summaryTable tbody');
    if (!tbody) {
        return;
    }
    tbody.innerHTML = summaryRows.map((row) => (
        '<tr>' +
        `<td>${escapeHtml(row.set_code)}</td>` +
        `<td>${escapeHtml(row.art_style)}</td>` +
        `<td>${row.cards}</td>` +
        `<td>${formatEuro(row.current_value)}</td>` +
        `<td>${formatPriceChange(row.price_change, row.previous_total)}</td>` +
        `<td>${formatProfit(row.profit_loss, 'Unknown')}</td>` +
        '</tr>'
    )).join('');
}

function renderCardsTable(cards, ownedOnly) {
    const tbody = document.querySelector('#cardsTable tbody');
    if (!tbody) {
        return;
    }
    tbody.innerHTML = cards.map((card) => (
        '<tr>' +
        `<td>${escapeHtml(card.set_code)}</td>` +
        `<td>${escapeHtml(card.art_style)}</td>` +
        `<td>${buildCardLabel(card, ownedOnly)}</td>` +
        `<td>${buildCurrentValueCell(card)}</td>` +
        `<td>${formatPriceChange(card.price_change, card.previous_value)}</td>` +
        `<td>${formatGainLoss(card.profit_loss, card.purchase_value)}</td>` +
        '</tr>'
    )).join('');
}

function destroyDataTable(selector) {
    if ($.fn.DataTable.isDataTable(selector)) {
        $(selector).DataTable().destroy();
    }
}

function createCardsTable() {
    return $('#cardsTable').DataTable({
        pageLength: 50,
        language: {
            search: '',
            searchPlaceholder: 'Search cards...',
        },
        columnDefs: [
            {
                targets: 1,
                visible: false,
            },
            {
                targets: 2,
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

function createSummaryTable() {
    return $('#summaryTable').DataTable({
        paging: false,
        searching: true,
        info: false,
        order: [[1, 'asc']],
        columnDefs: [
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

function initCollectionReport() {
    const data = window.COLLECTION_DATA;
    if (!data) {
        return;
    }

    let selectedArtStyle = null;
    let selectedSummarySet = null;
    let cardsTable = null;
    let summaryTable = null;
    let compareDate = getSelectedCompareDate(data);
    let compareLabel = getComparePreset(getSelectedComparePreset(data)).label;
    let enrichedCards = [];
    let enrichedSummary = [];

    function escapeRegex(value) {
        return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    function applyFilters() {
        if (!cardsTable) {
            return;
        }
        const page = getCurrentSet();
        let setSearch = '';
        if (page && page !== 'All') {
            setSearch = '^' + escapeRegex(page) + '$';
        } else if (selectedSummarySet) {
            setSearch = '^' + escapeRegex(selectedSummarySet) + '$';
        }
        cardsTable.column(0).search(setSearch, true, false);

        const artSearch = selectedArtStyle ? '^' + escapeRegex(selectedArtStyle) + '$' : '';
        cardsTable.column(1).search(artSearch, true, false);

        cardsTable.draw();
    }

    function bindSummaryFilter() {
        $('#summaryTable tbody').off('click').on('click', 'tr', function () {
            const setCode = $(this).find('td').eq(0).text().trim();
            const artStyle = $(this).find('td').eq(1).text().trim();

            if (selectedArtStyle === artStyle && selectedSummarySet === setCode) {
                selectedArtStyle = null;
                selectedSummarySet = null;
                $('#summaryTable tbody tr').removeClass('selected-row');
            } else {
                selectedArtStyle = artStyle;
                selectedSummarySet = setCode;
                $('#summaryTable tbody tr').removeClass('selected-row');
                $(this).addClass('selected-row');
            }

            applyFilters();
        });
    }

    function renderSummaryForCurrentSet() {
        const page = getCurrentSet();
        destroyDataTable('#summaryTable');
        const summaryRows = aggregateSummaryChanges(
            enrichedCards,
            filterBySet(data.summary, page),
        );
        enrichedSummary = summaryRows;
        renderSummaryTable(summaryRows);
        summaryTable = createSummaryTable();
        bindSummaryFilter();
    }

    function getVisibleCardsForExport() {
        const page = getCurrentSet();
        let cards = filterBySet(enrichedCards, page);

        if (page === 'All' && selectedSummarySet) {
            cards = cards.filter((card) => card.set_code === selectedSummarySet);
        }
        if (selectedArtStyle) {
            cards = cards.filter((card) => card.art_style === selectedArtStyle);
        }

        if (!cardsTable) {
            return cards;
        }

        const searchTerm = cardsTable.search();
        if (!searchTerm) {
            return cards;
        }

        const pattern = new RegExp(searchTerm, 'i');
        return cards.filter((card) => (
            pattern.test(card.name)
            || pattern.test(String(card.collector_number))
            || pattern.test(card.art_style)
            || pattern.test(card.set_code)
        ));
    }

    function applyCollectionUrlFilters() {
        const { setCode, artStyle } = parseCollectionUrlFilters();
        if (!artStyle) {
            return;
        }

        selectedArtStyle = artStyle;
        selectedSummarySet = setCode && setCode !== 'All' ? setCode : null;
        applyFilters();

        $('#summaryTable tbody tr').each(function () {
            const rowSet = $(this).find('td').eq(0).text().trim();
            const rowArt = $(this).find('td').eq(1).text().trim();
            if (rowArt === selectedArtStyle && (!selectedSummarySet || rowSet === selectedSummarySet)) {
                $(this).addClass('selected-row');
            }
        });
    }

    function renderForCompareDate(nextCompareDate, nextLabel) {
        compareDate = nextCompareDate;
        if (nextLabel) {
            compareLabel = nextLabel;
        }
        enrichedCards = data.cards.map((card) => (
            enrichCardWithSnapshot(card, compareDate, data.snapshots || {})
        ));

        updateChangeHeader('#cardsTable', 5, compareLabel, compareDate);
        updateChangeHeader('#summaryTable', 5, compareLabel, compareDate);
        renderSummaryForCurrentSet();

        destroyDataTable('#cardsTable');
        renderCardsTable(enrichedCards, data.ownedOnly);
        cardsTable = createCardsTable();
        applyFilters();
        applyCollectionUrlFilters();
        initCardImageTooltip();
    }

    function initExportButtons() {
        const exportCardsButton = document.getElementById('export-cards-csv');
        const exportSummaryButton = document.getElementById('export-summary-csv');

        if (exportCardsButton) {
            exportCardsButton.addEventListener('click', function () {
                const page = getCurrentSet();
                const prefix = data.ownedOnly ? 'owned' : 'all_cards';
                const filename = page === 'All'
                    ? `${prefix}.csv`
                    : `${prefix}_${page.toLowerCase()}.csv`;
                downloadCsv(filename, CARD_CSV_HEADERS, cardsToCsvRows(getVisibleCardsForExport()));
            });
        }

        if (exportSummaryButton) {
            exportSummaryButton.addEventListener('click', function () {
                const page = getCurrentSet();
                const prefix = data.ownedOnly ? 'summary_owned' : 'summary_all';
                const filename = page === 'All'
                    ? `${prefix}.csv`
                    : `${prefix}_${page.toLowerCase()}.csv`;
                downloadCsv(filename, SUMMARY_CSV_HEADERS, summaryToCsvRows(enrichedSummary));
            });
        }
    }

    function onSetChange() {
        selectedArtStyle = null;
        selectedSummarySet = null;
        if (!cardsTable) {
            renderForCompareDate(compareDate);
            return;
        }
        renderSummaryForCurrentSet();
        applyFilters();
    }

    function initCompareNav() {
        initPriceCompareNav(data, (nextCompareDate, preset) => {
            renderForCompareDate(nextCompareDate, preset.label);
        });
    }

    initSetNav(onSetChange);
    initCompareNav();
    initExportButtons();
}

$(document).ready(initCollectionReport);
