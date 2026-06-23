#ifndef LITEX_BUILD_SIM_CORE_SIM_QEMU_H
#define LITEX_BUILD_SIM_CORE_SIM_QEMU_H

#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <unistd.h>

#include <arpa/inet.h>
#include <event2/event.h>
#include <event2/listener.h>
#include <event2/util.h>
#include <json-c/json.h>

#include "error.h"
#include "modules.h"

#define LITEX_SIM_QEMU_REQ_MAGIC 0x3051584c /* "LXQ0" */
#define LITEX_SIM_QEMU_RSP_MAGIC 0x3052584c /* "LXR0" */
#define LITEX_SIM_QEMU_VERSION   1
#define LITEX_SIM_QEMU_MSG_SIZE  32

enum litex_sim_qemu_op {
  LITEX_SIM_QEMU_OP_READ  = 0,
  LITEX_SIM_QEMU_OP_WRITE = 1,
  LITEX_SIM_QEMU_OP_IRQ   = 2,
};

enum litex_sim_qemu_status {
  LITEX_SIM_QEMU_STATUS_OK      = 0,
  LITEX_SIM_QEMU_STATUS_ERR     = 1,
  LITEX_SIM_QEMU_STATUS_BAD_REQ = 2,
};

struct litex_sim_qemu_request_s {
  uint16_t op;
  uint32_t size;
  uint64_t addr;
  uint64_t data;
};

struct litex_sim_qemu_txn_s {
  uint32_t addr;
  uint32_t data;
  uint8_t strb;
  uint8_t bytes;
  uint8_t offset;
  uint8_t resp_shift;
};

enum litex_sim_qemu_read_rc {
  LITEX_SIM_QEMU_READ_OK = 0,
  LITEX_SIM_QEMU_READ_BAD_REQ,
  LITEX_SIM_QEMU_READ_CLOSED,
};

static inline uint16_t litex_sim_qemu_rd_le16(const uint8_t *p)
{
  return ((uint16_t)p[0]) | ((uint16_t)p[1] << 8);
}

static inline uint32_t litex_sim_qemu_rd_le32(const uint8_t *p)
{
  return ((uint32_t)p[0]) |
    ((uint32_t)p[1] << 8) |
    ((uint32_t)p[2] << 16) |
    ((uint32_t)p[3] << 24);
}

static inline uint64_t litex_sim_qemu_rd_le64(const uint8_t *p)
{
  return ((uint64_t)litex_sim_qemu_rd_le32(p)) |
    ((uint64_t)litex_sim_qemu_rd_le32(p + 4) << 32);
}

static inline void litex_sim_qemu_wr_le16(uint8_t *p, uint16_t v)
{
  p[0] = v & 0xff;
  p[1] = (v >> 8) & 0xff;
}

static inline void litex_sim_qemu_wr_le32(uint8_t *p, uint32_t v)
{
  p[0] = v & 0xff;
  p[1] = (v >> 8) & 0xff;
  p[2] = (v >> 16) & 0xff;
  p[3] = (v >> 24) & 0xff;
}

static inline void litex_sim_qemu_wr_le64(uint8_t *p, uint64_t v)
{
  litex_sim_qemu_wr_le32(p, v & 0xffffffffu);
  litex_sim_qemu_wr_le32(p + 4, v >> 32);
}

static inline int litex_sim_qemu_pads_get(struct pad_s *pads, const char *name,
  void **signal, const char *module_name)
{
  int i;

  if (!pads || !name || !signal) {
    return RC_INVARG;
  }

  *signal = NULL;
  for (i = 0; pads[i].name; i++) {
    if (!strcmp(pads[i].name, name)) {
      *signal = pads[i].signal;
      return RC_OK;
    }
  }

  fprintf(stderr, "[%s] missing pad: %s\n", module_name, name);
  return RC_ERROR;
}

