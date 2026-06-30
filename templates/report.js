$(document).ready(function() {
    function parseEuroNumber(value) {
        if (value == null) {
            return NaN;
        }

        const text = String(value)
            .replace(/<[^>]*>/g, '')
            .replace(/[€\s]/g, '')
            .replace(/\./g, '')
            .replace(/,/g, '.')
            .replace(/^[^\d+-]*/g, '');

        const match = text.match(/([-+]?\d+(?:\.\d+)?)/);
        return match ? parseFloat(match[1]) : NaN;
    }

    const cardsTable = $('#cardsTable').DataTable({
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

    const summaryTable = $('#summaryTable').DataTable({
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
    })

    let selectedArtStyle = null;
    const currentSet = $('body').attr('data-current-set') || 'All';

    function escapeRegex(value) {
        return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    function applyFilters() {
        const setSearch = (currentSet && currentSet !== 'All') ? '^' + escapeRegex(currentSet) + '$' : '';
        // apply set filter on the Set column (0)
        cardsTable.column(0).search(setSearch, true, false);

        // apply art style filter on hidden Art Style column (1)
        const artSearch = selectedArtStyle ? '^' + escapeRegex(selectedArtStyle) + '$' : '';
        cardsTable.column(1).search(artSearch, true, false);

        cardsTable.draw();
    }

    $('#summaryTable tbody').on('click', 'tr', function () {
        const artStyle = $(this).find('td').eq(1).text().trim();

        if (selectedArtStyle === artStyle) {
            selectedArtStyle = null;
            $('#summaryTable tbody tr').removeClass('selected-row');
        } else {
            selectedArtStyle = artStyle;
            $('#summaryTable tbody tr').removeClass('selected-row');
            $(this).addClass('selected-row');
        }

        applyFilters();
    });

    applyFilters();
    initCardImageTooltip();
    initDateNav();
});

function initDateNav() {
    const select = document.getElementById('report-date-select');
    if (!select) {
        return;
    }
    select.addEventListener('change', function () {
        if (this.value) {
            window.location.href = this.value;
        }
    });
}
