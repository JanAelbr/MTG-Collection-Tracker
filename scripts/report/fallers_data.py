from report.risers_data import load_risers_client_payload

# Fallers use the same owned-card payload as risers; filtering happens client-side.
load_fallers_client_payload = load_risers_client_payload