static inline int litex_sim_qemu_parse_bridge_args(char *args, char *bind,
  size_t bind_size, int *port, const char *module_name)
{
  json_object *args_json = NULL;
  json_object *obj = NULL;

  *port = 1235;
  snprintf(bind, bind_size, "%s", "127.0.0.1");

  if (!args) {
    return RC_OK;
  }

  args_json = json_tokener_parse(args);
  if (!args_json) {
    fprintf(stderr, "[%s] could not parse args: %s\n", module_name, args);
    return RC_JSERROR;
  }

  if (json_object_object_get_ex(args_json, "port", &obj)) {
    *port = json_object_get_int(obj);
  }
  if (json_object_object_get_ex(args_json, "bind", &obj)) {
    snprintf(bind, bind_size, "%s", json_object_get_string(obj));
  }

  json_object_put(args_json);
  return RC_OK;
}

static inline int litex_sim_qemu_parse_request(const uint8_t *rxbuf,
  struct litex_sim_qemu_request_s *req)
{
  uint32_t magic = litex_sim_qemu_rd_le32(rxbuf + 0);
  uint16_t version = litex_sim_qemu_rd_le16(rxbuf + 4);
  uint16_t op = litex_sim_qemu_rd_le16(rxbuf + 6);
  uint32_t size = litex_sim_qemu_rd_le32(rxbuf + 8);

  if (magic != LITEX_SIM_QEMU_REQ_MAGIC || version != LITEX_SIM_QEMU_VERSION) {
    return RC_ERROR;
  }

  if (op == LITEX_SIM_QEMU_OP_IRQ) {
    if (size != 0) {
      return RC_ERROR;
    }
  } else if ((op != LITEX_SIM_QEMU_OP_READ && op != LITEX_SIM_QEMU_OP_WRITE) ||
             (size != 1 && size != 2 && size != 4 && size != 8)) {
    return RC_ERROR;
  }

  req->op   = op;
  req->size = size;
  req->addr = litex_sim_qemu_rd_le64(rxbuf + 16);
  req->data = litex_sim_qemu_rd_le64(rxbuf + 24);
  return RC_OK;
}

static inline enum litex_sim_qemu_read_rc litex_sim_qemu_read_request(int fd,
  uint8_t *rxbuf, size_t *rx_len, int *req_valid,
  struct litex_sim_qemu_request_s *req)
{
  while (*rx_len < LITEX_SIM_QEMU_MSG_SIZE && !*req_valid) {
    ssize_t r = recv(fd, rxbuf + *rx_len, LITEX_SIM_QEMU_MSG_SIZE - *rx_len, 0);
    if (r > 0) {
      *rx_len += (size_t)r;
      continue;
    }
    if (r == 0) {
      return LITEX_SIM_QEMU_READ_CLOSED;
    }
    if (errno == EINTR) {
      continue;
    }
    if (errno == EAGAIN || errno == EWOULDBLOCK) {
      break;
    }
    return LITEX_SIM_QEMU_READ_CLOSED;
  }

  if (*rx_len == LITEX_SIM_QEMU_MSG_SIZE) {
    *rx_len = 0;
    if (litex_sim_qemu_parse_request(rxbuf, req) != RC_OK) {
      return LITEX_SIM_QEMU_READ_BAD_REQ;
    }
    *req_valid = 1;
  }

  return LITEX_SIM_QEMU_READ_OK;
}

