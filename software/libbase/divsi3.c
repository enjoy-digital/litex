#define divnorm(num, den, sign) 		\
{						\
  if(num < 0) 					\
    {						\
      num = -num;				\
      sign = 1;					\
    }						\
  else 						\
    {						\
      sign = 0;					\
    }						\
						\
  if(den < 0) 					\
    {						\
      den = - den;				\
      sign = 1 - sign;				\
    } 						\
}

#define exitdiv(sign, res) if (sign) { res = - res;} return res;

long __divsi3 (long numerator, long denominator);
long __divsi3 (long numerator, long denominator)
{
	int sign;
	long dividend;

	divnorm(numerator, denominator, sign);

	dividend = (unsigned int)numerator/(unsigned int)denominator;
	exitdiv(sign, dividend);
}

long __modsi3 (long numerator, long denominator);
long __modsi3 (long numerator, long denominator)
{
	int sign;
	long res;

	if(numerator < 0) {
		numerator = -numerator;
		sign = 1;
	} else
		sign = 0;

	if(denominator < 0)
		denominator = -denominator;

	res = (unsigned int)numerator % (unsigned int)denominator;

	if(sign)
		return -res;
	else
		return res;
}
