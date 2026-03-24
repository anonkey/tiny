import cocotb
from cocotb.triggers import RisingEdge, FallingEdge
from cocotb_helpers import start_clock, reset_sync, tick

# States (must match cpu_fsm.v localparams)
S_FETCH_REQ  = 0
S_FETCH_WAIT = 1
S_DECODE     = 2
S_EXECUTE    = 3
S_MEM_REQ    = 4
S_MEM_WAIT   = 5
S_WRITEBACK  = 6
S_PC_UPDATE  = 7

# Memory ops
MEM_OP_FETCH = 0b00
MEM_OP_LOAD  = 0b01
MEM_OP_STORE = 0b10


async def reset(dut):
  dut.pc.value = 0
  dut.alu_result.value = 0
  dut.rs2_data.value = 0
  dut.is_load.value = 0
  dut.is_store.value = 0
  dut.mem_done.value = 0
  dut.timeout.value = 0
  await reset_sync(dut)


async def pulse(dut, signal, cycles=1):
  """Assert signal for one cycle."""
  signal.value = 1
  await tick(dut)
  signal.value = 0


def state(dut):
  return int(dut.state.value)


@cocotb.test()
async def test_reset_state(dut):
  """After reset, FSM should be in S_FETCH_REQ (0)."""
  start_clock(dut)
  await reset(dut)
  assert state(dut) == S_FETCH_REQ, f"expected S_FETCH_REQ, got {state(dut)}"


@cocotb.test()
async def test_full_alu_cycle(dut):
  """ALU-only instruction: FETCH_REQ->FETCH_WAIT->(mem_done)->DECODE->EXECUTE->WRITEBACK->PC_UPDATE->FETCH_REQ."""
  start_clock(dut)
  await reset(dut)

  # FETCH_REQ -> FETCH_WAIT
  await tick(dut)
  assert state(dut) == S_FETCH_WAIT

  # FETCH_WAIT: pulse mem_done -> DECODE
  await pulse(dut, dut.mem_done)
  assert state(dut) == S_DECODE

  # DECODE -> EXECUTE (no load/store)
  dut.is_load.value = 0
  dut.is_store.value = 0
  await tick(dut)
  assert state(dut) == S_EXECUTE

  # EXECUTE (no load/store) -> WRITEBACK
  await tick(dut)
  assert state(dut) == S_WRITEBACK

  # WRITEBACK -> PC_UPDATE
  await tick(dut)
  assert state(dut) == S_PC_UPDATE

  # PC_UPDATE -> FETCH_REQ
  await tick(dut)
  assert state(dut) == S_FETCH_REQ


@cocotb.test()
async def test_load_cycle(dut):
  """LOAD instruction goes through MEM_REQ->MEM_WAIT->WRITEBACK."""
  start_clock(dut)
  await reset(dut)

  # Get to EXECUTE with is_load=1
  await tick(dut)  # -> FETCH_WAIT
  await pulse(dut, dut.mem_done)  # -> DECODE
  dut.is_load.value = 1
  dut.is_store.value = 0
  await tick(dut)  # -> EXECUTE
  assert state(dut) == S_EXECUTE

  # EXECUTE with is_load -> MEM_REQ
  await tick(dut)
  assert state(dut) == S_MEM_REQ

  # MEM_REQ -> MEM_WAIT
  await tick(dut)
  assert state(dut) == S_MEM_WAIT

  # MEM_WAIT + mem_done -> WRITEBACK
  await pulse(dut, dut.mem_done)
  assert state(dut) == S_WRITEBACK

  # WRITEBACK -> PC_UPDATE -> FETCH_REQ
  await tick(dut)
  assert state(dut) == S_PC_UPDATE
  await tick(dut)
  assert state(dut) == S_FETCH_REQ


@cocotb.test()
async def test_store_cycle(dut):
  """STORE instruction goes through MEM_REQ->MEM_WAIT->WRITEBACK."""
  start_clock(dut)
  await reset(dut)

  # Get to EXECUTE with is_store=1
  await tick(dut)  # -> FETCH_WAIT
  await pulse(dut, dut.mem_done)  # -> DECODE
  dut.is_load.value = 0
  dut.is_store.value = 1
  await tick(dut)  # -> EXECUTE
  assert state(dut) == S_EXECUTE

  # EXECUTE with is_store -> MEM_REQ
  await tick(dut)
  assert state(dut) == S_MEM_REQ

  # MEM_REQ -> MEM_WAIT
  await tick(dut)
  assert state(dut) == S_MEM_WAIT

  # MEM_WAIT + mem_done -> WRITEBACK
  await pulse(dut, dut.mem_done)
  assert state(dut) == S_WRITEBACK


