import json
import time
import sys
import os
import random
import configparser
from pathlib import Path
from datetime import timedelta
from collections import deque

from rich.console import Console, Group
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn
from rich.text import Text
from rich.align import Align
from rich.markup import escape

# --- Configuration Loading ---
config = configparser.ConfigParser()
CONFIG_FILE = Path(__file__).parent / "config.ini"

DEFAULT_CONFIG = {
    'Timing': {'update_interval_seconds': '30', 'seconds_per_day': '86400'},
    'StatsDecay': {'stat_decay_amount': '2', 'energy_decay_awake': '2', 'discipline_decay': '1'},
    'StatsGain': {'energy_regen_sleep': '8', 'happiness_regen_sleep': '2', 'health_regen_clean_fed': '1', 'medicine_health_gain': '40', 'scold_discipline_gain': '15', 'pet_happiness_gain': '5'},
    'StatsLoss': {'scold_happiness_loss': '10', 'train_energy_cost': '15', 'trick_energy_cost': '15', 'health_decay_poop': '3', 'health_decay_hunger': '2'},
    'Thresholds': {'auto_sleep_energy': '15', 'auto_wake_energy': '100', 'max_hunger_to_sleep': '75', 'critical_hunger': '90', 'critical_happiness': '10', 'critical_health': '15', 'critical_energy': '5'},
    'Limits': {'max_poop': '4'},
    'Death': {'max_age_days': '20', 'max_time_critical_seconds': '3600'},
    'Mechanics': {'poop_window_seconds_multiplier': '4', 'poop_chance_base': '0.05', 'poop_chance_after_meal': '0.40', 'refusal_chance_divisor': '150'},
    'Evolution': {'stage_child_age': '1', 'stage_teen_age': '5', 'stage_adult_age': '10', 'stage_senior_age': '15'},
    'Training': {'train_success_discipline_factor': '150', 'train_success_happiness_factor': '200', 'train_discipline_gain': '5', 'train_happiness_gain': '10', 'train_failure_discipline_loss': '-2', 'train_failure_happiness_loss': '-10', 'trick_dance_happiness_boost': '25', 'trick_sing_happiness_boost': '20', 'trick_fetch_happiness_boost': '15'},
    'UI': {'event_log_size': '10', 'use_emojis': 'true'},
    'Food': {'apple': '15;5;1;0.05', 'cake': '25;15;-2;0.20', 'veg': '10;2;3;0.02', 'fish': '20;8;2;0.10', 'treat': '5;25;-1;0.15', 'vitamins': '2;0;10;0.01'}
}

if CONFIG_FILE.exists():
    config.read(CONFIG_FILE)
else:
    print(f"[yellow]Warning: config.ini not found. Using default values.[/yellow]")
    config.read_dict(DEFAULT_CONFIG)

def get_config_value(section, key, type_func=str, fallback_section=None, fallback_key=None):
    """Helper to get config value with fallback to default."""
    try:
        return type_func(config.get(section, key))
    except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
        print(f"[yellow]Warning: Missing/invalid config [{section}].{key}. Using default.[/yellow]")
        fallback_section = fallback_section or section
        fallback_key = fallback_key or key
        return type_func(DEFAULT_CONFIG[fallback_section][fallback_key])

