from celery import shared_task
from .services.flights_api import fetch_flights
from .models import Flight, Airport

@shared_task
def update_flights_task(airport_code=None):
    data = fetch_flights(airport_code=airport_code)
    if not data or "data" not in data:
        return

    # Use the service function to handle parsing and saving
    # This avoids duplication and ensures model consistency
    from .services.flights_api import save_flights_to_db
    save_flights_to_db(data["data"])
