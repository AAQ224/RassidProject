import requests
from django.conf import settings
from flights.models import Airport, Flight

API_URL = "https://api.aviationstack.com/v1/flights"
API_KEY = settings.AVIATIONSTACK_API_KEY


def safe_get(value, default=None):
    return value if value is not None else default


def fetch_flights(airport_code=None):
    params = {
        "access_key": API_KEY,
        "limit": 100
    }
    if airport_code:
        params["dep_iata"] = airport_code

    print("USING KEY:", API_KEY)
    print("SENDING REQUEST TO:", API_URL)

    try:
        response = requests.get(API_URL, params=params)
        print("STATUS:", response.status_code)
        print("RAW RESPONSE:", response.text)

        if response.status_code != 200:
            raise Exception(f"API Error {response.status_code}: {response.text}")

        return response.json()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Network Error: {str(e)}")

    return response.json()







def get_airport_or_create(iata):
    if not iata:
        return None

    airport, _ = Airport.objects.get_or_create(
        code=iata,
        defaults={"name": iata}
    )
    return airport

def save_flights_to_db(flights_data):
    for flight in flights_data:
        dep = flight.get("departure", {})
        arr = flight.get("arrival", {})
        airline = flight.get("airline", {})
        f_info = flight.get("flight", {})

        # Helper to get better city name
        def get_city_or_name(data):
            # Prefer explicit city if available (rare in this API subset without paid)
            # Fallback to Airport Name. Timezone is too broad (e.g. Asia/Riyadh covers DMM, JED)
            return data.get("airport") or data.get("iata") or "Unknown"

        origin, _ = Airport.objects.update_or_create(
            code=dep.get("iata"),
            defaults={
                "name": dep.get("airport") or dep.get("iata"),
                "city": get_city_or_name(dep),
                "country": dep.get("country") or "Unknown",
            }
        )

        destination, _ = Airport.objects.update_or_create(
            code=arr.get("iata"),
            defaults={
                "name": arr.get("airport") or arr.get("iata"),
                "city": get_city_or_name(arr),
                "country": arr.get("country") or "Unknown",
            }
        )

        parsed = {
            "status": flight.get("flight_status"),
            "scheduledDeparture": dep.get("scheduled"),
            "scheduledArrival": arr.get("scheduled"),
            "airlineCode": airline.get("iata"),
            "origin": origin,
            "destination": destination,
        }

        Flight.objects.update_or_create(
            flightNumber=f_info.get("iata"),
            defaults=parsed
        )
    
