SIM ?= icarus
TOPLEVEL_LANG ?= verilog
SRC_DIR = $(PWD)/../../src

SIM_BUILD = ../artifacts/spi
VERILOG_SOURCES += $(SRC_DIR)/dff.v
VERILOG_SOURCES += $(SRC_DIR)/register.v
VERILOG_SOURCES += $(SRC_DIR)/spi_slave.v
VERILOG_SOURCES += $(PWD)/tb_spi_slave.v
COMPILE_ARGS += -I$(SRC_DIR)

TOPLEVEL = tb_spi_slave
COCOTB_TEST_MODULES = test_spi_slave

PYTHON ?= $(PWD)/../../.venv/bin/python
COCOTB_MAKEFILES := $(shell $(PYTHON) -m cocotb_tools.config --makefiles 2>/dev/null || cocotb-config --makefiles 2>/dev/null)

ifeq ($(strip $(COCOTB_MAKEFILES)),)
$(error Could not find cocotb makefiles. Create .venv and install deps: /opt/homebrew/bin/python3.12 -m venv .venv && ./.venv/bin/pip install -r test/requirements.txt)
endif

include $(COCOTB_MAKEFILES)/Makefile.sim
