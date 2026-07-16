# SQL for cards the user owns (inner join on purchases).
from util.alchemy_cards import exclude_alchemy_art_style_sql, exclude_alchemy_sql

_EXCLUDE_ALCHEMY = (
    f"{exclude_alchemy_sql('c.collector_number')} "
    f"AND {exclude_alchemy_art_style_sql('c.art_style')}"
)

_CARD_DETAIL_SELECT = """
    c.color_identity,
    c.oracle_text,
    c.mana_cost,
    c.cmc,
    c.power,
    c.toughness,
    c.rarity,"""

OWNED_CARDS_QUERY = f"""
SELECT
    c.set_code,
    c.collector_number,
    c.name,
    c.art_style,
    c.image_uri,
    c.cardmarket_url,
    c.cardmarket_url_foil,
    c.colors,
    c.type_line,
    c.card_type,
{_CARD_DETAIL_SELECT}
    c.market_value,
    c.market_value_foil,
    c.market_value_etched,
    c.has_nonfoil,
    c.has_foil,
    c.has_etched,
    p.finish,
    p.purchase_value,
    CASE
        WHEN p.finish = 2 THEN c.market_value_etched
        WHEN p.finish = 1 THEN c.market_value_foil
        ELSE c.market_value
    END AS current_value,
    CASE
        WHEN p.finish = 2 AND c.market_value_etched IS NOT NULL
            THEN c.market_value_etched - p.purchase_value
        WHEN p.finish = 1 AND c.market_value_foil IS NOT NULL
            THEN c.market_value_foil - p.purchase_value
        WHEN p.finish = 0 AND c.market_value IS NOT NULL
            THEN c.market_value - p.purchase_value
        ELSE NULL
    END AS profit_loss
FROM cards c
JOIN purchases p
    ON p.set_code = c.set_code
    AND p.collector_number = c.collector_number
WHERE {_EXCLUDE_ALCHEMY}
ORDER BY c.set_code, CAST(c.collector_number AS INTEGER)
"""

# Owned cards for a single set.
OWNED_CARDS_FOR_SET_QUERY = f"""
SELECT
    c.set_code,
    c.collector_number,
    c.name,
    c.art_style,
    c.image_uri,
    c.cardmarket_url,
    c.cardmarket_url_foil,
    c.colors,
    c.type_line,
    c.card_type,
{_CARD_DETAIL_SELECT}
    c.market_value,
    c.market_value_foil,
    c.market_value_etched,
    c.has_nonfoil,
    c.has_foil,
    c.has_etched,
    p.finish,
    p.purchase_value,
    CASE
        WHEN p.finish = 2 THEN c.market_value_etched
        WHEN p.finish = 1 THEN c.market_value_foil
        ELSE c.market_value
    END AS current_value,
    CASE
        WHEN p.finish = 2 AND c.market_value_etched IS NOT NULL
            THEN c.market_value_etched - p.purchase_value
        WHEN p.finish = 1 AND c.market_value_foil IS NOT NULL
            THEN c.market_value_foil - p.purchase_value
        WHEN p.finish = 0 AND c.market_value IS NOT NULL
            THEN c.market_value - p.purchase_value
        ELSE NULL
    END AS profit_loss
FROM cards c
JOIN purchases p
    ON p.set_code = c.set_code
    AND p.collector_number = c.collector_number
WHERE c.set_code = ?
  AND {_EXCLUDE_ALCHEMY}
ORDER BY CAST(c.collector_number AS INTEGER)
"""

