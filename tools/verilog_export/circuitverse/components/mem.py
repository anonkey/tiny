"""Memory cell: $mem_v2."""

from circuitverse.components._common import pin_clearance, _new_bus_pin, _param_int


def place_mem_v2(cell, conns, na, bit_nodes, components, x, y):
  """Map Yosys $mem_v2 to CircuitVerse verilogRAM. Returns y-advance."""
  params = cell.get("parameters", {})
  data_bw = _param_int(cell, "WIDTH", 8)
  addr_bw = _param_int(cell, "ABITS", 8)
  n_words = _param_int(cell, "SIZE", 256)
  n_rd = _param_int(cell, "RD_PORTS", 1)
  n_wr = _param_int(cell, "WR_PORTS", 1)

  # Init data
  init = params.get("INIT", "")
  if isinstance(init, int):
    init = ""
  mem_data = {}
  if init:
    for i in range(n_words):
      word = init[i * data_bw:(i + 1) * data_bw]
      if word and int(word, 2) != 0:
        mem_data[str(i)] = int(word, 2)

  # Read ports
  rd_addr_nodes = []
  rd_data_nodes = []
  rd_clk_nodes = []
  rd_en_nodes = []
  for i in range(n_rd):
    addr_bits = conns.get("RD_ADDR", [])[i * addr_bw:(i + 1) * addr_bw]
    data_bits = conns.get("RD_DATA", [])[i * data_bw:(i + 1) * data_bw]
    rd_addr_nodes.append(_new_bus_pin(na, bit_nodes, addr_bits, 0, addr_bw, rx=-20, ry=-10))
    rd_data_nodes.append(_new_bus_pin(na, bit_nodes, data_bits, 1, data_bw, rx=20, ry=-10))
    rd_clk_bits = conns.get("RD_CLK", [])
    if i < len(rd_clk_bits):
      rd_clk_nodes.append(_new_bus_pin(na, bit_nodes, [rd_clk_bits[i]], 0, 1, rx=-20, ry=10))
    else:
      rd_clk_nodes.append(na.alloc(-20, 10, 0, 1))
    rd_en_bits = conns.get("RD_EN", [])
    if i < len(rd_en_bits):
      rd_en_nodes.append(_new_bus_pin(na, bit_nodes, [rd_en_bits[i]], 0, 1, rx=-20, ry=20))
    else:
      rd_en_nodes.append(na.alloc(-20, 20, 0, 1))

  # Write ports
  wr_addr_nodes = []
  wr_data_nodes = []
  wr_en_nodes = []
  wr_clk_nodes = []
  for i in range(n_wr):
    addr_bits = conns.get("WR_ADDR", [])[i * addr_bw:(i + 1) * addr_bw]
    data_bits = conns.get("WR_DATA", [])[i * data_bw:(i + 1) * data_bw]
    wr_addr_nodes.append(_new_bus_pin(na, bit_nodes, addr_bits, 0, addr_bw, rx=-20, ry=-10))
    wr_data_nodes.append(_new_bus_pin(na, bit_nodes, data_bits, 0, data_bw, rx=-20, ry=10))
    wr_en_bits = conns.get("WR_EN", [])
    wr_en_start = i * data_bw
    if wr_en_start < len(wr_en_bits):
      wr_en_nodes.append(_new_bus_pin(na, bit_nodes, [wr_en_bits[wr_en_start]], 0, 1, rx=0, ry=20))
    else:
      wr_en_nodes.append(na.alloc(0, 20, 0, 1))
    wr_clk_bits = conns.get("WR_CLK", [])
    if i < len(wr_clk_bits):
      wr_clk_nodes.append(_new_bus_pin(na, bit_nodes, [wr_clk_bits[i]], 0, 1, rx=-20, ry=20))
    else:
      wr_clk_nodes.append(na.alloc(-20, 20, 0, 1))

  reset_node = na.alloc(0, 30, 0, 1)
  core_dump = na.alloc(0, -30, 0, 1)

  # Build rdports / wrports metadata
  rd_clk_pol = params.get("RD_CLK_POLARITY", "1" * n_rd)
  rd_clk_en = params.get("RD_CLK_ENABLE", "0" * n_rd)
  rd_transparency = params.get("RD_TRANSPARENCY_MASK", "0" * n_rd)

  rdports = []
  for i in range(n_rd):
    rdports.append({
      "clock_polarity": True if (isinstance(rd_clk_pol, str) and i < len(rd_clk_pol) and rd_clk_pol[i] == "1") else False,
      "enable": True if (isinstance(rd_clk_en, str) and i < len(rd_clk_en) and rd_clk_en[i] == "1") else False,
      "transparent": True if (isinstance(rd_transparency, str) and i < len(rd_transparency) and rd_transparency[i] == "1") else False,
    })

  wr_clk_pol = params.get("WR_CLK_POLARITY", "1" * n_wr)
  wr_clk_en = params.get("WR_CLK_ENABLE", "1" * n_wr)

  wrports = []
  for i in range(n_wr):
    wrports.append({
      "clock_polarity": True if (isinstance(wr_clk_pol, str) and i < len(wr_clk_pol) and wr_clk_pol[i] == "1") else False,
      "enable": True if (isinstance(wr_clk_en, str) and i < len(wr_clk_en) and wr_clk_en[i] == "1") else False,
    })

  # Read DFF nodes (required by verilogRAM)
  rd_dff_clock = []
  rd_dff_d = []
  rd_dff_q = []
  rd_dff_en = []
  for i in range(n_rd):
    rd_dff_clock.append(na.alloc(-20, 30, 0, 1))
    rd_dff_d.append(na.alloc(-20, 40, 0, data_bw))
    rd_dff_q.append(na.alloc(20, 40, 1, data_bw))
    rd_dff_en.append(na.alloc(-20, 50, 0, 1))

  # Write DFF nodes
  wr_dff_clock = []
  wr_dff_d = []
  wr_dff_q = []
  wr_dff_en = []
  for i in range(n_wr):
    wr_dff_clock.append(na.alloc(-20, 60, 0, 1))
    wr_dff_d.append(na.alloc(-20, 70, 0, data_bw))
    wr_dff_q.append(na.alloc(20, 70, 1, data_bw))
    wr_dff_en.append(na.alloc(-20, 80, 0, 1))

  comp = {
    "x": x, "y": y,
    "objectType": "verilogRAM",
    "label": "",
    "direction": "RIGHT",
    "labelDirection": "LEFT",
    "propagationDelay": 100,
    "customData": {
      "constructorParamaters": [
        "RIGHT", data_bw, addr_bw,
        mem_data, n_words,
        n_rd, n_wr,
        rdports, wrports,
      ],
      "nodes": {
        "readAddress": rd_addr_nodes,
        "writeAddress": wr_addr_nodes,
        "writeDataIn": wr_data_nodes,
        "writeEnable": wr_en_nodes,
        "dataOut": rd_data_nodes,
        "readDffClock": rd_dff_clock,
        "readDffDInp": rd_dff_d,
        "readDffQOutput": rd_dff_q,
        "readDffEn": rd_dff_en,
        "writeDffClock": wr_dff_clock,
        "writeDffDInp": wr_dff_d,
        "writeDffQOutput": wr_dff_q,
        "writeDffEn": wr_dff_en,
        "reset": reset_node,
        "coreDump": core_dump,
      },
    },
  }
  components.setdefault("verilogRAM", []).append(comp)
  return 110 + pin_clearance(4)
