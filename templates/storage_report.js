let storageTable = null;
const loadedLocationCards = new Map();
const loadingLocationCards = new Map();

function getCurrentLocation() {
    return document.body.dataset.currentLocation || '';
}

function setCurrentLocation(locationSlug) {
    document.body.dataset.currentLocation = locationSlug;
    syncStorageUrlParam(locationSlug);
}

function syncStorageUrlParam(locationSlug) {
    const params = new URLSearchParams(window.location.search);
    if (locationSlug) {
        params.set('location', locationSlug);
    } else {
        params.delete('location');
    }
    const query = params.toString();
    window.history.replaceState({}, '', query ? `${window.location.pathname}?${query}` : window.location.pathname);
}

function getInitialLocation(locations) {
    const params = new URLSearchParams(window.location.search);
    const requested = params.get('location');
    if (requested && locations.some((location) => location.slug === requested)) {
        return requested;
    }
    return locations[0]?.slug || '';
}

function findLocation(data, locationSlug) {
    return (data.locations || []).find((location) => location.slug === locationSlug) || null;
}

function locationCardsScriptUrl(locationSlug) {
    const filename = `${String(locationSlug).replace(/:/g, '_')}.js`;
    return `data/storage_locations/${filename}`;
}

function loadLocationCards(locationSlug) {
    if (loadedLocationCards.has(locationSlug)) {
        return Promise.resolve(loadedLocationCards.get(locationSlug));
    }
    if (loadingLocationCards.has(locationSlug)) {
        return loadingLocationCards.get(locationSlug);
    }

    const promise = new Promise((resolve) => {
        const script = document.createElement('script');
        script.src = locationCardsScriptUrl(locationSlug);
        script.onload = () => {
            const cards = window.STORAGE_LOCATION_CARDS || [];
            delete window.STORAGE_LOCATION_CARDS;
            loadedLocationCards.set(locationSlug, cards);
            loadingLocationCards.delete(locationSlug);
            resolve(cards);
        };
        script.onerror = () => {
            loadedLocationCards.set(locationSlug, []);
            loadingLocationCards.delete(locationSlug);
            resolve([]);
        };
        document.head.appendChild(script);
    });

    loadingLocationCards.set(locationSlug, promise);
    return promise;
}

function renderStorageOverview(data) {
    const container = document.getElementById('storageOverview');
    if (!container) {
        return;
    }

    const locations = data.locations || [];
    if (!locations.length) {
        container.innerHTML = '<p class="storage-empty">No stored cards yet. Import purchases and deck lists first.</p>';
        return;
    }

    container.innerHTML = locations.map((location) => (
        '<button type="button" class="storage-overview-card" data-location-slug="' +
        `${escapeHtml(location.slug)}">` +
        `<span class="storage-overview-label">${escapeHtml(location.label)}</span>` +
        `<span class="storage-overview-count">${location.cardCount} cards</span>` +
        `<span class="storage-overview-prints">${location.uniquePrints} unique prints</span>` +
        '</button>'
    )).join('');
}

function renderStorageLocationNav(data, activeSlug) {
    const nav = document.getElementById('storageLocationNav');
    if (!nav) {
        return;
    }

    nav.innerHTML = (data.locations || []).map((location) => {
        const activeClass = location.slug === activeSlug ? ' active' : '';
        return (
            `<button type="button" class="storage-location-link${activeClass}" ` +
            `data-location-slug="${escapeHtml(location.slug)}">` +
            `${escapeHtml(location.label)}` +
            `<span class="storage-location-count">${location.cardCount}</span>` +
            '</button>'
        );
    }).join('');
}

function buildStorageCardLabel(card) {
    const number = String(card.collector_number).padStart(3, '0');
    const ref = {
        set_code: card.set_code,
        collector_number: card.collector_number,
        name: card.name,
        foil: card.foil,
        image_uri: card.image_uri,
    };
    const nameLink = (
        `<a href="${cardDetailUrl(ref, card.foil)}" class="card-name-link">` +
        `${escapeHtml(displayName(ref))}</a>`
    );
    return wrapCardPreview(`${escapeHtml(number)} - ${nameLink}`, card.image_uri);
}

