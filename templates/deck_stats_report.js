function getCurrentDeck() {
    return document.body.dataset.currentDeck || 'All';
}

function setCurrentDeck(deckId) {
    document.body.dataset.currentDeck = deckId;
    persistDeckSelection(deckId);
    syncDeckReportLinks(deckId);
}

function syncDeckUrlParam(deckId) {
    const params = new URLSearchParams(window.location.search);
    if (deckId && deckId !== 'All') {
        params.set('deck', deckId);
    } else {
        params.delete('deck');
    }
    params.delete('foil');
    const query = params.toString();
    window.history.replaceState({}, '', query ? `${window.location.pathname}?${query}` : window.location.pathname);
}

function getInitialDeck(availableDecks) {
    return getInitialDeckSelection(availableDecks, { allowAll: true, defaultDeck: 'All' });
}

function initDeckNav(onDeckChange) {
    const select = document.getElementById('report-deck-select');
    const decks = window.DECK_STATS_DATA?.decks || [];
    const initialDeck = getInitialDeck(decks);
    if (select) {
        select.value = initialDeck;
    }
    setCurrentDeck(initialDeck);
    syncDeckUrlParam(initialDeck);
    onDeckChange(initialDeck);

    if (!select) {
        return;
    }

    select.addEventListener('change', function () {
        const deckId = select.value;
        setCurrentDeck(deckId);
        syncDeckUrlParam(deckId);
        onDeckChange(deckId);
    });
}

function formatCoverage(covered, total) {
    if (!total) {
        return 'Unknown';
    }
    const percent = (covered / total) * 100;
    return `${covered} / ${total} (${percent.toFixed(1)}%)`;
}

function setStatValue(selector, value) {
    const element = document.querySelector(selector);
    if (element) {
        element.innerHTML = value;
    }
}

function formatDeckRoi(profit, invested) {
    if (profit == null || invested == null || Number.isNaN(profit) || Number.isNaN(invested) || invested === 0) {
        return '';
    }
    return `Return ${((profit / invested) * 100).toFixed(1)}%`;
}

function deckDisplayName(deck) {
    return deck.label || deck.name;
}

function renderDeckValueTable(decks, pages) {
    const panel = document.getElementById('deckValuePanel');
    const cardsPanel = document.getElementById('deckCardsPanel');
    const tbody = document.querySelector('#deckValueTable tbody');
    const deckId = getCurrentDeck();
    const showDeckSummary = deckId === 'All';

    if (panel) {
        panel.hidden = !showDeckSummary;
    }
    if (cardsPanel) {
        cardsPanel.hidden = showDeckSummary;
    }
    if (!showDeckSummary || !tbody) {
        return;
    }

    if (!decks || !decks.length) {
        tbody.innerHTML = '<tr><td colspan="5">No decks available.</td></tr>';
        return;
    }

    const rows = decks.map((deck) => {
        const stats = pages[String(deck.id)] || {};
        return {
            id: deck.id,
            name: deck.name,
            label: deckDisplayName(deck),
            releaseYear: deck.releaseYear,
            deckSize: stats.deckSize || 0,
            current: stats.current,
            purchasePrice: stats.purchasePrice,
            profit: stats.profit,
        };
    }).sort((left, right) => {
        const yearDiff = (Number(left.releaseYear) || 9999) - (Number(right.releaseYear) || 9999);
        if (yearDiff !== 0) {
            return yearDiff;
        }
        return String(left.name).localeCompare(String(right.name));
    });

    tbody.innerHTML = rows.map((row) => {
        const deckLink = (
            `<a href="#" class="stats-art-style-link" data-deck-id="${escapeHtml(String(row.id))}">` +
            `${escapeHtml(row.label)}</a>`
        );
        return (
            '<tr>' +
            `<td>${deckLink}</td>` +
            `<td>${row.deckSize}</td>` +
            `<td>${formatEuro(row.current)}</td>` +
            `<td>${formatInvested(row.purchasePrice)}</td>` +
            `<td>${formatProfit(row.profit, 'Unknown')}</td>` +
            '</tr>'
        );
    }).join('');
}

