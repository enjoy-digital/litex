#include "sim_qemu.h"

#define QEMU_AXI_RESP_OKAY 0
#define QEMU_AXI_RESP_SLVERR 2
#define QEMU_AXI_SIZE_32B  2
#define QEMU_AXI_BURST_FIXED 0
#define QEMU_AXI_BURST_INCR 1

struct session_s {
  uint8_t  *awvalid;
  uint8_t  *awready;
  uint32_t *awaddr;
  uint8_t  *awburst;
  uint8_t  *awlen;
  uint8_t  *awsize;
  uint8_t  *awlock;
  uint8_t  *awprot;
  uint8_t  *awcache;
  uint8_t  *awqos;
  uint8_t  *awregion;
  uint8_t  *awid;
  uint8_t  *awuser;
  uint8_t  *wvalid;
  uint8_t  *wready;
  uint8_t  *wlast;
  uint32_t *wdata;
  uint8_t  *wstrb;
  uint8_t  *wuser;
  uint8_t  *bvalid;
  uint8_t  *bready;
  uint8_t  *bresp;
  uint8_t  *bid;
  uint8_t  *buser;
  uint8_t  *arvalid;
  uint8_t  *arready;
  uint32_t *araddr;
  uint8_t  *arburst;
  uint8_t  *arlen;
  uint8_t  *arsize;
  uint8_t  *arlock;
  uint8_t  *arprot;
  uint8_t  *arcache;
  uint8_t  *arqos;
  uint8_t  *arregion;
  uint8_t  *arid;
  uint8_t  *aruser;
  uint8_t  *rvalid;
  uint8_t  *rready;
  uint8_t  *rlast;
  uint8_t  *rresp;
  uint32_t *rdata;
  uint8_t  *rid;
  uint8_t  *ruser;
  uint8_t  *sys_clk;
  uint32_t *irq;
  uint8_t  *reset;

  clk_edge_state_t clk_edge;

  uint8_t  *ram_awvalid;
  uint8_t  *ram_awready;
  uint32_t *ram_awaddr;
  uint8_t  *ram_awburst;
  uint8_t  *ram_awlen;
  uint8_t  *ram_awsize;
  uint8_t  *ram_awlock;
  uint8_t  *ram_awprot;
  uint8_t  *ram_awcache;
  uint8_t  *ram_awqos;
  uint8_t  *ram_awregion;
  uint8_t  *ram_awid;
  uint8_t  *ram_awuser;
  uint8_t  *ram_wvalid;
  uint8_t  *ram_wready;
  uint8_t  *ram_wlast;
  uint32_t *ram_wdata;
  uint8_t  *ram_wstrb;
  uint8_t  *ram_wuser;
  uint8_t  *ram_bvalid;
  uint8_t  *ram_bready;
  uint8_t  *ram_bresp;
  uint8_t  *ram_bid;
  uint8_t  *ram_buser;
  uint8_t  *ram_arvalid;
  uint8_t  *ram_arready;
  uint32_t *ram_araddr;
  uint8_t  *ram_arburst;
  uint8_t  *ram_arlen;
  uint8_t  *ram_arsize;
  uint8_t  *ram_arlock;
  uint8_t  *ram_arprot;
  uint8_t  *ram_arcache;
  uint8_t  *ram_arqos;
  uint8_t  *ram_arregion;
  uint8_t  *ram_arid;
  uint8_t  *ram_aruser;
  uint8_t  *ram_rvalid;
  uint8_t  *ram_rready;
  uint8_t  *ram_rlast;
  uint8_t  *ram_rresp;
  uint32_t *ram_rdata;
  uint8_t  *ram_rid;
  uint8_t  *ram_ruser;

  int ram_fd;
  int ram_enabled;
  char ram_path[512];
  uint64_t ram_size;
  uint8_t *ram_mem;