static inline int litex_sim_qemu_send_response(int fd, uint16_t status,
  uint32_t irq, uint64_t data)
{
  uint8_t rsp[LITEX_SIM_QEMU_MSG_SIZE];
  size_t done = 0;

  if (fd < 0) {
    return RC_ERROR;
  }

  memset(rsp, 0, sizeof(rsp));
  litex_sim_qemu_wr_le32(rsp + 0, LITEX_SIM_QEMU_RSP_MAGIC);
  litex_sim_qemu_wr_le16(rsp + 4, LITEX_SIM_QEMU_VERSION);
  litex_sim_qemu_wr_le16(rsp + 6, status);
  litex_sim_qemu_wr_le32(rsp + 8, irq);
  litex_sim_qemu_wr_le64(rsp + 16, data);

  while (done < sizeof(rsp)) {
    ssize_t r = send(fd, rsp + done, sizeof(rsp) - done, 0);
    if (r > 0) {
      done += (size_t)r;
      continue;
    }
    if (r < 0 && errno == EINTR) {
      continue;
    }
    if (r < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) {
      return RC_OK;
    }
    return RC_ERROR;
  }

  return RC_OK;
}

static inline int litex_sim_qemu_listen(struct event_base *base,
  const char *module_name, const char *bind, int port,
  evconnlistener_cb accept_cb, evconnlistener_errorcb error_cb, void *ctx)
{
  struct evconnlistener *listener;
  struct sockaddr_in sin;

  memset(&sin, 0, sizeof(sin));
  sin.sin_family = AF_INET;
  sin.sin_port = htons((uint16_t)port);
  if (inet_pton(AF_INET, bind, &sin.sin_addr) != 1) {
    fprintf(stderr, "[%s] invalid bind address: %s\n", module_name, bind);
    return RC_ERROR;
  }

  listener = evconnlistener_new_bind(base, accept_cb, ctx,
    LEV_OPT_CLOSE_ON_FREE | LEV_OPT_REUSEABLE, -1,
    (struct sockaddr *)&sin, sizeof(sin));
  if (!listener) {
    fprintf(stderr, "[%s] could not bind %s:%d\n", module_name, bind, port);
    return RC_ERROR;
  }
  evconnlistener_set_error_cb(listener, error_cb);
  printf("[%s] listening on %s:%d\n", module_name, bind, port);

  return RC_OK;
}

static inline int litex_sim_qemu_build_txns(struct litex_sim_qemu_txn_s *txns,
  int max_txns, int *txn_count, uint64_t *resp_data, uint64_t addr,
  uint64_t data, uint32_t size)
{
  uint32_t remaining = size;
  uint8_t resp_shift = 0;

  *txn_count = 0;
  *resp_data = 0;

  while (remaining) {
    struct litex_sim_qemu_txn_s *txn;
    uint8_t offset = addr & 0x3;
    uint8_t bytes = 4 - offset;
    uint8_t i;

    if (bytes > remaining) {
      bytes = remaining;
    }
    if (*txn_count >= max_txns) {
      return RC_ERROR;
    }

    txn = &txns[(*txn_count)++];
    memset(txn, 0, sizeof(*txn));
    txn->addr = addr;
    txn->bytes = bytes;
    txn->offset = offset;
    txn->resp_shift = resp_shift;
    txn->strb = ((1u << bytes) - 1u) << offset;

    for (i = 0; i < bytes; i++) {
      uint8_t byte = (data >> ((resp_shift + i) * 8)) & 0xff;
      txn->data |= ((uint32_t)byte) << ((offset + i) * 8);
    }

    addr += bytes;
    remaining -= bytes;
    resp_shift += bytes;
  }

  return RC_OK;
}

static inline void litex_sim_qemu_capture_read(struct litex_sim_qemu_txn_s *txn,
  uint32_t word, uint64_t *resp_data)
{
  uint8_t i;

  for (i = 0; i < txn->bytes; i++) {
    uint8_t byte = (word >> ((txn->offset + i) * 8)) & 0xff;
    *resp_data |= ((uint64_t)byte) << ((txn->resp_shift + i) * 8);
  }
}

