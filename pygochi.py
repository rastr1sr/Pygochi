import json
import time
import sys
import os
import random
from pathlib import Path
from datetime import timedelta 

from rich.console import Console, Group
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn
from rich.text import Text
from rich.align import Align

# --- Constants ---
SAVE_FILE_DIR = Path.home() / ".terminal_tamagotchi"
SAVE_FILE = SAVE_FILE_DIR / "pet_save.json"

# Timing & Core Stats
UPDATE_INTERVAL_SECONDS = 30
STAT_DECAY_AMOUNT = 2
ENERGY_DECAY_AWAKE = 2
ENERGY_REGEN_SLEEP = 8
PLAY_ENERGY_COST = 10
HAPPINESS_REGEN_SLEEP = 2
DISCIPLINE_DECAY = 1
FEED_WEIGHT_GAIN = 0.1 
SCOLD_DISCIPLINE_GAIN = 15
SCOLD_HAPPINESS_LOSS = 10
TRAIN_ENERGY_COST = 15
TRICK_ENERGY_COST = 15
TRICK_HAPPINESS_BOOST = 25

# Health / Sickness
HEALTH_DECAY_POOP = 3
HEALTH_DECAY_HUNGER = 2
HEALTH_REGEN_CLEAN_FED = 1
MEDICINE_HEALTH_GAIN = 40

# Age
SECONDS_PER_DAY = 86400

# Thresholds & Limits
AUTO_SLEEP_ENERGY_THRESHOLD = 15
AUTO_WAKE_ENERGY_THRESHOLD = 100
MAX_HUNGER_TO_SLEEP = 75
CRITICAL_HUNGER_THRESHOLD = 90
CRITICAL_HAPPINESS_THRESHOLD = 10
CRITICAL_HEALTH_THRESHOLD = 15
CRITICAL_ENERGY_THRESHOLD = 5
MAX_POOP = 4

# Death Conditions
MAX_AGE_DAYS = 20 
MAX_TIME_CRITICAL_SECONDS = int(timedelta(hours=1).total_seconds()) # 1 hour at critical hunger/happiness

# Poop Mechanics
POOP_WINDOW_SECONDS = UPDATE_INTERVAL_SECONDS * 4
POOP_CHANCE_BASE = 0.05
POOP_CHANCE_AFTER_MEAL = 0.40

# Discipline Refusal Chance
REFUSAL_CHANCE_FACTOR = 150 # Higher value = less chance of refusal

# --- Global Objects & Emojis ---
console = Console()
# Using Emojis instead of ASCII Art
ASCII_ART = {
    "happy": "😺",    #
    "neutral": "🐱", 
    "sad": "😿",     
    "sleeping": "😴", 
    "sick": "🤢",    
    "dead": "💀",      
    "poop": "💩",    
    "angry": "😠",     
    "playing": "🧶",  
    "eating": "😋",    
    "thinking": "🤔",  
    "dancing": "🎶",   
    "alert": ":warning:", 
}

# Food Definitions
FOOD_ITEMS = {
    "apple": {"hunger_restore": 15, "happiness_boost": 5, "health_boost": 1, "weight_gain": 0.05},
    "cake":  {"hunger_restore": 25, "happiness_boost": 15, "health_boost": -2, "weight_gain": 0.2},
    "veg":   {"hunger_restore": 10, "happiness_boost": 2, "health_boost": 3, "weight_gain": 0.02},
}

# --- Helper Function create_progress_bar ---
def create_progress_bar( label, completed, total, low_color, mid_color, high_color, low_threshold, high_threshold, reverse_colors=False, ):
    progress = Progress( TextColumn(f"{label}:{' '*(10-len(label))}"), BarColumn(bar_width=20), TextColumn("{task.percentage:>3.0f}%"), ); style = mid_color
    if reverse_colors:
        if completed <= low_threshold: style = high_color
        elif completed >= high_threshold: style = low_color
    else:
        if completed <= low_threshold: style = low_color
        elif completed >= high_threshold: style = high_color
    task_id = progress.add_task(label.lower(), total=total, completed=completed); progress.update(task_id, style=style); return progress