@cocotb.test()
async def test_timeout_fetch_wait(dut):
  """Timeout in FETCH_WAIT should return to FETCH_REQ."""
  start_clock(dut)
  await reset(dut)

  await tick(dut)  # -> FETCH_WAIT
  assert state(dut) == S_FETCH_WAIT

  # Pulse timeout
  await pulse(dut, dut.timeout)
  assert state(dut) == S_FETCH_REQ, f"expected FETCH_REQ after timeout, got {state(dut)}"


@cocotb.test()
async def test_timeout_mem_wait(dut):
  """Timeout in MEM_WAIT should return to FETCH_REQ."""
  start_clock(dut)
  await reset(dut)

  # Get to MEM_WAIT
  await tick(dut)  # -> FETCH_WAIT
  await pulse(dut, dut.mem_done)  # -> DECODE
  dut.is_load.value = 1
  await tick(dut)  # -> EXECUTE
  await tick(dut)  # -> MEM_REQ
  await tick(dut)  # -> MEM_WAIT
  assert state(dut) == S_MEM_WAIT

  # Pulse timeout
  await pulse(dut, dut.timeout)
  assert state(dut) == S_FETCH_REQ


@cocotb.test()
async def test_pipeline_latch(dut):
  """Pipeline regs latch only in EXECUTE state."""
  start_clock(dut)
  await reset(dut)

  # Set inputs to known values
  dut.alu_result.value = 0xAA
  dut.rs2_data.value = 0xBB
  dut.is_load.value = 1
  dut.is_store.value = 0

  # Advance to EXECUTE
  await tick(dut)  # -> FETCH_WAIT
  await pulse(dut, dut.mem_done)  # -> DECODE
  await tick(dut)  # -> EXECUTE
  assert state(dut) == S_EXECUTE

  # On next tick, pipeline regs capture (latch enabled during EXECUTE)
  await tick(dut)  # -> MEM_REQ (latched)

  # Change inputs — should NOT affect latched values
  dut.alu_result.value = 0xFF
  dut.rs2_data.value = 0xFF
  await tick(dut)  # -> MEM_WAIT

  # Verify latched values are on the mem outputs
  assert int(dut.mem_addr.value) == 0xAA, \
    f"mem_addr should be latched 0xAA, got {int(dut.mem_addr.value):#04x}"
  assert int(dut.mem_wdata.value) == 0xBB, \
    f"mem_wdata should be latched 0xBB, got {int(dut.mem_wdata.value):#04x}"


@cocotb.test()
async def test_mem_req_pulse(dut):
  """o_mem_req should pulse for exactly one cycle in FETCH_WAIT and MEM_WAIT."""
  start_clock(dut)
  await reset(dut)

  # After reset in FETCH_REQ, on next tick we enter FETCH_WAIT.
  # mem_req is registered: it's driven by w_in_fetch_req, so it pulses
  # one cycle after we were in FETCH_REQ.
  await tick(dut)  # -> FETCH_WAIT
  assert int(dut.mem_req.value) == 1, "mem_req should be 1 in FETCH_WAIT (pulsed from FETCH_REQ)"

  await tick(dut)  # still FETCH_WAIT (no mem_done)
  assert int(dut.mem_req.value) == 0, "mem_req should return to 0"


@cocotb.test()
async def test_mem_op_fetch(dut):
  """mem_op should be MEM_OP_FETCH during fetch cycle."""
  start_clock(dut)
  await reset(dut)

  await tick(dut)  # -> FETCH_WAIT
  assert int(dut.mem_op.value) == MEM_OP_FETCH


@cocotb.test()
async def test_mem_op_load(dut):
  """mem_op should be MEM_OP_LOAD during load cycle."""
  start_clock(dut)
  await reset(dut)

  # Get to MEM_WAIT with is_load=1
  await tick(dut)  # -> FETCH_WAIT
  await pulse(dut, dut.mem_done)  # -> DECODE
  dut.is_load.value = 1
  dut.is_store.value = 0
  await tick(dut)  # -> EXECUTE
  await tick(dut)  # -> MEM_REQ (pipeline latched is_load=1)
  await tick(dut)  # -> MEM_WAIT

  assert int(dut.mem_op.value) == MEM_OP_LOAD, \
    f"mem_op should be LOAD (01), got {int(dut.mem_op.value):#04b}"


@cocotb.test()
async def test_mem_op_store(dut):
  """mem_op should be MEM_OP_STORE during store cycle."""
  start_clock(dut)
  await reset(dut)

  await tick(dut)  # -> FETCH_WAIT
  await pulse(dut, dut.mem_done)  # -> DECODE
  dut.is_load.value = 0
  dut.is_store.value = 1
  await tick(dut)  # -> EXECUTE
  await tick(dut)  # -> MEM_REQ
  await tick(dut)  # -> MEM_WAIT

  assert int(dut.mem_op.value) == MEM_OP_STORE, \
    f"mem_op should be STORE (10), got {int(dut.mem_op.value):#04b}"


