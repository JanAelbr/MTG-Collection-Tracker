import html

import pandas as pd

from util.formatting import euro


# Return True when a value is None or pandas NA.
def is_missing(value) -> bool:
    return value is None or pd.isna(value)


# Format a numeric value as euros, or "Unknown" when missing.
def format_monetary(value) -> str:
    if is_missing(value):
        return "Unknown"
    return euro(value)


# Format invested amounts, treating missing values as zero euros.
def format_invested(value) -> str:
    if is_missing(value):
        return euro(0)
    return euro(value)


# Format purchase values for owned cards; unowned cards get an empty cell.
def format_purchase_value(value) -> str:
    if is_missing(value):
        return ""
    return euro(value)


# Format profit/loss as a colored HTML table cell.
def format_profit_cell(value, unknown_label: str = "") -> str:
    if is_missing(value):
        return unknown_label
    if value >= 0:
        return f'<span class="profit-cell">🟢 {euro(value)}</span>'
    return f'<span class="loss-cell">🔴 {euro(value)}</span>'


# Return True when a purchase price is recorded for gain/loss display.
def has_purchase_price(value) -> bool:
    if is_missing(value):
        return False
    return float(value) != 0


# Format gain/loss only when a purchase price is recorded.
def format_gain_loss_cell(row, unknown_label: str = "") -> str:
    if not has_purchase_price(row.get("purchase_value")):
        return unknown_label
    if is_missing(row.get("profit_loss")):
        return unknown_label
    return format_profit_cell(row.get("profit_loss"), unknown_label=unknown_label)


# Format a price change versus the previous snapshot.
def format_price_change_cell(value) -> str:
    if is_missing(value):
        return "—"
    if value > 0:
        return f'<span class="profit-cell">🟢 +{euro(value)}</span>'
    if value < 0:
        return f'<span class="loss-cell">🔴 {euro(value)}</span>'
    return "No changes"


# Build column labels for price history columns, including the snapshot date when known.
def previous_value_column_label(previous_date) -> str:
    if is_missing(previous_date):
        return "Previous Value"
    return f"Previous ({previous_date})"


# Format the total profit/loss headline shown above the report tables.
def format_total_profit(value) -> str:
    if is_missing(value):
        return "Unknown"
    icon = "🟢" if value >= 0 else "🔴"
    return f"{icon} {euro(value)}"


# Wrap card text in a hover preview when an image URL is available.
def wrap_card_preview(label: str, image_uri) -> str:
    if is_missing(image_uri) or not str(image_uri).strip():
        return label
    safe_image = html.escape(str(image_uri), quote=True)
    return f'<span class="card-preview" data-image="{safe_image}">{label}</span>'


# Build the card label shown in the cards table, including unowned badges.
def card_label(row, owned_only: bool) -> str:
    label = f"{str(row['collector_number']).zfill(3)} - {row['name']}"
    if not owned_only and is_missing(row["purchase_value"]):
        label += ' <span class="unowned-badge">Not owned</span>'
    return wrap_card_preview(label, row.get("image_uri"))


# Prefix foil card names with a sparkle emoji.
def display_name(row) -> str:
    finish = row.get("finish", row.get("foil", 0))
    if finish == 1:
        return f"✨ {row['name']}"
    return row["name"]


# Format current value as plain text or a Cardmarket link.
def format_current_value_cell(row) -> str:
    text = format_monetary(row["current_value"])
    url = row.get("cardmarket_url")
    if is_missing(url) or not str(url).strip():
        return text
    safe_url = html.escape(str(url), quote=True)
    return (
        f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer" '
        f'class="price-link">{text}</a>'
    )


# Build the display-ready cards DataFrame for the HTML report.
def build_cards_display_df(cards_df: pd.DataFrame, owned_only: bool) -> pd.DataFrame:
    display_df = cards_df.copy()
    display_df["name"] = display_df.apply(display_name, axis=1)
    display_df["Card"] = display_df.apply(lambda row: card_label(row, owned_only), axis=1)
    drop_cols = ["collector_number", "name", "image_uri", "cardmarket_url"]
    if "finish" in display_df.columns:
        drop_cols.append("finish")
    elif "foil" in display_df.columns:
        drop_cols.append("foil")
    display_df = display_df.drop(columns=drop_cols)
    display_df = display_df.rename(columns={
        "set_code": "Set",
        "art_style": "Art Style",
        "purchase_value": "Purchase Value",
        "current_value": "Current Value",
        "profit_loss": "Profit / Loss",
    })
    display_df = display_df[[
        "Set", "Art Style", "Card",
        "Purchase Value", "Current Value", "Profit / Loss",
    ]]
    display_df["Purchase Value"] = cards_df["purchase_value"].apply(format_purchase_value)
    display_df["Current Value"] = cards_df.apply(format_current_value_cell, axis=1)
    display_df["Profit / Loss"] = cards_df.apply(
        lambda row: format_gain_loss_cell(row),
        axis=1,
    )
    return display_df


