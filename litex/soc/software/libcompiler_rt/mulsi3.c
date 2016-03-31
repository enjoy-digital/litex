
long
__mulsi3(unsigned long a, unsigned long b)
{
long res = 0;
while (a)
{
if (a & 1)
{
res += b;
}
b <<= 1;
a >>=1;
}
return res;
}