static inline uint64_t litex_sim_qemu_mem_parse_size(const char *value)
{
  char *end = NULL;
  uint64_t size;

  if (!value) {
    return 0;
  }

  errno = 0;
  size = strtoull(value, &end, 0);
  if (errno || end == value) {
    return 0;
  }

  if (!strcmp(end, "K") || !strcmp(end, "k")) {
    size *= 1024ULL;
  } else if (!strcmp(end, "M") || !strcmp(end, "m")) {
    size *= 1024ULL * 1024ULL;
  } else if (!strcmp(end, "G") || !strcmp(end, "g")) {
    size *= 1024ULL * 1024ULL * 1024ULL;
  } else if (*end != '\0') {
    return 0;
  }

  return size;
}

static inline int litex_sim_qemu_mem_parse_optional_args(char *args, char *path,
  size_t path_size, uint64_t *size, int *enabled, const char *module_name)
{
  json_object *args_json = NULL;
  json_object *obj = NULL;

  snprintf(path, path_size, "%s", "qemu-main-ram.bin");
  *size = 0;
  *enabled = 0;

  if (!args) {
    return RC_OK;
  }

  args_json = json_tokener_parse(args);
  if (!args_json) {
    fprintf(stderr, "[%s] could not parse args: %s\n", module_name, args);
    return RC_JSERROR;
  }

  if (json_object_object_get_ex(args_json, "path", &obj)) {
    snprintf(path, path_size, "%s", json_object_get_string(obj));
  }
  if (json_object_object_get_ex(args_json, "size", &obj)) {
    *enabled = 1;
    if (json_object_get_type(obj) == json_type_string) {
      *size = litex_sim_qemu_mem_parse_size(json_object_get_string(obj));
    } else {
      *size = (uint64_t)json_object_get_int64(obj);
    }
  }

  json_object_put(args_json);

  if (*enabled && *size == 0) {
    fprintf(stderr, "[%s] invalid size\n", module_name);
    return RC_INVARG;
  }

  return RC_OK;
}

static inline int litex_sim_qemu_mem_map(int *fd, uint8_t **mem,
  const char *path, uint64_t size, const char *module_name)
{
  *fd = open(path, O_RDWR | O_CREAT, 0666);
  if (*fd < 0) {
    fprintf(stderr, "[%s] could not open %s: %s\n", module_name, path, strerror(errno));
    return RC_ERROR;
  }

  if (ftruncate(*fd, (off_t)size) < 0) {
    fprintf(stderr, "[%s] could not size %s: %s\n", module_name, path, strerror(errno));
    close(*fd);
    *fd = -1;
    return RC_ERROR;
  }

  *mem = mmap(NULL, (size_t)size, PROT_READ | PROT_WRITE, MAP_SHARED, *fd, 0);
  if (*mem == MAP_FAILED) {
    *mem = NULL;
    fprintf(stderr, "[%s] could not mmap %s: %s\n", module_name, path, strerror(errno));
    close(*fd);
    *fd = -1;
    return RC_ERROR;
  }

  printf("[%s] mapped %s (%llu bytes)\n",
    module_name, path, (unsigned long long)size);

  return RC_OK;
}

static inline int litex_sim_qemu_mem_close(int fd, uint8_t *mem, uint64_t size)
{
  if (mem) {
    munmap(mem, (size_t)size);
  }
  if (fd >= 0) {
    close(fd);
  }
  return RC_OK;
}

static inline uint32_t litex_sim_qemu_mem_read32(uint8_t *mem, uint64_t addr)
{
  return ((uint32_t)mem[addr + 0]) |
    ((uint32_t)mem[addr + 1] << 8) |
    ((uint32_t)mem[addr + 2] << 16) |
    ((uint32_t)mem[addr + 3] << 24);
}

static inline void litex_sim_qemu_mem_write32(uint8_t *mem, uint64_t addr,
  uint32_t data, uint8_t sel)
{
  int i;

  for (i = 0; i < 4; i++) {
    if (sel & (1 << i)) {
      mem[addr + i] = (data >> (8 * i)) & 0xff;
    }
  }
}

#endif /* LITEX_BUILD_SIM_CORE_SIM_QEMU_H */