  int ram_write_active;
  uint32_t ram_wr_addr;
  uint8_t ram_wr_len;
  uint8_t ram_wr_size;
  uint8_t ram_wr_burst;
  uint8_t ram_wr_id;
  uint8_t ram_wr_beat;
  uint8_t ram_wr_resp;
  int ram_b_valid;
  uint8_t ram_b_resp;
  uint8_t ram_b_id;

  int ram_read_active;
  uint32_t ram_rd_addr;
  uint8_t ram_rd_len;
  uint8_t ram_rd_size;
  uint8_t ram_rd_burst;
  uint8_t ram_rd_id;
  uint8_t ram_rd_beat;
  int ram_r_valid;
  uint32_t ram_r_data;
  uint8_t ram_r_resp;
  uint8_t ram_r_id;
  uint8_t ram_r_last;

  struct event *ev;
  int fd;
  int port;
  char bind[64];
  uint8_t rxbuf[LITEX_SIM_QEMU_MSG_SIZE];
  size_t rx_len;

  int req_valid;
  int active;
  int reset_latched;
  int aw_done;
  int w_done;
  int b_seen;
  int ar_done;
  int r_seen;
  uint8_t b_resp;
  uint8_t r_resp;
  struct litex_sim_qemu_request_s req;
  struct litex_sim_qemu_txn_s txns[4];
  int txn_count;
  int txn_index;
  uint64_t resp_data;
};

static struct event_base *base;

static void qemu_axi_drive_idle(struct session_s *s)
{
  if (!s->awvalid) {
    return;
  }
  *s->awvalid = 0;
  *s->awaddr  = 0;
  *s->awburst = 0;
  *s->awlen   = 0;
  *s->awsize  = 0;
  *s->awlock  = 0;
  *s->awprot  = 0;
  *s->awcache = 0;
  *s->awqos   = 0;
  *s->awregion = 0;
  *s->awid    = 0;
  *s->awuser  = 0;
  *s->wvalid  = 0;
  *s->wlast   = 0;
  *s->wdata   = 0;
  *s->wstrb   = 0;
  *s->wuser   = 0;
  *s->bready  = 0;
  *s->arvalid = 0;
  *s->araddr  = 0;
  *s->arburst = 0;
  *s->arlen   = 0;
  *s->arsize  = 0;
  *s->arlock  = 0;
  *s->arprot  = 0;
  *s->arcache = 0;
  *s->arqos   = 0;
  *s->arregion = 0;
  *s->arid    = 0;
  *s->aruser  = 0;
  *s->rready  = 0;
}

static uint32_t qemu_axi_irq(struct session_s *s)
{
  return s->irq ? *s->irq : 0;
}

static void qemu_axi_latch_reset(struct session_s *s)
{
  if (s->reset && *s->reset) {
    s->reset_latched = 1;
  }
}

static uint64_t qemu_axi_reset_status(struct session_s *s)
{
  uint64_t reset = s->reset_latched || (s->reset && *s->reset);

  s->reset_latched = 0;
  return reset;
}

static void qemu_axi_close_client(struct session_s *s)
{
  if (s->ev) {
    event_del(s->ev);
    event_free(s->ev);
    s->ev = NULL;
  }
  if (s->fd >= 0) {
    close(s->fd);
    s->fd = -1;
  }
  s->rx_len = 0;
  s->req_valid = 0;
  s->active = 0;
  qemu_axi_drive_idle(s);
}

static int qemu_axi_send_response(struct session_s *s, uint16_t status, uint64_t data)
{
  int ret;

  ret = litex_sim_qemu_send_response(s->fd, status, qemu_axi_irq(s), data);
  if (ret != RC_OK) {
    qemu_axi_close_client(s);
  }
  return ret;
}

