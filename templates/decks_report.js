const SECTION_ORDER = {
    commander: 0,
    main: 1,
    sideboard: 2,
};

const GALLERY_COMMANDER_COUNT = 2;
const GALLERY_TOP_CARD_COUNT = 4;
const HERO_TOP_CARD_COUNT = 5;
const GALLERY_SORT_KEY = 'reportDeckGallerySort';

let decksTable = null;
let gallerySort = 'year';

function getCurrentDeck() {
    return document.body.dataset.currentDeck || '';
}

function setCurrentDeck(deckId) {
    document.body.dataset.currentDeck = deckId;
    persistDeckSelection(deckId);
    syncDeckReportLinks(deckId);
}

function syncDeckUrlParam(deckId) {
    const params = new URLSearchParams(window.location.search);
    if (deckId) {
        params.set('deck', deckId);
    } else {
        params.delete('deck');
    }
    params.delete('foil');
    const query = params.toString();
    window.history.replaceState({}, '', query ? `${window.location.pathname}?${query}` : window.location.pathname);
}

function deckDisplayName(deck) {
    return deck?.label || deck?.name || '';
}

function deckCardName(card) {
    return resolveCardName(card);
}

function getInitialDeck(availableDecks) {
    return getInitialDeckSelection(availableDecks, { allowAll: false });
}

function formatDeckValueRange(ownedValue, totalValue) {
    return `${formatEuro(ownedValue)} / ${formatEuro(totalValue)}`;
}

function initDeckBrowseNav(onDeckChange) {
    const decks = window.DECKS_DATA?.decks || [];
    const initialDeck = getInitialDeck(decks);

    setCurrentDeck(initialDeck);
    syncDeckUrlParam(initialDeck);
    onDeckChange(initialDeck);
}

function getCommanderCards(cards) {
    return (cards || []).filter((card) => card.section === 'commander' && card.image_uri);
}

function getTopValueCards(cards, limit, excludeCommanders = true) {
    let pool = (cards || []).filter(
        (card) => card.in_catalog && card.image_uri && card.current_value != null,
    );
    if (excludeCommanders) {
        pool = pool.filter((card) => card.section !== 'commander');
    }
    return [...pool].sort(
        (left, right) => (right.current_value || 0) - (left.current_value || 0),
    ).slice(0, limit);
}

function buildDeckThumbImage(card, className) {
    if (!card?.image_uri) {
        return '';
    }
    const name = deckCardName(card);
    return (
        `<figure class="${className}">` +
        `<img src="${escapeHtml(card.image_uri)}" alt="${escapeHtml(name)}" loading="lazy" title="${escapeHtml(name)}">` +
        '</figure>'
    );
}

function buildDeckHeroFigure(card, options = {}) {
    const { rank, showValue = true } = options;
    if (!card?.image_uri) {
        return '';
    }
    const name = deckCardName(card);
    const rankHtml = rank != null ? `<span class="top-card-rank">#${rank}</span>` : '';
    const valueHtml = showValue && card.current_value != null
        ? `<span class="top-card-value">${escapeHtml(formatEuro(card.current_value))}</span>`
        : '';
    return (
        `<figure class="top-card-image deck-hero-image">` +
        `<img src="${escapeHtml(card.image_uri)}" alt="${escapeHtml(name)}" loading="lazy">` +
        '<figcaption>' +
        rankHtml +
        `<span class="top-card-name">${escapeHtml(name)}</span>` +
        valueHtml +
        '</figcaption></figure>'
    );
}

function getStoredGallerySort() {
    const stored = localStorage.getItem(GALLERY_SORT_KEY);
    return stored === 'value' ? 'value' : 'year';
}

function getGallerySortValue() {
    const checked = document.querySelector('.deck-gallery-sort-input:checked');
    return checked?.value === 'value' ? 'value' : 'year';
}

