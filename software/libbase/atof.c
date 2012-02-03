/*  atof.c: converts an ASCII string to float

    Copyright (C) 2003  Jesus Calvino-Fraga, jesusc@ieee.org

    This library is free software; you can redistribute it and/or
    modify it under the terms of the GNU Lesser General Public
    License as published by the Free Software Foundation; either
    version 2.1 of the License, or (at your option) any later version.

    This library is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
    Lesser General Public License for more details.

    You should have received a copy of the GNU Lesser General Public
    License along with this library; if not, write to the Free Software
    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307 USA */

#include <stdlib.h>
#include <ctype.h>

float atof(const char * s)
{
	float value, fraction;
	char iexp;
	char sign;

	//Skip leading blanks
	while (isspace(*s)) s++;

	//Get the sign
	if (*s == '-')
	{
		sign=1;
		s++;
	}
	else
	{
		sign=0;
		if (*s == '+') s++;
	}

	//Get the integer part
	for (value=0.0f; isdigit(*s); s++)
	{
		value=10.0f*value+(*s-'0');
	}

	//Get the fraction
	if (*s == '.')
	{
		s++;
		for (fraction=0.1f; isdigit(*s); s++)
		{
			value+=(*s-'0')*fraction;
			fraction*=0.1f;
		}
	}

	//Finally, the exponent (not very efficient, but enough for now)
	if (toupper(*s)=='E')
	{
		s++;
		iexp=(char)atoi(s);
		{
			while(iexp!=0)
			{
				if(iexp<0)
				{
					value*=0.1f;
					iexp++;
				}
				else
				{
					value*=10.0f;
					iexp--;
				}
			}
		}
	}

	if(sign) value*=-1.0f;
	return (value);
}