static void qemu_axi_read_handler(int fd, short event, void *arg)
{
  struct session_s *s = (struct session_s *)arg;
  enum litex_sim_qemu_read_rc ret;

  (void)event;

  ret = litex_sim_qemu_read_request(fd, s->rxbuf, &s->rx_len,
    &s->req_valid, &s->req);
  if (ret == LITEX_SIM_QEMU_READ_CLOSED) {
    qemu_axi_close_client(s);
  } else if (ret == LITEX_SIM_QEMU_READ_BAD_REQ) {
    qemu_axi_send_response(s, LITEX_SIM_QEMU_STATUS_BAD_REQ, 0);
  }
}

static void qemu_axi_accept_cb(struct evconnlistener *listener,
  evutil_socket_t fd, struct sockaddr *address, int socklen, void *ctx)
{
  struct session_s *s = (struct session_s *)ctx;

  (void)listener;
  (void)address;
  (void)socklen;

  qemu_axi_close_client(s);
  s->fd = fd;
  evutil_make_socket_nonblocking(fd);
  s->ev = event_new(base, fd, EV_READ | EV_PERSIST, qemu_axi_read_handler, s);
  event_add(s->ev, NULL);
  printf("[qemu_axi] client connected\n");
}

static void qemu_axi_accept_error_cb(struct evconnlistener *listener, void *ctx)
{
  struct event_base *event_base = evconnlistener_get_base(listener);

  (void)ctx;
  fprintf(stderr, "[qemu_axi] listener error\n");
  event_base_loopexit(event_base, NULL);
}

static int qemu_axi_start(void *b)
{
  base = (struct event_base *)b;
  printf("[qemu_axi] loaded (%p)\n", base);
  return RC_OK;
}

static int qemu_axi_new(void **sess, char *args)
{
  int ret = RC_OK;
  struct session_s *s = NULL;

  if (!sess) {
    return RC_INVARG;
  }

  s = (struct session_s *)malloc(sizeof(struct session_s));
  if (!s) {
    return RC_NOENMEM;
  }
  memset(s, 0, sizeof(struct session_s));
  s->fd = -1;
  s->ram_fd = -1;

  ret = litex_sim_qemu_parse_bridge_args(args, s->bind, sizeof(s->bind),
    &s->port, "qemu_axi");
  if (ret != RC_OK) {
    goto out;
  }

  ret = litex_sim_qemu_mem_parse_optional_args(args, s->ram_path, sizeof(s->ram_path),
    &s->ram_size, &s->ram_enabled, "qemu_axi");
  if (ret != RC_OK) {
    goto out;
  }

  if (s->ram_enabled) {
    ret = litex_sim_qemu_mem_map(&s->ram_fd, &s->ram_mem,
      s->ram_path, s->ram_size, "qemu_axi");
    if (ret != RC_OK) {
      goto out;
    }
  }

  ret = litex_sim_qemu_listen(base, "qemu_axi", s->bind, s->port,
    qemu_axi_accept_cb, qemu_axi_accept_error_cb, s);

out:
  *sess = (void *)s;
  return ret;
}

