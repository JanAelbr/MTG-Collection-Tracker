const MANAGER_CSV_HEADERS = ['card_number', 'purchase_value', 'foil'];

let managerTable = null;
let currentSetCode = '';
let currentCards = [];

function cloneCardsForSet(data, setCode) {
    return (data.cardsBySet[setCode] || []).map((card) => ({ ...card }));
}

function renderOwnershipCheckbox(card, finish) {
    const available = finish === 0 ? card.has_nonfoil : card.has_foil;
    if (!available) {
        return '<span class="manager-finish-unavailable">—</span>';
    }

    const owned = finish === 0 ? card.owned_nonfoil : card.owned_foil;
    return (
        `<input type="checkbox" class="manager-own-checkbox" ` +
        `data-collector-number="${escapeHtml(card.collector_number)}" ` +
        `data-finish="${finish}"${owned ? ' checked' : ''}>`
    );
}

function renderManagerCardLabel(card) {
    const number = String(card.collector_number).padStart(3, '0');
    const nameLink = (
        `<a href="${cardDetailUrl(card)}" class="card-name-link">` +
        `${escapeHtml(card.name)}</a>`
    );
    const labelHtml = `${escapeHtml(number)} - ${nameLink}`;
    return wrapCardPreview(labelHtml, card.image_uri);
}

function destroyManagerTable() {
    if ($.fn.DataTable.isDataTable('#managerTable')) {
        $('#managerTable').DataTable().destroy();
    }
    managerTable = null;
}

function renderManagerTable(cards) {
    destroyManagerTable();

    const sortedCards = sortCardsByCollectorNumber(cards);
    const tbody = document.querySelector('#managerTable tbody');
    tbody.innerHTML = sortedCards.map((card) => (
        '<tr>' +
        `<td>${escapeHtml(card.collector_number)}</td>` +
        `<td>${renderManagerCardLabel(card)}</td>` +
        `<td>${escapeHtml(card.art_style)}</td>` +
        `<td class="manager-checkbox-cell">${renderOwnershipCheckbox(card, 0)}</td>` +
        `<td class="manager-checkbox-cell">${renderOwnershipCheckbox(card, 1)}</td>` +
        '</tr>'
    )).join('');

    managerTable = $('#managerTable').DataTable({
        pageLength: 100,
        ordering: false,
        language: {
            search: '',
            searchPlaceholder: 'Search cards...',
        },
        columnDefs: [
            {
                targets: [3, 4],
                searchable: false,
            },
        ],
    });
}

function updateCardOwnership(collectorNumber, finish, owned) {
    const card = currentCards.find((item) => item.collector_number === collectorNumber);
    if (!card) {
        return;
    }

    if (finish === 0) {
        card.owned_nonfoil = owned;
    } else {
        card.owned_foil = owned;
    }
}

function purchaseValueForExport(card, finish) {
    const value = finish === 0 ? card.purchase_value_nonfoil : card.purchase_value_foil;
    if (value != null && !Number.isNaN(value)) {
        return value;
    }
    return 0;
}

function managerCardsToCsvRows(cards) {
    const rows = [];
    cards.forEach((card) => {
        if (card.has_nonfoil && card.owned_nonfoil) {
            rows.push([
                card.collector_number,
                purchaseValueForExport(card, 0),
                0,
            ]);
        }
        if (card.has_foil && card.owned_foil) {
            rows.push([
                card.collector_number,
                purchaseValueForExport(card, 1),
                1,
            ]);
        }
    });
    return rows;
}

function renderManagerSet(data, setCode, foilFilter) {
    currentSetCode = setCode;
    const cards = cloneCardsForSet(data, setCode);
    currentCards = applyManagerFoilFilter(cards, foilFilter);
    renderManagerTable(currentCards);
}

function initManagerCheckboxes() {
    const table = document.getElementById('managerTable');
    if (!table) {
        return;
    }

    table.addEventListener('change', function (event) {
        const checkbox = event.target.closest('.manager-own-checkbox');
        if (!checkbox) {
            return;
        }

        updateCardOwnership(
            checkbox.dataset.collectorNumber,
            Number(checkbox.dataset.finish),
            checkbox.checked,
        );
    });
}

function initManagerExport() {
    const exportButton = document.getElementById('export-manager-csv');
    if (!exportButton) {
        return;
    }

    exportButton.addEventListener('click', function () {
        if (!currentSetCode) {
            return;
        }
        downloadCsv(
            `${currentSetCode.toLowerCase()}.csv`,
            MANAGER_CSV_HEADERS,
            managerCardsToCsvRows(currentCards),
        );
    });
}

function initManagerReport() {
    const data = window.MANAGER_DATA;
    if (!data || !data.sets || !data.sets.length) {
        return;
    }

    let foilFilter = getStoredFoilFilter();

    initFoilFilterRadios(function () {
        foilFilter = getFoilFilterValue();
        localStorage.setItem(FOIL_FILTER_KEY, foilFilter);
        syncSetUrlParam(getCurrentSet());
        renderManagerSet(data, getCurrentSet(), foilFilter);
    });
    foilFilter = getFoilFilterValue();

    initSetNav(function (setCode) {
        renderManagerSet(data, setCode, foilFilter);
    }, { includeAll: false });
    initManagerCheckboxes();
    initManagerExport();
    initCardImageTooltip('#managerTable');
}

$(document).ready(initManagerReport);
