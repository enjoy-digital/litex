CC=clang
OBJ=ipc.o main.o

all: migensim.vpi

%.o: %.c
	$(CC) -fPIC -Wall -O2 -c -o $@ $<

migensim.vpi: $(OBJ)
	$(CC) -shared -o $@ $(OBJ) -lvpi

clean:
	rm -f $(OBJ)
	rm -f migensim.vpi

.PHONY: clean
