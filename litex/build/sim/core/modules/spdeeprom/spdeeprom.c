#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "error.h"
#include "modules.h"

/*
 * This is a simulation of SPD EEPROM I2C slave.
 * It only supports basic read/write commands.
 * Although it has been written with SPD EEPROM chips in mind, it should be
 * compatible with some other EEPROM chips that use single byte addressing.
 *
 * Some details can be controlled using defines/environmental variables:
 *   #define SPD_EEPROM_ADDR    7bit address of I2C slave
 *   #define DEBUG_SPD_EEPROM   print debug messages
 *   env SPD_EEPROM_FILE        load memory contents from file
 */

#define SPD_EEPROM_ADDR 0b000

#ifdef DEBUG_SPD_EEPROM
#define DBG(...) do{ fprintf(stderr, __VA_ARGS__); } while(0)
#else
#define DBG(...) do{ } while (0)
#endif

// state of the serial-to-parallel FSM
enum SerialState {
  IDLE,
  WRITE,   // slave writing a byte to master
  READ,    // slave reading a byte from master
  RACK_0,  // slave starts sending ACK
  RACK_1,  // slave finishes sending ACK
  WACK,    // slave reads ACK
};

// state of the transaction FSM
enum TransactionState {
  DEV_ADDR,    // reading slave device address
  WRITE_ADDR,  // master writes address
  WRITE_DATA,  // master writes data
  READ_DATA,   // master reads data
};

// module state
struct session_s {
  // DUT pads (need separate SDA io/out as Verilator does not support tristate pins)
  char *sys_clk;
  char *sda_in;
  char *sda_out;
  char *scl;
  // SPD EEPROM memory contents
  unsigned char mem[256];
  // state machine
  enum TransactionState state_transaction;
  enum SerialState state_serial;
  unsigned int byte_in;
  unsigned int byte_out;
  unsigned int bit_counter;
  unsigned int devaddr;
  unsigned int addr;
};

// Module interface
static int spdeeprom_start();
static int spdeeprom_new(void **sess, char *args);
static int spdeeprom_add_pads(void *sess, struct pad_list_s *plist);
static int spdeeprom_tick(void *sess, uint64_t time_ps);
// EEPROM simulation
static void fsm_tick(struct session_s *s);
static enum SerialState state_serial_next(struct session_s *s);
// Helper functions
static void spdeeprom_from_file(struct session_s *s, FILE *file);
static int litex_sim_module_pads_get(struct pad_s *pads, char *name, void **signal);

/*** Module interface *****************************************************************************/

static struct ext_module_s ext_mod = {
  "spdeeprom",
  spdeeprom_start,
  spdeeprom_new,
  spdeeprom_add_pads,
  NULL,
  spdeeprom_tick
};

int litex_sim_ext_module_init(int (*register_module)(struct ext_module_s *))
{
  int ret = RC_OK;
  ret = register_module(&ext_mod);
  return ret;
}

static int spdeeprom_start()
{
  printf("[spdeeprom] loaded (addr = 0x%01x)\n", SPD_EEPROM_ADDR);
  return RC_OK;
}

static int spdeeprom_new(void **sess, char *args)
{
  int ret = RC_OK;
  int i;
  char *spd_filename;
  FILE *spd_file;

  struct session_s *s=NULL;

  if(!sess) {
    ret = RC_INVARG;
    goto out;
  }

  s = (struct session_s*) malloc(sizeof(struct session_s));
  if(!s) {
    ret=RC_NOENMEM;
    goto out;
  }
  memset(s, 0, sizeof(struct session_s));

  spd_filename = getenv("SPD_EEPROM_FILE");
  if (spd_filename != NULL) {
    spd_file = fopen(spd_filename, "r");
  }
  if (spd_filename != NULL && spd_file != NULL) {
    printf("[spdeeprom] loading EEPROM contents from file: %s\n", spd_filename);
    spdeeprom_from_file(s, spd_file);
    fclose(spd_file);
  } else {  // fill in the memory with some data
    for (i = 0; i < sizeof(s->mem) / sizeof(s->mem[0]); ++i) {
      s->mem[i] = i & 0xff;
    }
  }

out:
  *sess = (void*) s;
  return ret;
}

