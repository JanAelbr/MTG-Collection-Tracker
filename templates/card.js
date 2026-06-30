const NEIGHBOR_BATCH = 10;
const neighborBrowseState = {
    prevCount: NEIGHBOR_BATCH,
    nextCount: NEIGHBOR_BATCH,
};
const neighborListScrollState = {
    userScrolled: false,
    programmatic: false,
    alignment: 'center',
};

function printKey(card) {
    return `${card.set_code}|${card.collector_number}`;
}

function parseCardParams() {
    const params = new URLSearchParams(window.location.search);
    const finishParam = params.get('finish') ?? params.get('foil');
    return {
        set_code: (params.get('set') || '').toUpperCase(),
        collector_number: params.get('number') || '',
        finish: finishParam === '1' ? '1' : '0',
    };
}

function lookupCard(data, params) {
    const key = printKey(params);
    return data.cards[key] || null;
}

function availableFinishes(card) {
    return ['0', '1'].filter((finish) => card.finishes[finish]);
}

function defaultFinish(card, preferredFinish) {
    if (card.finishes[preferredFinish]) {
        return preferredFinish;
    }
    const owned = availableFinishes(card).find((finish) => card.finishes[finish].owned);
    return owned || availableFinishes(card)[0] || '0';
}

function formatFinishLabel(finish) {
    return Number(finish) === 1 ? 'Foil' : 'Non-foil';
}

function renderNotFound(root) {
    root.innerHTML = (
        '<section class="card-detail-panel">' +
        '<h1>Card not found</h1>' +
        '<p>This card is not in the catalog or has no pricing data yet.</p>' +
        '</section>'
    );
}

function renderVariantImage(variant) {
    if (!variant.image_uri) {
        return '<div class="card-variant-image-wrap"><div class="card-variant-image card-variant-image-empty"></div></div>';
    }
    return (
        '<div class="card-variant-image-wrap">' +
        `<img src="${escapeHtml(variant.image_uri)}" alt="${escapeHtml(variant.name)}" ` +
        'class="card-variant-image" loading="lazy">' +
        '</div>'
    );
}

function renderVariantDetails(variant, showName) {
    const number = String(variant.collector_number).padStart(3, '0');
    const nonfoil = variant.finishes['0'];
    const foil = variant.finishes['1'];
    const nameRow = showName
        ? `<div class="card-variant-row card-variant-row-name"><span>${escapeHtml(variant.name)}</span></div>`
        : '';
    return (
        '<div class="card-variant-details">' +
        nameRow +
        `<div class="card-variant-row card-variant-row-set"><span class="card-variant-key">Set</span><span class="card-variant-set-name">${escapeHtml(formatSetLabel(variant.set_code))}</span></div>` +
        `<div class="card-variant-row"><span class="card-variant-key">Nr</span><span>#${escapeHtml(number)}</span></div>` +
        `<div class="card-variant-row"><span class="card-variant-key">Non-foil</span><span>${formatEuro(nonfoil?.current_value)}</span></div>` +
        `<div class="card-variant-row card-variant-row-price"><span class="card-variant-key">Foil</span><span>${formatEuro(foil?.current_value)}</span></div>` +
        '</div>'
    );
}

function renderVariantContent(variant, showName) {
    return (
        '<div class="card-variant-body">' +
        renderVariantImage(variant) +
        renderVariantDetails(variant, showName) +
        '</div>'
    );
}

function renderVariantTile(variant, options) {
    const {
        isCurrent = false,
        href = null,
        finish = null,
    } = options;
    const inner = renderVariantContent(variant, Boolean(options.showName));
    if (isCurrent) {
        return `<div class="card-variant card-variant-current">${inner}</div>`;
    }
    const url = href || cardDetailUrl(variant, finish);
    return `<a href="${url}" class="card-variant">${inner}</a>`;
}

function getSetInfo(setCode) {
    return window.CARDS_DATA.sets?.[setCode] || null;
}

