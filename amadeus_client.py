import requests
from utils.logger import get_logger
from utils.config import Config

logger = get_logger(__name__)


class AmadeusClient:
    """
    Production-ready Amadeus API client.
    Handles:
    - OAuth token generation
    - Automatic token refresh
    - Flight Offers Search
    """

    def __init__(self):
        self.api_key = Config.AMADEUS_API_KEY
        self.api_secret = Config.AMADEUS_API_SECRET

        # TEST environment endpoints (Self-Service)
        self.token_url = "https://test.api.amadeus.com/v1/security/oauth2/token"
        self.search_url = "https://test.api.amadeus.com/v2/shopping/flight-offers"

        self.access_token = None

    # ---------------------------------------------------------
    # AUTHENTICATION
    # ---------------------------------------------------------
    def authenticate(self):
        """
        Generates a fresh OAuth access token.
        """
        logger.info("Authenticating with Amadeus...")

        data = {
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.api_secret
        }

        response = requests.post(self.token_url, data=data)

        if response.status_code != 200:
            logger.error(f"Amadeus OAuth failed: {response.text}")
            raise Exception("Failed to authenticate with Amadeus")

        self.access_token = response.json()["access_token"]
        logger.info("Amadeus authentication successful")

    # ---------------------------------------------------------
    # FLIGHT SEARCH
    # ---------------------------------------------------------
    def search_flights(self, origin, destination, date, adults=2, children=2):
        """
        Calls Amadeus Flight Offers Search API.
        Automatically refreshes token if expired.
        """

        # Ensure we have a token
        if not self.access_token:
            self.authenticate()

        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }

        params = {
            "originLocationCode": origin,
            "destinationLocationCode": destination,
            "departureDate": date,
            "adults": adults,
            "children": children,
            "currencyCode": "CAD",
            "max": 50
        }

        logger.info(f"Searching flights for {origin} -> {destination} on {date}")


        response = requests.get(self.search_url, headers=headers, params=params)

        # If token expired, refresh and retry once
        if response.status_code == 401:
            logger.warning("Token expired — refreshing...")
            self.authenticate()

            headers["Authorization"] = f"Bearer {self.access_token}"
            response = requests.get(self.search_url, headers=headers, params=params)

        if response.status_code != 200:
            logger.error(f"Amadeus search failed: {response.text}")
            return None

        return response.json()
