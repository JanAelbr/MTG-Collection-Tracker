let cardImageTooltipElement = null;
let cardImageTooltipBound = false;

function ensureCardImageTooltip() {
    if (!cardImageTooltipElement) {
        cardImageTooltipElement = document.createElement('div');
        cardImageTooltipElement.id = 'card-image-tooltip';
        cardImageTooltipElement.className = 'card-image-tooltip';
        cardImageTooltipElement.innerHTML = '<img alt="">';
        document.body.appendChild(cardImageTooltipElement);
    }
    return cardImageTooltipElement;
}

function positionCardImageTooltip(tooltipEl, event) {
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

    tooltipEl.style.left = `${left}px`;
    tooltipEl.style.top = `${top}px`;
}

function readCardPreviewImageUrl(previewEl) {
    return previewEl.getAttribute('data-image') || '';
}

function bindCardImageTooltip() {
    if (cardImageTooltipBound) {
        return;
    }
    cardImageTooltipBound = true;

    const tooltipEl = ensureCardImageTooltip();
    const imageEl = tooltipEl.querySelector('img');

    function moveTooltip(event) {
        positionCardImageTooltip(tooltipEl, event);
    }

    function hideTooltip() {
        tooltipEl.style.display = 'none';
        imageEl.onload = null;
        imageEl.removeAttribute('src');
    }

    function showTooltip(imageUrl, event) {
        imageEl.onload = function () {
            moveTooltip(event);
        };
        imageEl.src = imageUrl;
        tooltipEl.style.display = 'block';
        moveTooltip(event);
        if (imageEl.complete) {
            moveTooltip(event);
        }
    }

    document.addEventListener('mouseover', function (event) {
        const previewEl = event.target.closest('.card-preview');
        if (!previewEl) {
            return;
        }
        const imageUrl = readCardPreviewImageUrl(previewEl);
        if (!imageUrl) {
            return;
        }
        showTooltip(imageUrl, event);
    });

    document.addEventListener('mousemove', function (event) {
        if (tooltipEl.style.display !== 'block') {
            return;
        }
        if (!event.target.closest('.card-preview')) {
            return;
        }
        moveTooltip(event);
    });

    document.addEventListener('mouseout', function (event) {
        const previewEl = event.target.closest('.card-preview');
        if (!previewEl) {
            return;
        }
        const related = event.relatedTarget;
        if (related && previewEl.contains(related)) {
            return;
        }
        hideTooltip();
    });
}

// Initialize card image previews for any table rendered on the page.
function initCardImageTooltip(_tableSelector) {
    bindCardImageTooltip();
}

$(document).ready(function () {
    initCardImageTooltip();
});
