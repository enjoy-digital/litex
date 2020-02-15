UNAME_S := $(shell uname -s)

$(OBJ_DIR)/%.o: %.c
	$(CC) -c $(CFLAGS) -I../.. -o $@ $<

$(OBJ_DIR)/%.so: $(OBJ_DIR)/%.o
ifeq ($(UNAME_S),Darwin)
	$(CC) $(LDFLAGS) -o $@ $^
else
	$(CC) $(LDFLAGS) -Wl,-soname,$@ -o $@ $<
endif

.PHONY: clean
clean:
	rm -f $(OBJ_DIR)/*.o $(OBJ_DIR)/*.so