@cocotb.test()
async def test_mem_addr_fetch(dut):
  """mem_addr should be i_pc during FETCH."""
  start_clock(dut)
  await reset(dut)

  dut.pc.value = 0x42
  await tick(dut)  # -> FETCH_WAIT
  assert int(dut.mem_addr.value) == 0x42, \
    f"mem_addr should be PC=0x42, got {int(dut.mem_addr.value):#04x}"


@cocotb.test()
async def test_mem_addr_load(dut):
  """mem_addr should be latched ALU result during LOAD."""
  start_clock(dut)
  await reset(dut)

  dut.alu_result.value = 0xBE
  await tick(dut)  # -> FETCH_WAIT
  await pulse(dut, dut.mem_done)  # -> DECODE
  dut.is_load.value = 1
  await tick(dut)  # -> EXECUTE (latch)
  await tick(dut)  # -> MEM_REQ
  await tick(dut)  # -> MEM_WAIT

  assert int(dut.mem_addr.value) == 0xBE, \
    f"mem_addr should be ALU result 0xBE, got {int(dut.mem_addr.value):#04x}"


@cocotb.test()
async def test_control_instr_en(dut):
  """o_instr_en should pulse when transitioning from FETCH_WAIT to DECODE."""
  start_clock(dut)
  await reset(dut)

  await tick(dut)  # -> FETCH_WAIT
  assert int(dut.instr_en.value) == 0

  # Pulse mem_done -> DECODE
  await pulse(dut, dut.mem_done)
  # instr_en is registered from (FETCH_WAIT & mem_done), visible one cycle later
  assert int(dut.instr_en.value) == 1, "instr_en should be 1 after FETCH_WAIT->DECODE"

  await tick(dut)  # -> EXECUTE
  assert int(dut.instr_en.value) == 0, "instr_en should return to 0"


@cocotb.test()
async def test_control_reg_we_pc_en(dut):
  """o_reg_we and o_pc_en should pulse after WRITEBACK."""
  start_clock(dut)
  await reset(dut)

  # Get to WRITEBACK
  await tick(dut)  # -> FETCH_WAIT
  await pulse(dut, dut.mem_done)  # -> DECODE
  await tick(dut)  # -> EXECUTE
  await tick(dut)  # -> WRITEBACK
  assert state(dut) == S_WRITEBACK

  # reg_we and pc_en are registered from w_in_writeback
  await tick(dut)  # -> PC_UPDATE
  assert int(dut.reg_we.value) == 1, "reg_we should be 1 after WRITEBACK"
  assert int(dut.pc_en.value) == 1, "pc_en should be 1 after WRITEBACK"

  await tick(dut)  # -> FETCH_REQ
  assert int(dut.reg_we.value) == 0, "reg_we should return to 0"
  assert int(dut.pc_en.value) == 0, "pc_en should return to 0"


@cocotb.test()
async def test_load_data_sel(dut):
  """o_load_data_sel should be 1 during WRITEBACK when is_load was set."""
  start_clock(dut)
  await reset(dut)

  # ALU-only cycle: load_data_sel should stay 0
  await tick(dut)  # -> FETCH_WAIT
  await pulse(dut, dut.mem_done)  # -> DECODE
  dut.is_load.value = 0
  await tick(dut)  # -> EXECUTE
  await tick(dut)  # -> WRITEBACK
  await tick(dut)  # -> PC_UPDATE
  assert int(dut.load_data_sel.value) == 0, "load_data_sel should be 0 for ALU-only"

  # Now do a LOAD cycle
  await tick(dut)  # -> FETCH_REQ
  await tick(dut)  # -> FETCH_WAIT
  await pulse(dut, dut.mem_done)  # -> DECODE
  dut.is_load.value = 1
  await tick(dut)  # -> EXECUTE
  await tick(dut)  # -> MEM_REQ
  await tick(dut)  # -> MEM_WAIT

  # MEM_WAIT + mem_done -> WRITEBACK, load_data_sel activates
  await pulse(dut, dut.mem_done)  # -> WRITEBACK
  assert state(dut) == S_WRITEBACK
  # load_data_sel = (MEM_WAIT & mem_done & is_load) | (WRITEBACK & is_load)
  # After pulsing mem_done in MEM_WAIT, we're now in WRITEBACK
  # The registered output captures the combinational result
  assert int(dut.load_data_sel.value) == 1, \
    f"load_data_sel should be 1 during WRITEBACK for LOAD, got {int(dut.load_data_sel.value)}"