static int qemu_axi_add_pads(void *sess, struct pad_list_s *plist)
{
  int ret = RC_OK;
  struct session_s *s = (struct session_s *)sess;
  struct pad_s *pads;

  if (!sess || !plist) {
    return RC_INVARG;
  }

  pads = plist->pads;
  if (!strcmp(plist->name, "qemu_axi")) {
    ret |= litex_sim_qemu_pads_get(pads, "awvalid",  (void **)&s->awvalid,  "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "awready",  (void **)&s->awready,  "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "awaddr",   (void **)&s->awaddr,   "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "awburst",  (void **)&s->awburst,  "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "awlen",    (void **)&s->awlen,    "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "awsize",   (void **)&s->awsize,   "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "awlock",   (void **)&s->awlock,   "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "awprot",   (void **)&s->awprot,   "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "awcache",  (void **)&s->awcache,  "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "awqos",    (void **)&s->awqos,    "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "awregion", (void **)&s->awregion, "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "awid",     (void **)&s->awid,     "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "awuser",   (void **)&s->awuser,   "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "wvalid",   (void **)&s->wvalid,   "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "wready",   (void **)&s->wready,   "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "wlast",    (void **)&s->wlast,    "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "wdata",    (void **)&s->wdata,    "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "wstrb",    (void **)&s->wstrb,    "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "wuser",    (void **)&s->wuser,    "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "bvalid",   (void **)&s->bvalid,   "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "bready",   (void **)&s->bready,   "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "bresp",    (void **)&s->bresp,    "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "bid",      (void **)&s->bid,      "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "buser",    (void **)&s->buser,    "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "arvalid",  (void **)&s->arvalid,  "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "arready",  (void **)&s->arready,  "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "araddr",   (void **)&s->araddr,   "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "arburst",  (void **)&s->arburst,  "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "arlen",    (void **)&s->arlen,    "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "arsize",   (void **)&s->arsize,   "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "arlock",   (void **)&s->arlock,   "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "arprot",   (void **)&s->arprot,   "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "arcache",  (void **)&s->arcache,  "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "arqos",    (void **)&s->arqos,    "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "arregion", (void **)&s->arregion, "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "arid",     (void **)&s->arid,     "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "aruser",   (void **)&s->aruser,   "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "rvalid",   (void **)&s->rvalid,   "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "rready",   (void **)&s->rready,   "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "rlast",    (void **)&s->rlast,    "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "rresp",    (void **)&s->rresp,    "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "rdata",    (void **)&s->rdata,    "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "rid",      (void **)&s->rid,      "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "ruser",    (void **)&s->ruser,    "qemu_axi");
  } else if (!strcmp(plist->name, "qemu_axi_shared_ram")) {
    ret |= litex_sim_qemu_pads_get(pads, "awvalid",  (void **)&s->ram_awvalid,  "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "awready",  (void **)&s->ram_awready,  "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "awaddr",   (void **)&s->ram_awaddr,   "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "awburst",  (void **)&s->ram_awburst,  "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "awlen",    (void **)&s->ram_awlen,    "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "awsize",   (void **)&s->ram_awsize,   "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "awlock",   (void **)&s->ram_awlock,   "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "awprot",   (void **)&s->ram_awprot,   "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "awcache",  (void **)&s->ram_awcache,  "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "awqos",    (void **)&s->ram_awqos,    "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "awregion", (void **)&s->ram_awregion, "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "awid",     (void **)&s->ram_awid,     "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "awuser",   (void **)&s->ram_awuser,   "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "wvalid",   (void **)&s->ram_wvalid,   "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "wready",   (void **)&s->ram_wready,   "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "wlast",    (void **)&s->ram_wlast,    "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "wdata",    (void **)&s->ram_wdata,    "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "wstrb",    (void **)&s->ram_wstrb,    "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "wuser",    (void **)&s->ram_wuser,    "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "bvalid",   (void **)&s->ram_bvalid,   "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "bready",   (void **)&s->ram_bready,   "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "bresp",    (void **)&s->ram_bresp,    "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "bid",      (void **)&s->ram_bid,      "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "buser",    (void **)&s->ram_buser,    "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "arvalid",  (void **)&s->ram_arvalid,  "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "arready",  (void **)&s->ram_arready,  "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "araddr",   (void **)&s->ram_araddr,   "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "arburst",  (void **)&s->ram_arburst,  "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "arlen",    (void **)&s->ram_arlen,    "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "arsize",   (void **)&s->ram_arsize,   "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "arlock",   (void **)&s->ram_arlock,   "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "arprot",   (void **)&s->ram_arprot,   "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "arcache",  (void **)&s->ram_arcache,  "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "arqos",    (void **)&s->ram_arqos,    "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "arregion", (void **)&s->ram_arregion, "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "arid",     (void **)&s->ram_arid,     "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "aruser",   (void **)&s->ram_aruser,   "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "rvalid",   (void **)&s->ram_rvalid,   "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "rready",   (void **)&s->ram_rready,   "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "rlast",    (void **)&s->ram_rlast,    "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "rresp",    (void **)&s->ram_rresp,    "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "rdata",    (void **)&s->ram_rdata,    "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "rid",      (void **)&s->ram_rid,      "qemu_axi");
    ret |= litex_sim_qemu_pads_get(pads, "ruser",    (void **)&s->ram_ruser,    "qemu_axi");
  } else if (!strcmp(plist->name, "qemu_irq")) {
    ret |= litex_sim_qemu_pads_get(pads, "qemu_irq", (void **)&s->irq, "qemu_axi");
  } else if (!strcmp(plist->name, "qemu_reset")) {
    ret |= litex_sim_qemu_pads_get(pads, "qemu_reset", (void **)&s->reset, "qemu_axi");
  } else if (!strcmp(plist->name, "sys_clk")) {
    ret |= litex_sim_qemu_pads_get(pads, "sys_clk", (void **)&s->sys_clk, "qemu_axi");
  }

  return ret;
}

static uint8_t qemu_axi_shared_ram_write(struct session_s *s,
  uint32_t addr, uint32_t data, uint8_t strb)
{
  uint64_t word_addr = (uint64_t)addr & ~3ULL;

  if (word_addr + 4 > s->ram_size) {
    return QEMU_AXI_RESP_SLVERR;
  }

  litex_sim_qemu_mem_write32(s->ram_mem, word_addr, data, strb);
  return QEMU_AXI_RESP_OKAY;
}

static uint8_t qemu_axi_shared_ram_read(struct session_s *s, uint32_t addr, uint32_t *data)
{
  uint64_t word_addr = (uint64_t)addr & ~3ULL;

  if (word_addr + 4 > s->ram_size) {
    *data = 0;
    return QEMU_AXI_RESP_SLVERR;
  }

  *data = litex_sim_qemu_mem_read32(s->ram_mem, word_addr);
  return QEMU_AXI_RESP_OKAY;
}

static uint32_t qemu_axi_shared_ram_next_addr(uint32_t addr, uint8_t size, uint8_t burst)
{
  uint32_t step = 1u << size;

  if (step > 4) {
    step = 4;
  }
  if (burst == QEMU_AXI_BURST_FIXED) {
    return addr;
  }
  return addr + step;
}

static void qemu_axi_shared_ram_drive(struct session_s *s)
{
  *s->ram_awready = !s->ram_write_active && !s->ram_b_valid;
  *s->ram_wready  = s->ram_write_active && !s->ram_b_valid;
  *s->ram_bvalid  = s->ram_b_valid;
  *s->ram_bresp   = s->ram_b_resp;
  *s->ram_bid     = s->ram_b_id;
  *s->ram_buser   = 0;
  *s->ram_arready = !s->ram_read_active && !s->ram_r_valid;
  *s->ram_rvalid  = s->ram_r_valid;
  *s->ram_rresp   = s->ram_r_resp;
  *s->ram_rdata   = s->ram_r_data;
  *s->ram_rid     = s->ram_r_id;
  *s->ram_rlast   = s->ram_r_last;
  *s->ram_ruser   = 0;
}

static void qemu_axi_shared_ram_start_read_beat(struct session_s *s)
{
  s->ram_r_resp = qemu_axi_shared_ram_read(s, s->ram_rd_addr, &s->ram_r_data);
  s->ram_r_id = s->ram_rd_id;
  s->ram_r_last = s->ram_rd_beat >= s->ram_rd_len;
  s->ram_r_valid = 1;

  if (!s->ram_r_last) {
    s->ram_rd_beat++;
    s->ram_rd_addr = qemu_axi_shared_ram_next_addr(
      s->ram_rd_addr, s->ram_rd_size, s->ram_rd_burst);
  }
}

static void qemu_axi_shared_ram_tick(struct session_s *s)
{
  if (!s->ram_enabled || !s->ram_awvalid) {
    return;
  }

  if (s->ram_b_valid && *s->ram_bready) {
    s->ram_b_valid = 0;
  }

  if (s->ram_r_valid && *s->ram_rready) {
    if (s->ram_r_last) {
      s->ram_read_active = 0;
    }
    s->ram_r_valid = 0;
  }

  if (!s->ram_write_active && !s->ram_b_valid && *s->ram_awvalid) {
    s->ram_write_active = 1;
    s->ram_wr_addr  = *s->ram_awaddr;
    s->ram_wr_len   = *s->ram_awlen;
    s->ram_wr_size  = *s->ram_awsize;
    s->ram_wr_burst = *s->ram_awburst;
    s->ram_wr_id    = *s->ram_awid;
    s->ram_wr_beat  = 0;
    s->ram_wr_resp  = QEMU_AXI_RESP_OKAY;
  }

  if (s->ram_write_active && !s->ram_b_valid && *s->ram_wvalid) {
    uint8_t resp = qemu_axi_shared_ram_write(s,
      s->ram_wr_addr, *s->ram_wdata, *s->ram_wstrb);
    if (resp != QEMU_AXI_RESP_OKAY) {
      s->ram_wr_resp = resp;
    }
    if (*s->ram_wlast || s->ram_wr_beat >= s->ram_wr_len) {
      s->ram_b_resp = s->ram_wr_resp;
      s->ram_b_id = s->ram_wr_id;
      s->ram_b_valid = 1;
      s->ram_write_active = 0;
    } else {
      s->ram_wr_beat++;
      s->ram_wr_addr = qemu_axi_shared_ram_next_addr(
        s->ram_wr_addr, s->ram_wr_size, s->ram_wr_burst);
    }
  }

  if (!s->ram_read_active && !s->ram_r_valid && *s->ram_arvalid) {
    s->ram_read_active = 1;
    s->ram_rd_addr  = *s->ram_araddr;
    s->ram_rd_len   = *s->ram_arlen;
    s->ram_rd_size  = *s->ram_arsize;
    s->ram_rd_burst = *s->ram_arburst;
    s->ram_rd_id    = *s->ram_arid;
    s->ram_rd_beat  = 0;
  }

  if (s->ram_read_active && !s->ram_r_valid) {
    qemu_axi_shared_ram_start_read_beat(s);
  }

  qemu_axi_shared_ram_drive(s);
}

static int qemu_axi_build_txns(struct session_s *s)
{
  s->txn_index = 0;
  return litex_sim_qemu_build_txns(s->txns,
    sizeof(s->txns) / sizeof(s->txns[0]),
    &s->txn_count, &s->resp_data,
    s->req.addr, s->req.data, s->req.size);
}

static void qemu_axi_reset_txn_state(struct session_s *s)
{
  s->aw_done = 0;
  s->w_done = 0;
  s->b_seen = 0;
  s->ar_done = 0;
  s->r_seen = 0;
  s->b_resp = 0;
  s->r_resp = 0;
}

static void qemu_axi_capture_read(struct session_s *s)
{
  litex_sim_qemu_capture_read(&s->txns[s->txn_index],
    *s->rdata, &s->resp_data);
}

static void qemu_axi_finish_txn(struct session_s *s, uint8_t resp)
{
  if (resp != QEMU_AXI_RESP_OKAY) {
    qemu_axi_send_response(s, LITEX_SIM_QEMU_STATUS_ERR, 0);
    s->active = 0;
    s->req_valid = 0;
    return;
  }

  s->txn_index++;
  if (s->txn_index >= s->txn_count) {
    qemu_axi_send_response(s, LITEX_SIM_QEMU_STATUS_OK, s->resp_data);
    s->active = 0;
    s->req_valid = 0;
  } else {
    qemu_axi_reset_txn_state(s);
  }
}

static void qemu_axi_drive_txn(struct session_s *s)
{
  struct litex_sim_qemu_txn_s *txn = &s->txns[s->txn_index];

  if (s->req.op == LITEX_SIM_QEMU_OP_WRITE) {
    *s->awvalid = !s->aw_done;
    *s->awaddr  = txn->addr;
    *s->awburst = QEMU_AXI_BURST_INCR;
    *s->awlen   = 0;
    *s->awsize  = QEMU_AXI_SIZE_32B;
    *s->awlock  = 0;
    *s->awprot  = 0;
    *s->awcache = 0x3;
    *s->awqos   = 0;
    *s->awregion = 0;
    *s->awid    = 0;
    *s->awuser  = 0;
    *s->wvalid  = !s->w_done;
    *s->wlast   = 1;
    *s->wdata   = txn->data;
    *s->wstrb   = txn->strb;
    *s->wuser   = 0;
    *s->bready  = s->b_seen;
    *s->arvalid = 0;
    *s->rready  = 0;
  } else {
    *s->awvalid = 0;
    *s->wvalid  = 0;
    *s->bready  = 0;
    *s->arvalid = !s->ar_done;
    *s->araddr  = txn->addr;
    *s->arburst = QEMU_AXI_BURST_INCR;
    *s->arlen   = 0;
    *s->arsize  = QEMU_AXI_SIZE_32B;
    *s->arlock  = 0;
    *s->arprot  = 0;
    *s->arcache = 0x3;
    *s->arqos   = 0;
    *s->arregion = 0;
    *s->arid    = 0;
    *s->aruser  = 0;
    *s->rready  = s->r_seen;
  }
}

static int qemu_axi_tick(void *sess, uint64_t time_ps)
{
  struct session_s *s = (struct session_s *)sess;

  (void)time_ps;

  if (!s || !s->sys_clk || !clk_pos_edge(&s->clk_edge, *s->sys_clk)) {
    return RC_OK;
  }
  qemu_axi_latch_reset(s);
  qemu_axi_shared_ram_tick(s);

  if (s->active && s->req.op == LITEX_SIM_QEMU_OP_WRITE) {
    int aw_valid = !s->aw_done;
    int w_valid  = (s->aw_done || (aw_valid && *s->awready)) && !s->w_done;
    if (s->b_seen) {
      qemu_axi_finish_txn(s, s->b_resp);
    } else {
      if (aw_valid && *s->awready) {
        s->aw_done = 1;
      }
      if (w_valid && *s->wready) {
        s->w_done = 1;
      }
      if (*s->bvalid) {
        s->b_resp = *s->bresp;
        s->b_seen = 1;
      }
    }
  }

  if (s->active && s->req.op == LITEX_SIM_QEMU_OP_READ) {
    int ar_valid = !s->ar_done;
    if (s->r_seen) {
      qemu_axi_finish_txn(s, s->r_resp);
    } else {
      if (ar_valid && *s->arready) {
        s->ar_done = 1;
      }
      if (*s->rvalid) {
        qemu_axi_capture_read(s);
        s->r_resp = *s->rresp;
        s->r_seen = 1;
      }
    }
  }

  if (!s->active && s->req_valid) {
    if (s->req.op == LITEX_SIM_QEMU_OP_IRQ) {
      qemu_axi_send_response(s, LITEX_SIM_QEMU_STATUS_OK, qemu_axi_reset_status(s));
      s->req_valid = 0;
    } else if (qemu_axi_build_txns(s) != RC_OK) {
      qemu_axi_send_response(s, LITEX_SIM_QEMU_STATUS_BAD_REQ, 0);
      s->req_valid = 0;
    } else {
      qemu_axi_reset_txn_state(s);
      s->active = 1;
    }
  }

  if (s->active) {
    qemu_axi_drive_txn(s);
  } else {
    qemu_axi_drive_idle(s);
  }

  return RC_OK;
}

static struct ext_module_s ext_mod = {
  "qemu_axi",
  qemu_axi_start,
  qemu_axi_new,
  qemu_axi_add_pads,
  NULL,
  qemu_axi_tick
};

int litex_sim_ext_module_init(int (*register_module)(struct ext_module_s *))
{
  return register_module(&ext_mod);
}
