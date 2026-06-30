from html import escape

from lib.config import (
    OUTPUT_FILE_DECK_STATS,
    OUTPUT_FILE_DECKS,
    OUTPUT_FILE_FALLERS,
    OUTPUT_FILE_MANAGER,
    OUTPUT_FILE_RISERS,
    OUTPUT_FILE_STATS,
    OUTPUT_FILE_STORAGE,
    OUTPUT_FILE_TOP,
)
from report.set_selector_data import SetSelectorEntry, get_set_selector_entries
RANKED_REPORTS = (
    ("top", "Top cards", OUTPUT_FILE_TOP.name),
    ("risers", "Top risers", OUTPUT_FILE_RISERS.name),
    ("fallers", "Top fallers", OUTPUT_FILE_FALLERS.name),
)

MANAGER_REPORT = ("manager", "Set Manager", OUTPUT_FILE_MANAGER.name)
STORAGE_REPORT = ("storage", "Storage", OUTPUT_FILE_STORAGE.name)
STATS_REPORT = ("stats", "Statistics", OUTPUT_FILE_STATS.name)
DECK_STATS_REPORT = ("deck_stats", "Deck statistics", OUTPUT_FILE_DECK_STATS.name)
DECKS_REPORT = ("decks", "Decks", OUTPUT_FILE_DECKS.name)

DECK_MANAGER_REPORTS = (MANAGER_REPORT, STORAGE_REPORT, DECKS_REPORT)

REPORT_TYPES = RANKED_REPORTS + DECK_MANAGER_REPORTS + (STATS_REPORT, DECK_STATS_REPORT)
COLLECTION_MANAGER_SECTION = "Collection manager"


# Build one vertical list of side navigation links.
def build_side_nav_links(links: list[tuple[str, str, bool]]) -> str:
    items = []
    for href, label, is_active in links:
        css_class = "side-nav-link active" if is_active else "side-nav-link"
        items.append(f'<a href="{href}" class="{css_class}">{label}</a>')
    return "\n".join(items)


# Wrap a group of side navigation links with a section title.
def build_side_nav_section(title: str, links_html: str) -> str:
    return (
        f'<div class="side-nav-section">'
        f'<div class="side-nav-title">{title}</div>'
        f'<nav class="side-nav-links">{links_html}</nav>'
        f"</div>"
    )


# Build link tuples for one navigation group.
def build_nav_link_specs(
    specs: tuple[tuple[str, str, str], ...],
    active: str,
) -> list[tuple[str, str, bool]]:
    return [(filename, label, active == report_id) for report_id, label, filename in specs]


# Build the full sidebar with separate sections for reports, manager, and stats.
def build_full_side_nav_html(active: str) -> str:
    sections = [
        build_side_nav_section(
            "Reports",
            build_side_nav_links(build_nav_link_specs(RANKED_REPORTS, active)),
        ),
        build_side_nav_section(
            COLLECTION_MANAGER_SECTION,
            build_side_nav_links(build_nav_link_specs(DECK_MANAGER_REPORTS, active)),
        ),
        build_side_nav_section(
            "Statistics",
            build_side_nav_links(
                build_nav_link_specs((STATS_REPORT, DECK_STATS_REPORT), active)
            ),
        ),
    ]
    return "\n".join(sections)


# Build HTML options for one set selector entry.
def _set_selector_option_html(entry: SetSelectorEntry) -> str:
    if entry.separator:
        return (
            f'<option disabled class="report-set-separator">{escape(entry.label)}</option>'
        )
    selected_attrs = ' disabled' if entry.disabled else ''
    return (
        f'<option value="{escape(entry.value, quote=True)}"{selected_attrs}>'
        f'{escape(entry.label)}</option>'
    )


# Build the set selector shown at the top of report pages.
def build_set_selector_html(include_all: bool = True) -> str:
    entries = get_set_selector_entries(include_all=include_all)
    options = "".join(_set_selector_option_html(entry) for entry in entries)
    return (
        '<label class="report-set-label" for="report-set-select">Set</label>'
        f'<select id="report-set-select" class="report-set-select">{options}</select>'
    )


# Build foil finish filter as styled radio buttons for report pages.
def build_foil_filter_html() -> str:
    options = (
        ("all", "All finishes", "report-foil-all"),
        ("nonfoil", "Non-foil", "report-foil-nonfoil"),
        ("foil", "Foil", "report-foil-foil"),
    )
    buttons = []
    for value, label, input_id in options:
        buttons.append(
            f'<input type="radio" name="report-foil-filter" id="{input_id}" '
            f'value="{value}" class="report-foil-input">'
            f'<label for="{input_id}" class="filter-button">{label}</label>'
        )
    return (
        '<div class="report-foil-filter">'
        f'<div class="button-group report-foil-group">{"".join(buttons)}</div>'
        "</div>"
    )


