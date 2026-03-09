// D flip-flop with async active-low reset and enable
// Built from NAND gates (master-slave topology)

module sr_latch_nand (o_Q, o_Qn, i_Sn, i_Rn);
   output o_Q, o_Qn;
   input  i_Sn, i_Rn;

   wire o_Q, o_Qn;

   nand (o_Q,  i_Sn, o_Qn);
   nand (o_Qn, i_Rn, o_Q);

endmodule

module dff (o_Q, o_Qn, i_D, i_clk, i_rst_n, i_en);
   output o_Q, o_Qn;
   input  i_D, i_clk, i_rst_n, i_en;

   wire w_clk_n, w_clk_en;
   wire w_D_mux;
   wire w_Dm, w_Dmn;
   wire w_Mm, w_Mmn;
   wire w_Sm, w_Smn;

   // Enable mux: when en=0, feed back Q to hold value
   // D_mux = (en & D) | (~en & Q)
   wire w_en_n, w_en_and_d, w_enn_and_q;
   nand (w_en_n, i_en, i_en);
   nand (w_en_and_d, i_en, i_D);
   nand (w_enn_and_q, w_en_n, o_Q);
   nand (w_D_mux, w_en_and_d, w_enn_and_q);

   // Inverted clock
   nand (w_clk_n, i_clk, i_clk);

   // Master stage gating
   nand (w_Dm,  w_D_mux, w_clk_n);
   nand (w_Dmn, w_D_mux, w_D_mux); // NOT D_mux
   wire w_Dmn2;
   nand (w_Dmn2, w_Dmn, w_clk_n);

   // Master SR latch
   wire w_Mq, w_Mqn;
   nand (w_Mq,  w_Dm,   w_Mqn);
   nand (w_Mqn, w_Dmn2, w_Mq);

   // Slave stage gating
   nand (w_Sm,  w_Mq,  i_clk);
   nand (w_Smn, w_Mqn, i_clk);

   // Slave SR latch with async reset
   wire w_Q_int, w_Qn_int;
   nand (w_Q_int,  w_Sm,  w_Qn_int);
   nand (w_Qn_int, w_Smn, w_Q_int, i_rst_n);

   assign o_Q  = w_Q_int;
   assign o_Qn = w_Qn_int;

endmodule
