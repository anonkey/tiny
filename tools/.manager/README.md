# manage — Tools Manager

List, browse, and run project tools interactively.

## Usage

```bash
# Interactive: pick a tool, see examples, type args to run
python tools/.manager/manager.py

# Interactive params for a specific tool
python tools/.manager/manager.py waveform

# Direct run with passthrough args (no interactive prompts)
python tools/.manager/manager.py assembler -- example.asm -o out.hex
python tools/.manager/manager.py waveform -- wave spi "sclk" "cs_n"

# Substring matching works
python tools/.manager/manager.py wave
```

## Interactive mode

After selecting a tool, the manager shows:
- Usage line from `--help`
- Numbered example commands from the tool's README
- A prompt where you can type an example number or custom arguments

## Via root manager

```bash
python manage.py tools
python manage.py tools -- waveform
```

## Dependencies

- [Rich](https://github.com/Textualize/rich) (`pip install rich`)
