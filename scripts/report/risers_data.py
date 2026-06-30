from report.ranked_cards_data import load_ranked_cards_data, load_ranked_client_payload


# Load card and snapshot data embedded in risers report pages.
def load_risers_client_payload() -> dict:
    return load_ranked_client_payload(load_ranked_cards_data())
