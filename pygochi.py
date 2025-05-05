import json
import time
from pathlib import Path
import sys
import os
import random

# --- Rich Library Imports ---
from rich.console import Console, Group
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn
from rich.text import Text
from rich.table import Table

# --- Constants ---
SAVE_FILE_DIR = Path.home() / ".terminal_tamagotchi"
SAVE_FILE = SAVE_FILE_DIR / "pet_save.json"
UPDATE_INTERVAL_SECONDS = 600 # Every 10 minutes stats change
STAT_CHANGE_AMOUNT = 5
SECONDS_PER_DAY = 86400 # For calculating age
MAX_POOP = 5            # Max poop before getting sick risk
POOP_CHANCE_PER_INTERVAL = 0.3 # 30% chance to poop each interval awake
SICKNESS_CHANCE_PER_INTERVAL_WITH_MAX_POOP = 0.4 # Chance if poop is max

console = Console()

# --- ASCII Art ---
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
    """,
    "sick": r"""
    (X_x)
    """,
    "poop": ":poop:"
}

class Pet:
    def __init__(self, name="Critter"):
        self.name = name
        self.hunger = 50        # 0 = full, 100 = starving
        self.happiness = 50     # 100 = very happy, 0 = very sad
        self.awake = True
        self.last_updated_timestamp = time.time()
        self.birthday_timestamp = time.time() 
        self.poop_count = 0     
        self.is_sick = False   

    def get_age_in_days(self):
        """Calculates the pet's age in days."""
        return int((time.time() - self.birthday_timestamp) // SECONDS_PER_DAY)

    def get_mood_art(self):
        """Selects ASCII art based on current state."""
        if self.is_sick:
            return ASCII_ART["sick"]
        if not self.awake:
            return ASCII_ART["sleeping"]
        if self.happiness > 70 and self.hunger < 30:
            return ASCII_ART["happy"]
        elif self.happiness < 30 or self.hunger > 70 or self.poop_count > MAX_POOP // 2:
            return ASCII_ART["sad"]
        else:
            return ASCII_ART["neutral"]

    def update_needs(self):
        """Calculates and applies stat changes based on elapsed time."""
        now = time.time()
        elapsed_seconds = now - self.last_updated_timestamp
        intervals_passed = int(elapsed_seconds // UPDATE_INTERVAL_SECONDS)

        if intervals_passed <= 0:
            return 

        # Needs only change while awake
        if self.awake:
            hunger_increase = STAT_CHANGE_AMOUNT * intervals_passed
            happiness_decrease = STAT_CHANGE_AMOUNT * intervals_passed
            if self.is_sick:
                 happiness_decrease += (STAT_CHANGE_AMOUNT * intervals_passed) # Double decrease if sick
            if self.poop_count > 0:
                 happiness_decrease += (self.poop_count * intervals_passed) # Decrease more with more poop

            self.hunger = min(100, self.hunger + hunger_increase)
            self.happiness = max(0, self.happiness - happiness_decrease)

            for _ in range(intervals_passed):
                if random.random() < POOP_CHANCE_PER_INTERVAL and self.poop_count < MAX_POOP + 2:
                    self.poop_count += 1

            if self.poop_count >= MAX_POOP and not self.is_sick:
                 if random.random() < (SICKNESS_CHANCE_PER_INTERVAL_WITH_MAX_POOP * intervals_passed):
                     self.is_sick = True
                     console.print(f"[bold red]:rotating_light: {self.name} got sick from the mess![/bold red]")

            console.print(f"[dim]({intervals_passed} update intervals passed while awake)[/dim]")

        else: # Pet is sleeping
             # Sleeping restores some happiness slowly, unless sick
             if not self.is_sick:
                 happiness_increase = (STAT_CHANGE_AMOUNT // 2) * intervals_passed # Heal slower than decay
                 self.happiness = min(100, self.happiness + happiness_increase)

             # Still check for sickness from lingering poop while asleep
             if self.poop_count >= MAX_POOP and not self.is_sick:
                 if random.random() < (SICKNESS_CHANCE_PER_INTERVAL_WITH_MAX_POOP * intervals_passed):
                     self.is_sick = True

             console.print(f"[dim]({intervals_passed} update intervals passed while sleeping)[/dim]")

        # Important: Update based on intervals processed, not 'now', to avoid drift
        self.last_updated_timestamp += intervals_passed * UPDATE_INTERVAL_SECONDS


    def feed(self):
        if not self.awake:
            console.print(f"[yellow]{self.name} is sleeping and cannot eat.[/yellow]")
            return
        if self.is_sick:
            console.print(f"[yellow]{self.name} is too sick to eat much.[/yellow]")
            hunger_decrease = 5
        else:
            hunger_decrease = 25

        self.hunger = max(0, self.hunger - hunger_decrease)
        console.print(f"[green]:pot_of_food: {self.name} eats. Hunger decreased by {hunger_decrease}.[/green]")

        if self.hunger < 50 and not self.is_sick:
             happiness_increase = 5
             self.happiness = min(100, self.happiness + happiness_increase)
             console.print(f"[green]+{happiness_increase} happiness.[/green]")
        self.update_last_timestamp() # Use current time for direct interaction

    def play(self):
        if not self.awake:
            console.print(f"[yellow]{self.name} is sleeping and cannot play.[/yellow]")
            return
        if self.is_sick:
            console.print(f"[yellow]{self.name} is too sick to play.[/yellow]")
            return
        if self.hunger > 80:
             console.print(f"[yellow]{self.name} is too hungry to play.[/yellow]")
             return
        if self.poop_count > MAX_POOP // 2:
            console.print(f"[yellow]{self.name} doesn't want to play in this mess.[/yellow]")
            return

        happiness_increase = 20
        hunger_increase = 10
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
            console.print(f"[purple]:zzz: {self.name} goes to sleep.[/purple]")
            self.update_last_timestamp()

    def wake(self):
        if self.awake:
            console.print(f"[yellow]{self.name} is already awake.[/yellow]")
        else:
            self.awake = True
            console.print(f"[purple]:sunny: {self.name} wakes up![/purple]")
            self.update_needs()

    def clean(self):
        if self.poop_count == 0:
            console.print(f"[yellow]Nothing to clean! ✨[/yellow]")
        else:
            cleaned_count = self.poop_count
            self.poop_count = 0
            # Small happiness boost for cleaning
            happiness_increase = min(15, cleaned_count * 3)
            self.happiness = min(100, self.happiness + happiness_increase)
            console.print(f"[cyan]:sparkles: Cleaned up {cleaned_count} poop(s). +{happiness_increase} happiness.[/cyan]")
        self.update_last_timestamp()

    def give_medicine(self):
        if not self.is_sick:
             console.print(f"[yellow]{self.name} isn't sick.[/yellow]")
        else:
             self.is_sick = False
             # Medicine might make them slightly less happy initially
             self.happiness = max(0, self.happiness - 5)
             console.print(f"[magenta]:pill: {self.name} took medicine and feels better![/magenta]")
             console.print(f"[magenta]-5 happiness (bad taste!).[/magenta]")
        self.update_last_timestamp()


    def display_status(self):
        """Displays the pet's status using Rich components."""
        console.clear()

        art = self.get_mood_art()
        title = f"{self.name} - Age: {self.get_age_in_days()} days"
        status_details = []
        if not self.awake:
             status_details.append("[purple]Sleeping[/]")
        if self.is_sick:
             status_details.append("[bold red]Sick[/]")

        subtitle = " | ".join(status_details) if status_details else "Awake"

        # --- Progress Bars ---
        hunger_progress = Progress(TextColumn("Hunger:   "), BarColumn(bar_width=20), TextColumn("{task.percentage:>3.0f}%"))
        hunger_style = "green" if self.hunger < 40 else ("yellow" if self.hunger < 80 else "red")
        hunger_task = hunger_progress.add_task("hunger", total=100, completed=self.hunger)
        hunger_progress.update(hunger_task, style=hunger_style)

        happiness_progress = Progress(TextColumn("Happiness:"), BarColumn(bar_width=20), TextColumn("{task.percentage:>3.0f}%"))
        happiness_style = "red" if self.happiness < 30 else ("yellow" if self.happiness < 70 else "green")
        happiness_task = happiness_progress.add_task("happiness", total=100, completed=self.happiness)
        happiness_progress.update(happiness_task, style=happiness_style)

        # --- Poop Display ---
        poop_display = f"Cleanliness: {' '.join([ASCII_ART['poop']] * self.poop_count)}" if self.poop_count > 0 else "Cleanliness: [green]:sparkles: Spotless![/green]"
        if self.poop_count >= MAX_POOP:
            poop_display = f"Cleanliness: [bold red]{'[poop]' * self.poop_count} Danger![/bold red]" # :poop: emoji doesn't work well with style tags here

        status_text = Text(art, justify="center")
        panel_content = Group(
            status_text,
            hunger_progress,
            happiness_progress,
            poop_display 
        )

        console.print(Panel(panel_content, title=title, subtitle=subtitle, border_style="blue", subtitle_align="right"))

    def update_last_timestamp(self):
        """Updates the timestamp after direct interaction - use current time."""
        self.last_updated_timestamp = time.time()

    def to_dict(self):
        """Converts pet state to a dictionary for saving."""
        return {
            'name': self.name,
            'hunger': self.hunger,
            'happiness': self.happiness,
            'awake': self.awake,
            'last_updated_timestamp': self.last_updated_timestamp,
            'birthday_timestamp': self.birthday_timestamp,
            'poop_count': self.poop_count,
            'is_sick': self.is_sick,
        }

    @classmethod
    def from_dict(cls, data):
        """Creates a Pet instance from a dictionary."""
        # Use current time as default birthday for saves created before this feature
        default_birthday = data.get('last_updated_timestamp', time.time())

        pet = cls(data.get('name', 'Critter'))
        pet.hunger = data.get('hunger', 50)
        pet.happiness = data.get('happiness', 50)
        pet.awake = data.get('awake', True)
        pet.last_updated_timestamp = data.get('last_updated_timestamp', time.time())
        pet.birthday_timestamp = data.get('birthday_timestamp', default_birthday)
        pet.poop_count = data.get('poop_count', 0)
        pet.is_sick = data.get('is_sick', False)
        return pet


# --- Save/Load Functions ---
def load_pet():
    """Loads pet state from the save file."""
    if SAVE_FILE.exists():
        try:
            with open(SAVE_FILE, 'r') as f:
                data = json.load(f)
                console.print(f"[bold green]Loading saved state for '{data.get('name', 'pet')}'...[/bold green]")
                return Pet.from_dict(data)
        except (json.JSONDecodeError, IOError, KeyError, TypeError) as e:
            console.print(f"[bold red]Error loading state:[/bold red] {e}. Save file might be incompatible or corrupted. Starting a new pet.")
            SAVE_FILE.unlink(missing_ok=True)
            return create_new_pet()
    else:
        console.print("[yellow]No save file found. Starting a new pet.[/yellow]")
        return create_new_pet()

def create_new_pet():
    """Handles the creation of a new pet."""
    name = console.input("[bold cyan]What would you like to name your new pet? [/bold cyan]")
    new_pet = Pet(name if name else "Critter")
    console.print(f"[bold green]Created a new Pygochi named {new_pet.name}![/bold green]")
    save_pet(new_pet)
    return new_pet

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
    pet.update_needs()

    available_commands = "[cyan]feed[/], [cyan]play[/], [cyan]sleep[/], [cyan]wake[/], [cyan]clean[/], [cyan]medicine[/], [cyan]status[/], [cyan]quit[/]"

    while True:
        pet.display_status()
        command = console.input(f"Command ({available_commands}): ").lower().strip()

        action_taken = True
        if command == "feed":
            pet.feed()
        elif command == "play":
            pet.play()
        elif command == "sleep":
            pet.sleep()
        elif command == "wake":
             pet.wake()
        elif command == "clean":
             pet.clean()
        elif command == "medicine":
             pet.give_medicine()
        elif command == "status":
            action_taken = False
            pass
        elif command == "quit":
            console.print(f"[bold yellow]Saving state for {pet.name}...[/bold yellow]")
            save_pet(pet)
            console.print("[bold blue]Goodbye![/bold blue]")
            sys.exit()
        else:
            console.print("[bold red]Unknown command.[/bold red]")
            action_taken = False
            time.sleep(1)

        # Short pause after most actions
        if action_taken:
             time.sleep(1.5)