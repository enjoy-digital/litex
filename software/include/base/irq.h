/*
 * Milkymist SoC (Software)
 * Copyright (C) 2007, 2008, 2009 Sebastien Bourdeauducq
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, version 3 of the License.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#ifndef __IRQ_H
#define __IRQ_H

static inline void irq_enable(unsigned int en)
{
       __asm__ __volatile__("wcsr IE, %0" : : "r" (en));
}

static inline unsigned int irq_getmask(void)
{
       unsigned int mask;
       __asm__ __volatile__("rcsr %0, IM" : "=r" (mask));
       return mask;
}

static inline void irq_setmask(unsigned int mask)
{
       __asm__ __volatile__("wcsr IM, %0" : : "r" (mask));
}

static inline unsigned int irq_pending(void)
{
       unsigned int pending;
       __asm__ __volatile__("rcsr %0, IP" : "=r" (pending));
       return pending;
}

static inline void irq_ack(unsigned int mask)
{
       __asm__ __volatile__("wcsr IP, %0" : : "r" (mask));
}

static inline unsigned int irq_getie(void)
{
       unsigned int ie;
       __asm__ __volatile__("rcsr %0, IE" : "=r" (ie));
       return ie;
}

static inline void irq_setie(unsigned int ie)
{
       __asm__ __volatile__("wcsr IE, %0" : : "r" (ie));
}

#endif /* __IRQ_H */