# Build the display-ready art-style summary DataFrame for the HTML report.
def build_summary_display_df(summary_df: pd.DataFrame) -> pd.DataFrame:
    summary_display = summary_df.copy()
    summary_display = summary_display.rename(columns={
        "set_code": "Set",
        "art_style": "Art Style",
        "cards": "Cards",
        "invested": "Invested",
        "current_value": "Current Value",
        "profit_loss": "Profit / Loss",
    })
    summary_display["Invested"] = summary_display["Invested"].apply(format_invested)
    summary_display["Current Value"] = summary_display["Current Value"].apply(format_monetary)
    summary_display["Profit / Loss"] = summary_df["profit_loss"].apply(
        lambda value: format_profit_cell(value, unknown_label="Unknown")
    )
    return summary_display


# Build the card label used in the top-cards report table.
def top_card_label(row) -> str:
    name = row["name"]
    if row.get("finish", row.get("foil", 0)) == 1:
        name = f"✨ {name}"
    label = f"{str(row['collector_number']).zfill(3)} - {name}"
    return wrap_card_preview(label, row.get("image_uri"))


# Build shared display columns for ranked card reports.
def build_ranked_cards_display_df(
    cards_df: pd.DataFrame,
    *,
    variant: str = "top",
) -> pd.DataFrame:
    ranked = cards_df.copy()
    ranked["Rank"] = range(1, len(ranked) + 1)
    ranked["Card"] = ranked.apply(top_card_label, axis=1)
    ranked["Art"] = ranked["art_style"]
    ranked["Current Value"] = ranked.apply(format_current_value_cell, axis=1)
    ranked["Previous Value"] = ranked["previous_value"].apply(format_monetary)
    ranked["Change"] = ranked["price_change"].apply(format_price_change_cell)
    ranked["Gain / Loss"] = ranked.apply(
        lambda row: format_gain_loss_cell(row),
        axis=1,
    )

    previous_label = previous_value_column_label(
        ranked["previous_date"].iloc[0] if "previous_date" in ranked.columns and len(ranked) else None,
    )
    ranked = ranked.rename(columns={"Previous Value": previous_label})

    if variant == "risers":
        return ranked[[
            "Rank", "Card", "Art", previous_label, "Current Value", "Change", "Gain / Loss",
        ]]
    return ranked[[
        "Rank", "Card", "Art", "Current Value", previous_label, "Change", "Gain / Loss",
    ]]


# Build the display-ready DataFrame for the top-cards report.
def build_top_cards_display_df(cards_df: pd.DataFrame) -> pd.DataFrame:
    return build_ranked_cards_display_df(cards_df, variant="top")


# Build the display-ready DataFrame for the top-risers report.
def build_risers_display_df(cards_df: pd.DataFrame) -> pd.DataFrame:
    return build_ranked_cards_display_df(cards_df, variant="risers")


TOP_CARD_IMAGE_LIMIT = 5


# Build one gallery figure for a ranked card with an image URL.
def top_card_image_figure(rank: int, row) -> str:
    image_uri = row.get("image_uri")
    if is_missing(image_uri) or not str(image_uri).strip():
        return ""
    name = row["name"]
    if row.get("finish", row.get("foil", 0)) == 1:
        name = f"✨ {name}"
    safe_url = html.escape(str(image_uri), quote=True)
    safe_name = html.escape(name)
    safe_value = html.escape(format_monetary(row["current_value"]))
    return (
        f'<figure class="top-card-image">'
        f'<img src="{safe_url}" alt="{safe_name}" loading="lazy">'
        f'<figcaption>'
        f'<span class="top-card-rank">#{rank}</span>'
        f'<span class="top-card-name">{safe_name}</span>'
        f'<span class="top-card-value">{safe_value}</span>'
        f"</figcaption></figure>"
    )


# Build the top card image gallery shown above the top-cards table.
def build_top_card_images_html(cards_df: pd.DataFrame, limit: int = TOP_CARD_IMAGE_LIMIT) -> str:
    figures = []
    for rank, (_, row) in enumerate(cards_df.head(limit).iterrows(), start=1):
        figure = top_card_image_figure(rank, row)
        if figure:
            figures.append(figure)
    if not figures:
        return ""
    return f'<div class="top-card-images">{"".join(figures)}</div>'


# Return the owned card row with the highest current market value.
def best_valued_card(cards_df: pd.DataFrame):
    valued = cards_df[cards_df["current_value"].notna()]
    if valued.empty:
        return None
    return valued.loc[valued["current_value"].idxmax()]


# Build the featured card display for the stats report.
def build_best_card_html(row) -> str:
    if row is None:
        return '<div class="card-value">Unknown</div>'

    name = row["name"]
    if row.get("finish", row.get("foil", 0)) == 1:
        name = f"✨ {name}"
    value = format_monetary(row["current_value"])
    image_uri = row.get("image_uri")
    if is_missing(image_uri) or not str(image_uri).strip():
        safe_name = html.escape(name)
        safe_value = html.escape(value)
        return f'<div class="card-value card-value-small">{safe_name} ({safe_value})</div>'

    safe_url = html.escape(str(image_uri), quote=True)
    safe_name = html.escape(name)
    safe_value = html.escape(value)
    return (
        f'<figure class="best-card-figure">'
        f'<img src="{safe_url}" alt="{safe_name}" loading="lazy">'
        f"<figcaption>"
        f'<span class="best-card-name">{safe_name}</span>'
        f'<span class="best-card-value">{safe_value}</span>'
        f"</figcaption></figure>"
    )