function sortDecksForGallery(decks, pages, sortBy) {
    return [...decks].sort((left, right) => {
        if (sortBy === 'value') {
            const leftValue = pages[String(left.id)]?.current;
            const rightValue = pages[String(right.id)]?.current;
            const leftNumber = leftValue == null || Number.isNaN(leftValue) ? -Infinity : leftValue;
            const rightNumber = rightValue == null || Number.isNaN(rightValue) ? -Infinity : rightValue;
            const valueDiff = rightNumber - leftNumber;
            if (valueDiff !== 0) {
                return valueDiff;
            }
        } else {
            const leftYear = Number(left.releaseYear) || 9999;
            const rightYear = Number(right.releaseYear) || 9999;
            const yearDiff = leftYear - rightYear;
            if (yearDiff !== 0) {
                return yearDiff;
            }
        }
        return String(left.name).localeCompare(String(right.name));
    });
}

function renderDeckGallery(decks, pages, activeDeckId, sortBy = gallerySort) {
    const container = document.getElementById('deck-gallery');
    if (!container) {
        return;
    }

    const sortedDecks = sortDecksForGallery(decks, pages, sortBy);
    container.innerHTML = sortedDecks.map((deck) => {
        const stats = pages[String(deck.id)] || {};
        const cards = stats.cards || [];
        const commanders = getCommanderCards(cards).slice(0, GALLERY_COMMANDER_COUNT);
        const topCards = getTopValueCards(cards, GALLERY_TOP_CARD_COUNT);
        const ownedLabel = stats.ownedCurrent != null && stats.current != null
            ? formatDeckValueRange(stats.ownedCurrent, stats.current)
            : formatEuro(stats.current);
        const activeClass = String(deck.id) === String(activeDeckId) ? ' active' : '';
        const yearLabel = deck.releaseYear ? String(deck.releaseYear) : '';

        const commanderHtml = commanders.length
            ? commanders.map((card) => buildDeckThumbImage(card, 'deck-gallery-commander')).join('')
            : '<div class="deck-gallery-placeholder">No commander image</div>';

        const highlightsHtml = topCards.length
            ? topCards.map((card) => buildDeckThumbImage(card, 'deck-gallery-highlight')).join('')
            : '<div class="deck-gallery-placeholder deck-gallery-placeholder-small">No priced cards</div>';

        return (
            `<button type="button" class="deck-gallery-card${activeClass}" data-deck-id="${escapeHtml(String(deck.id))}">` +
            '<div class="deck-gallery-visual">' +
            `<div class="deck-gallery-commanders">${commanderHtml}</div>` +
            `<div class="deck-gallery-highlights">${highlightsHtml}</div>` +
            '</div>' +
            '<div class="deck-gallery-meta">' +
            `<h3 class="deck-gallery-name">${escapeHtml(deckDisplayName(deck))}</h3>` +
            '<div class="deck-gallery-stats">' +
            (yearLabel ? `<span class="deck-gallery-year">${escapeHtml(yearLabel)}</span>` : '') +
            `<span class="deck-gallery-value">${escapeHtml(ownedLabel)}</span>` +
            '</div></div></button>'
        );
    }).join('');
}

function initDeckGallerySort(onChange) {
    gallerySort = getStoredGallerySort();
    document.querySelectorAll('.deck-gallery-sort-input').forEach((input) => {
        input.checked = input.value === gallerySort;
        input.addEventListener('change', () => {
            gallerySort = getGallerySortValue();
            localStorage.setItem(GALLERY_SORT_KEY, gallerySort);
            onChange();
        });
    });
}