# --- Pet Class ---
class Pet:
    def __init__(self, name="Critter"):
        self.name = name
        self.hunger = 50; self.happiness = 50; self.energy = 100; self.health = 100; self.discipline = 50; self.weight = 1.0
        self.awake = True; self.last_updated_timestamp = time.time(); self.birthday_timestamp = time.time(); self.poop_count = 0; self.last_meal_timestamp = 0
        self._last_needs_message = ""; self.is_dead = False
        self.time_hunger_critical_start = 0
        self.time_happiness_critical_start = 0
        self.tricks_learned = []
    def get_age_in_days(self):
        return int((time.time() - self.birthday_timestamp) // SECONDS_PER_DAY)

    def get_mood_art(self):
        if self.is_dead: return ASCII_ART["dead"]
        if self.health < CRITICAL_HEALTH_THRESHOLD: return ASCII_ART["sick"]
        if not self.awake: return ASCII_ART["sleeping"]
        if self.happiness < CRITICAL_HAPPINESS_THRESHOLD or self.hunger > CRITICAL_HUNGER_THRESHOLD or self.energy < CRITICAL_ENERGY_THRESHOLD or self.health < 50: return ASCII_ART["sad"]
        if self.happiness > 75 and self.hunger < 30 and self.energy > 60 and self.health > 80: return ASCII_ART["happy"]
        return ASCII_ART["neutral"]

    def get_needs_update_message(self): msg = self._last_needs_message; self._last_needs_message = ""; return msg

    def _check_death_conditions(self, now):
        if self.is_dead: return
        age_days = self.get_age_in_days(); death_reason = None
        if self.health <= 0: death_reason = "succumbed to poor health"
        elif age_days > MAX_AGE_DAYS and random.random() < (age_days - MAX_AGE_DAYS) * 0.05: death_reason = "passed away peacefully from old age"
        elif self.hunger >= 100:
            if self.time_hunger_critical_start == 0: self.time_hunger_critical_start = now
            elif (now - self.time_hunger_critical_start) > MAX_TIME_CRITICAL_SECONDS: death_reason = "starved"
        elif self.hunger < 100: self.time_hunger_critical_start = 0
        if self.happiness <= 0:
             if self.time_happiness_critical_start == 0: self.time_happiness_critical_start = now
             elif (now - self.time_happiness_critical_start) > MAX_TIME_CRITICAL_SECONDS: death_reason = "lost the will to live"
        elif self.happiness > 0: self.time_happiness_critical_start = 0
        if death_reason:
            self.is_dead = True; self._last_needs_message = f"[bold red on white] !!! {self.name} has {death_reason} !!! [/bold red on white]"; self.awake = False

    def update_needs(self):
        if self.is_dead: return False
        now = time.time(); elapsed_seconds = now - self.last_updated_timestamp; intervals_passed = int(elapsed_seconds // UPDATE_INTERVAL_SECONDS)
        if intervals_passed <= 0: return False

        needs_changed = False; health_change_msg = ""
        for i in range(intervals_passed):
            self._check_death_conditions(self.last_updated_timestamp + i * UPDATE_INTERVAL_SECONDS)
            if self.is_dead: return True
            needs_changed = True
            current_interval_time = ( self.last_updated_timestamp + (i + 1) * UPDATE_INTERVAL_SECONDS ); current_health = self.health
            self.discipline = max(0, self.discipline - DISCIPLINE_DECAY)
            if self.awake:
                self.hunger = min(100, self.hunger + STAT_DECAY_AMOUNT); self.energy = max(0, self.energy - ENERGY_DECAY_AWAKE)
                happiness_drain = STAT_DECAY_AMOUNT
                if self.hunger > 75: happiness_drain += STAT_DECAY_AMOUNT // 2
                if self.energy < 25: happiness_drain += STAT_DECAY_AMOUNT // 2
                if current_health < 50: happiness_drain += STAT_DECAY_AMOUNT
                if self.poop_count > 0: happiness_drain += self.poop_count * 2
                self.happiness = max(0, self.happiness - happiness_drain)
                time_since_meal = current_interval_time - self.last_meal_timestamp if self.last_meal_timestamp > 0 else float('inf')
                poop_chance = POOP_CHANCE_AFTER_MEAL if time_since_meal <= POOP_WINDOW_SECONDS else POOP_CHANCE_BASE
                if random.random() < poop_chance and self.poop_count < MAX_POOP + 2: self.poop_count += 1
            else: # Sleeping
                self.energy = min(100, self.energy + ENERGY_REGEN_SLEEP)
                if current_health > CRITICAL_HEALTH_THRESHOLD: self.happiness = min(100, self.happiness + HAPPINESS_REGEN_SLEEP)
            health_change_this_interval = 0
            if self.poop_count >= MAX_POOP: health_change_this_interval -= HEALTH_DECAY_POOP
            if self.hunger >= CRITICAL_HUNGER_THRESHOLD: health_change_this_interval -= HEALTH_DECAY_HUNGER
            if self.poop_count == 0 and self.hunger < 50 and self.energy > 30 and self.awake: health_change_this_interval += HEALTH_REGEN_CLEAN_FED
            self.health = max(0, min(100, self.health + health_change_this_interval))
            if health_change_this_interval < 0 and not health_change_msg:
                 if self.poop_count >= MAX_POOP : health_change_msg = f"[yellow]Health declining due to mess![/yellow]"
                 elif self.hunger >= CRITICAL_HUNGER_THRESHOLD: health_change_msg = f"[yellow]Health declining due to hunger![/yellow]"
        self.last_updated_timestamp += intervals_passed * UPDATE_INTERVAL_SECONDS
        interval_msg = f"[dim]({intervals_passed} update intervals processed)[/dim]" if needs_changed else ""
        self._last_needs_message = interval_msg
        if health_change_msg: self._last_needs_message += ("\n" if self._last_needs_message else "") + health_change_msg
        self._check_death_conditions(now)
        return needs_changed

    def _should_refuse(self):
        refusal_chance = max(0, (100 - self.discipline)) / REFUSAL_CHANCE_FACTOR
        return random.random() < refusal_chance

    def feed(self, food_name: str):
        if not self.awake: return f"[yellow]{self.name} {ASCII_ART['sleeping']} is sleeping.[/yellow]", False
        if self._should_refuse(): return f"[orange1]{self.name} {ASCII_ART['angry']} ignores the {food_name}.[/orange1]", False
        if food_name not in FOOD_ITEMS: return f"[red]Unknown food: {food_name}. Try: {', '.join(FOOD_ITEMS.keys())}[/red]", False
        food = FOOD_ITEMS[food_name]
        hunger_decrease = food["hunger_restore"]; happiness_increase = food["happiness_boost"]; health_change = food["health_boost"]; weight_increase = food["weight_gain"]
        if self.health < 40:
            hunger_decrease = max(1, hunger_decrease // 3); happiness_increase = max(0, happiness_increase // 2)
            msg_prefix = f"[yellow]{self.name} {ASCII_ART['sick']} is feeling unwell and nibbles the {food_name}.[/yellow]"
        elif self.health < 70:
             hunger_decrease = max(1, int(hunger_decrease * 0.75)); msg_prefix = f"[yellow]{self.name} eats the {food_name} slowly.[/yellow]"
        else: msg_prefix = f"[green]{ASCII_ART['eating']} {self.name} eats the {food_name}.[/green]"
        self.hunger = max(0, self.hunger - hunger_decrease); self.happiness = min(100, max(0, self.happiness + happiness_increase)); self.health = min(100, max(0, self.health + health_change)); self.weight += weight_increase; self.last_meal_timestamp = time.time()
        msg = msg_prefix; msg += f"\nHunger -{hunger_decrease}"
        if happiness_increase != 0: msg += f", Happiness {'+' if happiness_increase > 0 else ''}{happiness_increase}"
        if health_change != 0: msg += f", Health {'+' if health_change > 0 else ''}{health_change}"
        msg += f", Weight +{weight_increase:.2f}"
        return msg, True

    def play_rps(self):
        if not self.awake: return f"[yellow]{self.name} {ASCII_ART['sleeping']} is sleeping.[/yellow]", False
        if self.health < 50: return f"[yellow]{self.name} {ASCII_ART['sick']} is too unwell to play.[/yellow]", False
        if self.hunger > 80: return f"[yellow]{self.name} {ASCII_ART['sad']} is too hungry to play.[/yellow]", False
        if self.energy < PLAY_ENERGY_COST + 5: return f"[yellow]{self.name} {ASCII_ART['sad']} is too tired to play.[/yellow]", False
        if self.poop_count > MAX_POOP // 2: return f"[yellow]{self.name} {ASCII_ART['sad']} doesn't want to play in this mess.[/yellow]", False
        if self._should_refuse(): return f"[orange1]{self.name} {ASCII_ART['angry']} doesn't feel like playing.[/orange1]", False

        console.print(f"[cyan]Let's play Rock-Paper-Scissors! {ASCII_ART['playing']}[/cyan]")
        choices = ["rock", "paper", "scissors"]; pet_choice = random.choice(choices)
        while True:
            user_choice = console.input("Choose ([bold]r[/]ock, [bold]p[/]aper, [bold]s[/]cissors): ").lower().strip()
            if user_choice in ["r", "rock"]: user_choice = "rock"; break
            elif user_choice in ["p", "paper"]: user_choice = "paper"; break
            elif user_choice in ["s", "scissors"]: user_choice = "scissors"; break
            else: console.print("[red]Invalid choice. Try again.[/red]")
        console.print(f"{self.name} chose: [bold]{pet_choice}[/bold]"); console.print(f"You chose: [bold]{user_choice}[/bold]")

        outcome_msg = ""; happiness_change = 0
        if user_choice == pet_choice: outcome_msg = "[yellow]It's a draw![/yellow]"; happiness_change = 5
        elif (user_choice == "rock" and pet_choice == "scissors") or (user_choice == "scissors" and pet_choice == "paper") or (user_choice == "paper" and pet_choice == "rock"): outcome_msg = "[bold green]You win![/bold green]"; happiness_change = 15
        else: outcome_msg = "[bold red]You lose![/bold red]"; happiness_change = 0

        hunger_increase = 5; energy_decrease = PLAY_ENERGY_COST
        self.happiness = min(100, max(0, self.happiness + happiness_change)); self.hunger = min(100, self.hunger + hunger_increase); self.energy = max(0, self.energy - energy_decrease)
        time.sleep(1.5)
        msg = f"{outcome_msg}\nHappiness {'+' if happiness_change >=0 else ''}{happiness_change}, Hunger +{hunger_increase}, Energy -{energy_decrease}."
        return msg, True

    def attempt_sleep(self):
        if not self.awake: return f"[yellow]{self.name} is already sleeping.[/yellow]", False
        if self.hunger > MAX_HUNGER_TO_SLEEP: return f"[yellow]{self.name} {ASCII_ART['sad']} is too hungry to sleep (Hunger: {self.hunger}/{MAX_HUNGER_TO_SLEEP}).[/yellow]", False
        if self.health < CRITICAL_HEALTH_THRESHOLD + 10: return f"[yellow]{self.name} {ASCII_ART['sick']} is too unwell to sleep properly.[/yellow]", False
        self.awake = False; return f"[purple]{ASCII_ART['sleeping']} {self.name} goes to sleep.[/purple]", True

    def wake(self, reason: str | None = None):
        if self.awake: return None, False
        self.awake = True; wake_message = f"[purple]:sunny: {self.name} wakes up!"
        if reason: wake_message += f" ({reason})"
        else: wake_message += f" (Energy: {self.energy}/100)"
        self.update_needs(); return wake_message, True

    def clean(self):
        if self.poop_count == 0: return f"[yellow]Nothing to clean! ✨[/yellow]", False
        cleaned_count = self.poop_count; self.poop_count = 0; happiness_increase = min(15, cleaned_count * 3); self.happiness = min(100, self.happiness + happiness_increase)
        msg = f"[cyan]:sparkles: Cleaned up {cleaned_count} {ASCII_ART['poop']}(s). Happiness +{happiness_increase}.[/cyan]"; return msg, True

    def give_medicine(self):
        if self.health >= 95 : return f"[yellow]{self.name} doesn't need medicine.[/yellow]", False
        health_increase = MEDICINE_HEALTH_GAIN; self.health = min(100, self.health + health_increase); self.happiness = max(0, self.happiness - 5)
        msg = f"[magenta]:pill: {self.name} took medicine. Health +{health_increase}.[/magenta]"; msg += f"\n[magenta]Happiness -5 (bad taste!).[/magenta]"
        return msg, True

    def scold(self):
        if not self.awake: return f"[yellow]{self.name} {ASCII_ART['sleeping']} is sleeping.[/yellow]", False
        discipline_gain = SCOLD_DISCIPLINE_GAIN; happiness_loss = SCOLD_HAPPINESS_LOSS
        self.discipline = min(100, self.discipline + discipline_gain); self.happiness = max(0, self.happiness - happiness_loss)
        msg = f"[orange1]{ASCII_ART['angry']} You scold {self.name}. Discipline +{discipline_gain}, Happiness -{happiness_loss}.[/orange1]"
        return msg, True

    def train(self):
        if not self.awake: return f"[yellow]{self.name} {ASCII_ART['sleeping']} is sleeping.[/yellow]", False
        if self.energy < TRAIN_ENERGY_COST: return f"[yellow]{self.name} {ASCII_ART['sad']} is too tired to focus.[/yellow]", False
        if self.happiness < 40: return f"[yellow]{self.name} {ASCII_ART['sad']} isn't happy enough to train.[/yellow]", False

        success_chance = (self.discipline / 150) + (self.happiness / 200)
        did_succeed = random.random() < success_chance
        energy_cost = TRAIN_ENERGY_COST; discipline_change = 0; happiness_change = -5; msg = ""

        if did_succeed:
            if "dance" not in self.tricks_learned:
                self.tricks_learned.append("dance"); discipline_change = 5; happiness_change = 10
                msg = f"[bold green]:sparkles: {self.name} learned to dance![/bold green]"
            else:
                discipline_change = 1; happiness_change = 2
                msg = f"[green]{self.name} {ASCII_ART['thinking']} practices dancing.[/green]"
        else:
            discipline_change = -2; happiness_change = -10
            msg = f"[yellow]{self.name} {ASCII_ART['sad']} couldn't figure it out.[/yellow]"

        self.energy = max(0, self.energy - energy_cost); self.discipline = min(100, max(0, self.discipline + discipline_change)); self.happiness = min(100, max(0, self.happiness + happiness_change))
        msg += f"\nEnergy -{energy_cost}, Discipline {'+' if discipline_change>=0 else ''}{discipline_change}, Happiness {'+' if happiness_change>=0 else ''}{happiness_change}."
        return msg, True

    def do_trick(self, trick_name):
        if not self.awake: return f"[yellow]{self.name} {ASCII_ART['sleeping']} is sleeping.[/yellow]", False
        if trick_name not in self.tricks_learned: return f"[red]{self.name} doesn't know how to {trick_name}. Known: {', '.join(self.tricks_learned)}. Try 'train'.[/red]", False
        if self.energy < TRICK_ENERGY_COST: return f"[yellow]{self.name} {ASCII_ART['sad']} is too tired to perform.[/yellow]", False

        msg = ""; happiness_boost = 0; energy_cost = 0
        if trick_name == "dance":
            console.print(f"{self.name} {ASCII_ART['dancing']} starts to dance...")
            time.sleep(0.5); console.print("   ♪┏(・o･)┛ ♪ ┗ ( ･o･) ┓♪") 
            time.sleep(0.7); console.print("      ┗ (･o･ ) ┓ ♪ ┏(･o･)┛")
            time.sleep(0.5);
            happiness_boost = TRICK_HAPPINESS_BOOST; energy_cost = TRICK_ENERGY_COST
            msg = f"[magenta]{self.name} danced happily! Happiness +{happiness_boost}, Energy -{energy_cost}.[/magenta]"
        else: return f"[red]Unknown trick logic: {trick_name}[/red]", False

        self.happiness = min(100, self.happiness + happiness_boost); self.energy = max(0, self.energy - energy_cost)
        return msg, True

    def get_notifications(self):
        alerts = []
        if self.hunger >= CRITICAL_HUNGER_THRESHOLD: alerts.append("hunger")
        if self.happiness <= CRITICAL_HAPPINESS_THRESHOLD: alerts.append("happiness")
        if self.health <= CRITICAL_HEALTH_THRESHOLD: alerts.append("health")
        if self.energy <= CRITICAL_ENERGY_THRESHOLD and self.awake: alerts.append("energy")
        if self.poop_count >= MAX_POOP: alerts.append("poop")
        return alerts

    def display_status(self):
        if self.is_dead:
             console.print(Panel(Align.center(f"[bold red]R.I.P.\n{ASCII_ART['dead']}\n{self.name}[/bold red]"), border_style="red"))
             return

        alerts = self.get_notifications(); panel_border_style = "blink red" if alerts else "blue"
        art = self.get_mood_art(); title = f"{self.name} - Age: {self.get_age_in_days()} days"
        status_details = []
        if not self.awake: status_details.append("[purple]Sleeping[/]")
        if "health" in alerts: status_details.append("[bold red]HEALTH CRITICAL![/]")
        elif self.health < 50: status_details.append("[yellow]Unwell[/]")
        subtitle = " | ".join(status_details) if status_details else "[green]Awake[/]"

        hunger_bar = create_progress_bar("Hunger", self.hunger, 100, "red", "yellow", "green", 40, CRITICAL_HUNGER_THRESHOLD, True)
        happiness_bar = create_progress_bar("Happiness", self.happiness, 100, "red", "yellow", "green", CRITICAL_HAPPINESS_THRESHOLD+10, 70)
        energy_bar = create_progress_bar("Energy", self.energy, 100, "red", "yellow", "green", CRITICAL_ENERGY_THRESHOLD+10, 75)
        health_bar = create_progress_bar("Health", self.health, 100, "red", "yellow", "green", CRITICAL_HEALTH_THRESHOLD+10, 80)
        discipline_bar = create_progress_bar("Discipline", self.discipline, 100, "red", "yellow", "green", 30, 70)
        poop_art_str = (" " + ASCII_ART['poop']) * self.poop_count
        aligned_art = Align.center(f"{art}{poop_art_str}")
        weight_text = f"Weight: {self.weight:.1f}"
        panel_content = Group( aligned_art, hunger_bar, happiness_bar, energy_bar, health_bar, discipline_bar, weight_text )
        console.print(Panel( panel_content, title=title, subtitle=subtitle, border_style=panel_border_style, subtitle_align="right" ))

    def to_dict(self):
        return { "name": self.name, "hunger": self.hunger, "happiness": self.happiness, "energy": self.energy, "health": self.health, "discipline": self.discipline, "weight": self.weight, "awake": self.awake, "last_updated_timestamp": self.last_updated_timestamp, "birthday_timestamp": self.birthday_timestamp, "poop_count": self.poop_count, "last_meal_timestamp": self.last_meal_timestamp, "is_dead": self.is_dead, "time_hunger_critical_start": self.time_hunger_critical_start, "time_happiness_critical_start": self.time_happiness_critical_start, "tricks_learned": self.tricks_learned }
    @classmethod
    def from_dict(cls, data):
        default_birthday = data.get("last_updated_timestamp", time.time()); pet = cls(data.get("name", "Critter"))
        pet.hunger=data.get("hunger",50); pet.happiness=data.get("happiness",50); pet.energy=data.get("energy",100); pet.health=data.get("health",100); pet.discipline=data.get("discipline",50); pet.weight=data.get("weight",1.0); pet.awake=data.get("awake",True); pet.last_updated_timestamp=data.get("last_updated_timestamp",time.time()); pet.birthday_timestamp=data.get("birthday_timestamp",default_birthday); pet.poop_count=data.get("poop_count",0); pet.last_meal_timestamp=data.get("last_meal_timestamp",0); pet.is_dead=data.get("is_dead",False); pet.time_hunger_critical_start=data.get("time_hunger_critical_start",0); pet.time_happiness_critical_start=data.get("time_happiness_critical_start",0);
        pet.tricks_learned = data.get("tricks_learned", [])
        if pet.is_dead: pet.awake = False
        return pet

# --- Save/Load Functions ---
def load_pet():
    if not SAVE_FILE.exists(): return create_new_pet()
    try:
        with open(SAVE_FILE, "r") as f: data = json.load(f)
        console.print(f"[bold green]Loading saved state for '{data.get('name', 'pet')}'...[/bold green]");
        loaded_pet = Pet.from_dict(data)
        if loaded_pet.is_dead: console.print(f"[bold red]{loaded_pet.name} was found dead...[/bold red]"); time.sleep(2.0)
        else: console.print("[dim]Performing initial needs update...[/dim]"); loaded_pet.update_needs(); time.sleep(1.0)
        return loaded_pet
    except (json.JSONDecodeError, IOError, KeyError, TypeError) as e:
        console.print(f"[bold red]Error loading state:[/bold red] {e}. Save data might be incompatible or corrupt."); backup_path = SAVE_FILE.with_suffix(".corrupt.json")
        try: SAVE_FILE.rename(backup_path); console.print(f"[yellow]Backed up corrupt save to {backup_path}[/yellow]")
        except OSError: console.print("[yellow]Could not back up corrupt save file."); SAVE_FILE.unlink(missing_ok=True)
        console.print("[yellow]Starting a new pet."); return create_new_pet()
def create_new_pet(is_restart=False):
    if not is_restart: console.print("[yellow]Creating a new Pygochi![/yellow]")
    name = console.input("[bold cyan]What would you like to name your new pet? [/bold cyan]")
    new_pet = Pet(name if name else "Critter"); console.print(f"[bold green]Say hello to {new_pet.name}![/bold green]"); save_pet(new_pet); time.sleep(1.0); return new_pet
def save_pet(pet):
    try:
        SAVE_FILE_DIR.mkdir(parents=True, exist_ok=True)
        with open(SAVE_FILE, "w") as f:
            json.dump(pet.to_dict(), f, indent=4)
    except IOError as e:
        console.print(f"[bold red]Error saving state:[/bold red] {e}")
    except IOError as e: console.print(f"[bold red]Error saving state:[/bold red] {e}")

# --- Main Execution Block ---
if __name__ == "__main__":
    pet = load_pet()
    available_commands_display = "[cyan]feed [item][/], [cyan]play[/], [cyan]sleep[/], [cyan]wake[/], [cyan]clean[/], [cyan]medicine[/], [cyan]scold[/], [cyan]train[/], [cyan]trick [name][/], [cyan]quit[/]"
    last_action_message = ""

    while not pet.is_dead:
        os.system('cls' if os.name == 'nt' else 'clear')
        auto_action_message = None; auto_action_success = False
        if pet.awake and pet.energy < AUTO_SLEEP_ENERGY_THRESHOLD: auto_action_message, auto_action_success = pet.attempt_sleep()
        elif not pet.awake:
            wake_reason = None
            if pet.energy >= AUTO_WAKE_ENERGY_THRESHOLD: wake_reason = "fully rested"
            elif pet.hunger > CRITICAL_HUNGER_THRESHOLD: wake_reason = "critically hungry"
            elif pet.health < CRITICAL_HEALTH_THRESHOLD + 5: wake_reason = "critically unhealthy"
            if wake_reason: auto_action_message, auto_action_success = pet.wake(reason=wake_reason)

        needs_updated = pet.update_needs()
        if pet.is_dead: break
        needs_msg = pet.get_needs_update_message()

        pet.display_status() 

        message_to_display = "" 
        if needs_msg: message_to_display += needs_msg + "\n"
        if last_action_message: message_to_display += last_action_message + "\n"; last_action_message = ""
        if auto_action_message: message_to_display += auto_action_message + "\n"
        alerts = pet.get_notifications()
        if alerts:
            alert_texts = []
            if "hunger" in alerts: alert_texts.append("[bold red]Hunger![/]")
            if "happiness" in alerts: alert_texts.append("[bold red]Unhappy![/]")
            if "health" in alerts: alert_texts.append("[bold red]Health![/]")
            if "energy" in alerts: alert_texts.append("[bold yellow]Tired![/]")
            if "poop" in alerts: alert_texts.append("[bold yellow]Dirty![/]")
            message_to_display += f"{ASCII_ART['alert']} " + " ".join(alert_texts) + "\n"

        if message_to_display: console.print(message_to_display.strip())

        if auto_action_success: time.sleep(1.0); continue

        command = ""; # Get input
        try: command = console.input(f"Command ({available_commands_display}): ").lower().strip()
        except EOFError: command = "quit"
        except KeyboardInterrupt: command = "quit"; console.print("\n[bold yellow]Quitting on user interrupt...[/bold yellow]")

        action_taken = False; message = None 
        if command.startswith("feed"):
            parts = command.split(maxsplit=1); food_item = parts[1] if len(parts) > 1 else None
            if food_item: message, action_taken = pet.feed(food_item)
            else: message = "[red]Usage: feed [item]. Avail: " + ', '.join(FOOD_ITEMS.keys()) + "[/red]"; action_taken = False
        elif command == "play": message, action_taken = pet.play_rps()
        elif command == "sleep": message, action_taken = pet.attempt_sleep()
        elif command == "wake": message, action_taken = pet.wake()
        elif command == "clean": message, action_taken = pet.clean()
        elif command == "medicine": message, action_taken = pet.give_medicine()
        elif command == "scold": message, action_taken = pet.scold()
        elif command == "train": message, action_taken = pet.train()
        elif command.startswith("trick"):
             parts = command.split(maxsplit=1); trick_name = parts[1] if len(parts) > 1 else None
             if trick_name: message, action_taken = pet.do_trick(trick_name)
             else: message = "[red]Usage: trick [name]. Known: " + ", ".join(pet.tricks_learned) + "[/red]"; action_taken = False
        elif command == "quit": save_pet(pet); break
        else: message = "[bold red]Unknown command.[/bold red]"; action_taken = False
        if message: last_action_message = message

    # --- Game Over / Quit ---
    os.system('cls' if os.name == 'nt' else 'clear')
    if pet.is_dead:
        pet.display_status(); console.print(pet.get_needs_update_message())
        console.print("\n[yellow]Game Over.[/yellow]")
        if console.input("Start over with a new Pygochi? (yes/no): ").lower().strip() in ["y", "yes"]:
             if SAVE_FILE.exists(): SAVE_FILE.unlink()
             console.print("[green]Creating new save...[/green]")
             create_new_pet(is_restart=True); console.print("[bold]Run the program again to start![/bold]")
        else: console.print("[blue]Goodbye.[/blue]")
    else: console.print(f"[bold blue]Goodbye! {pet.name} state saved.[/bold blue]")