static int spdeeprom_add_pads(void *sess, struct pad_list_s *plist)
{
  int ret = RC_OK;
  struct session_s *s = (struct session_s*) sess;
  struct pad_s *pads;

  if(!sess || !plist) {
    ret = RC_INVARG;
    goto out;
  }
  pads = plist->pads;

  if(!strcmp(plist->name, "i2c")) {
    litex_sim_module_pads_get(pads, "sda_in", (void**) &s->sda_in);
    litex_sim_module_pads_get(pads, "sda_out", (void**) &s->sda_out);
    litex_sim_module_pads_get(pads, "scl", (void**) &s->scl);
  }

  if(!strcmp(plist->name, "sys_clk"))
    litex_sim_module_pads_get(pads, "sys_clk", (void**) &s->sys_clk);

out:
  return ret;
}

static int spdeeprom_tick(void *sess, uint64_t time_ps)
{
  static clk_edge_state_t edge;
  struct session_s *s = (struct session_s*) sess;

  if (s->sda_in == 0 || s->sda_out == 0 || s->scl == 0) {
      return RC_OK;
  }

  if(!clk_pos_edge(&edge, *s->sys_clk)) {
    return RC_OK;
  }

  fsm_tick(s);

  return RC_OK;
}

/*** Simulation ***********************************************************************************/

#ifdef DEBUG_SPD_EEPROM
static inline const char *state_serial_str(enum SerialState s)
{
  switch (s) {
    case IDLE:   return "IDLE";
    case WRITE:  return "WRITE";
    case READ:   return "READ";
    case RACK_0: return "RACK_0";
    case RACK_1: return "RACK_1";
    case WACK:   return "WACK";
    default:     return "_";
  }
}

static inline const char *state_transaction_str(enum TransactionState s)
{
  switch (s) {
    case DEV_ADDR:   return "DEV_ADDR";
    case WRITE_ADDR: return "WRITE_ADDR";
    case WRITE_DATA: return "WRITE_DATA";
    case READ_DATA:  return "READ_DATA";
    default:         return "_";
  }
}
#endif

static void fsm_tick(struct session_s *s)
{
  static int sda_last = 1;
  static int scl_last = 1;

  enum SerialState last_state_serial;
  int sda_rising_edge;
  int sda_falling_edge;
  int start_cond;
  int stop_cond;
  int scl_rising;
  int scl_falling;

  sda_rising_edge  = !sda_last && *s->sda_out;
  sda_falling_edge = sda_last && !*s->sda_out;
  start_cond       = sda_falling_edge && *s->scl;
  stop_cond        = sda_rising_edge && *s->scl;
  scl_rising       = !scl_last && *s->scl;
  scl_falling      = scl_last && !*s->scl;

  sda_last = *s->sda_out;
  scl_last = *s->scl;

  if (start_cond) {
    DBG("[spdeeprom] START condition\n");
    s->state_serial = READ;
    s->state_transaction = DEV_ADDR;
    s->bit_counter = 0;
  }
  if (stop_cond) {
    DBG("[spdeeprom] STOP condition\n");
    s->state_serial = IDLE;
    s->state_transaction = DEV_ADDR;
  }

  last_state_serial = s->state_serial;

  switch (s->state_serial) {
    case IDLE:
      *s->sda_in = 1;
      break;
    case READ:
      if (s->bit_counter == 0) {
        s->byte_in = 0;
      }
      if (scl_rising) {
        s->byte_in <<= 1;
        s->byte_in |= *s->sda_out & 1;
        s->bit_counter++;
      }
      if (s->bit_counter >= 8) {
        s->bit_counter = 0;
        s->state_serial = RACK_0;
      }
      break;
    case WRITE:
      if (scl_rising) {
        *s->sda_in = (s->byte_out & (1 << 7)) != 0;
        s->byte_out <<= 1;
        s->bit_counter++;
      }
      if (s->bit_counter >= 8) {
        s->bit_counter = 0;
        s->state_serial = WACK;
      }
      break;
    case RACK_0:  // first falling edge
      if (scl_falling) {
        *s->sda_in = 0;
        s->state_serial = RACK_1;
      }
      break;
    case RACK_1:  // second falling edge
      if (scl_falling) {
        *s->sda_in = 1;
        s->state_serial = state_serial_next(s);
      }
      break;
    case WACK:
      if (scl_rising) {
        if ((*s->sda_out) != 0) {
          DBG("[spdeeprom] No ACK from master!\n");
        }
        s->state_serial = state_serial_next(s);
      }
      break;
    default: DBG("[spdeeprom] unknown state_serial\n"); break;
  }

  if (s->state_serial != last_state_serial) {
    DBG("[spdeeprom] state_serial: %s -> %s\n",
        state_serial_str(last_state_serial), state_serial_str(s->state_serial));
  }

}