function destroyStorageTable() {
    if ($.fn.DataTable.isDataTable('#storageTable')) {
        $('#storageTable').DataTable().destroy();
    }
    storageTable = null;
}

function renderStorageTable(cards) {
    destroyStorageTable();
    const tbody = document.querySelector('#storageTable tbody');
    if (!cards.length) {
        tbody.innerHTML = '<tr><td colspan="7">No cards in this location.</td></tr>';
        return;
    }

    tbody.innerHTML = cards.map((card) => {
        const unitValue = card.current_value;
        const totalValue = unitValue != null ? unitValue * card.copy_count : null;
        return (
            '<tr>' +
            `<td>${buildSetLinkCell(card.set_code)}</td>` +
            `<td>${escapeHtml(String(card.collector_number).padStart(3, '0'))}</td>` +
            `<td>${buildStorageCardLabel(card)}</td>` +
            `<td>${escapeHtml(card.art_style || '—')}</td>` +
            `<td>${escapeHtml(formatFinish(card.foil))}</td>` +
            `<td>${card.copy_count}</td>` +
            `<td>${formatEuro(totalValue)}</td>` +
            '</tr>'
        );
    }).join('');

    storageTable = $('#storageTable').DataTable({
        pageLength: 100,
        order: [[0, 'asc']],
        language: {
            search: '',
            searchPlaceholder: 'Search cards...',
        },
    });
}

function setStorageTableLoading(isLoading) {
    destroyStorageTable();
    const tbody = document.querySelector('#storageTable tbody');
    if (!tbody) {
        return;
    }
    tbody.innerHTML = isLoading
        ? '<tr><td colspan="7">Loading cards...</td></tr>'
        : '';
}

function renderStorageLocationHeader(data, locationSlug) {
    const location = findLocation(data, locationSlug);
    const title = document.getElementById('storageLocationTitle');
    const description = document.getElementById('storageLocationDescription');
    const stats = document.getElementById('storageLocationStats');

    if (title) {
        title.textContent = location?.label || 'Storage';
    }
    if (description) {
        description.textContent = location?.description || '';
    }
    if (stats) {
        stats.textContent = location
            ? `${location.cardCount} physical cards · ${location.uniquePrints} unique prints`
            : '';
    }

    renderStorageLocationNav(data, locationSlug);
    document.querySelectorAll('.storage-overview-card').forEach((button) => {
        button.classList.toggle('active', button.dataset.locationSlug === locationSlug);
    });
}

async function renderStorageLocation(data, locationSlug) {
    renderStorageLocationHeader(data, locationSlug);
    setStorageTableLoading(true);

    const cards = await loadLocationCards(locationSlug);
    renderStorageTable(cards);
    initCardImageTooltip('#storageTable');
}

function initStorageReport() {
    const data = window.STORAGE_DATA;
    if (!data) {
        return;
    }

    renderStorageOverview(data);
    const initialLocation = getInitialLocation(data.locations || []);
    setCurrentLocation(initialLocation);
    renderStorageLocation(data, initialLocation);

    function selectLocation(locationSlug) {
        if (!locationSlug || !findLocation(data, locationSlug)) {
            return;
        }
        setCurrentLocation(locationSlug);
        renderStorageLocation(data, locationSlug);
    }

    document.getElementById('storageOverview')?.addEventListener('click', (event) => {
        const button = event.target.closest('[data-location-slug]');
        if (!button) {
            return;
        }
        selectLocation(button.dataset.locationSlug);
    });

    document.getElementById('storageLocationNav')?.addEventListener('click', (event) => {
        const button = event.target.closest('[data-location-slug]');
        if (!button) {
            return;
        }
        selectLocation(button.dataset.locationSlug);
    });
}

document.addEventListener('DOMContentLoaded', initStorageReport);
