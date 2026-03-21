# Sample testbench for a Tiny Tapeout project

This is a sample testbench for a Tiny Tapeout project. It uses [cocotb](https://docs.cocotb.org/en/stable/) to drive the DUT and check the outputs.
See below to get started or for more information, check the [website](https://tinytapeout.com/hdl/testing/).

## Structure

Each module has its own subdirectory with a testbench, test script, and Makefile:

```
test/
  <module>/
    tb_<module>.v     # Verilog testbench
    test_<module>.py  # cocotb test script
    Makefile          # build & run
  artifacts/          # shared build artifacts (gitignored)
```

## Setting up

1. Edit the module's `Makefile` and modify `VERILOG_SOURCES` to point to your Verilog files.
2. Edit `tb_<module>.v` and set up your DUT instantiation.

## How to run

To run a specific module's test:

```sh
cd test/<module>
make -B
```

For example, to test the ALU:

```sh
cd test/alu
make -B
```

To run the top-level RTL simulation:

```sh
cd test/top
make -B
```

To run gatelevel simulation, first harden your project and copy `../runs/wokwi/results/final/verilog/gl/{your_module_name}.v` to `test/top/gate_level_netlist.v`.

Then run:

```sh
cd test/top
make -B GATES=yes
```

## How to view the waveform file

Waveform files are generated in `test/artifacts/`.

Using GTKWave

```sh
gtkwave test/artifacts/tb_alu.fst
```

Using Surfer

```sh
surfer test/artifacts/tb_alu.fst
```
