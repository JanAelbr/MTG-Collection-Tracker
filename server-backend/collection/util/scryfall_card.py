from util.card_metadata import encode_card_colors, normalize_card_colors, primary_card_type


# Extract a display image URL from a Scryfall card payload.
def card_image_uri(card: dict) -> str | None:
    image_uris = card.get("image_uris")
    if image_uris:
        return image_uris.get("normal") or image_uris.get("large")
    for face in card.get("card_faces", []):
        face_uris = face.get("image_uris")
        if face_uris:
            return face_uris.get("normal") or face_uris.get("large")
    return None


# Extract the Cardmarket purchase URL from a Scryfall card payload.
def cardmarket_url(card: dict) -> str | None:
    purchase_uris = card.get("purchase_uris") or {}
    return purchase_uris.get("cardmarket")


# Extract WUBRG colors from a Scryfall card payload.
def card_colors(card: dict) -> list[str]:
    colors = card.get("colors")
    if isinstance(colors, list) and colors:
        return normalize_card_colors(colors)
    for face in card.get("card_faces") or []:
        face_colors = face.get("colors")
        if isinstance(face_colors, list) and face_colors:
            return normalize_card_colors(face_colors)
    return []


# Serialize card colors for storage in the cards table.
def card_colors_json(card: dict) -> str:
    return encode_card_colors(card_colors(card))


# Extract the full type line from a Scryfall card payload.
def card_type_line(card: dict) -> str:
    type_line = str(card.get("type_line") or "").strip()
    if type_line:
        return type_line
    faces = card.get("card_faces") or []
    parts = [
        str(face.get("type_line") or "").strip()
        for face in faces
        if str(face.get("type_line") or "").strip()
    ]
    return " // ".join(parts)


# Return the primary deck-building type for one Scryfall card payload.
def card_primary_type(card: dict) -> str:
    return primary_card_type(card_type_line(card))