# --- Load Constants from Config ---
UPDATE_INTERVAL_SECONDS = get_config_value('Timing', 'update_interval_seconds', int)
SECONDS_PER_DAY = get_config_value('Timing', 'seconds_per_day', int)
STAT_DECAY_AMOUNT = get_config_value('StatsDecay', 'stat_decay_amount', int)
ENERGY_DECAY_AWAKE = get_config_value('StatsDecay', 'energy_decay_awake', int)
DISCIPLINE_DECAY = get_config_value('StatsDecay', 'discipline_decay', int)
ENERGY_REGEN_SLEEP = get_config_value('StatsGain', 'energy_regen_sleep', int)
HAPPINESS_REGEN_SLEEP = get_config_value('StatsGain', 'happiness_regen_sleep', int)
HEALTH_REGEN_CLEAN_FED = get_config_value('StatsGain', 'health_regen_clean_fed', int)
MEDICINE_HEALTH_GAIN = get_config_value('StatsGain', 'medicine_health_gain', int)
SCOLD_DISCIPLINE_GAIN = get_config_value('StatsGain', 'scold_discipline_gain', int)
PET_HAPPINESS_GAIN = get_config_value('StatsGain', 'pet_happiness_gain', int)
SCOLD_HAPPINESS_LOSS = get_config_value('StatsLoss', 'scold_happiness_loss', int)
TRAIN_ENERGY_COST = get_config_value('StatsLoss', 'train_energy_cost', int)
TRICK_ENERGY_COST = get_config_value('StatsLoss', 'trick_energy_cost', int)
HEALTH_DECAY_POOP = get_config_value('StatsLoss', 'health_decay_poop', int)
HEALTH_DECAY_HUNGER = get_config_value('StatsLoss', 'health_decay_hunger', int)
AUTO_SLEEP_ENERGY_THRESHOLD = get_config_value('Thresholds', 'auto_sleep_energy', int)
AUTO_WAKE_ENERGY_THRESHOLD = get_config_value('Thresholds', 'auto_wake_energy', int)
MAX_HUNGER_TO_SLEEP = get_config_value('Thresholds', 'max_hunger_to_sleep', int)
CRITICAL_HUNGER_THRESHOLD = get_config_value('Thresholds', 'critical_hunger', int)
CRITICAL_HAPPINESS_THRESHOLD = get_config_value('Thresholds', 'critical_happiness', int)
CRITICAL_HEALTH_THRESHOLD = get_config_value('Thresholds', 'critical_health', int)
CRITICAL_ENERGY_THRESHOLD = get_config_value('Thresholds', 'critical_energy', int)
MAX_POOP = get_config_value('Limits', 'max_poop', int)
MAX_AGE_DAYS = get_config_value('Death', 'max_age_days', int)
MAX_TIME_CRITICAL_SECONDS = get_config_value('Death', 'max_time_critical_seconds', int)
POOP_WINDOW_SECONDS = UPDATE_INTERVAL_SECONDS * get_config_value('Mechanics', 'poop_window_seconds_multiplier', int)
POOP_CHANCE_BASE = get_config_value('Mechanics', 'poop_chance_base', float)
POOP_CHANCE_AFTER_MEAL = get_config_value('Mechanics', 'poop_chance_after_meal', float)
REFUSAL_CHANCE_DIVISOR = get_config_value('Mechanics', 'refusal_chance_divisor', int)
STAGE_CHILD_AGE = get_config_value('Evolution', 'stage_child_age', int)
STAGE_TEEN_AGE = get_config_value('Evolution', 'stage_teen_age', int)
STAGE_ADULT_AGE = get_config_value('Evolution', 'stage_adult_age', int)
STAGE_SENIOR_AGE = get_config_value('Evolution', 'stage_senior_age', int)
TRAIN_SUCCESS_DISCIPLINE_FACTOR = get_config_value('Training', 'train_success_discipline_factor', float)
TRAIN_SUCCESS_HAPPINESS_FACTOR = get_config_value('Training', 'train_success_happiness_factor', float)
TRAIN_DISCIPLINE_GAIN = get_config_value('Training', 'train_discipline_gain', int)
TRAIN_HAPPINESS_GAIN = get_config_value('Training', 'train_happiness_gain', int)
TRAIN_FAILURE_DISCIPLINE_LOSS = get_config_value('Training', 'train_failure_discipline_loss', int)
TRAIN_FAILURE_HAPPINESS_LOSS = get_config_value('Training', 'train_failure_happiness_loss', int)
TRICK_DANCE_HAPPINESS_BOOST = get_config_value('Training', 'trick_dance_happiness_boost', int)
TRICK_SING_HAPPINESS_BOOST = get_config_value('Training', 'trick_sing_happiness_boost', int)
TRICK_FETCH_HAPPINESS_BOOST = get_config_value('Training', 'trick_fetch_happiness_boost', int)
EVENT_LOG_SIZE = get_config_value('UI', 'event_log_size', int)
USE_EMOJIS = config.getboolean('UI', 'use_emojis', fallback=DEFAULT_CONFIG['UI']['use_emojis']=='true')

# --- Load Food Items from Config ---
FOOD_ITEMS = {}
try:
    for food_name, data_str in config.items('Food'):
        parts = data_str.split(';')
        if len(parts) == 4:
            FOOD_ITEMS[food_name] = { "hunger_restore": int(parts[0]), "happiness_boost": int(parts[1]), "health_boost": int(parts[2]), "weight_gain": float(parts[3]) }
except configparser.NoSectionError:
     print("[yellow]Warning: [Food] section missing in config.ini. Using defaults.[/yellow]")
     config.read_dict({'Food': DEFAULT_CONFIG['Food']}) # Add default section temporarily
     for food_name, data_str in config.items('Food'):
        parts = data_str.split(';')
        if len(parts) == 4: FOOD_ITEMS[food_name] = { "hunger_restore": int(parts[0]),"happiness_boost": int(parts[1]),"health_boost": int(parts[2]), "weight_gain": float(parts[3]) }
if not FOOD_ITEMS:
     print("[red]Error: No food items loaded. Using minimal default.[/red]")
     FOOD_ITEMS['apple'] = { "hunger_restore": 15, "happiness_boost": 5, "health_boost": 1, "weight_gain": 0.05 }

# --- File Paths ---
SAVE_FILE_DIR = Path.home() / ".terminal_tamagotchi"
SAVE_FILE = SAVE_FILE_DIR / "pet_save.json"

# --- Global Objects & Emojis / ASCII ---
console = Console()
if USE_EMOJIS:
    ASCII_ART = { "happy": "😺", "neutral": "🐱", "sad": "😿", "sleeping": "😴", "sick": "🤢", "dead": "💀", "poop": "💩", "angry": "😠", "playing": "🧶", "eating": "😋", "thinking": "🤔", "dancing": "🎶", "singing": "🎤", "fetching": "🦴", "alert": ":warning:" }