# SQL for every card in the database, with optional purchase data.
ALL_CARDS_QUERY = f"""
SELECT
    c.set_code,
    c.collector_number,
    c.name,
    c.art_style,
    c.image_uri,
    c.cardmarket_url,
    c.cardmarket_url_foil,
    c.colors,
    c.type_line,
    c.card_type,
{_CARD_DETAIL_SELECT}
    c.market_value,
    c.market_value_foil,
    c.market_value_etched,
    c.has_nonfoil,
    c.has_foil,
    c.has_etched,
    p.finish,
    p.purchase_value,
    CASE
        WHEN p.finish = 2 THEN c.market_value_etched
        WHEN p.finish = 1 THEN c.market_value_foil
        ELSE c.market_value
    END AS current_value,
    CASE
        WHEN p.purchase_value IS NOT NULL
            AND p.finish = 2
            AND c.market_value_etched IS NOT NULL
            THEN c.market_value_etched - p.purchase_value
        WHEN p.purchase_value IS NOT NULL
            AND p.finish = 1
            AND c.market_value_foil IS NOT NULL
            THEN c.market_value_foil - p.purchase_value
        WHEN p.purchase_value IS NOT NULL
            AND p.finish = 0
            AND c.market_value IS NOT NULL
            THEN c.market_value - p.purchase_value
        ELSE NULL
    END AS profit_loss
FROM cards c
LEFT JOIN purchases p
    ON p.set_code = c.set_code
    AND p.collector_number = c.collector_number
WHERE {_EXCLUDE_ALCHEMY}
ORDER BY c.set_code, CAST(c.collector_number AS INTEGER)
"""

# All cards for a single set, with optional purchase data.
SET_CARDS_QUERY = f"""
SELECT
    c.set_code,
    c.collector_number,
    c.name,
    c.art_style,
    c.image_uri,
    c.cardmarket_url,
    c.cardmarket_url_foil,
    c.colors,
    c.type_line,
    c.card_type,
{_CARD_DETAIL_SELECT}
    c.market_value,
    c.market_value_foil,
    c.market_value_etched,
    c.has_nonfoil,
    c.has_foil,
    c.has_etched,
    p.finish,
    p.purchase_value,
    CASE
        WHEN p.finish = 2 THEN c.market_value_etched
        WHEN p.finish = 1 THEN c.market_value_foil
        ELSE c.market_value
    END AS current_value,
    CASE
        WHEN p.purchase_value IS NOT NULL
            AND p.finish = 2
            AND c.market_value_etched IS NOT NULL
            THEN c.market_value_etched - p.purchase_value
        WHEN p.purchase_value IS NOT NULL
            AND p.finish = 1
            AND c.market_value_foil IS NOT NULL
            THEN c.market_value_foil - p.purchase_value
        WHEN p.purchase_value IS NOT NULL
            AND p.finish = 0
            AND c.market_value IS NOT NULL
            THEN c.market_value - p.purchase_value
        ELSE NULL
    END AS profit_loss
FROM cards c
LEFT JOIN purchases p
    ON p.set_code = c.set_code
    AND p.collector_number = c.collector_number
WHERE c.set_code = ?
  AND {_EXCLUDE_ALCHEMY}
ORDER BY CAST(c.collector_number AS INTEGER)
"""

# Purchases that are not linked to a catalog row yet.
ORPHAN_PURCHASES_QUERY = f"""
SELECT
    p.set_code,
    p.collector_number,
    NULL AS name,
    '' AS art_style,
    '' AS image_uri,
    '' AS cardmarket_url,
    '' AS cardmarket_url_foil,
    NULL AS market_value,
    NULL AS market_value_foil,
    NULL AS market_value_etched,
    NULL AS has_nonfoil,
    NULL AS has_foil,
    NULL AS has_etched,
    p.finish,
    p.purchase_value,
    NULL AS current_value,
    NULL AS profit_loss
FROM purchases p
LEFT JOIN cards c
    ON c.set_code = p.set_code
    AND c.collector_number = p.collector_number
WHERE c.set_code IS NULL
  AND {exclude_alchemy_sql("p.collector_number")}
ORDER BY p.set_code, CAST(p.collector_number AS INTEGER), p.finish
"""

# Orphan purchases for a single set (no matching catalog row).
SET_ORPHAN_PURCHASES_QUERY = f"""
SELECT
    p.set_code,
    p.collector_number,
    NULL AS name,
    '' AS art_style,
    '' AS image_uri,
    '' AS cardmarket_url,
    '' AS cardmarket_url_foil,
    NULL AS market_value,
    NULL AS market_value_foil,
    NULL AS market_value_etched,
    NULL AS has_nonfoil,
    NULL AS has_foil,
    NULL AS has_etched,
    p.finish,
    p.purchase_value,
    NULL AS current_value,
    NULL AS profit_loss
FROM purchases p
LEFT JOIN cards c
    ON c.set_code = p.set_code
    AND c.collector_number = p.collector_number
WHERE c.set_code IS NULL
  AND p.set_code = ?
  AND {exclude_alchemy_sql("p.collector_number")}
ORDER BY CAST(p.collector_number AS INTEGER), p.finish
"""