function formatSetLabel(setCode) {
    const info = getSetInfo(setCode);
    if (info?.name) {
        return `${info.name} (${setCode})`;
    }
    return setCode;
}

function formatReleaseDate(isoDate) {
    if (!isoDate) {
        return null;
    }
    const parts = String(isoDate).split('-').map(Number);
    if (parts.length !== 3 || parts.some(Number.isNaN)) {
        return isoDate;
    }
    return new Date(parts[0], parts[1] - 1, parts[2]).toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
    });
}

function renderSetInfo(setCode) {
    const info = getSetInfo(setCode);
    const label = formatSetLabel(setCode);
    const nameHtml = info?.scryfall_uri
        ? `<a href="${escapeHtml(info.scryfall_uri)}" target="_blank" rel="noopener noreferrer" class="card-detail-set-link">${escapeHtml(label)}</a>`
        : `<span class="card-detail-set-name">${escapeHtml(label)}</span>`;
    const release = formatReleaseDate(info?.released_at);
    const meta = release
        ? `<p class="card-detail-set-meta">Released ${escapeHtml(release)}</p>`
        : '';
    return `<div class="card-detail-set-info">${nameHtml}${meta}</div>`;
}

function getSetOrder(setCode) {
    return window.CARDS_DATA.set_orders?.[setCode] || [];
}

function getNeighborCarousel(card, currentPrintKey) {
    const order = getSetOrder(card.set_code);
    const index = order.indexOf(currentPrintKey);
    if (index === -1) {
        return null;
    }

    const prevStart = Math.max(0, index - neighborBrowseState.prevCount);
    const prevKeys = order.slice(prevStart, index);
    const nextKeys = order.slice(index + 1, index + 1 + neighborBrowseState.nextCount);

    if (!prevKeys.length && !nextKeys.length) {
        return null;
    }

    return {
        prevKeys,
        nextKeys,
        hasMorePrev: prevStart > 0,
        hasMoreNext: index + 1 + neighborBrowseState.nextCount < order.length,
    };
}

function renderSetNeighbors(card, currentPrintKey, finish) {
    const carousel = getNeighborCarousel(card, currentPrintKey);
    if (!carousel) {
        return '';
    }

    const data = window.CARDS_DATA;
    const allKeys = carousel.prevKeys.concat([currentPrintKey], carousel.nextKeys);
    const items = allKeys.map((key) => {
        const neighbor = data.cards[key];
        if (!neighbor) {
            return '';
        }
        return renderVariantTile(neighbor, {
            showName: true,
            finish,
            isCurrent: key === currentPrintKey,
        });
    }).filter(Boolean).join('');

    return (
        '<section class="card-detail-panel card-detail-neighbors">' +
        '<div class="card-neighbor-header">' +
        `<button type="button" class="card-neighbor-arrow card-neighbor-arrow-prev${carousel.hasMorePrev ? '' : ' is-hidden'}" ` +
        'aria-label="More previous cards" title="More previous cards">&larr;</button>' +
        '<h2>Previous & next numbers</h2>' +
        `<button type="button" class="card-neighbor-arrow card-neighbor-arrow-next${carousel.hasMoreNext ? '' : ' is-hidden'}" ` +
        'aria-label="More next cards" title="More next cards">&rarr;</button>' +
        '</div>' +
        `<div class="card-neighbor-list">${items}</div>` +
        '</section>'
    );
}

function updateSetNeighbors(card, currentPrintKey, finish, scrollAlignment = 'center') {
    const container = document.getElementById('cardSetNeighbors');
    if (!container) {
        return;
    }
    container.innerHTML = renderSetNeighbors(card, currentPrintKey, finish);
    bindNeighborBrowsing(card, currentPrintKey, finish);
    bindNeighborListScroll(scrollAlignment);
}

