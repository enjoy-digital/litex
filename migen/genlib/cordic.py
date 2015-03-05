from math import atan, atanh, log, sqrt, pi

from migen.fhdl.std import *

class TwoQuadrantCordic(Module):
	"""Coordinate rotation digital computer

	Trigonometric, and arithmetic functions implemented using
	additions/subtractions and shifts.

	http://eprints.soton.ac.uk/267873/1/tcas1_cordic_review.pdf

	http://www.andraka.com/files/crdcsrvy.pdf

	http://zatto.free.fr/manual/Volder_CORDIC.pdf

	The way the CORDIC is executed is controlled by `eval_mode`.
	If `"iterative"` the stages are iteratively evaluated, one per clock
	cycle. This mode uses the least amount of registers, but has the
	lowest throughput and highest latency.  If `"pipelined"` all stages
	are executed in every clock cycle but separated by registers.  This
	mode has full throughput but uses many registers and has large
	latency. If `"combinatorial"`, there are no registers, throughput is
	maximal and latency is zero. `"pipelined"` and `"combinatorial"` use
	the same number of shifters and adders.

	The type of trigonometric/arithmetic function is determined by
	`cordic_mode` and `func_mode`. :math:`g` is the gain of the CORDIC.

		* rotate-circular: rotate the vector `(xi, yi)` by an angle `zi`.
		  Used to calculate trigonometric functions, `sin(), cos(),
		  tan() = sin()/cos()`, or to perform polar-to-cartesian coordinate
		  transformation:

			.. math::
				x_o = g \\cos(z_i) x_i - g \\sin(z_i) y_i

				y_o = g \\sin(z_i) x_i + g \\cos(z_i) y_i

		* vector-circular: determine length and angle of the vector
		  `(xi, yi)`.  Used to calculate `arctan(), sqrt()` or
		  to perform cartesian-to-polar transformation:

			.. math::
				x_o = g\\sqrt{x_i^2 + y_i^2}

				z_o = z_i + \\tan^{-1}(y_i/x_i)

		* rotate-hyperbolic: hyperbolic functions of `zi`. Used to
		  calculate hyperbolic functions, `sinh, cosh, tanh = cosh/sinh,
		  exp = cosh + sinh`:

			.. math::
				x_o = g \\cosh(z_i) x_i + g \\sinh(z_i) y_i

				y_o = g \\sinh(z_i) x_i + g \\cosh(z_i) z_i

		* vector-hyperbolic: natural logarithm `ln(), arctanh()`, and
		  `sqrt()`. Use `x_i = a + b` and `y_i = a - b` to obtain `2*
		  sqrt(a*b)` and `ln(a/b)/2`:

			.. math::
				x_o = g\\sqrt{x_i^2 - y_i^2}

				z_o = z_i + \\tanh^{-1}(y_i/x_i)

		* rotate-linear: multiply and accumulate (not a very good
		  multiplier implementation):

			.. math::
				y_o = g(y_i + x_i z_i)

		* vector-linear: divide and accumulate:

			.. math::
				z_o = g(z_i + y_i/x_i)

	Parameters
	----------
	width : int
		Bit width of the input and output signals. Defaults to 16. Input
		and output signals are signed.
	widthz : int
		Bit with of `zi` and `zo`. Defaults to the `width`.
	stages : int or None
		Number of CORDIC incremental rotation stages. Defaults to
		`width + min(1, guard)`.
	guard : int or None
		Add guard bits to the intermediate signals. If `None`,
		defaults to `guard = log2(width)` which guarantees accuracy
		to `width` bits.
	eval_mode : str, {"iterative", "pipelined", "combinatorial"}
	cordic_mode : str, {"rotate", "vector"}
	func_mode : str, {"circular", "linear", "hyperbolic"}
		Evaluation and arithmetic mode. See above.

	Attributes
	----------
	xi, yi, zi : Signal(width), in
		Input values, signed.
	xo, yo, zo : Signal(width), out
		Output values, signed.
	new_out : Signal(1), out
		Asserted if output values are freshly updated in the current
		cycle.
	new_in : Signal(1), out
		Asserted if new input values are being read in the next cycle.
	zmax : float
		`zi` and `zo` normalization factor. Floating point `zmax`
		corresponds to `1<<(widthz - 1)`. `x` and `y` are scaled such
		that floating point `1` corresponds to `1<<(width - 1)`.
	gain : float
		Cumulative, intrinsic gain and scaling factor. In circular mode
		`sqrt(xi**2 + yi**2)` should be no larger than `2**(width - 1)/gain`
		to prevent overflow. Additionally, in hyperbolic and linear mode,
		the operation itself can cause overflow.
	interval : int
		Output interval in clock cycles. Inverse throughput.
	latency : int
		Input-to-output latency. The result corresponding to the inputs
		appears at the outputs `latency` cycles later.

	Notes
	-----

	Each stage `i` in the CORDIC performs the following operation:

	.. math::
		x_{i+1} = x_i - m d_i y_i r^{-s_{m,i}},

		y_{i+1} = y_i + d_i x_i r^{-s_{m,i}},

		z_{i+1} = z_i - d_i a_{m,i},

	where:

		* :math:`d_i`: clockwise or counterclockwise, determined by
		  `sign(z_i)` in rotate mode or `sign(-y_i)` in vector mode.

		* :math:`r`: radix of the number system (2)

		* :math:`m`: 1: circular, 0: linear, -1: hyperbolic

		* :math:`s_{m,i}`: non decreasing integer shift sequence

		* :math:`a_{m,i}`: elemetary rotation angle: :math:`a_{m,i} =
		  \\tan^{-1}(\\sqrt{m} s_{m,i})/\\sqrt{m}`.
	"""
	def __init__(self, width=16, widthz=None, stages=None, guard=0,
			eval_mode="iterative", cordic_mode="rotate",
			func_mode="circular"):
		# validate parameters
		assert eval_mode in ("combinatorial", "pipelined", "iterative")
		assert cordic_mode in ("rotate", "vector")
		assert func_mode in ("circular", "linear", "hyperbolic")
		self.cordic_mode = cordic_mode
		self.func_mode = func_mode
		if guard is None:
			# guard bits to guarantee "width" accuracy
			guard = int(log(width)/log(2))
		if widthz is None:
			widthz = width
		if stages is None:
			stages = width + min(1, guard) # cuts error below LSB

		# input output interface
		self.xi = Signal((width, True))
		self.yi = Signal((width, True))
		self.zi = Signal((widthz, True))
		self.xo = Signal((width, True))
		self.yo = Signal((width, True))
		self.zo = Signal((widthz, True))
		self.new_in = Signal()
		self.new_out = Signal()

		###

		a, s, self.zmax, self.gain = self._constants(stages, widthz + guard)
		stages = len(a) # may have increased due to repetitions

		if eval_mode == "iterative":
			num_sig = 3
			self.interval = stages + 1
			self.latency = stages + 2
		else:
			num_sig = stages + 1
			self.interval = 1
			if eval_mode == "pipelined":
				self.latency = stages
			else: # combinatorial
				self.latency = 0

		# inter-stage signals
		x = [Signal((width + guard, True)) for i in range(num_sig)]
		y = [Signal((width + guard, True)) for i in range(num_sig)]
		z = [Signal((widthz + guard, True)) for i in range(num_sig)]

		# hook up inputs and outputs to the first and last inter-stage
		# signals
		self.comb += [
			x[0].eq(self.xi<<guard),
			y[0].eq(self.yi<<guard),
			z[0].eq(self.zi<<guard),
			self.xo.eq(x[-1]>>guard),
			self.yo.eq(y[-1]>>guard),
			self.zo.eq(z[-1]>>guard),
			]

		if eval_mode == "iterative":
			# We afford one additional iteration for in/out.
			i = Signal(max=stages + 1)
			self.comb += [
					self.new_in.eq(i == stages),
					self.new_out.eq(i == 1),
					]
			ai = Signal((widthz + guard, True))
			self.sync += ai.eq(Array(a)[i])
			if range(stages) == s:
				si = i - 1 # shortcut if no stage repetitions
			else:
				si = Signal(max=stages + 1)
				self.sync += si.eq(Array(s)[i])
			xi, yi, zi = x[1], y[1], z[1]
			self.sync += [
					self._stage(xi, yi, zi, xi, yi, zi, si, ai),
					i.eq(i + 1),
					If(i == stages,
						i.eq(0),
					),
					If(i == 0,
						x[2].eq(xi),
						y[2].eq(yi),
						z[2].eq(zi),
						xi.eq(x[0]),
						yi.eq(y[0]),
						zi.eq(z[0]),
					)]
		else:
			self.comb += [
					self.new_out.eq(1),
					self.new_in.eq(1),
					]
			for i, si in enumerate(s):
				stmt = self._stage(x[i], y[i], z[i],
						x[i + 1], y[i + 1], z[i + 1], si, a[i])
				if eval_mode == "pipelined":
					self.sync += stmt
				else: # combinatorial
					self.comb += stmt

	def _constants(self, stages, bits):
		if self.func_mode == "circular":
			s = range(stages)
			a = [atan(2**-i) for i in s]
			g = [sqrt(1 + 2**(-2*i)) for i in s]
			#zmax = sum(a)
			# use pi anyway as the input z can cause overflow
			# and we need the range for quadrant mapping
			zmax = pi
		elif self.func_mode == "linear":
			s = range(stages)
			a = [2**-i for i in s]
			g = [1 for i in s]
			#zmax = sum(a)
			# use 2 anyway as this simplifies a and scaling
			zmax = 2.
		else: # hyperbolic
			s = []
			# need to repeat some stages:
			j = 4
			for i in range(stages):
				if i == j:
					s.append(j)
					j = 3*j + 1
				s.append(i + 1)
			a = [atanh(2**-i) for i in s]
			g = [sqrt(1 - 2**(-2*i)) for i in s]
			zmax = sum(a)*2
		# round here helps the width=2**i - 1 case but hurts the
		# important width=2**i case
		cast = int
		if log(bits)/log(2) % 1:
			cast = round
		a = [cast(ai*2**(bits - 1)/zmax) for ai in a]
		gain = 1.
		for gi in g:
			gain *= gi
		return a, s, zmax, gain

	def _stage(self, xi, yi, zi, xo, yo, zo, i, ai):
		dir = Signal()
		if self.cordic_mode == "rotate":
			self.comb += dir.eq(zi < 0)
		else: # vector
			self.comb += dir.eq(yi >= 0)
		dx = yi>>i
		dy = xi>>i
		dz = ai
		if self.func_mode == "linear":
			dx = 0
		elif self.func_mode == "hyperbolic":
			dx = -dx
		stmt = [
				xo.eq(xi + Mux(dir, dx, -dx)),
				yo.eq(yi + Mux(dir, -dy, dy)),
				zo.eq(zi + Mux(dir, dz, -dz))
		]
		return stmt

class Cordic(TwoQuadrantCordic):
	"""Four-quadrant CORDIC

	Same as :class:`TwoQuadrantCordic` but with support and convergence
	for `abs(zi) > pi/2 in circular rotate mode or `xi < 0` in circular
	vector mode.
	"""
	def __init__(self, **kwargs):
		TwoQuadrantCordic.__init__(self, **kwargs)
		if self.func_mode != "circular":
			return # no need to remap quadrants

		cxi, cyi, czi = self.xi, self.yi, self.zi
		self.xi = xi = Signal.like(cxi)
		self.yi = yi = Signal.like(cyi)
		self.zi = zi = Signal.like(czi)

		###

		q = Signal()
		if self.cordic_mode == "rotate":
			self.comb += q.eq(zi[-2] ^ zi[-1])
		else: # vector
			self.comb += q.eq(xi < 0)
		self.comb += [
				If(q,
					Cat(cxi, cyi, czi).eq(Cat(-xi, -yi,
						zi + (1 << flen(zi) - 1)))
				).Else(
					Cat(cxi, cyi, czi).eq(Cat(xi, yi, zi))
				)
		]
