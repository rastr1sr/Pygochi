import json
import time
from pathlib import Path
import sys # Needed for sys.exit()

# Define where the save data will be stored
SAVE_FILE_DIR = Path.home() / ".terminal_tamagotchi"
SAVE_FILE = SAVE_FILE_DIR / "pet_save.json"
UPDATE_INTERVAL_SECONDS = 600 # How often stats change (e.g., every 10 minutes)
STAT_CHANGE_AMOUNT = 5 # How much stats change per interval

class Pet:
    def __init__(self, name="Critter"):
        self.name = name
        self.hunger = 50        # 0 = full, 100 = starving
        self.happiness = 50     # 100 = very happy, 0 = very sad
        # Store last update time as a Unix timestamp
        self.last_updated_timestamp = time.time()

    def update_needs(self):
        """Calculates and applies stat changes based on elapsed time."""
        now = time.time()
        elapsed_seconds = now - self.last_updated_timestamp
        intervals_passed = int(elapsed_seconds // UPDATE_INTERVAL_SECONDS)

        if intervals_passed > 0:
            self.hunger = min(100, self.hunger + (STAT_CHANGE_AMOUNT * intervals_passed))
            self.happiness = max(0, self.happiness - (STAT_CHANGE_AMOUNT * intervals_passed))
            self.last_updated_timestamp = now # Only update timestamp if intervals passed
            print(f"({intervals_passed} update intervals passed since last time)")

    def feed(self):
        self.hunger = max(0, self.hunger - 25)
        print(f"{self.name} eats. Hunger decreased.")
        self.update_last_timestamp() 

    def play(self):
        self.happiness = min(100, self.happiness + 20)
        print(f"{self.name} plays. Happiness increased.")
        self.update_last_timestamp()

    def display_status(self):
        print("\n--- Pet Status ---")
        print(f"  Name: {self.name}")
        print(f"  Hunger: {self.hunger}/100")
        print(f"  Happiness: {self.happiness}/100")
        print("------------------\n")

    def update_last_timestamp(self):
        """Updates the timestamp after direct interaction."""
        self.last_updated_timestamp = time.time()

    def to_dict(self):
        """Converts pet state to a dictionary for saving."""
        return {
            'name': self.name,
            'hunger': self.hunger,
            'happiness': self.happiness,
            'last_updated_timestamp': self.last_updated_timestamp,
        }

    @classmethod
    def from_dict(cls, data):
        """Creates a Pet instance from a dictionary."""
        pet = cls(data.get('name', 'Critter')) # Use default if name missing
        pet.hunger = data.get('hunger', 50)
        pet.happiness = data.get('happiness', 50)
        pet.last_updated_timestamp = data.get('last_updated_timestamp', time.time())
        return pet


def load_pet():
    """Loads pet state from the save file."""
    if SAVE_FILE.exists():
        try:
            with open(SAVE_FILE, 'r') as f:
                data = json.load(f)
                print(f"Loading saved state for '{data.get('name', 'pet')}'...")
                return Pet.from_dict(data)
        except (json.JSONDecodeError, IOError, KeyError) as e:
            print(f"Error loading state: {e}. Starting a new pet.")
            return Pet()
    else:
        print("No save file found. Starting a new pet.")
        name = input("What would you like to name your new pet? ")
        return Pet(name if name else "Critter")

def save_pet(pet):
    """Saves pet state to the save file."""
    try:
        SAVE_FILE_DIR.mkdir(parents=True, exist_ok=True)
        with open(SAVE_FILE, 'w') as f:
            json.dump(pet.to_dict(), f, indent=4)
    except IOError as e:
        print(f"Error saving state: {e}")

# --- Main Game Logic ---
if __name__ == "__main__":
    pet = load_pet()

    # Crucial: Update needs immediately after loading to account for time passed
    pet.update_needs()

    while True:
        pet.display_status()
        command = input("Command (feed, play, status, quit): ").lower().strip()

        if command == "feed":
            pet.feed()
            # Recalculate needs immediately after action for responsiveness
            pet.update_needs()
        elif command == "play":
            pet.play()
            pet.update_needs()
        elif command == "status":
            # Status is displayed at the start of the loop
            pass
        elif command == "quit":
            print(f"Saving state for {pet.name}...")
            save_pet(pet)
            print("Goodbye!")
            sys.exit()
        else:
            print("Unknown command. Available: feed, play, status, quit")