# SQL summary grouped by set and art style; lists every art style with owned totals.
OWNED_SUMMARY_QUERY = f"""
SELECT
    c.set_code,
    c.art_style,
    COUNT(p.purchase_id) AS cards,
    ROUND(COALESCE(SUM(p.purchase_value), 0), 2) AS invested,
    ROUND(
        COALESCE(
            SUM(
                CASE
                    WHEN p.purchase_id IS NOT NULL AND p.finish = 2
                        THEN c.market_value_etched
                    WHEN p.purchase_id IS NOT NULL AND p.finish = 1
                        THEN c.market_value_foil
                    WHEN p.purchase_id IS NOT NULL AND p.finish = 0
                        THEN c.market_value
                    ELSE NULL
                END
            ),
            0
        ),
        2
    ) AS current_value,
    ROUND(
        COALESCE(
            SUM(
                CASE
                    WHEN p.purchase_id IS NOT NULL
                        AND p.finish = 2
                        AND c.market_value_etched IS NOT NULL
                        THEN c.market_value_etched - p.purchase_value
                    WHEN p.purchase_id IS NOT NULL
                        AND p.finish = 1
                        AND c.market_value_foil IS NOT NULL
                        THEN c.market_value_foil - p.purchase_value
                    WHEN p.purchase_id IS NOT NULL
                        AND p.finish = 0
                        AND c.market_value IS NOT NULL
                        THEN c.market_value - p.purchase_value
                    ELSE 0
                END
            ),
            0
        ),
        2
    ) AS profit_loss
FROM cards c
LEFT JOIN purchases p
    ON p.set_code = c.set_code
    AND p.collector_number = c.collector_number
WHERE {_EXCLUDE_ALCHEMY}
GROUP BY c.set_code, c.art_style
ORDER BY c.set_code, c.art_style
"""

# SQL summary grouped by set and art style for all cards in the database.
ALL_SUMMARY_QUERY = f"""
SELECT
    c.set_code,
    c.art_style,
    COUNT(*) AS cards,
    ROUND(SUM(p.purchase_value), 2) AS invested,
    ROUND(
        SUM(
            CASE
                WHEN p.finish = 2 THEN c.market_value_etched
                WHEN p.finish = 1 THEN c.market_value_foil
                ELSE c.market_value
            END
        ),
        2
    ) AS current_value,
    ROUND(
        SUM(
            CASE
                WHEN p.purchase_value IS NOT NULL
                    AND p.finish = 2
                    AND c.market_value_etched IS NOT NULL
                    THEN c.market_value_etched - p.purchase_value
                WHEN p.purchase_value IS NOT NULL
                    AND p.finish = 1
                    AND c.market_value_foil IS NOT NULL
                    THEN c.market_value_foil - p.purchase_value
                WHEN p.purchase_value IS NOT NULL
                    AND p.finish = 0
                    AND c.market_value IS NOT NULL
                    THEN c.market_value - p.purchase_value
                ELSE 0
            END
        ),
        2
    ) AS profit_loss
FROM cards c
LEFT JOIN purchases p
    ON p.set_code = c.set_code
    AND p.collector_number = c.collector_number
WHERE {_EXCLUDE_ALCHEMY}
GROUP BY c.set_code, c.art_style
ORDER BY c.set_code, c.art_style
"""


# Return the cards query for owned-only or all-cards mode.
def cards_query(owned_only: bool) -> str:
    return OWNED_CARDS_QUERY if owned_only else ALL_CARDS_QUERY


# Return the summary query for owned-only or all-cards mode.
def summary_query(owned_only: bool) -> str:
    return OWNED_SUMMARY_QUERY if owned_only else ALL_SUMMARY_QUERY
