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
    
    # --- Hardcoded Passenger Logic (User Request) ---
    create_and_link_test_passengers(airport_code)

def create_and_link_test_passengers(airport_code=None):
    from passengers.models import Passenger, PassengerFlight
    import random
    import string

    # 1. Define the 3 requested passengers
    test_passengers = [
        {"fullName": "Ziyad Alzahrani", "phone": "+966535778335", "email": "zsyz6279@gmail.com", "preferredLanguage": "ar"},
        {"fullName": "Rakan Alyami", "phone": "+966509835558", "email": "srakan595@gmail.com", "preferredLanguage": "ar"},
        {"fullName": "Abdulrahman Alqahtani", "phone": "+966505510181", "email": "aaq_224@hotmail.com", "preferredLanguage": "ar"},
    ]

    saved_passengers = []
    for p_data in test_passengers:
        passenger, created = Passenger.objects.get_or_create(
            email=p_data["email"],
            defaults={
                "fullName": p_data["fullName"],
                "phone": p_data["phone"],
                "preferredLanguage": p_data["preferredLanguage"]
            }
        )
        saved_passengers.append(passenger)
        if created:
            print(f"Created passenger: {passenger.fullName}")

    # 2. Get Flights to link to
    if airport_code:
        flights = Flight.objects.filter(origin__code=airport_code, status__iexact="scheduled")
    else:
        flights = Flight.objects.filter(status__iexact="scheduled")

    # 3. Link Passengers
    for flight in flights:
        for passenger in saved_passengers:
            # Check if already linked
            if not PassengerFlight.objects.filter(passenger=passenger, flight=flight).exists():
                # Generate dummy seat and reference
                row = random.randint(1, 30)
                col = random.choice(['A', 'B', 'C', 'D', 'E', 'F'])
                seat = f"{row}{col}"
                ref = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                
                PassengerFlight.objects.create(
                    passenger=passenger,
                    flight=flight,
                    seatNumber=seat,
                    bookingRef=ref,
                    ticketStatus="Checked-in"
                )
                print(f"Linked {passenger.fullName} to {flight.flightNumber}")
