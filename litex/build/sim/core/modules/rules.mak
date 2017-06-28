$(OBJ_DIR)/%.o: %.c
	$(CC) -c $(CFLAGS) -I../.. -o $@ $<

$(OBJ_DIR)/%.so: $(OBJ_DIR)/%.o
	$(CC) $(LDFLAGS) -Wl,-soname,$@ -o $@ $<

.PHONY: clean
clean:
	rm -f $(OBJ_DIR)/*.o $(OBJ_DIR)/*.so
