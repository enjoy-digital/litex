//
// usbkbd.v
//
// Copyright 2020, Gary Wong <gtw@gnu.org>
//
// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions
// are met:
// 
// 1. Redistributions of source code must retain the above copyright
//    notice, this list of conditions and the following disclaimer.
// 2. Redistributions in binary form must reproduce the above copyright
//    notice, this list of conditions and the following disclaimer in
//    the documentation and/or other materials provided with the
//    distribution.
// 
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
// "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
// LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
// FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
// COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
// INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
// (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
// SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
// HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
// STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
// ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED
// OF THE POSSIBILITY OF SUCH DAMAGE.

module usbkbd( input clk, output reg[ 63:0 ] report, output reg interrupt,
	       input intack, inout dp, inout dn );

    // frequency of clk (Hz): need the absolute frequency specified to derive
    // USB timing parameters from it
    parameter CLK_FREQ = 80000000;

    // idle timeout: 0 means no reports when idle, 1 means idle report every
    // 192 ms
    parameter REPORT_IDLE = 0;
    
    // clk periods from transition to sample point: 333.33 ns
    localparam RX_EYE = CLK_FREQ / 3000000;
    // clk periods per symbol: 666.67 ns
    localparam TX_TICK = CLK_FREQ / 1500000;
    localparam TX_LASTTICK = TX_TICK - 1;

    // Fast (~1 ms) timer:
    localparam FAST_TIMER_SIZE = CLK_FREQ < 4000000 ? 11 :
				 CLK_FREQ < 8000000 ? 12 :
				 CLK_FREQ < 16000000 ? 13 :
				 CLK_FREQ < 32000000 ? 14 :
				 CLK_FREQ < 64000000 ? 15 :
				 CLK_FREQ < 128000000 ? 16 : 17;
    localparam FOLLOW_TIMER_SIZE = FAST_TIMER_SIZE - 8;

    // Slow (~10 ms) timer:
    localparam SLOW_TIMER_SIZE = FAST_TIMER_SIZE + 3;

    reg[ SLOW_TIMER_SIZE:0 ] timectr = 0;

    always @( posedge clk )
	timectr <= timectr + 1;

    wire fasttimer;
    wire slowtimer;
    assign fasttimer = &timectr[ FAST_TIMER_SIZE:0 ];
    assign slowtimer = &timectr[ SLOW_TIMER_SIZE:0 ];

    reg[ FOLLOW_TIMER_SIZE:0 ] followtimer;
    reg follow = 1'b0;
    
    always @( posedge clk )
	if( follow && state == IDLE )
	    followtimer <= followtimer + 1;
	else
	    followtimer <= 0;
    
    reg transmit = 1'b0;   
    reg dptx;
    reg dntx;   
    wire dprx_unsync;
    wire dnrx_unsync;
    reg dprx;
    reg dnrx;
    reg dpprev = 1'b0;

    BB bbdp( dptx, !transmit, dprx_unsync, dp );
    BB bbdn( dntx, !transmit, dnrx_unsync, dn );   

    always @( posedge clk ) begin
	dprx <= dprx_unsync;
	dnrx <= dnrx_unsync;
	dpprev <= dprx;
    end

    // initstate:
    localparam
	INITWAIT = 3'd0, // 10 ms timeout -> RESET
	RESET = 3'd1, // 10 ms timeout -> RESETWAIT
	RESETWAIT = 3'd2, // 10 ms timeout -> SETADDRESS
	SETADDRESS = 3'd3, // success -> SETCONFIG; 10 ms timeout -> INITWAIT
	SETCONFIG = 3'd4, // success -> SETPROTOCL; 10 ms timeout -> INITWAIT
	SETPROTOCOL = 3'd5, // success -> SETPROTOCL; 10 ms timeout -> INITWAIT
	SETIDLE = 3'd6, // success -> SETIDLE; 10 ms timeout -> INITWAIT
	POLL = 3'd7; // 10 ms timeout -> INITWAIT
    reg[ 2:0 ] initstate = INITWAIT;
    reg watchdog;
    
    always @( posedge clk ) begin
	if( initstate == INITWAIT && slowtimer )
	    initstate <= RESET;
	else if( initstate == RESET && slowtimer )
	    initstate <= RESETWAIT;
	else if( initstate == RESETWAIT && slowtimer )
	    initstate <= SETADDRESS;
	else if( initstate >= SETADDRESS && initstate != POLL && rxmustack && 
	    state == TX )
	    initstate <= initstate + 1;
	else if( slowtimer && watchdog )
	    initstate <= INITWAIT;
    end

    always @( posedge clk ) begin
	if( initstate < SETADDRESS || rxbitctr == 8'b00001000 )
	    watchdog <= 1'b0;
	// FIXME watchdog is too eager... don't reset until much longer
//	else if( slowtimer )
//	    watchdog <= 1'b1;
    end
    
    // shared between TX/RX
    localparam
	IDLE = 3'd0,
	RX = 3'd2,
	RX_EOP = 3'd3,
	TX = 3'd4,
	TX_EOP = 3'd5,
	TX_FORCE = 3'd6,
	TX_EOP2 = 3'd7;
    reg[ 2:0 ] state = IDLE;
    reg[ 2:0 ] nextstate;

    reg[ 63:0 ] rxword;   
    reg rxoldlev;   
    reg[ 2:0 ] rxstuffctr = 3'b0;
    reg[ 7:0 ] rxbitctr;
    reg rxmustack;
    reg rxrecvd;
    reg[ 5:0 ] rxphase;
    wire rxeye;
    assign rxeye = rxphase == RX_EYE;

    wire rxtrans;
    assign rxtrans = dprx != dpprev;
   
    wire rxrecv;
    assign rxrecv = rxeye && rxstuffctr < 3'd6 && ( dprx || dnrx );   
	    
    // TX
    reg[ 6:0 ] txlen;      
    reg[ 7:0 ] txcount;      
    reg[ 87:0 ] txbuf;   
    reg[ 5:0 ] txtick = 6'b0;
    reg[ 2:0 ] txstuffctr = 3'b0;
    reg sendsetup;
    wire txtrans;
    assign txtrans = txstuffctr == 3'd6 ||
		     ( txcount[ 7 ] && txcount[ 2:0 ] != 3'b111 ) ||
		     ( !txcount[ 7 ] && !txbuf[ 0 ] );
    
    // Main state machine
    always @*
	if( state == RX )
	    // FIXME should check CRC
	    nextstate = rxeye && !dprx && !dnrx ? RX_EOP : RX;
	else if( state == RX_EOP )
	    if( dnrx )
		nextstate = rxmustack ? TX : IDLE;
	    else
		nextstate = RX_EOP;
	else if( state == TX )
	    nextstate = txtick == TX_LASTTICK && txcount == txlen &&
			 txstuffctr < 3'd6 ? TX_EOP : TX;
	else if( state == TX_EOP )
	    nextstate = txtick == TX_LASTTICK ? TX_EOP2 : TX_EOP;
	else if( state == TX_FORCE )
	    nextstate = initstate == RESET ? TX_FORCE : RX_EOP;
	else if( state == TX_EOP2 )
	    nextstate = txtick == TX_LASTTICK ? IDLE : TX_EOP2;
	else begin
	    // idle
	    if( dprx )
		nextstate = RX;
	    else if( txlen )
		nextstate = TX;
	    else if( ( initstate == RESETWAIT && fasttimer && !slowtimer ) ||
		     ( initstate == POLL && fasttimer && interrupt ) )
		nextstate = TX_EOP; // send low-speed keep-alive
	    else if( initstate == RESET )
		nextstate = TX_FORCE;
	    else
		nextstate = state;	
	end
   
    always @( posedge clk ) begin
	// RX phase: reset at transition, then increment
	if( state == RX ) begin
	    rxphase <= ( rxtrans || rxphase == TX_TICK ) ? 5'b0 : rxphase + 1'b1;
	end else
	    rxphase <= 5'b0;      

	// RX bit stuffing counter: increment on consecutive bits
	if( rxeye && rxstuffctr < 3'd6 && rxoldlev == dprx )
	    rxstuffctr <= rxstuffctr + 1'b1;
	else if( rxeye || state != RX )
	    rxstuffctr <= 3'd0;

	// RX previous symbol
	if( rxeye )
	    rxoldlev <= dprx;
	else if( state != RX )
	    rxoldlev <= 1'b0;

	// RX shift register
	if( rxrecv )
	    rxword[ 63:0 ] <= { dprx == rxoldlev, rxword[ 63:1 ] };      

	rxrecvd <= rxrecv;      
      
	// RX bit counter
	if( rxrecv )
	    rxbitctr <= rxbitctr + 1'b1;
	else if( state == RX )
	    rxbitctr <= rxbitctr;
	else
	    rxbitctr <= 8'b11111000;

	if( rxbitctr == 8'b00000010 )
	    rxmustack <= rxword[ 63:62 ] == 2'b11;
	else if( state == RX || state == RX_EOP )
	    rxmustack <= rxmustack;
	else
	    rxmustack <= 1'b0;      
      
	if( state == RX && rxmustack && nextstate == RX_EOP &&
	    rxbitctr[ 6:0 ] < 7'b1001000 )
	    report[ 63:0 ] <= 64'h0000000000000000;
	else if( rxrecvd && rxbitctr[ 6:0 ] == 7'b1001000 )
	    report[ 63:0 ] <= rxword[ 63:0 ];
	
	state <= nextstate;      

	// TX symbol
	if( state == TX ) begin
	    if( txtick == TX_LASTTICK && nextstate == TX ) begin
		dptx <= txtrans ? ~dptx : dptx;
		dntx <= txtrans ? ~dntx : dntx;
	    end
	end else if( state == TX_EOP || state == TX_EOP2 ) begin
	    // single ended 0 EOP
	    dptx <= 1'b0;
	    dntx <= state == TX_EOP2 && txtick >= TX_LASTTICK - 1; // before float
	end else if( state == TX_FORCE ) begin
	    // forced TX symbol
	    dptx <= 1'b0;
	    dntx <= 1'b0;
	end else begin
	    // idle J state
	    dptx <= 1'b0;
	    dntx <= 1'b1;	 
	end
	
	// TX bit stuffing counter
	if( state == TX )
	    txstuffctr <= txtrans ? 3'b0 : txstuffctr + 3'b1;
	else
	    txstuffctr <= 3'b0;      

	if( transmit )
	    txtick <= txtick == TX_LASTTICK ? 6'b0 : txtick + 1'b1;
	else
	    txtick <= 6'b0;
      
	transmit <= state[ 2 ];
      
	// TX bit counter
	if( state == IDLE )
	    txcount <= 8'b11111000;
	else if( state == TX && txtick == TX_LASTTICK && txstuffctr < 3'd6 )
	    txcount <= txcount + 1'b1;      

	if( fasttimer )
	    sendsetup <= 1'b0;
	else if( rxmustack )
	    sendsetup <= 1'b1;
	
	// TX shift register
	if( initstate == INITWAIT ) begin
	    txlen <= 7'd0;
	    follow <= 1'b0;
	end else if( state == RX_EOP && rxmustack ) begin
	    txbuf[ 87:0 ] <= 88'hXXXXXXXXXXXXXXXXXXXXD2; // ACK
	    txlen <= 7'd8;
	end else if( initstate == SETADDRESS && !timectr ) begin
	    txbuf[ 87:0 ] <= 88'hXXXXXXXXXXXXXXXX10002D; // SETUP
	    txlen <= 7'd24;
	    follow <= 1'b1;
	end else if( initstate == SETADDRESS && follow && &followtimer ) begin
	    txbuf[ 87:0 ] <= 88'h25EB0000000000010500C3; // set address
	    txlen <= 7'd88;
	    follow <= 1'd0;
	end else if( initstate == SETADDRESS && fasttimer ) begin
	    txbuf[ 87:0 ] <= 88'hXXXXXXXXXXXXXXXX100069; // IN
	    txlen <= 7'd24;
	end else if( initstate >= SETCONFIG && initstate <= SETIDLE && 
		     sendsetup && fasttimer ) begin
	    txbuf[ 87:0 ] <= 88'hXXXXXXXXXXXXXXXXE8012D; // SETUP
	    txlen <= 7'd24;
	    follow <= 1'b1;
	end else if( initstate == SETCONFIG && follow && &followtimer ) begin
	    txbuf[ 87:0 ] <= 88'h25270000000000010900C3; // set configuration
	    txlen <= 7'd88;
	    follow <= 1'd0;	    
	end else if( initstate == SETPROTOCOL && follow && &followtimer ) begin
	    txbuf[ 87:0 ] <= 88'hE0C60000000000000B21C3; // set protocol
	    txlen <= 7'd88;
	    follow <= 1'd0;	    
	end else if( initstate == SETIDLE && follow && &followtimer ) begin
	    txbuf[ 87:0 ] <= REPORT_IDLE ? 88'h24960000000030000A21C3 :
			     88'h20D60000000000000A21C3; // set idle
	    txlen <= 7'd88;
	    follow <= 1'd0;	    
	end else if( initstate >= SETCONFIG && initstate <= SETIDLE &&
		     fasttimer ) begin
	    txbuf[ 87:0 ] <= 88'hXXXXXXXXXXXXXXXXE80169; // IN
	    txlen <= 7'd24;
	end else if( initstate == POLL && fasttimer && !interrupt ) begin
	    txbuf[ 87:0 ] <= 88'hXXXXXXXXXXXXXXXX588169; // INTR IN
	    txlen <= 7'd24;
	end else if( state == TX && txtick == TX_LASTTICK && txstuffctr < 3'd6
		 && !txcount[ 7 ] )
	    txbuf[ 87:0 ] <= { 1'bX, txbuf[ 87:1 ] };
	else if( state == TX_EOP )
	    txlen <= 0;
    end

    always @( posedge clk )
	if( initstate == POLL && rxmustack &&
	    state == RX && nextstate == RX_EOP )
	    interrupt <= 1'b1;
	else if( intack )
	    interrupt <= 1'b0;
endmodule

module wishbone_usbkbd( inout dp, inout dn, output interrupt,
			input RST_I, input CLK_I, input ADR_I,
			input[ 31:0 ] DAT_I, output[ 31:0 ] DAT_O,
			input WE_I, input[ 3:0 ] SEL_I, input STB_I,
			output reg ACK_O, input CYC_I );

    // frequency of clk (Hz): need the absolute frequency specified to derive
    // USB timing parameters from it
    parameter CLK_FREQ = 80000000;

    // idle timeout: 0 means no reports when idle, 1 means idle report every
    // 192 ms
    parameter REPORT_IDLE = 0;
    
    wire[ 63:0 ] report;
    wire intack;
    
    usbkbd u( CLK_I, report, interrupt, intack, dp, dn );
    defparam u.CLK_FREQ = CLK_FREQ;
    defparam u.REPORT_IDLE = REPORT_IDLE;
    
    assign intack = CYC_I & STB_I & !ADR_I & !WE_I;
    assign DAT_O = ADR_I ? report[ 63:32 ] : report[ 31:0 ];
    always @( posedge CLK_I )
	ACK_O <= CYC_I & STB_I;
endmodule
