# Top War Emulator Bot

Automates *Top War: Battle Game* on an Android emulator. It starts the emulator, launches the game, and loops:

1. **Dismisses popups and ads** (`close_*` buttons)
2. **Collects resources, claims free rewards, and taps alliance help** (`collect_*`, `claim_*`, `help_*`)
3. **Merges units.** It finds every pair of identical units on the base and drags them together, lowest level first, so slots free up and merges chain upward. It rescans until no pairs are left.
4. **Fills empty slots** with the buy button (optional), then merges again.

> Botting is against Top War's Terms of Service and can get your account banned. Use at your own risk.

## Setup

```bash
pip install -r requirements.txt
```

**Emulator:** pick one:
- **Android Studio AVD:** create a device with a *Google Play* system image at **1280x720**, name it `TopWar`, install Top War from the Play Store, and keep `mode: avd` in `config.yaml`.
- **BlueStacks / LDPlayer / MuMu:** turn on ADB in the emulator settings, set `mode: connect` and `address` (BlueStacks/LDPlayer `127.0.0.1:5555`, MuMu `127.0.0.1:7555`).

Check the package name with `adb shell pm list packages | grep -i war` and update `game.package` if it differs.

## Capture templates (one-time)

The bot recognises things by image, so capture them from **your** screen at the resolution you'll run at:

```bash
python -m topwar_bot.capture crop units/tank_01        # box a level-1 tank, press Enter
python -m topwar_bot.capture crop units/tank_02
python -m topwar_bot.capture crop buttons/close_x
python -m topwar_bot.capture crop buttons/collect_gold
python -m topwar_bot.capture crop buttons/claim_chest
python -m topwar_bot.capture crop buttons/help_alliance
python -m topwar_bot.capture crop buttons/buy_unit
python -m topwar_bot.capture test units/tank_01        # check that it matches
```

Unit names must be `<type>_<level>` (`tank_05`, `plane_12`, `ship_03`). Crop tightly around the unit's body and leave out the background, so units on different tiles still match. Capture every level you currently have.

## Run

```bash
python -m topwar_bot.bot              # run forever (Ctrl+C to stop)
python -m topwar_bot.bot --cycles 20 -v
```

## Tuning for efficiency (`config.yaml` → `bot`)

| Setting | Effect |
|---|---|
| `battlefield_region` | `[x1,y1,x2,y2]` of the merge grid. Speeds up scans and stops false matches |
| `base_slots` | Number of grid slots. Turns on auto-buy into empty slots |
| `max_merge_level` | Stop merging at a level (e.g. to keep units for a formation) |
| `merge_delay`, `tap_delay`, `cycle_delay` | Lower = faster, but too low and the game drops inputs |
| `unit_threshold` | Raise if units are confused, lower if they're missed |

## Tests

```bash
python -m pytest tests
```

The tests use synthetic screens and a fake device, so they need no emulator.
