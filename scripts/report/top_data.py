import pandas as pd

from report.ranked_cards_data import load_ranked_client_payload


# Build the client payload for top report pages.
def load_top_client_payload(cards_df: pd.DataFrame) -> dict:
    return load_ranked_client_payload(cards_df)