# Build ownership filter as styled radio buttons for ranked reports.
def build_owned_filter_html() -> str:
    options = (
        ("owned", "Owned", "report-owned-owned"),
        ("all", "All cards", "report-owned-all"),
        ("unowned", "Not owned", "report-owned-unowned"),
    )
    buttons = []
    for value, label, input_id in options:
        buttons.append(
            f'<input type="radio" name="report-owned-filter" id="{input_id}" '
            f'value="{value}" class="report-owned-input">'
            f'<label for="{input_id}" class="filter-button">{label}</label>'
        )
    return (
        '<div class="report-owned-filter">'
        f'<div class="button-group report-owned-group">{"".join(buttons)}</div>'
        '</div>'
    )


# Build cross-link toolbar for the deck browser page.
def build_deck_browse_toolbar_html() -> str:
    return (
        f'<a id="deck-stats-link" href="{OUTPUT_FILE_DECK_STATS.name}" '
        f'class="deck-cross-link">Deck statistics</a>'
    )


# Build deck selector for deck report pages.
def build_deck_toolbar_html(
    decks: list[dict],
    include_all: bool = True,
    cross_link: str | None = None,
) -> str:
    options = []
    if include_all:
        options.append('<option value="All">All decks</option>')
    for deck in decks:
        label = deck.get("label") or deck["name"]
        options.append(
            f'<option value="{deck["id"]}">{escape(label)}</option>'
        )
    link_html = ""
    if cross_link == "stats":
        link_html = (
            f'<a id="deck-stats-link" href="{OUTPUT_FILE_DECK_STATS.name}" '
            f'class="deck-cross-link">Deck statistics</a>'
        )
    elif cross_link == "browse":
        link_html = (
            f'<a id="deck-browse-link" href="{OUTPUT_FILE_DECKS.name}" '
            f'class="deck-cross-link">View deck</a>'
        )
    return (
        '<label class="report-set-label" for="report-deck-select">Deck</label>'
        f'<select id="report-deck-select" class="report-set-select report-deck-select">'
        f'{"".join(options)}</select>'
        f"{link_html}"
    )


# Build filter controls for stats report pages.
def build_stats_toolbar_html() -> str:
    return (
        f'{build_set_selector_html(include_all=True)}'
        f"{build_foil_filter_html()}"
        '<label class="report-set-label" for="stats-art-filter">Art style</label>'
        '<select id="stats-art-filter" class="report-set-select report-art-select">'
        '<option value="">All art styles</option>'
        '</select>'
    )


# Build the comparison-period controls for ranked report toolbars (filled by JS).
def build_compare_toolbar_html() -> str:
    return (
        '<div class="report-compare-filter">'
        '<span class="report-set-label">Compare with</span>'
        '<nav id="price-compare-nav" class="report-compare-nav"></nav>'
        "</div>"
    )


# Build filter controls for top, risers, and fallers reports.
def build_ranked_report_toolbar_html() -> str:
    filters = (
        f'{build_set_selector_html(include_all=True)}'
        f'{build_owned_filter_html()}'
        f"{build_foil_filter_html()}"
        '<label class="report-set-label" for="report-art-filter">Art style</label>'
        '<select id="report-art-filter" class="report-set-select report-art-select">'
        '<option value="">All art styles</option>'
        '</select>'
    )
    return (
        f'<div class="report-toolbar-filters">{filters}</div>'
        f"{build_compare_toolbar_html()}"
    )


# Build the comparison-period nav for sidebar use on legacy collection reports.
def build_compare_nav(compare_dates: list[str], current_compare_date: str | None = None) -> str:
    if not compare_dates:
        return ""

    return (
        '<div class="side-nav-section side-nav-date">'
        '<div class="side-nav-title">Compare with</div>'
        '<nav id="price-compare-nav" class="side-nav-links side-nav-compare"></nav>'
        "</div>"
    )


# Build side navigation for top reports.
def build_top_side_nav_html() -> str:
    return build_full_side_nav_html("top")


# Build side navigation for collection reports with price comparison.
def build_collection_side_nav_html(
    active: str,
    compare_dates: list[str],
    compare_date: str | None,
) -> str:
    sections = [
        build_full_side_nav_html(active),
        build_compare_nav(compare_dates, compare_date),
    ]
    return "\n".join(section for section in sections if section)


# Build side navigation for risers reports.
def build_risers_side_nav_html() -> str:
    return build_full_side_nav_html("risers")


# Build side navigation for fallers reports.
def build_fallers_side_nav_html() -> str:
    return build_full_side_nav_html("fallers")


# Build side navigation for the set manager.
def build_manager_side_nav_html() -> str:
    return build_full_side_nav_html("manager")


# Build side navigation for the storage page.
def build_storage_side_nav_html() -> str:
    return build_full_side_nav_html("storage")


# Build the complete side navigation for one stats report page.
def build_side_nav_html() -> str:
    return build_full_side_nav_html("stats")


# Build the complete side navigation for deck statistics pages.
def build_deck_stats_side_nav_html() -> str:
    return build_full_side_nav_html("deck_stats")


# Build the complete side navigation for deck browser pages.
def build_decks_side_nav_html() -> str:
    return build_full_side_nav_html("decks")
