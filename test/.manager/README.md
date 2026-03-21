# manage — Module Browser & Test Runner

Browse module documentation and run tests interactively.

## Usage

```bash
# Interactive: pick a module, see docs, run tests
python test/.manager/manager.py

# Show specific module docs + run option
python test/.manager/manager.py alu

# Show multiple modules
python test/.manager/manager.py cpu decoder pc

# Run tests directly (no interactive prompts)
python test/.manager/manager.py --run alu

# Substring matching works
python test/.manager/manager.py kogge
```

## Interactive mode

After selecting a module, the manager shows:
- Module documentation (from `docs/`)
- A prompt with options:
  - `r` — run tests via `make`
  - `m` — run `make` with custom args (e.g. `FST=`)
  - `q` — quit

## Via root manager

```bash
python manage.py test
python manage.py test -- alu
```

## Dependencies

- [Rich](https://github.com/Textualize/rich) (`pip install rich`)
