
/*
===============================================================================

This C header file is part of the SoftFloat IEC/IEEE Floating-point
Arithmetic Package, Release 2.

Written by John R. Hauser.  This work was made possible in part by the
International Computer Science Institute, located at Suite 600, 1947 Center
Street, Berkeley, California 94704.  Funding was partially provided by the
National Science Foundation under grant MIP-9311980.  The original version
of this code was written as part of a project to build a fixed-point vector
processor in collaboration with the University of California at Berkeley,
overseen by Profs. Nelson Morgan and John Wawrzynek.  More information
is available through the Web page `http://HTTP.CS.Berkeley.EDU/~jhauser/
arithmetic/softfloat.html'.

THIS SOFTWARE IS DISTRIBUTED AS IS, FOR FREE.  Although reasonable effort
has been made to avoid it, THIS SOFTWARE MAY CONTAIN FAULTS THAT WILL AT
TIMES RESULT IN INCORRECT BEHAVIOR.  USE OF THIS SOFTWARE IS RESTRICTED TO
PERSONS AND ORGANIZATIONS WHO CAN AND WILL TAKE FULL RESPONSIBILITY FOR ANY
AND ALL LOSSES, COSTS, OR OTHER PROBLEMS ARISING FROM ITS USE.

Derivative works are acceptable, even for commercial purposes, so long as
(1) they include prominent notice that the work is derivative, and (2) they
include prominent notice akin to these three paragraphs for those parts of
this code that are retained.

===============================================================================
*/

/*
-------------------------------------------------------------------------------
Software IEC/IEEE floating-point types.
-------------------------------------------------------------------------------
*/
typedef unsigned int float32;

/*
-------------------------------------------------------------------------------
Software IEC/IEEE floating-point underflow tininess-detection mode.
-------------------------------------------------------------------------------
*/
extern int float_detect_tininess;
enum {
    float_tininess_after_rounding  = 0,
    float_tininess_before_rounding = 1
};

/*
-------------------------------------------------------------------------------
Software IEC/IEEE floating-point rounding mode.
-------------------------------------------------------------------------------
*/
extern int float_rounding_mode;
enum {
    float_round_nearest_even = 0,
    float_round_to_zero      = 1,
    float_round_up           = 2,
    float_round_down         = 3
};

/*
-------------------------------------------------------------------------------
Software IEC/IEEE floating-point exception flags.
-------------------------------------------------------------------------------
*/
extern int float_exception_flags;
enum {
    float_flag_inexact   =  1,
    float_flag_divbyzero =  2,
    float_flag_underflow =  4,
    float_flag_overflow  =  8,
    float_flag_invalid   = 16
};

/*
-------------------------------------------------------------------------------
Routine to raise any or all of the software IEC/IEEE floating-point
exception flags.
-------------------------------------------------------------------------------
*/
void float_raise( int );

/*
-------------------------------------------------------------------------------
Software IEC/IEEE integer-to-floating-point conversion routines.
-------------------------------------------------------------------------------
*/
float32 int32_to_float32( int );

/*
-------------------------------------------------------------------------------
Software IEC/IEEE single-precision conversion routines.
-------------------------------------------------------------------------------
*/
int float32_to_int32( float32 );
int float32_to_int32_round_to_zero( float32 );

/*
-------------------------------------------------------------------------------
Software IEC/IEEE single-precision operations.
-------------------------------------------------------------------------------
*/
float32 float32_round_to_int( float32 );
float32 float32_add( float32, float32 );
float32 float32_sub( float32, float32 );
float32 float32_mul( float32, float32 );
float32 float32_div( float32, float32 );
float32 float32_rem( float32, float32 );
float32 float32_sqrt( float32 );
int float32_eq( float32, float32 );
int float32_le( float32, float32 );
int float32_lt( float32, float32 );
int float32_eq_signaling( float32, float32 );
int float32_le_quiet( float32, float32 );
int float32_lt_quiet( float32, float32 );
int float32_is_signaling_nan( float32 );

