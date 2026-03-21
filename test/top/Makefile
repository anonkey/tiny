# Makefile
# See https://docs.cocotb.org/en/stable/quickstart.html for more info

# defaults
SIM ?= icarus
FST ?= -fst # Use more efficient FST format
TOPLEVEL_LANG ?= verilog

SRC_DIR = $(PWD)/../../src
PROJECT_SOURCES = kogge-stone.v mux.v dff.v register.v regfile.v alu.v pc.v rom.v decoder.v cpu.v top.v

ifneq ($(GATES),yes)

# RTL simulation:
SIM_BUILD				= ../artifacts/rtl
VERILOG_SOURCES += $(addprefix $(SRC_DIR)/,$(PROJECT_SOURCES))

else

# Gate level simulation:
SIM_BUILD				= ../artifacts/gl
COMPILE_ARGS    += -DGL_TEST
COMPILE_ARGS    += -DFUNCTIONAL
COMPILE_ARGS    += -DSIM
VERILOG_SOURCES += $(PDK_ROOT)/ihp-sg13g2/libs.ref/sg13g2_io/verilog/sg13g2_io.v
VERILOG_SOURCES += $(PDK_ROOT)/ihp-sg13g2/libs.ref/sg13g2_stdcell/verilog/sg13g2_stdcell.v

# this gets copied in by the GDS action workflow
VERILOG_SOURCES += $(PWD)/gate_level_netlist.v

endif

# Allow sharing configuration between design and testbench via `include`:
COMPILE_ARGS 		+= -I$(SRC_DIR)

# Include the testbench sources:
VERILOG_SOURCES += $(PWD)/tb.v
TOPLEVEL = tb

# List test modules to run, separated by commas and without the .py suffix:
COCOTB_TEST_MODULES = test

PYTHON ?= $(PWD)/../../.venv/bin/python
COCOTB_MAKEFILES := $(shell $(PYTHON) -m cocotb_tools.config --makefiles 2>/dev/null || cocotb-config --makefiles 2>/dev/null)

ifeq ($(strip $(COCOTB_MAKEFILES)),)
$(error Could not find cocotb makefiles. Create .venv and install deps: /opt/homebrew/bin/python3.12 -m venv .venv && ./.venv/bin/pip install -r test/requirements.txt)
endif

# include cocotb's make rules to take care of the simulator setup
include $(COCOTB_MAKEFILES)/Makefile.sim
