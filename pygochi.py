import json
import time
import sys
import os
import random
from pathlib import Path

from rich.console import Console, Group
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn
from rich.text import Text

# --- Constants ---
SAVE_FILE_DIR = Path.home() / ".terminal_tamagotchi"
SAVE_FILE = SAVE_FILE_DIR / "pet_save.json"

UPDATE_INTERVAL_SECONDS = 30
STAT_DECAY_AMOUNT = 2
ENERGY_DECAY_AWAKE = 2
ENERGY_REGEN_SLEEP = 8
PLAY_ENERGY_COST = 15
HAPPINESS_REGEN_SLEEP = 2
SECONDS_PER_DAY = 86400

AUTO_SLEEP_ENERGY_THRESHOLD = 15
AUTO_WAKE_ENERGY_THRESHOLD = 100
MAX_HUNGER_TO_SLEEP = 75
CRITICAL_HUNGER_THRESHOLD = 95

MAX_POOP = 4
POOP_WINDOW_SECONDS = UPDATE_INTERVAL_SECONDS * 4
POOP_CHANCE_BASE = 0.05
POOP_CHANCE_AFTER_MEAL = 0.40
SICKNESS_CHANCE_PER_INTERVAL_WITH_MAX_POOP = 0.20

# --- Global Objects ---
console = Console()
ASCII_ART = {
    "happy": r" (^_^)/ ",
    "neutral": r" (._.) ",
    "sad": r" (T_T) ",
    "sleeping": r" (-_-) Zzz... ",
    "sick": r" (X_x) ",
    "poop": ":poop:",
}

# --- Helper Functions ---
def create_progress_bar(
    label,
    completed,
    total,
    low_color,
    mid_color,
    high_color,
    low_threshold,
    high_threshold,
    reverse_colors=False,
):
    """Creates and styles a Rich Progress bar."""
    progress = Progress(
        TextColumn(f"{label}:{' '*(10-len(label))}"),
        BarColumn(bar_width=20),
        TextColumn("{task.percentage:>3.0f}%"),
    )
    style = mid_color
    if reverse_colors:
        if completed <= low_threshold:
            style = high_color
        elif completed >= high_threshold:
            style = low_color
    else:
        if completed <= low_threshold:
            style = low_color
        elif completed >= high_threshold:
            style = high_color
    task_id = progress.add_task(label.lower(), total=total, completed=completed)
    progress.update(task_id, style=style)
    return progress