function bindNeighborBrowsing(card, currentPrintKey, finish) {
    const prevButton = document.querySelector('.card-neighbor-arrow-prev');
    const nextButton = document.querySelector('.card-neighbor-arrow-next');

    if (prevButton) {
        prevButton.addEventListener('click', function () {
            neighborBrowseState.prevCount += NEIGHBOR_BATCH;
            updateSetNeighbors(card, currentPrintKey, finish, 'start');
        });
    }

    if (nextButton) {
        nextButton.addEventListener('click', function () {
            neighborBrowseState.nextCount += NEIGHBOR_BATCH;
            updateSetNeighbors(card, currentPrintKey, finish, 'end');
        });
    }
}

function scrollNeighborList(alignment) {
    const list = document.querySelector('.card-neighbor-list');
    if (!list) {
        return;
    }

    neighborListScrollState.programmatic = true;

    if (alignment === 'start') {
        list.scrollLeft = 0;
    } else if (alignment === 'end') {
        list.scrollLeft = Math.max(0, list.scrollWidth - list.clientWidth);
    } else {
        const current = list.querySelector('.card-variant-current');
        if (current) {
            const listRect = list.getBoundingClientRect();
            const currentRect = current.getBoundingClientRect();
            const delta = (currentRect.left + currentRect.width / 2)
                - (listRect.left + listRect.width / 2);
            list.scrollLeft += delta;
        }
    }

    requestAnimationFrame(() => {
        neighborListScrollState.programmatic = false;
    });
}

function bindNeighborListScroll(alignment = 'center') {
    neighborListScrollState.userScrolled = false;
    neighborListScrollState.alignment = alignment;

    const list = document.querySelector('.card-neighbor-list');
    if (!list) {
        return;
    }

    list.addEventListener('scroll', () => {
        if (neighborListScrollState.programmatic) {
            return;
        }
        neighborListScrollState.userScrolled = true;
    }, { passive: true });

    const applyScroll = () => scrollNeighborList(neighborListScrollState.alignment);
    requestAnimationFrame(() => {
        applyScroll();
        if (neighborListScrollState.alignment === 'end') {
            requestAnimationFrame(applyScroll);
        }
    });

    list.querySelectorAll('img.card-variant-image').forEach((img) => {
        if (img.complete) {
            return;
        }
        img.addEventListener('load', () => {
            if (!neighborListScrollState.userScrolled) {
                applyScroll();
            }
        }, { once: true });
    });
}

function centerVariantList(listSelector, scrollState) {
    const list = document.querySelector(listSelector);
    const current = list?.querySelector('.card-variant-current');
    if (!list || !current) {
        return;
    }

    const listRect = list.getBoundingClientRect();
    const currentRect = current.getBoundingClientRect();
    const delta = (currentRect.left + currentRect.width / 2)
        - (listRect.left + listRect.width / 2);

    if (scrollState) {
        scrollState.programmatic = true;
    }
    list.scrollLeft += delta;
    if (scrollState) {
        requestAnimationFrame(() => {
            scrollState.programmatic = false;
        });
    }
}

function syncVariantListLayout() {
    const list = document.querySelector('.card-variant-list');
    if (!list) {
        return;
    }

    list.classList.toggle('is-fit-centered', list.scrollWidth <= list.clientWidth + 1);

    if (!list.classList.contains('is-fit-centered')) {
        centerVariantList('.card-variant-list');
    }
}

function bindVariantListScroll() {
    requestAnimationFrame(() => {
        syncVariantListLayout();
        requestAnimationFrame(syncVariantListLayout);
    });

    const list = document.querySelector('.card-variant-list');
    if (!list) {
        return;
    }

    list.querySelectorAll('img.card-variant-image').forEach((img) => {
        if (img.complete) {
            return;
        }
        img.addEventListener('load', syncVariantListLayout, { once: true });
    });

    window.addEventListener('resize', syncVariantListLayout);
}