function initDeckValueTableLinks(onDeckSelect) {
    const table = document.getElementById('deckValueTable');
    if (!table) {
        return;
    }

    table.addEventListener('click', function (event) {
        const link = event.target.closest('[data-deck-id]');
        if (!link) {
            return;
        }
        event.preventDefault();
        onDeckSelect(String(link.dataset.deckId));
    });
}

function renderDeckCardsTable(cards) {
    const tbody = document.querySelector('#deckCardsTable tbody');
    if (!tbody) {
        return;
    }

    if (!cards || !cards.length) {
        tbody.innerHTML = '<tr><td colspan="4">No cards in this deck.</td></tr>';
        return;
    }

    tbody.innerHTML = cards.map((card) => {
        const labelCell = buildDeckCardNameHtml(card, {
            linkClass: 'stats-art-style-link',
            showSetInName: true,
            showNotOwnedBadge: false,
        });
        const owned = card.owned_qty > 0 ? `${card.owned_qty} / ${card.qty}` : '—';
        return (
            '<tr>' +
            `<td>${labelCell}</td>` +
            `<td>${card.qty}</td>` +
            `<td>${formatEuro(card.current_value)}</td>` +
            `<td>${owned}</td>` +
            '</tr>'
        );
    }).join('');
}

function renderDeckStatsPage(stats) {
    setStatValue('[data-stat="current"]', formatEuro(stats.current));
    setStatValue('[data-stat="tracked-coverage"]', `${stats.trackedQty || 0} tracked cards priced`);
    setStatValue('[data-stat="owned"]', formatCoverage(stats.ownedQty, stats.deckSize));
    setStatValue('[data-stat="owned-coverage"]', stats.ownedCoverage != null ? `${stats.ownedCoverage}% of deck` : '');
    setStatValue('[data-stat="missing"]', stats.missingQty ? `${stats.missingQty} missing copies` : '');
    setStatValue('[data-stat="purchase-price"]', formatInvested(stats.purchasePrice));
    setStatValue('[data-stat="profit"]', formatProfit(stats.profit, 'Unknown'));
    setStatValue('[data-stat="return"]', formatDeckRoi(stats.profit, stats.purchasePrice || stats.invested));
    setStatValue('[data-stat="deck-size"]', String(stats.deckSize || 0));
    setStatValue('[data-stat="tracked"]', formatCoverage(stats.trackedQty, stats.deckSize));
    setStatValue('[data-stat="average"]', formatEuro(stats.average));
    setStatValue('[data-stat="unknown"]', `${stats.unknownQty || 0} cards`);
    setStatValue('[data-stat="unknown-count"]', `${stats.unknownCount || 0} unique entries`);
    setStatValue('[data-stat="winners"]', String(stats.winners || 0));
    setStatValue('[data-stat="losers"]', String(stats.losers || 0));
    renderDeckCardsTable(stats.cards);
}

function initDeckStatsReport() {
    const data = window.DECK_STATS_DATA;
    if (!data) {
        return;
    }

    function renderCurrentView() {
        const deckId = getCurrentDeck();
        const pageStats = data.pages[deckId] || data.pages.All;
        if (!pageStats) {
            return;
        }
        renderDeckValueTable(data.decks, data.pages);
        renderDeckStatsPage(pageStats);
    }

    initDeckValueTableLinks(function (deckId) {
        const select = document.getElementById('report-deck-select');
        if (select) {
            select.value = deckId;
        }
        setCurrentDeck(deckId);
        syncDeckUrlParam(deckId);
        renderCurrentView();
    });

    initDeckNav(function () {
        renderCurrentView();
    });
}

$(document).ready(initDeckStatsReport);
