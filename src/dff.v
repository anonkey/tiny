// D flip-flop with async active-low reset and enable
// Built from NAND gates (master-slave topology)

module sr_latch_nand (Q, Qn, Sn, Rn);
   output Q, Qn;
   input  Sn, Rn;

   wire Q, Qn;

   nand (Q,  Sn, Qn);
   nand (Qn, Rn, Q);

endmodule

module dff (Q, Qn, D, clk, rst_n, en);
   output Q, Qn;
   input  D, clk, rst_n, en;

   wire clk_n, clk_en;
   wire D_mux;
   wire Dm, Dmn;
   wire Mm, Mmn;
   wire Sm, Smn;

   // Enable mux: when en=0, feed back Q to hold value
   // D_mux = (en & D) | (~en & Q)
   wire en_n, en_and_d, enn_and_q;
   nand (en_n, en, en);
   nand (en_and_d, en, D);
   nand (enn_and_q, en_n, Q);
   nand (D_mux, en_and_d, enn_and_q);

   // Inverted clock
   nand (clk_n, clk, clk);

   // Master stage gating
   nand (Dm,  D_mux, clk_n);
   nand (Dmn, D_mux, D_mux); // NOT D_mux
   wire Dmn2;
   nand (Dmn2, Dmn, clk_n);

   // Master SR latch
   wire Mq, Mqn;
   nand (Mq,  Dm,   Mqn);
   nand (Mqn, Dmn2, Mq);

   // Slave stage gating
   nand (Sm,  Mq,  clk);
   nand (Smn, Mqn, clk);

   // Slave SR latch with async reset
   wire Q_int, Qn_int;
   nand (Q_int,  Sm,  Qn_int);
   nand (Qn_int, Smn, Q_int, rst_n);

   assign Q  = Q_int;
   assign Qn = Qn_int;

endmodule