function renderVariants(card, currentPrintKey, finish) {
    const variants = card.variant_keys || [];
    if (variants.length <= 1) {
        return '';
    }

    const data = window.CARDS_DATA;
    const items = variants.map((key) => {
        const variant = data.cards[key];
        if (!variant) {
            return '';
        }
        return renderVariantTile(variant, {
            isCurrent: key === currentPrintKey,
            finish,
        });
    }).filter(Boolean).join('');

    return (
        '<section class="card-detail-panel card-detail-variants">' +
        '<h2>Alternative versions</h2>' +
        `<div class="card-variant-list">${items}</div>` +
        '</section>'
    );
}

function renderDetailFinishLinks(card, selectedFinish) {
    const finishes = availableFinishes(card);
    if (finishes.length <= 1) {
        return '';
    }

    const links = finishes.map((finish) => (
        `<a href="${cardDetailUrl(card, finish)}" ` +
        `class="card-detail-finish-link${finish === selectedFinish ? ' active' : ''}">` +
        `${escapeHtml(formatFinishLabel(finish))}</a>`
    )).join('<span class="card-finish-separator"> · </span>');

    return `<div class="card-detail-finish-links">${links}</div>`;
}

function renderCardImage(card) {
    if (!card.image_uri) {
        return '<div class="card-detail-image card-detail-image-empty">No image</div>';
    }
    return (
        `<img src="${escapeHtml(card.image_uri)}" alt="${escapeHtml(card.name)}" ` +
        'class="card-detail-image">'
    );
}

function renderCollectionLinks(card) {
    const ownedUrl = collectionReportUrl(card.set_code, card.art_style, true);
    const allUrl = collectionReportUrl(card.set_code, card.art_style, false);
    return (
        '<div class="card-detail-collection-links">' +
        `<a href="${escapeHtml(ownedUrl)}" class="card-detail-collection-link">Top cards (owned)</a>` +
        '<span class="card-finish-separator"> · </span>' +
        `<a href="${escapeHtml(allUrl)}" class="card-detail-collection-link">Top cards (all)</a>` +
        '</div>'
    );
}

function renderLocationLinks(card, selectedFinish) {
    const finishData = card.finishes[selectedFinish];
    const locations = finishData?.locations || [];
    if (!locations.length) {
        return '';
    }

    const links = locations.map((location) => {
        const countLabel = location.count > 1 ? ` (${location.count}×)` : '';
        return (
            `<a href="${escapeHtml(locationReportUrl(location))}" ` +
            `class="card-detail-location-link">${escapeHtml(location.label)}${countLabel}</a>`
        );
    }).join('<span class="card-finish-separator"> · </span>');

    return (
        '<div class="card-detail-locations">' +
        '<span class="card-detail-locations-label">Stored in</span> ' +
        links +
        '</div>'
    );
}

function finishSnapshotKey(card, finish) {
    return `${card.set_code}|${card.collector_number}|${finish}`;
}

function finishPriceChange(card, finish) {
    const finishData = card.finishes[finish];
    if (!finishData) {
        return { change: null, previous: null };
    }
    if (finishData.price_change != null || finishData.previous_value != null) {
        return {
            change: finishData.price_change,
            previous: finishData.previous_value,
        };
    }

    const data = window.CARDS_DATA;
    if (!data?.snapshots) {
        return { change: null, previous: null };
    }
    const compareDate = getSelectedCompareDate(data);
    const previous = (data.snapshots[compareDate] || {})[finishSnapshotKey(card, finish)];
    if (previous == null || finishData.current_value == null) {
        return { change: null, previous: null };
    }
    return { change: finishData.current_value - previous, previous };
}