function renderDeckHero(stats, deck) {
    const hero = document.getElementById('deck-hero');
    if (!hero) {
        return;
    }

    const cards = stats.cards || [];
    const commanders = getCommanderCards(cards);
    const topCards = getTopValueCards(cards, HERO_TOP_CARD_COUNT);
    const titleEl = document.getElementById('deck-hero-title');
    const valueEl = document.getElementById('deck-hero-value');
    const commanderTitleEl = document.querySelector('.deck-hero-commanders .deck-hero-panel-title');
    const commanderImagesEl = document.querySelector('.deck-hero-commanders .deck-hero-images');
    const topImagesEl = document.querySelector('.deck-hero-top .deck-hero-images');

    if (titleEl) {
        titleEl.textContent = deckDisplayName(deck);
    }
    if (valueEl) {
        valueEl.textContent = formatDeckValueRange(stats.ownedCurrent, stats.current);
    }
    if (commanderTitleEl) {
        commanderTitleEl.textContent = commanders.length > 1 ? 'Commanders' : 'Commander';
    }
    if (commanderImagesEl) {
        commanderImagesEl.innerHTML = commanders.length
            ? commanders.map((card) => buildDeckHeroFigure(card, { showValue: true })).join('')
            : '<p class="deck-hero-empty">No commander images available.</p>';
    }
    if (topImagesEl) {
        topImagesEl.innerHTML = topCards.length
            ? topCards.map((card, index) => buildDeckHeroFigure(card, { rank: index + 1 })).join('')
            : '<p class="deck-hero-empty">No priced cards available.</p>';
    }
}

function initDeckGallery(onSelect) {
    const container = document.getElementById('deck-gallery');
    if (!container) {
        return;
    }

    container.addEventListener('click', (event) => {
        const card = event.target.closest('[data-deck-id]');
        if (!card) {
            return;
        }
        onSelect(String(card.dataset.deckId));
    });
}

function formatSection(section) {
    if (!section) {
        return '';
    }
    return section.charAt(0).toUpperCase() + section.slice(1);
}

function formatFinish(foil) {
    return Number(foil) === 1 ? 'Foil' : 'Non-foil';
}

function formatCoverage(covered, total) {
    if (!total) {
        return 'Unknown';
    }
    const percent = (covered / total) * 100;
    return `${covered} / ${total} (${percent.toFixed(1)}%)`;
}

function setSummaryValue(selector, value) {
    const element = document.querySelector(selector);
    if (element) {
        element.textContent = value;
    }
}

function deckCardRef(card) {
    return {
        set_code: card.set_code,
        collector_number: card.collector_number,
        name: resolveCardName(card),
        foil: card.foil,
        image_uri: card.image_uri,
        cardmarket_url: card.cardmarket_url,
    };
}

function buildDeckCardLabel(card) {
    return buildDeckCardNameHtml(card, { showNotOwnedBadge: true });
}

function buildDeckUnitValueCell(card) {
    if (!card.in_catalog) {
        return '—';
    }

    const ref = deckCardRef(card);
    ref.current_value = card.unit_value;
    return buildCurrentValueCell(ref);
}

function buildDeckTotalValueCell(card) {
    if (!card.in_catalog) {
        return '—';
    }

    const ref = deckCardRef(card);
    ref.current_value = card.current_value;
    return buildCurrentValueCell(ref);
}

function sortDeckCards(cards) {
    return [...cards].sort((left, right) => {
        const sectionDiff = (SECTION_ORDER[left.section] ?? 9) - (SECTION_ORDER[right.section] ?? 9);
        if (sectionDiff !== 0) {
            return sectionDiff;
        }
        const orderDiff = (left.sort_order ?? 0) - (right.sort_order ?? 0);
        if (orderDiff !== 0) {
            return orderDiff;
        }
        return String(left.card_name).localeCompare(String(right.card_name));
    });
}

function destroyDecksTable() {
    if ($.fn.DataTable.isDataTable('#decksTable')) {
        $('#decksTable').DataTable().destroy();
    }
    decksTable = null;
}

