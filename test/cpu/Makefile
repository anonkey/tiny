SIM ?= icarus
FST ?= -fst
TOPLEVEL_LANG ?= verilog

SRC_DIR = $(PWD)/../../src

SIM_BUILD = ../artifacts/cpu
VERILOG_SOURCES += $(SRC_DIR)/kogge-stone.v
VERILOG_SOURCES += $(SRC_DIR)/mux.v
VERILOG_SOURCES += $(SRC_DIR)/dff.v
VERILOG_SOURCES += $(SRC_DIR)/register.v
VERILOG_SOURCES += $(SRC_DIR)/regfile.v
VERILOG_SOURCES += $(SRC_DIR)/alu.v
VERILOG_SOURCES += $(SRC_DIR)/pc.v
VERILOG_SOURCES += $(SRC_DIR)/rom.v
VERILOG_SOURCES += $(SRC_DIR)/decoder.v
VERILOG_SOURCES += $(SRC_DIR)/cpu.v
VERILOG_SOURCES += $(PWD)/tb_cpu.v

TOPLEVEL = tb_cpu
COCOTB_TEST_MODULES = test_cpu

PYTHON ?= $(PWD)/../../.venv/bin/python
COCOTB_MAKEFILES := $(shell $(PYTHON) -m cocotb_tools.config --makefiles 2>/dev/null || cocotb-config --makefiles 2>/dev/null)

ifeq ($(strip $(COCOTB_MAKEFILES)),)
$(error Could not find cocotb makefiles. Create .venv and install deps: /opt/homebrew/bin/python3.12 -m venv .venv && ./.venv/bin/pip install -r test/requirements.txt)
endif

include $(COCOTB_MAKEFILES)/Makefile.sim