function renderPricingGrid(card) {
    const finishes = availableFinishes(card);
    if (!finishes.length) {
        return '';
    }

    const header = ['<span class="card-detail-pricing-label"></span>']
        .concat(finishes.map((finish) => (
            `<span class="card-detail-pricing-label">${escapeHtml(formatFinishLabel(finish))}</span>`
        )))
        .join('');

    function valueCell(finish, getter, isProfit, linkToCardmarket) {
        const data = card.finishes[finish];
        if (!data) {
            return '<span>—</span>';
        }
        const value = getter(data);
        let text;
        if (isProfit) {
            text = formatProfit(value, '—');
        } else {
            text = formatEuro(value);
        }
        if (linkToCardmarket && card.cardmarket_url) {
            const safeUrl = escapeHtml(card.cardmarket_url);
            return (
                `<a href="${safeUrl}" target="_blank" rel="noopener noreferrer" ` +
                `class="price-link">${text}</a>`
            );
        }
        return text;
    }

    function pricingRow(label, getter, isProfit, linkToCardmarket) {
        const cells = finishes.map((finish) => (
            `<span>${valueCell(finish, getter, isProfit, linkToCardmarket)}</span>`
        )).join('');
        return (
            '<div class="card-detail-pricing-row">' +
            `<span class="card-detail-pricing-label">${escapeHtml(label)}</span>${cells}` +
            '</div>'
        );
    }

    function pricingChangeRow() {
        const compareLabel = getComparePreset(getSelectedComparePreset(window.CARDS_DATA)).label;
        const cells = finishes.map((finish) => {
            const { change, previous } = finishPriceChange(card, finish);
            return `<span>${formatPriceChange(change, previous)}</span>`;
        }).join('');
        return (
            '<div class="card-detail-pricing-row">' +
            `<span class="card-detail-pricing-label">Change (${escapeHtml(compareLabel)})</span>${cells}` +
            '</div>'
        );
    }

    return (
        '<div class="card-detail-pricing-grid">' +
        `<div class="card-detail-pricing-row card-detail-pricing-header">${header}</div>` +
        pricingRow('Current value', (data) => data.current_value, false, true) +
        pricingChangeRow() +
        pricingRow('Purchase', (data) => data.purchase_value, false, false) +
        pricingRow('Profit / loss', (data) => data.profit_loss, true, false) +
        '</div>'
    );
}

function renderCardDetail(card, selectedFinish) {
    const root = document.getElementById('cardDetailRoot');
    const currentPrintKey = printKey(card);

    root.innerHTML = (
        '<section class="card-detail-panel card-detail-main">' +
        `<div class="card-detail-image-wrap">${renderCardImage(card)}</div>` +
        '<div class="card-detail-meta">' +
        `<h1>${escapeHtml(card.name)}</h1>` +
        renderSetInfo(card.set_code) +
        `<p class="card-detail-subtitle">#${escapeHtml(String(card.collector_number).padStart(3, '0'))}</p>` +
        `<p class="card-detail-art-style">${escapeHtml(card.art_style)}</p>` +
        renderCollectionLinks(card) +
        renderLocationLinks(card, selectedFinish) +
        renderDetailFinishLinks(card, selectedFinish) +
        renderPricingGrid(card) +
        '</div>' +
        '</section>' +
        renderVariants(card, currentPrintKey, selectedFinish) +
        `<div id="cardSetNeighbors">${renderSetNeighbors(card, currentPrintKey, selectedFinish)}</div>`
    );

    bindVariantListScroll();
    bindNeighborBrowsing(card, currentPrintKey, selectedFinish);
    bindNeighborListScroll();
    document.title = `${card.name} · ${formatSetLabel(card.set_code)}`;
}

function resetNeighborBrowseState() {
    neighborBrowseState.prevCount = NEIGHBOR_BATCH;
    neighborBrowseState.nextCount = NEIGHBOR_BATCH;
}

function initCardDetailPage() {
    const data = window.CARDS_DATA;
    const root = document.getElementById('cardDetailRoot');
    if (!data || !root) {
        return;
    }

    resetNeighborBrowseState();

    const params = parseCardParams();
    const card = lookupCard(data, params);
    if (!card) {
        renderNotFound(root);
        document.title = 'Card not found';
        return;
    }

    const finish = defaultFinish(card, params.finish);
    renderCardDetail(card, finish);
}

document.addEventListener('DOMContentLoaded', initCardDetailPage);