static enum SerialState state_serial_next(struct session_s *s)
{
  enum TransactionState state_transaction_last = s->state_transaction;
  enum SerialState state_serial = IDLE;

  switch (s->state_transaction) {
    case DEV_ADDR:
      if (s->state_serial != RACK_1) {
        DBG("[spdeeprom] ERROR: DEV_ADDR during WACK\n");
      }
      s->devaddr = s->byte_in;
      if (((s->devaddr & 0b1110) >> 1) != SPD_EEPROM_ADDR) {
        DBG("[spdeeprom] ERROR: read wrong address\n");
        state_serial = IDLE;
      } else {
        DBG("[spdeeprom] devaddr = 0x%02x\n", s->devaddr);
        if ((s->devaddr & 1) != 0) { // read command
          DBG("[spdeeprom] registered READ cmd\n");
          s->state_transaction = READ_DATA;
          s->byte_out = s->mem[s->addr++];
          s->addr %= sizeof(s->mem);
          state_serial = WRITE;
        } else { // write command
          DBG("[spdeeprom] registered WRITE cmd\n");
          s->state_transaction = WRITE_ADDR;
          state_serial = READ;
        }
      }
      break;
    case WRITE_ADDR:
      if (s->state_serial != RACK_1) {
        DBG("[spdeeprom] ERROR: WRITE_ADDR during WACK\n");
      }
      s->addr = s->byte_in;
      s->state_transaction = WRITE_DATA;
      DBG("[spdeeprom] addr = 0x%02x\n", s->addr);
      state_serial = READ;
      break;
    case WRITE_DATA:
      if (s->state_serial != RACK_1) {
        DBG("[spdeeprom] ERROR: WRITE_DATA during WACK\n");
      }
      s->mem[s->addr++] = s->byte_in;
      s->addr %= sizeof(s->mem);
      s->state_transaction = WRITE_DATA;
      DBG("[spdeeprom] wdata = 0x%02x\n", s->byte_in);
      state_serial = READ;
      break;
    case READ_DATA:
      if (s->state_serial != WACK) {
        DBG("[spdeeprom] ERROR: READ_DATA during RACK\n");
      }
      s->state_transaction = READ_DATA;
      s->byte_out = s->mem[s->addr++];
      DBG("[spdeeprom] rdata = 0x%02x\n", s->byte_out);
      state_serial = WRITE;
      break;
    default:
      DBG("[spdeeprom] ERROR: wrong state_transaction!\n");
      break;
  }

  if (state_serial == IDLE) {
    DBG("[spdeeprom] ERROR: unhandled state_serial_next\n");
  }
  if (state_transaction_last != s->state_transaction) {
    DBG("[spdeeprom] state_transaction: %s -> %s\n", state_transaction_str(state_transaction_last), state_transaction_str(s->state_transaction));
  }
  return state_serial;
}

/*** Helper functions *****************************************************************************/

static void spdeeprom_from_file(struct session_s *s, FILE *file)
{
  size_t bufsize = 0;
  ssize_t n_read;
  char *line = NULL;
  char *c;
  unsigned int byte;
  int i;

  for (i = 0; i < sizeof(s->mem) / sizeof(s->mem[0]); ++i) {
    if ((n_read = getline(&line, &bufsize, file)) < 0) {
      break;
    }
    byte = strtoul(line, &c, 16);
    if (c == line) {
      DBG("[spdeeprom] Incorrect value at line %d\n", i);
    } else {
      s->mem[i] = byte;
    }
  }

  if (line != NULL)
    free(line);
}

static int litex_sim_module_pads_get(struct pad_s *pads, char *name, void **signal)
{
  int ret = RC_OK;
  void *sig=NULL;
  int i;

  if(!pads || !name || !signal) {
    ret = RC_INVARG;
    goto out;
  }

  i = 0;
  while(pads[i].name) {
    if(!strcmp(pads[i].name, name))
    {
      sig = (void*) pads[i].signal;
      break;
    }
    i++;
  }

out:
  *signal = sig;
  return ret;
}
