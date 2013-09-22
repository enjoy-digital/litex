// Use this code in your LM32 code to control CSR
// over uart

#define WRITE_CMD 0x01
#define READ_CMD 0x02
#define CLOSE_CMD 0x03
#define MMPTR(x) (*((volatile unsigned int *)(x)))

static void uart2wb(void)
{
	unsigned char cmd;
	unsigned char burst_length;
	unsigned char adr_t[4];
	unsigned int adr;
	char data_t[4];
	unsigned int data;
	unsigned char i;
	unsigned char j;
	
	while(cmd != CLOSE_CMD)
	{
		cmd = readchar();
	
		if (cmd == WRITE_CMD)
		{ 
			burst_length = readchar();
			for(i=0;i<4;i++) adr_t[i] = readchar();
			adr =  adr_t[0]<<24 | adr_t[1]<<16 | adr_t[2]<<8 | adr_t[3];
			for(i=0;i<burst_length;i++)
			{
				for(j=0;j<4;j++) data_t[j] = readchar();
				data = data_t[0]<<24 | data_t[1]<<16 | data_t[2]<<8 | data_t[3];
				MMPTR(adr+4*i) = data;
			}
		}
	
		if (cmd == READ_CMD)
		{
			burst_length = readchar();
			for(i=0;i<4;i++) adr_t[i] = readchar();
			adr = adr_t[0]<<24 | adr_t[1]<<16 | adr_t[2]<<8 | adr_t[3];
			for(i=0;i<burst_length;i++)
			{
				data = MMPTR(adr+4*i);
				data_t[0] = (data & 0xff000000)>>24;
				data_t[1] = (data & 0x00ff0000)>>16;
				data_t[2] = (data & 0x0000ff00)>>8;
				data_t[3] = (data & 0x000000ff);
				for(j=0;j<4;j++) putchar(data_t[j]);
			}
		}
	}
}