# --- Pet Class ---
class Pet:
    def __init__(self, name="Critter"):
        self.name = name
        self.hunger = 50
        self.happiness = 50
        self.energy = 100
        self.awake = True
        self.last_updated_timestamp = time.time()
        self.birthday_timestamp = time.time()
        self.poop_count = 0
        self.is_sick = False
        self.last_meal_timestamp = 0
        self._last_needs_message = ""

    def get_age_in_days(self):
        return int((time.time() - self.birthday_timestamp) // SECONDS_PER_DAY)

    def get_mood_art(self):
        if self.is_sick:
            return ASCII_ART["sick"]
        if not self.awake:
            return ASCII_ART["sleeping"]
        if self.happiness < 20 or self.hunger > 85 or self.energy < 15:
            return ASCII_ART["sad"]
        if self.happiness > 75 and self.hunger < 30 and self.energy > 60:
            return ASCII_ART["happy"]
        return ASCII_ART["neutral"]

    def get_needs_update_message(self):
        """Returns the message from the last needs update and clears it."""
        msg = self._last_needs_message
        self._last_needs_message = ""
        return msg

    def update_needs(self):
        """Calculates and applies stat changes based on elapsed time."""
        now = time.time()
        elapsed_seconds = now - self.last_updated_timestamp
        intervals_passed = int(elapsed_seconds // UPDATE_INTERVAL_SECONDS)

        if intervals_passed <= 0:
            return False

        needs_changed = False
        sick_message = ""
        for i in range(intervals_passed):
            needs_changed = True
            current_interval_time = (
                self.last_updated_timestamp + (i + 1) * UPDATE_INTERVAL_SECONDS
            )

            if self.awake:
                self.hunger = min(100, self.hunger + STAT_DECAY_AMOUNT)
                self.energy = max(0, self.energy - ENERGY_DECAY_AWAKE)

                happiness_drain = STAT_DECAY_AMOUNT
                if self.hunger > 75:
                    happiness_drain += STAT_DECAY_AMOUNT // 2
                if self.energy < 25:
                    happiness_drain += STAT_DECAY_AMOUNT // 2
                if self.is_sick:
                    happiness_drain += STAT_DECAY_AMOUNT
                if self.poop_count > 0:
                    happiness_drain += self.poop_count * 2
                self.happiness = max(0, self.happiness - happiness_drain)

                time_since_meal = (
                    current_interval_time - self.last_meal_timestamp
                    if self.last_meal_timestamp > 0
                    else float("inf")
                )
                poop_chance = (
                    POOP_CHANCE_AFTER_MEAL
                    if time_since_meal <= POOP_WINDOW_SECONDS
                    else POOP_CHANCE_BASE
                )
                if (
                    random.random() < poop_chance
                    and self.poop_count < MAX_POOP + 2
                ):
                    self.poop_count += 1
            else: # Sleeping
                self.energy = min(100, self.energy + ENERGY_REGEN_SLEEP)
                if not self.is_sick:
                    self.happiness = min(
                        100, self.happiness + HAPPINESS_REGEN_SLEEP
                    )

            if self.poop_count >= MAX_POOP and not self.is_sick:
                if (
                    random.random()
                    < SICKNESS_CHANCE_PER_INTERVAL_WITH_MAX_POOP
                ):
                    self.is_sick = True
                    if self.awake:
                        sick_message = f"[bold red]:rotating_light: {self.name} got sick from the mess![/bold red]"

        self.last_updated_timestamp += intervals_passed * UPDATE_INTERVAL_SECONDS

        if needs_changed:
            self._last_needs_message = (
                f"[dim]({intervals_passed} update intervals processed)[/dim]"
            )
        else:
            self._last_needs_message = ""
        if sick_message:
            self._last_needs_message += (
                ("\n" if self._last_needs_message else "") + sick_message
            )
        return needs_changed

    def feed(self):
        """Feeds the pet, returns message and success status."""
        if not self.awake:
            return f"[yellow]{self.name} is sleeping.[/yellow]", False
        if self.is_sick:
            hunger_decrease = 5
            msg = f"[yellow]{self.name} is too sick to eat much. Hunger -{hunger_decrease}.[/yellow]"
        else:
            hunger_decrease = 25
            msg = f"[green]:pot_of_food: {self.name} eats. Hunger -{hunger_decrease}.[/green]"

        self.hunger = max(0, self.hunger - hunger_decrease)
        self.last_meal_timestamp = time.time()

        if self.hunger < 50 and not self.is_sick:
            happiness_increase = 5
            self.happiness = min(100, self.happiness + happiness_increase)
            msg += f"\n[green]Happiness +{happiness_increase}.[/green]"
        return msg, True

    def play(self):
        """Plays with the pet, returns message and success status."""
        if not self.awake:
            return f"[yellow]{self.name} is sleeping.[/yellow]", False
        if self.is_sick:
            return f"[yellow]{self.name} is too sick to play.[/yellow]", False
        if self.hunger > 80:
            return f"[yellow]{self.name} is too hungry to play.[/yellow]", False
        if self.energy < PLAY_ENERGY_COST + 5:
            return f"[yellow]{self.name} is too tired to play.[/yellow]", False
        if self.poop_count > MAX_POOP // 2:
            return (
                f"[yellow]{self.name} doesn't want to play in this mess.[/yellow]",
                False,
            )

        happiness_increase = 20
        hunger_increase = 10
        energy_decrease = PLAY_ENERGY_COST
        self.happiness = min(100, self.happiness + happiness_increase)
        self.hunger = min(100, self.hunger + hunger_increase)
        self.energy = max(0, self.energy - energy_decrease)
        msg = f"[blue]:video_game: {self.name} plays! Happiness +{happiness_increase}, Hunger +{hunger_increase}, Energy -{energy_decrease}.[/blue]"
        return msg, True

    def attempt_sleep(self):
        """Attempts to put the pet to sleep, returns message and success status."""
        if not self.awake:
            return f"[yellow]{self.name} is already sleeping.[/yellow]", False
        if self.hunger > MAX_HUNGER_TO_SLEEP:
            return (
                f"[yellow]{self.name} is too hungry to sleep (Hunger: {self.hunger}/{MAX_HUNGER_TO_SLEEP}).[/yellow]",
                False,
            )
        self.awake = False
        return f"[purple]:zzz: {self.name} goes to sleep.[/purple]", True

    def wake(self, reason: str | None = None):
        """Wakes the pet up, returns message and success status."""
        if self.awake:
            return None, False

        self.awake = True
        wake_message = f"[purple]:sunny: {self.name} wakes up!"
        if reason:
            wake_message += f" ({reason})"
        else:
            wake_message += f" (Energy: {self.energy}/100)"
        self.update_needs()
        return wake_message, True

    def clean(self):
        """Cleans up pet waste, returns message and success status."""
        if self.poop_count == 0:
            return f"[yellow]Nothing to clean! ✨[/yellow]", False

        cleaned_count = self.poop_count
        self.poop_count = 0
        happiness_increase = min(15, cleaned_count * 3)
        self.happiness = min(100, self.happiness + happiness_increase)
        msg = f"[cyan]:sparkles: Cleaned up {cleaned_count} poop(s). Happiness +{happiness_increase}.[/cyan]"
        return msg, True

    def give_medicine(self):
        """Gives medicine if sick, returns message and success status."""
        if not self.is_sick:
            return f"[yellow]{self.name} isn't sick.[/yellow]", False

        self.is_sick = False
        self.happiness = max(0, self.happiness - 5)
        msg = f"[magenta]:pill: {self.name} took medicine and feels better![/magenta]"
        msg += f"\n[magenta]Happiness -5 (bad taste!).[/magenta]"
        return msg, True

    def display_status(self):
        """Constructs the status panel and prints it to the console."""
        art = self.get_mood_art()
        title = f"{self.name} - Age: {self.get_age_in_days()} days"
        status_details = []
        if not self.awake:
            status_details.append("[purple]Sleeping[/]")
        if self.is_sick:
            status_details.append("[bold red]Sick[/]")
        subtitle = " | ".join(status_details) if status_details else "[green]Awake[/]"

        hunger_bar = create_progress_bar(
            "Hunger", self.hunger, 100, "red", "yellow", "green", 40, 80, True
        )
        happiness_bar = create_progress_bar(
            "Happiness", self.happiness, 100, "red", "yellow", "green", 30, 70
        )
        energy_bar = create_progress_bar(
            "Energy", self.energy, 100, "red", "yellow", "green", 25, 75
        )

        poop_display_text = "Cleanliness:"
        if self.poop_count == 0:
            poop_display_text += " [green]:sparkles: Spotless![/green]"
        else:
            poop_art = ASCII_ART["poop"] * self.poop_count
            if self.poop_count >= MAX_POOP:
                poop_display_text += (
                    f" [bold red on white]{poop_art} Sick Risk![/bold red on white]"
                )
            else:
                poop_display_text += f" [yellow]{poop_art}[/yellow]"

        status_text = Text(art, justify="center")
        panel_content = Group(
            status_text, hunger_bar, happiness_bar, energy_bar, poop_display_text
        )

        console.print(
            Panel(
                panel_content,
                title=title,
                subtitle=subtitle,
                border_style="blue",
                subtitle_align="right",
            )
        )

    def to_dict(self):
        """Converts pet state to a dictionary for saving."""
        return {
            "name": self.name,
            "hunger": self.hunger,
            "happiness": self.happiness,
            "energy": self.energy,
            "awake": self.awake,
            "last_updated_timestamp": self.last_updated_timestamp,
            "birthday_timestamp": self.birthday_timestamp,
            "poop_count": self.poop_count,
            "is_sick": self.is_sick,
            "last_meal_timestamp": self.last_meal_timestamp,
        }

    @classmethod
    def from_dict(cls, data):
        """Creates a Pet instance from loaded dictionary data."""
        default_birthday = data.get("last_updated_timestamp", time.time())
        pet = cls(data.get("name", "Critter"))
        pet.hunger = data.get("hunger", 50)
        pet.happiness = data.get("happiness", 50)
        pet.energy = data.get("energy", 100)
        pet.awake = data.get("awake", True)
        pet.last_updated_timestamp = data.get(
            "last_updated_timestamp", time.time()
        )
        pet.birthday_timestamp = data.get("birthday_timestamp", default_birthday)
        pet.poop_count = data.get("poop_count", 0)
        pet.is_sick = data.get("is_sick", False)
        pet.last_meal_timestamp = data.get("last_meal_timestamp", 0)
        return pet


# --- Save/Load Functions ---
def load_pet():
    """Loads pet state from the save file, or creates a new pet."""
    if not SAVE_FILE.exists():
        return create_new_pet()
    try:
        with open(SAVE_FILE, "r") as f:
            data = json.load(f)
        console.print(
            f"[bold green]Loading saved state for '{data.get('name', 'pet')}'...[/bold green]"
        )
        console.print("[dim]Performing initial needs update...[/dim]")
        loaded_pet = Pet.from_dict(data)
        loaded_pet.update_needs()
        time.sleep(1.0)
        return loaded_pet
    except (json.JSONDecodeError, IOError, KeyError, TypeError) as e:
        console.print(
            f"[bold red]Error loading state:[/bold red] {e}. Save data might be incompatible or corrupt."
        )
        backup_path = SAVE_FILE.with_suffix(".corrupt.json")
        try:
            SAVE_FILE.rename(backup_path)
            console.print(f"[yellow]Backed up corrupt save to {backup_path}[/yellow]")
        except OSError:
            console.print("[yellow]Could not back up corrupt save file.")
            SAVE_FILE.unlink(missing_ok=True)
        console.print("[yellow]Starting a new pet.")
        return create_new_pet()


def create_new_pet():
    """Handles the interactive creation of a new pet."""
    console.print("[yellow]Creating a new Pygochi![/yellow]")
    name = console.input(
        "[bold cyan]What would you like to name your new pet? [/bold cyan]"
    )
    new_pet = Pet(name if name else "Critter")
    console.print(f"[bold green]Say hello to {new_pet.name}![/bold green]")
    save_pet(new_pet)
    time.sleep(1.0)
    return new_pet


def save_pet(pet):
    """Saves the current pet state to the save file."""
    try:
        SAVE_FILE_DIR.mkdir(parents=True, exist_ok=True)
        with open(SAVE_FILE, "w") as f:
            json.dump(pet.to_dict(), f, indent=4)
    except IOError as e:
        console.print(f"[bold red]Error saving state:[/bold red] {e}")


# --- Main Execution Block ---
if __name__ == "__main__":
    pet = load_pet()

    available_commands = "[cyan]feed[/], [cyan]play[/], [cyan]sleep[/], [cyan]wake[/], [cyan]clean[/], [cyan]medicine[/], [cyan]quit[/]"
    last_action_message = ""

    while True:
        os.system("cls" if os.name == "nt" else "clear")

        auto_action_message = None
        auto_action_success = False
        if pet.awake and pet.energy < AUTO_SLEEP_ENERGY_THRESHOLD:
            auto_action_message, auto_action_success = pet.attempt_sleep()
        elif not pet.awake:
            wake_reason = None
            if pet.energy >= AUTO_WAKE_ENERGY_THRESHOLD:
                wake_reason = "fully rested"
            elif pet.hunger > CRITICAL_HUNGER_THRESHOLD:
                wake_reason = "critically hungry"
            if wake_reason:
                auto_action_message, auto_action_success = pet.wake(
                    reason=wake_reason
                )

        needs_updated = pet.update_needs()
        needs_msg = pet.get_needs_update_message()

        pet.display_status()

        message_to_display = ""
        if needs_msg:
            message_to_display += needs_msg + "\n"
        if last_action_message:
            message_to_display += last_action_message + "\n"
            last_action_message = ""
        if auto_action_message:
            message_to_display += auto_action_message + "\n"

        if message_to_display:
            console.print(message_to_display)

        if auto_action_success:
            time.sleep(1.0)
            continue

        command = ""
        try:
            command = (
                console.input(f"Command ({available_commands}): ")
                .lower()
                .strip()
            )
        except EOFError:
            command = "quit"
        except KeyboardInterrupt:
            command = "quit"
            console.print("\n[bold yellow]Quitting on user interrupt...[/bold yellow]")

        action_taken = False
        message = None
        if command == "feed":
            message, action_taken = pet.feed()
        elif command == "play":
            message, action_taken = pet.play()
        elif command == "sleep":
            message, action_taken = pet.attempt_sleep()
        elif command == "wake":
            message, action_taken = pet.wake()
        elif command == "clean":
            message, action_taken = pet.clean()
        elif command == "medicine":
            message, action_taken = pet.give_medicine()
        elif command == "quit":
            save_pet(pet)
            break
        else:
            message = "[bold red]Unknown command.[/bold red]"
            action_taken = False

        if message:
            last_action_message = message

    console.print(f"[bold blue]Goodbye! {pet.name} state saved.[/bold blue]")