else:
    ASCII_ART = { "happy": "(^.^)", "neutral": "(._.)", "sad": "(~_~)", "sleeping": "(-.-)zz", "sick": "(x.x)", "dead": "x_x", "poop": "*", "angry": ">.<", "playing": "o", "eating": ":P", "thinking": "(?)", "dancing": "/o\\", "singing": "~", "fetching": "=", "alert": "!" }


# --- Helper Function ---
def create_progress_bar( label, completed, total, low_color, mid_color, high_color, low_threshold, high_threshold, reverse_colors=False, alert=False):
    prefix = f"{ASCII_ART['alert']} " if alert else ""
    progress = Progress( TextColumn(f"{prefix}{label}:{' '*(10-len(label))}"), BarColumn(bar_width=20), TextColumn("{task.percentage:>3.0f}%"), ); style = mid_color
    label_style = "blink " + style if alert else style
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
        self.time_hunger_critical_start = 0; self.time_happiness_critical_start = 0
        self.tricks_learned = []
        self.event_log = deque(maxlen=EVENT_LOG_SIZE)
        self.illness_type = None
        self._add_event("Born!")

    def _add_event(self, message):
        timestamp = time.strftime("%H:%M:%S")
        self.event_log.append(f"[{timestamp}] {escape(message)}")

    def get_stage(self):
        age = self.get_age_in_days()
        if age < STAGE_CHILD_AGE: return "Baby"
        if age < STAGE_TEEN_AGE: return "Child"
        if age < STAGE_ADULT_AGE: return "Teen"
        if age < STAGE_SENIOR_AGE: return "Adult"
        return "Senior"

    def get_age_in_days(self): return int((time.time() - self.birthday_timestamp) // SECONDS_PER_DAY)

    def get_mood_art(self):
        stage = self.get_stage()
        base_emoji = ASCII_ART["neutral"]
        if stage == "Baby": base_emoji = "👶" if USE_EMOJIS else "(o.o)"
        elif stage == "Child": base_emoji = "🧒" if USE_EMOJIS else "(^_^)"
        elif stage == "Teen": base_emoji = "🧑" if USE_EMOJIS else "(._.)"
        elif stage == "Adult": base_emoji = "🐱" if USE_EMOJIS else "(._.)"
        elif stage == "Senior": base_emoji = "👴" if USE_EMOJIS else "(-.-)"

        if self.is_dead: return ASCII_ART["dead"]
        if self.illness_type: return ASCII_ART["sick"]
        if self.health < CRITICAL_HEALTH_THRESHOLD: return ASCII_ART["sick"]
        if not self.awake: return ASCII_ART["sleeping"]
        if self.happiness < CRITICAL_HAPPINESS_THRESHOLD or self.hunger > CRITICAL_HUNGER_THRESHOLD or self.energy < CRITICAL_ENERGY_THRESHOLD or self.health < 50: return ASCII_ART["sad"]
        if self.happiness > 75 and self.hunger < 30 and self.energy > 60 and self.health > 80: return ASCII_ART["happy"]
        return base_emoji

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
            self.is_dead = True; self._last_needs_message = f"[bold red on white] !!! {self.name} has {death_reason} !!! [/bold red on white]"; self.awake = False; self._add_event(f"Died ({death_reason})")

    def update_needs(self):
        if self.is_dead: return False
        now = time.time(); elapsed_seconds = now - self.last_updated_timestamp; intervals_passed = int(elapsed_seconds // UPDATE_INTERVAL_SECONDS)
        if intervals_passed <= 0: return False

        needs_changed = False; health_change_msg = ""; illness_msg = ""
        stage = self.get_stage()

        for i in range(intervals_passed):
            self._check_death_conditions(self.last_updated_timestamp + i * UPDATE_INTERVAL_SECONDS)
            if self.is_dead: return True

            needs_changed = True
            current_interval_time = ( self.last_updated_timestamp + (i + 1) * UPDATE_INTERVAL_SECONDS ); current_health = self.health
            decay_modifier = 1.5 if stage == "Senior" else (0.8 if stage == "Baby" else 1.0)
            self.discipline = max(0, self.discipline - int(DISCIPLINE_DECAY * decay_modifier))

            if self.awake:
                self.hunger = min(100, self.hunger + int(STAT_DECAY_AMOUNT * decay_modifier))
                self.energy = max(0, self.energy - int(ENERGY_DECAY_AWAKE * decay_modifier))
                happiness_drain = int(STAT_DECAY_AMOUNT * decay_modifier)
                if self.hunger > 75: happiness_drain += STAT_DECAY_AMOUNT // 2
                if self.energy < 25: happiness_drain += STAT_DECAY_AMOUNT // 2
                if current_health < 50: happiness_drain += STAT_DECAY_AMOUNT
                if self.illness_type: happiness_drain += STAT_DECAY_AMOUNT
                if self.poop_count > 0: happiness_drain += self.poop_count * 2
                self.happiness = max(0, self.happiness - happiness_drain)
                time_since_meal = current_interval_time - self.last_meal_timestamp if self.last_meal_timestamp > 0 else float('inf')
                poop_chance = POOP_CHANCE_AFTER_MEAL if time_since_meal <= POOP_WINDOW_SECONDS else POOP_CHANCE_BASE
                if random.random() < poop_chance and self.poop_count < MAX_POOP + 2: self.poop_count += 1
            else: # Sleeping
                self.energy = min(100, self.energy + ENERGY_REGEN_SLEEP)
                if current_health > CRITICAL_HEALTH_THRESHOLD and not self.illness_type: self.happiness = min(100, self.happiness + HAPPINESS_REGEN_SLEEP)

            health_change_this_interval = 0
            if self.poop_count >= MAX_POOP: health_change_this_interval -= HEALTH_DECAY_POOP
            if self.hunger >= CRITICAL_HUNGER_THRESHOLD: health_change_this_interval -= HEALTH_DECAY_HUNGER
            if self.illness_type == "Cold": health_change_this_interval -= 2
            if self.illness_type == "Stomachache": health_change_this_interval -= 3
            if self.poop_count == 0 and self.hunger < 50 and self.energy > 30 and self.awake and not self.illness_type: health_change_this_interval += HEALTH_REGEN_CLEAN_FED
            self.health = max(0, min(100, self.health + health_change_this_interval))

            if not self.illness_type and not self.is_dead:
                 if current_health < 50 and random.random() < 0.05: # Chance for cold if health is low
                      self.illness_type = "Cold"; illness_msg = f"[yellow]{self.name} caught a Cold! {ASCII_ART['sick']}[/yellow]"; self._add_event("Caught a Cold")
                 elif self.hunger > 95 and random.random() < 0.1: # Chance for stomachache if very hungry
                      self.illness_type = "Stomachache"; illness_msg = f"[yellow]{self.name} has a Stomachache! {ASCII_ART['sick']}[/yellow]"; self._add_event("Got a Stomachache")

            if health_change_this_interval < 0 and not health_change_msg:
                 if self.poop_count >= MAX_POOP : health_change_msg = f"[yellow]Health declining due to mess![/yellow]"
                 elif self.hunger >= CRITICAL_HUNGER_THRESHOLD: health_change_msg = f"[yellow]Health declining due to hunger![/yellow]"

        self.last_updated_timestamp += intervals_passed * UPDATE_INTERVAL_SECONDS
        interval_msg = f"[dim]({intervals_passed} update intervals processed)[/dim]" if needs_changed else ""
        self._last_needs_message = interval_msg
        if health_change_msg: self._last_needs_message += ("\n" if self._last_needs_message else "") + health_change_msg
        if illness_msg: self._last_needs_message += ("\n" if self._last_needs_message else "") + illness_msg
        self._check_death_conditions(now)
        return needs_changed

    def _should_refuse(self, action_difficulty=0):
        if self.happiness < 20: refusal_base_chance = 0.3
        elif self.energy < 15: refusal_base_chance = 0.2
        else: refusal_base_chance = 0.05
        discipline_modifier = max(0, (100 - self.discipline)) / REFUSAL_CHANCE_DIVISOR
        refusal_chance = refusal_base_chance + discipline_modifier
        return random.random() < refusal_chance

    def _get_refusal_message(self):
        if self.happiness < 20: return f"[orange1]{self.name} {ASCII_ART['sad']} is too unhappy to listen.[/orange1]"
        if self.energy < 15: return f"[orange1]{self.name} {ASCII_ART['sleeping']} is too tired.[/orange1]"
        return f"[orange1]{self.name} {ASCII_ART['angry']} ignores you.[/orange1]"

    def feed(self, food_name: str):
        if not self.awake: return f"[yellow]{self.name} {ASCII_ART['sleeping']} is sleeping.[/yellow]", False
        if self._should_refuse(): return self._get_refusal_message(), False
        if food_name not in FOOD_ITEMS: return f"[red]Unknown food: {food_name}. Try: {', '.join(FOOD_ITEMS.keys())}[/red]", False
        food = FOOD_ITEMS[food_name]
        if self.illness_type == "Stomachache": return f"[yellow]{self.name} {ASCII_ART['sick']} has a stomachache and doesn't want to eat {food_name}.[/yellow]", False
        hunger_decrease = food["hunger_restore"]; happiness_increase = food["happiness_boost"]; health_change = food["health_boost"]; weight_increase = food["weight_gain"]
        if self.health < 40:
            hunger_decrease = max(1, hunger_decrease // 3); happiness_increase = max(0, happiness_increase // 2)
            msg_prefix = f"[yellow]{self.name} {ASCII_ART['sick']} is feeling unwell and nibbles the {food_name}.[/yellow]"
        elif self.health < 70: hunger_decrease = max(1, int(hunger_decrease * 0.75)); msg_prefix = f"[yellow]{self.name} eats the {food_name} slowly.[/yellow]"
        else: msg_prefix = f"[green]{ASCII_ART['eating']} {self.name} eats the {food_name}.[/green]"
        self.hunger = max(0, self.hunger - hunger_decrease); self.happiness = min(100, max(0, self.happiness + happiness_increase)); self.health = min(100, max(0, self.health + health_change)); self.weight += weight_increase; self.last_meal_timestamp = time.time()
        msg = msg_prefix; msg += f"\nHunger -{hunger_decrease}"
        if happiness_increase != 0: msg += f", Happiness {'+' if happiness_increase > 0 else ''}{happiness_increase}"
        if health_change != 0: msg += f", Health {'+' if health_change > 0 else ''}{health_change}"
        msg += f", Weight +{weight_increase:.2f}"; self._add_event(f"Ate {food_name}"); return msg, True

    def play_game(self, game_type=None):
        if not self.awake: return f"[yellow]{self.name} {ASCII_ART['sleeping']} is sleeping.[/yellow]", False
        if self.illness_type == "Cold": return f"[yellow]{self.name} {ASCII_ART['sick']} has a cold and shouldn't play.[/yellow]", False
        if self.health < 50: return f"[yellow]{self.name} {ASCII_ART['sick']} is too unwell to play.[/yellow]", False
        if self.hunger > 80: return f"[yellow]{self.name} {ASCII_ART['sad']} is too hungry to play.[/yellow]", False
        if self.energy < PLAY_ENERGY_COST + 5: return f"[yellow]{self.name} {ASCII_ART['sad']} is too tired to play.[/yellow]", False
        if self.poop_count > MAX_POOP // 2: return f"[yellow]{self.name} {ASCII_ART['sad']} doesn't want to play in this mess.[/yellow]", False
        if self._should_refuse(): return self._get_refusal_message(), False

        available_games = ["rps", "guess"]
        if game_type and game_type in available_games: chosen_game = game_type
        elif game_type: return f"[red]Unknown game '{game_type}'. Available: {', '.join(available_games)}[/red]", False
        else: chosen_game = random.choice(available_games)

        if chosen_game == "rps": return self._play_rps()
        elif chosen_game == "guess": return self._play_guess_number()
        return "[red]Error: No game selected.[/red]", False

    def _play_rps(self):
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
        time.sleep(1.5); msg = f"{outcome_msg}\nHappiness {'+' if happiness_change >=0 else ''}{happiness_change}, Hunger +{hunger_increase}, Energy -{energy_decrease}."; self._add_event(f"Played RPS ({outcome_msg.split('!')[0].split('[')[-1]})"); return msg, True

    def _play_guess_number(self):
        console.print(f"[cyan]Let's play Guess the Number! {ASCII_ART['playing']}[/cyan]")
        lower_bound, upper_bound = 1, 10; pet_number = random.randint(lower_bound, upper_bound); guesses_left = 3; won = False
        while guesses_left > 0:
            try:
                user_guess_str = console.input(f"Guess a number between {lower_bound} and {upper_bound} ({guesses_left} guesses left): ")
                user_guess = int(user_guess_str)
                if not (lower_bound <= user_guess <= upper_bound): console.print(f"[red]Number must be between {lower_bound} and {upper_bound}.[/red]"); continue
            except ValueError: console.print("[red]Invalid input. Please enter a number.[/red]"); continue
            guesses_left -= 1
            if user_guess == pet_number: won = True; break
            elif user_guess < pet_number: console.print("[yellow]Too low![/yellow]")
            else: console.print("[yellow]Too high![/yellow]")
        outcome_msg = ""; happiness_change = 0
        if won: outcome_msg = f"[bold green]You guessed it! The number was {pet_number}.[/bold green]"; happiness_change = 20
        else: outcome_msg = f"[bold red]Out of guesses! The number was {pet_number}.[/bold red]"; happiness_change = 0
        hunger_increase = 3; energy_decrease = PLAY_ENERGY_COST - 5
        self.happiness = min(100, max(0, self.happiness + happiness_change)); self.hunger = min(100, self.hunger + hunger_increase); self.energy = max(0, self.energy - energy_decrease)
        time.sleep(1.5); msg = f"{outcome_msg}\nHappiness {'+' if happiness_change >=0 else ''}{happiness_change}, Hunger +{hunger_increase}, Energy -{energy_decrease}."; self._add_event(f"Played Guess ({'Won' if won else 'Lost'})"); return msg, True

    def attempt_sleep(self):
        if not self.awake: return f"[yellow]{self.name} is already sleeping.[/yellow]", False
        if self.hunger > MAX_HUNGER_TO_SLEEP: return f"[yellow]{self.name} {ASCII_ART['sad']} is too hungry to sleep (Hunger: {self.hunger}/{MAX_HUNGER_TO_SLEEP}).[/yellow]", False
        if self.health < CRITICAL_HEALTH_THRESHOLD + 10: return f"[yellow]{self.name} {ASCII_ART['sick']} is too unwell to sleep properly.[/yellow]", False
        self.awake = False; msg = f"[purple]{ASCII_ART['sleeping']} {self.name} goes to sleep.[/purple]"; self._add_event("Went to sleep"); return msg, True

    def wake(self, reason: str | None = None):
        if self.awake: return None, False
        self.awake = True; wake_message = f"[purple]:sunny: {self.name} wakes up!"
        if reason: wake_message += f" ({reason})"
        else: wake_message += f" (Energy: {self.energy}/100)"
        self.update_needs(); self._add_event(f"Woke up ({reason or 'Manually'})"); return wake_message, True

    def clean(self):
        if self.poop_count == 0: return f"[yellow]Nothing to clean! ✨[/yellow]", False
        cleaned_count = self.poop_count; self.poop_count = 0; happiness_increase = min(15, cleaned_count * 3); self.happiness = min(100, self.happiness + happiness_increase)
        msg = f"[cyan]:sparkles: Cleaned up {cleaned_count} {ASCII_ART['poop']}(s). Happiness +{happiness_increase}.[/cyan]"; self._add_event(f"Cleaned {cleaned_count} poops"); return msg, True

    def give_medicine(self):
        illness_cured = self.illness_type is not None; health_boosted = self.health < 95
        if not illness_cured and not health_boosted : return f"[yellow]{self.name} doesn't need medicine.[/yellow]", False
        msg = f"[magenta]:pill: {self.name} took medicine.[/magenta]"
        if illness_cured: msg += f" The {self.illness_type} is gone!"; self._add_event(f"Cured {self.illness_type}"); self.illness_type = None
        if health_boosted: health_increase = MEDICINE_HEALTH_GAIN; self.health = min(100, self.health + health_increase); msg += f" Health +{health_increase}."; self._add_event("Took medicine for health")
        self.happiness = max(0, self.happiness - 5); msg += f"\n[magenta]Happiness -5 (bad taste!).[/magenta]"
        return msg, True

    def scold(self):
        if not self.awake: return f"[yellow]{self.name} {ASCII_ART['sleeping']} is sleeping.[/yellow]", False
        discipline_gain = SCOLD_DISCIPLINE_GAIN; happiness_loss = SCOLD_HAPPINESS_LOSS
        self.discipline = min(100, self.discipline + discipline_gain); self.happiness = max(0, self.happiness - happiness_loss)
        msg = f"[orange1]{ASCII_ART['angry']} You scold {self.name}. Discipline +{discipline_gain}, Happiness -{happiness_loss}.[/orange1]"; self._add_event("Was scolded"); return msg, True

    def train(self, trick_to_learn=None):
        stage = self.get_stage()
        if stage == "Baby": return "[yellow]Babies are too young to train seriously.[/yellow]", False
        if not self.awake: return f"[yellow]{self.name} {ASCII_ART['sleeping']} is sleeping.[/yellow]", False
        if self.energy < TRAIN_ENERGY_COST: return f"[yellow]{self.name} {ASCII_ART['sad']} is too tired to focus.[/yellow]", False
        if self.happiness < 40: return f"[yellow]{self.name} {ASCII_ART['sad']} isn't happy enough to train.[/yellow]", False

        available_tricks = ["dance", "sing", "fetch"]
        learnable_tricks = [t for t in available_tricks if t not in self.tricks_learned]
        if not learnable_tricks: return f"[green]{self.name} knows all the current tricks![/green]", False

        if trick_to_learn and trick_to_learn in learnable_tricks: target_trick = trick_to_learn
        else: target_trick = random.choice(learnable_tricks)

        success_chance = (self.discipline / TRAIN_SUCCESS_DISCIPLINE_FACTOR) + (self.happiness / TRAIN_SUCCESS_HAPPINESS_FACTOR)
        did_succeed = random.random() < success_chance
        energy_cost = TRAIN_ENERGY_COST; discipline_change = 0; happiness_change = -5; msg = ""

        if did_succeed:
            self.tricks_learned.append(target_trick); discipline_change = TRAIN_DISCIPLINE_GAIN; happiness_change = TRAIN_HAPPINESS_GAIN
            msg = f"[bold green]:sparkles: {self.name} learned to {target_trick}![/bold green]"; self._add_event(f"Learned trick: {target_trick}")
        else:
            discipline_change = TRAIN_FAILURE_DISCIPLINE_LOSS; happiness_change = TRAIN_FAILURE_HAPPINESS_LOSS
            msg = f"[yellow]{self.name} {ASCII_ART['sad']} couldn't figure out how to {target_trick}.[/yellow]"; self._add_event(f"Failed training: {target_trick}")

        self.energy = max(0, self.energy - energy_cost); self.discipline = min(100, max(0, self.discipline + discipline_change)); self.happiness = min(100, max(0, self.happiness + happiness_change))
        msg += f"\nEnergy -{energy_cost}, Discipline {'+' if discipline_change>=0 else ''}{discipline_change}, Happiness {'+' if happiness_change>=0 else ''}{happiness_change}."
        return msg, True

    def do_trick(self, trick_name):
        if not self.awake: return f"[yellow]{self.name} {ASCII_ART['sleeping']} is sleeping.[/yellow]", False
        if trick_name not in self.tricks_learned: return f"[red]{self.name} doesn't know how to {trick_name}. Known: {', '.join(self.tricks_learned)}. Try 'train'.[/red]", False
        if self.energy < TRICK_ENERGY_COST: return f"[yellow]{self.name} {ASCII_ART['sad']} is too tired to perform.[/yellow]", False

        msg = ""; happiness_boost = 0; energy_cost = TRICK_ENERGY_COST
        if trick_name == "dance":
            console.print(f"{self.name} {ASCII_ART['dancing']} starts to dance..."); time.sleep(0.5); console.print("   ♪┏(・o･)┛ ♪ ┗ ( ･o･) ┓♪"); time.sleep(0.7); console.print("      ┗ (･o･ ) ┓ ♪ ┏(･o･)┛"); time.sleep(0.5);
            happiness_boost = TRICK_DANCE_HAPPINESS_BOOST; msg = f"[magenta]{self.name} danced happily! Happiness +{happiness_boost}, Energy -{energy_cost}.[/magenta]"
        elif trick_name == "sing":
             console.print(f"{self.name} {ASCII_ART['singing']} clears its throat..."); time.sleep(0.7); notes = ["Laa", "Meeow", "Purrr", "DoReMi"]; console.print(f"... {random.choice(notes)}! ..."); time.sleep(1.0);
             happiness_boost = TRICK_SING_HAPPINESS_BOOST; msg = f"[magenta]{self.name} sang a little tune! Happiness +{happiness_boost}, Energy -{energy_cost}.[/magenta]"
        elif trick_name == "fetch":
             console.print(f"{self.name} {ASCII_ART['fetching']} looks eager..."); time.sleep(0.7); console.print("... *Wags tail* ..."); time.sleep(1.0);
             happiness_boost = TRICK_FETCH_HAPPINESS_BOOST; msg = f"[magenta]{self.name} fetched imaginary stick! Happiness +{happiness_boost}, Energy -{energy_cost}.[/magenta]"
        else: return f"[red]Unknown trick logic: {trick_name}[/red]", False

        self.happiness = min(100, self.happiness + happiness_boost); self.energy = max(0, self.energy - energy_cost)
        self._add_event(f"Performed trick: {trick_name}")
        return msg, True

    def pet(self):
        if not self.awake: return f"[yellow]{self.name} {ASCII_ART['sleeping']} is sleeping.[/yellow]", False
        happiness_increase = PET_HAPPINESS_GAIN; self.happiness = min(100, self.happiness + happiness_increase)
        msg = f"[pink]You pet {self.name}. Happiness +{happiness_increase}.[/pink]"; self._add_event("Got petted"); return msg, True

    def get_notifications(self):
        alerts = []
        if self.hunger >= CRITICAL_HUNGER_THRESHOLD: alerts.append("hunger")
        if self.happiness <= CRITICAL_HAPPINESS_THRESHOLD: alerts.append("happiness")
        if self.health <= CRITICAL_HEALTH_THRESHOLD: alerts.append("health")
        if self.energy <= CRITICAL_ENERGY_THRESHOLD and self.awake: alerts.append("energy")
        if self.poop_count >= MAX_POOP: alerts.append("poop")
        if self.illness_type: alerts.append("ill")
        return alerts

    def display_status(self):
        if self.is_dead: console.print(Panel(Align.center(f"[bold red]R.I.P.\n{ASCII_ART['dead']}\n{self.name}[/bold red]"), border_style="red")); return

        alerts = self.get_notifications(); panel_border_style = "blink red" if alerts else "blue"
        art = self.get_mood_art(); stage = self.get_stage(); title = f"{self.name} ({stage}) - Age: {self.get_age_in_days()} days"
        status_details = []
        if not self.awake: status_details.append("[purple]Sleeping[/]")
        if self.illness_type: status_details.append(f"[orange1]Ill ({self.illness_type})[/]")
        elif "health" in alerts: status_details.append("[bold red]HEALTH CRITICAL![/]")
        elif self.health < 50: status_details.append("[yellow]Unwell[/]")
        subtitle = " | ".join(status_details) if status_details else "[green]Awake[/]"

        hunger_bar = create_progress_bar("Hunger", self.hunger, 100, "red", "yellow", "green", 40, CRITICAL_HUNGER_THRESHOLD, True, alert="hunger" in alerts)
        happiness_bar = create_progress_bar("Happiness", self.happiness, 100, "red", "yellow", "green", CRITICAL_HAPPINESS_THRESHOLD+10, 70, alert="happiness" in alerts)
        energy_bar = create_progress_bar("Energy", self.energy, 100, "red", "yellow", "green", CRITICAL_ENERGY_THRESHOLD+10, 75, alert="energy" in alerts)
        health_bar = create_progress_bar("Health", self.health, 100, "red", "yellow", "green", CRITICAL_HEALTH_THRESHOLD+10, 80, alert="health" in alerts)
        discipline_bar = create_progress_bar("Discipline", self.discipline, 100, "red", "yellow", "green", 30, 70)
        poop_art_str = (" " + ASCII_ART['poop']) * self.poop_count
        aligned_art = Align.center(f"{art}{poop_art_str}")
        weight_text = f"Weight: {self.weight:.1f}"
        panel_content = Group( aligned_art, hunger_bar, happiness_bar, energy_bar, health_bar, discipline_bar, weight_text )
        console.print(Panel( panel_content, title=title, subtitle=subtitle, border_style=panel_border_style, subtitle_align="right" ))

    def display_log(self):
        console.print("\n--- Event Log ---")
        if not self.event_log: console.print("[dim]No events yet.[/dim]")
        else:
            for event in self.event_log: console.print(event)
        console.print("-----------------\n")
        console.input("[dim]Press Enter to continue...[/dim]")

    def to_dict(self):
        log_list = list(self.event_log)
        return { "name": self.name, "hunger": self.hunger, "happiness": self.happiness, "energy": self.energy, "health": self.health, "discipline": self.discipline, "weight": self.weight, "awake": self.awake, "last_updated_timestamp": self.last_updated_timestamp, "birthday_timestamp": self.birthday_timestamp, "poop_count": self.poop_count, "last_meal_timestamp": self.last_meal_timestamp, "is_dead": self.is_dead, "time_hunger_critical_start": self.time_hunger_critical_start, "time_happiness_critical_start": self.time_happiness_critical_start, "tricks_learned": self.tricks_learned, "event_log": log_list, "illness_type": self.illness_type }
    @classmethod
    def from_dict(cls, data):
        default_birthday = data.get("last_updated_timestamp", time.time()); pet = cls(data.get("name", "Critter"))
        pet.hunger=data.get("hunger",50); pet.happiness=data.get("happiness",50); pet.energy=data.get("energy",100); pet.health=data.get("health",100); pet.discipline=data.get("discipline",50); pet.weight=data.get("weight",1.0); pet.awake=data.get("awake",True); pet.last_updated_timestamp=data.get("last_updated_timestamp",time.time()); pet.birthday_timestamp=data.get("birthday_timestamp",default_birthday); pet.poop_count=data.get("poop_count",0); pet.last_meal_timestamp=data.get("last_meal_timestamp",0); pet.is_dead=data.get("is_dead",False); pet.time_hunger_critical_start=data.get("time_hunger_critical_start",0); pet.time_happiness_critical_start=data.get("time_happiness_critical_start",0);
        pet.tricks_learned = data.get("tricks_learned", []); log_list = data.get("event_log", []); pet.event_log = deque(log_list, maxlen=EVENT_LOG_SIZE); pet.illness_type = data.get("illness_type", None)
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
    available_commands_display = "[cyan]feed [item][/], [cyan]play [game][/], [cyan]sleep[/], [cyan]wake[/], [cyan]clean[/], [cyan]medicine[/], [cyan]scold[/], [cyan]train[/], [cyan]trick [name][/], [cyan]pet[/], [cyan]log[/], [cyan]quit[/]"
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
            alert_texts = []; prefix = ASCII_ART['alert']
            if "hunger" in alerts: alert_texts.append("[bold red]Hunger![/]")
            if "happiness" in alerts: alert_texts.append("[bold red]Unhappy![/]")
            if "health" in alerts: alert_texts.append("[bold red]Health![/]")
            if "energy" in alerts: alert_texts.append("[bold yellow]Tired![/]")
            if "poop" in alerts: alert_texts.append("[bold yellow]Dirty![/]")
            if "ill" in alerts: alert_texts.append(f"[bold orange1]Ill ({pet.illness_type})![/]"); prefix=ASCII_ART['sick']
            message_to_display += f"{prefix} " + " ".join(alert_texts) + "\n"

        if message_to_display: console.print(message_to_display.strip())

        if auto_action_success: time.sleep(1.0); continue

        command = "";
        try: command = console.input(f"Command ({available_commands_display}): ").lower().strip()
        except EOFError: command = "quit"
        except KeyboardInterrupt: command = "quit"; console.print("\n[bold yellow]Quitting on user interrupt...[/bold yellow]")

        action_taken = False; message = None 
        if command.startswith("feed"):
            parts = command.split(maxsplit=1); food_item = parts[1] if len(parts) > 1 else None
            if food_item: message, action_taken = pet.feed(food_item)
            else: message = "[red]Usage: feed [item]. Avail: " + ', '.join(FOOD_ITEMS.keys()) + "[/red]"; action_taken = False
        elif command.startswith("play"):
             parts = command.split(maxsplit=1); game_type = parts[1] if len(parts) > 1 else None
             message, action_taken = pet.play_game(game_type)
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
        elif command == "pet": message, action_taken = pet.pet()
        elif command == "log": pet.display_log(); action_taken = False
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