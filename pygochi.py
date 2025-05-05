import json
import time
from pathlib import Path
import sys
import os # Needed for clearing screen

# --- Rich Library Imports ---
from rich.console import Console, Group 
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn
from rich.text import Text

# --- Constants ---
SAVE_FILE_DIR = Path.home() / ".terminal_tamagotchi"
SAVE_FILE = SAVE_FILE_DIR / "pet_save.json"
UPDATE_INTERVAL_SECONDS = 600 # Every 10 minutes
STAT_CHANGE_AMOUNT = 5

console = Console()

# --- Basic ASCII Art ---
ASCII_ART = {
    "happy": r"""
    (^_^)/
    """,
    "neutral": r"""
    (._.)
    """,
    "sad": r"""
    (T_T)
    """,
    "sleeping": r"""
    (-_-) Zzz...
    """ 
}

class Pet:
    def __init__(self, name="Critter"):
        self.name = name
        self.hunger = 50        # 0 = full, 100 = starving
        self.happiness = 50     # 100 = very happy, 0 = very sad
        self.awake = True       # New state: Is the pet awake?
        self.last_updated_timestamp = time.time()

    def get_mood_art(self):
        """Selects ASCII art based on current state."""
        if not self.awake:
            return ASCII_ART["sleeping"]
        if self.happiness > 70 and self.hunger < 30:
            return ASCII_ART["happy"]
        elif self.happiness < 30 or self.hunger > 70:
            return ASCII_ART["sad"]
        else:
            return ASCII_ART["neutral"]

    def update_needs(self):
        """Calculates and applies stat changes based on elapsed time."""
        now = time.time()
        elapsed_seconds = now - self.last_updated_timestamp
        intervals_passed = int(elapsed_seconds // UPDATE_INTERVAL_SECONDS)

        if intervals_passed > 0 and self.awake: # Needs only change while awake
            hunger_increase = STAT_CHANGE_AMOUNT * intervals_passed
            happiness_decrease = STAT_CHANGE_AMOUNT * intervals_passed

            self.hunger = min(100, self.hunger + hunger_increase)
            self.happiness = max(0, self.happiness - happiness_decrease)
            self.last_updated_timestamp = now 
            console.print(f"[dim]({intervals_passed} update intervals passed while awake)[/dim]")
        elif intervals_passed > 0 and not self.awake:
            # Only update the timestamp if asleep, no stat changes
            self.last_updated_timestamp = now
            console.print(f"[dim]({intervals_passed} update intervals passed while sleeping)[/dim]")


    def feed(self):
        if not self.awake:
            console.print(f"[yellow]{self.name} is sleeping and cannot eat.[/yellow]")
            return
        hunger_decrease = 25
        self.hunger = max(0, self.hunger - hunger_decrease)
        console.print(f"[green]:pot_of_food: {self.name} eats. Hunger decreased by {hunger_decrease}.[/green]")
        # Small happiness boost for eating when hungry
        if self.hunger < 50:
             happiness_increase = 5
             self.happiness = min(100, self.happiness + happiness_increase)
             console.print(f"[green]+{happiness_increase} happiness.[/green]")
        self.update_last_timestamp()

    def play(self):
        if not self.awake:
            console.print(f"[yellow]{self.name} is sleeping and cannot play.[/yellow]")
            return
        if self.hunger > 80:
             console.print(f"[yellow]{self.name} is too hungry to play.[/yellow]")
             return

        happiness_increase = 20
        hunger_increase = 10 # Playing makes the pet a bit hungry
        self.happiness = min(100, self.happiness + happiness_increase)
        self.hunger = min(100, self.hunger + hunger_increase)
        console.print(f"[blue]:video_game: {self.name} plays. Happiness increased by {happiness_increase}.[/blue]")
        console.print(f"[blue]+{hunger_increase} hunger.[/blue]")
        self.update_last_timestamp()

    def sleep(self):
        if not self.awake:
            console.print(f"[yellow]{self.name} is already sleeping.[/yellow]")
        else:
            self.awake = False
            # Sleeping restores some happiness slowly over time (handled in update_needs indirectly)
            console.print(f"[purple]:zzz: {self.name} goes to sleep.[/purple]")
            self.update_last_timestamp()

    def wake(self):
        if self.awake:
            console.print(f"[yellow]{self.name} is already awake.[/yellow]")
        else:
            self.awake = True
            console.print(f"[purple]:sunny: {self.name} wakes up![/purple]")
            # Check needs immediately upon waking
            self.update_needs()


    def display_status(self):
        """Displays the pet's status using Rich components."""
        # Clear screen for clean display (works on most terminals)
        console.clear()

        art = self.get_mood_art()
        title = f"{self.name}'s Status"
        if not self.awake:
            title += " (Sleeping)"

        # Use Rich Progress bars for stats
        hunger_progress = Progress(
            TextColumn("Hunger:   "),
            BarColumn(bar_width=20),
            TextColumn("{task.percentage:>3.0f}%"),
            transient=True # Removes bar after completion (not relevant here, but good practice)
        )
        # Style the hunger bar based on value
        hunger_style = "green" if self.hunger < 40 else ("yellow" if self.hunger < 80 else "red")
        hunger_task = hunger_progress.add_task("hunger", total=100, completed=self.hunger)
        hunger_progress.update(hunger_task, style=hunger_style)


        happiness_progress = Progress(
             TextColumn("Happiness:"),
             BarColumn(bar_width=20),
             TextColumn("{task.percentage:>3.0f}%"),
             transient=True
        )
        # Style the happiness bar based on value
        happiness_style = "red" if self.happiness < 30 else ("yellow" if self.happiness < 70 else "green")
        happiness_task = happiness_progress.add_task("happiness", total=100, completed=self.happiness)
        happiness_progress.update(happiness_task, style=happiness_style)

        status_text = Text(art, justify="center")
        panel_content = Group(
            status_text,
            hunger_progress,
            happiness_progress
        )
        console.print(Panel(panel_content, title=title, border_style="blue"))


    def update_last_timestamp(self):
        """Updates the timestamp after direct interaction."""
        self.last_updated_timestamp = time.time()

    def to_dict(self):
        """Converts pet state to a dictionary for saving."""
        return {
            'name': self.name,
            'hunger': self.hunger,
            'happiness': self.happiness,
            'awake': self.awake,
            'last_updated_timestamp': self.last_updated_timestamp,
        }

    @classmethod
    def from_dict(cls, data):
        """Creates a Pet instance from a dictionary."""
        pet = cls(data.get('name', 'Critter'))
        pet.hunger = data.get('hunger', 50)
        pet.happiness = data.get('happiness', 50)
        pet.awake = data.get('awake', True) # Load awake state, default to True
        pet.last_updated_timestamp = data.get('last_updated_timestamp', time.time())
        return pet


def load_pet():
    """Loads pet state from the save file."""
    if SAVE_FILE.exists():
        try:
            with open(SAVE_FILE, 'r') as f:
                data = json.load(f)
                console.print(f"[bold green]Loading saved state for '{data.get('name', 'pet')}'...[/bold green]")
                return Pet.from_dict(data)
        except (json.JSONDecodeError, IOError, KeyError) as e:
            console.print(f"[bold red]Error loading state:[/bold red] {e}. Starting a new pet.")
            SAVE_FILE.unlink(missing_ok=True)
            return create_new_pet()
    else:
        console.print("[yellow]No save file found. Starting a new pet.[/yellow]")
        return create_new_pet()

def create_new_pet():
    """Handles the creation of a new pet."""
    name = console.input("[bold cyan]What would you like to name your new pet? [/bold cyan]")
    return Pet(name if name else "Critter")


def save_pet(pet):
    """Saves pet state to the save file."""
    try:
        SAVE_FILE_DIR.mkdir(parents=True, exist_ok=True)
        with open(SAVE_FILE, 'w') as f:
            json.dump(pet.to_dict(), f, indent=4)
    except IOError as e:
        console.print(f"[bold red]Error saving state:[/bold red] {e}")

# --- Main Game Logic ---
if __name__ == "__main__":
    pet = load_pet()
    pet.update_needs() # Update needs immediately after loading

    available_commands = "[cyan]feed[/], [cyan]play[/], [cyan]sleep[/], [cyan]wake[/], [cyan]status[/], [cyan]quit[/]"

    while True:
        pet.display_status() # Display status at the start of each loop
        command = console.input(f"Command ({available_commands}): ").lower().strip()

        needs_updated_by_action = False
        if command == "feed":
            pet.feed()
            needs_updated_by_action = True
        elif command == "play":
            pet.play()
            needs_updated_by_action = True
        elif command == "sleep":
            pet.sleep()
            needs_updated_by_action = True
        elif command == "wake":
             pet.wake()
             # update_needs is called within wake()
        elif command == "status":
            # Status is already displayed
            pass
        elif command == "quit":
            console.print(f"[bold yellow]Saving state for {pet.name}...[/bold yellow]")
            save_pet(pet)
            console.print("[bold blue]Goodbye![/bold blue]")
            sys.exit()
        else:
            console.print("[bold red]Unknown command.[/bold red]")
            time.sleep(1) # Pause slightly on unknown command

        # Update needs if an action potentially changed state relevant to time
        if needs_updated_by_action:
             pet.update_needs()

        # Short pause to make interactions feel less abrupt
        if command != "status" and command != "quit":
             time.sleep(1.5)