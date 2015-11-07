import cairo
import math


def _cairo_draw_node(ctx, dx, radius, color, outer_color, s):
    ctx.save()

    ctx.translate(dx, 0)

    ctx.set_line_width(0.0)
    gradient_color = cairo.RadialGradient(0, 0, 0, 0, 0, radius)
    gradient_color.add_color_stop_rgb(0, *color)
    gradient_color.add_color_stop_rgb(1, *outer_color)
    ctx.set_source(gradient_color)
    ctx.arc(0, 0, radius, 0, 2*math.pi)
    ctx.fill()

    lines = s.split("\n")
    textws = []
    texths = []
    for line in lines:
        x_bearing, y_bearing, w, h, x_advance, y_advance = ctx.text_extents(line)
        textws.append(w)
        texths.append(h + 2)
    ctx.translate(0, -sum(texths[1:])/2)
    for line, w, h in zip(lines, textws, texths):
        ctx.translate(-w/2, h/2)
        ctx.move_to(0, 0)
        ctx.set_source_rgb(0, 0, 0)
        ctx.show_text(line)
        ctx.translate(w/2, h/2)

    ctx.restore()


def _cairo_draw_connection(ctx, x0, y0, color0, x1, y1, color1):
    ctx.move_to(x0, y0)
    ctx.curve_to(x0, y0+20, x1, y1-20, x1, y1)
    ctx.set_line_width(1.2)
    gradient_color = cairo.LinearGradient(x0, y0, x1, y1)
    gradient_color.add_color_stop_rgb(0, *color0)
    gradient_color.add_color_stop_rgb(1, *color1)
    ctx.set_source(gradient_color)
    ctx.stroke()


class RenderNode:
    def __init__(self, label, children=None, color=(0.8, 0.8, 0.8), radius=40):
        self.label = label
        if children is None:
            children = []
        self.children = children
        self.color = color
        self.outer_color = (color[0]*3/5, color[1]*3/5, color[2]*3/5)
        self.radius = radius
        self.pitch = self.radius*3

    def get_dimensions(self):
        if self.children:
            cws, chs, cdxs = zip(*[c.get_dimensions() for c in self.children])
            w = sum(cws)
            h = self.pitch + max(chs)
            dx = cws[0]/4 - cws[-1]/4
        else:
            w = h = self.pitch
            dx = 0
        return w, h, dx

    def render(self, ctx):
        if self.children:
            cws, chs, cdxs = zip(*[c.get_dimensions() for c in self.children])
            first_child_x = -sum(cws)/2

            ctx.save()
            ctx.translate(first_child_x, self.pitch)
            for c, w in zip(self.children, cws):
                ctx.translate(w/2, 0)
                c.render(ctx)
                ctx.translate(w/2, 0)
            ctx.restore()

            dx = cws[0]/4 - cws[-1]/4

            current_x = first_child_x
            for c, w, cdx in zip(self.children, cws, cdxs):
                current_y = self.pitch - c.radius
                current_x += w/2
                _cairo_draw_connection(ctx, dx, self.radius, self.outer_color, current_x+cdx, current_y, c.outer_color)
                current_x += w/2
        else:
            dx = 0
        _cairo_draw_node(ctx, dx, self.radius, self.color, self.outer_color, self.label)

    def to_svg(self, name):
        w, h, dx = self.get_dimensions()
        surface = cairo.SVGSurface(name, w, h)
        ctx = cairo.Context(surface)
        ctx.translate(w/2, self.pitch/2)
        self.render(ctx)
        surface.finish()


def _test():
    xns = [RenderNode("X"+str(n)) for n in range(5)]
    yns = [RenderNode("Y"+str(n), [RenderNode("foo", color=(0.1*n, 0.5+0.2*n, 1.0-0.3*n))]) for n in range(3)]
    n1 = RenderNode("n1", yns)
    n2 = RenderNode("n2", xns, color=(0.8, 0.5, 0.9))
    top = RenderNode("top", [n1, n2])
    top.to_svg("test.svg")

if __name__ == "__main__":
    _test()