function renderDecksTable(cards) {
    destroyDecksTable();

    const tbody = document.querySelector('#decksTable tbody');
    if (!cards.length) {
        tbody.innerHTML = '<tr><td colspan="10">No cards in this deck.</td></tr>';
        return;
    }

    tbody.innerHTML = sortDeckCards(cards).map((card) => {
        const owned = card.owned_qty > 0 ? `${card.owned_qty} / ${card.qty}` : '—';
        return (
            '<tr>' +
            `<td>${escapeHtml(formatSection(card.section))}</td>` +
            `<td>${card.qty}</td>` +
            `<td>${buildDeckCardLabel(card)}</td>` +
            `<td>${buildSetLinkCell(card.set_code)}</td>` +
            `<td>${escapeHtml(formatFinish(card.foil))}</td>` +
            `<td>${escapeHtml(card.art_style || '—')}</td>` +
            `<td>${buildDeckUnitValueCell(card)}</td>` +
            `<td>${buildDeckTotalValueCell(card)}</td>` +
            `<td>${owned}</td>` +
            `<td>${formatGainLoss(card.profit_loss, card.purchase_value)}</td>` +
            '</tr>'
        );
    }).join('');

    decksTable = $('#decksTable').DataTable({
        pageLength: 100,
        order: [[0, 'asc']],
        language: {
            search: '',
            searchPlaceholder: 'Search cards...',
        },
        columnDefs: [
            {
                targets: 0,
                render(data, type) {
                    if (type === 'sort' || type === 'type') {
                        return SECTION_ORDER[String(data).toLowerCase()] ?? 9;
                    }
                    return data;
                },
            },
            {
                targets: 1,
                render(data, type) {
                    if (type === 'sort' || type === 'type') {
                        return parseInt(String(data), 10) || 0;
                    }
                    return data;
                },
            },
            {
                targets: 2,
                render(data, type) {
                    if (type === 'sort' || type === 'type') {
                        const match = String(data).match(/^\s*0*(\d+)\s*-\s*/);
                        return match ? parseInt(match[1], 10) : data;
                    }
                    return data;
                },
            },
            {
                targets: [6, 7, 9],
                render(data, type) {
                    if (type === 'sort' || type === 'type') {
                        return parseEuroNumber(data);
                    }
                    return data;
                },
            },
        ],
    });
}

function renderDeckSummary(stats) {
    setSummaryValue('[data-stat="value-range"]', formatDeckValueRange(stats.ownedCurrent, stats.current));
    setSummaryValue('[data-stat="deck-size"]', String(stats.deckSize || 0));
    setSummaryValue('[data-stat="owned"]', formatCoverage(stats.ownedQty, stats.deckSize));
    setSummaryValue('[data-stat="missing"]', String(stats.missingQty || 0));
    setSummaryValue(
        '[data-stat="tracked"]',
        stats.trackedCoverage != null ? `${stats.trackedCoverage}% priced` : 'Unknown',
    );
}

function renderDeckBrowsePage(stats, deck) {
    renderDeckHero(stats, deck);
    renderDeckSummary(stats);
    renderDecksTable(stats.cards || []);
}

function initDecksReport() {
    const data = window.DECKS_DATA;
    if (!data) {
        return;
    }

    function selectDeck(deckId) {
        setCurrentDeck(deckId);
        syncDeckUrlParam(deckId);
        renderCurrentView();
    }

    function renderCurrentView() {
        const deckId = getCurrentDeck();
        const pageStats = data.pages[deckId];
        const deck = data.decks.find((entry) => String(entry.id) === String(deckId));
        if (!pageStats) {
            return;
        }

        renderDeckGallery(data.decks, data.pages, deckId, gallerySort);
        renderDeckBrowsePage(pageStats, deck);

        const activeCard = document.querySelector(`.deck-gallery-card[data-deck-id="${deckId}"]`);
        if (activeCard) {
            activeCard.scrollIntoView({ block: 'nearest', inline: 'center', behavior: 'smooth' });
        }
    }

    initDeckGallerySort(renderCurrentView);
    initDeckGallery(selectDeck);
    initDeckBrowseNav(renderCurrentView);
}

$(document).ready(initDecksReport);
