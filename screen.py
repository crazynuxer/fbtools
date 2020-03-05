# Graphic image using pgmagick, works with python 2 or 3
# See https://www.imagemagick.org/Magick++/Image++.html for C++ API which is
# directly exposed by the python module.

from __future__ import print_function, division
import os, sys
from pgmagick import *

# directory containing this module also contains needed fonts
__here__ = os.path.dirname(__file__) or '.'

# default font is monospaced
__font__ = __here__ + "/WenQuanYiMicroHeiMono.ttf"

# dict of gravities
gravities={ "nw": GravityType.NorthWestGravity,
            "n":  GravityType.NorthGravity,
            "ne": GravityType.NorthEastGravity,
            "w":  GravityType.WestGravity,
            "c":  GravityType.CenterGravity,
            "e":  GravityType.EastGravity,
            "sw": GravityType.SouthWestGravity,
            "s":  GravityType.SouthGravity,
            "se": GravityType.SouthEastGravity }

# python version-agnostic convert object to str or bytes
def _to_str(s):
    try:
        return s.decode('utf-8')
    except:
        return str(s)

def _to_bytes(s):
    try:
        return bytes(s, 'utf-8')
    except:
        return bytes(s)

class image():

    def __init__(
            self,
            width=None, height=None,    # image size
            bg="black", fg="white",     # default colors
            rgb=None                    # init with rgb data (must be the correct size)
        ):

        self.width = width
        self.height = height
        self.fg = fg
        self.bg = bg

        if rgb:
            self.image = Image(Blob(rgb), Geometry(width, height), 8, "RGB")
        else:
            self.image = Image(Geometry(width, height), Color(bg))

    # A bounding box is defined as (left, top, right, bottom), each specified
    # as fraction of the relevant screen dimension if <= 1 , or as an absolute
    # coordinate if > 1. Parse the box for current image, make sure x2,y2 is
    # southeast of x1,y1 and return (left, top, width, height)
    def box(self, l, t, r, b):
        x1 = l if l > 1 else self.width * l
        y1 = t if t > 1 else self.height * t
        x2 = r if r > 1 else self.width * r
        y2 = b if b > 1 else self.height * b
        assert x1 < x2 and y1 < y2
        return (int(x1), int(y1), int(x2-x1+1), int(y2-y1+1))

    # create transparent layer for subsequent overlay
    def layer(self, width=None, height=None, bg="transparent"):
        return Image(Geometry(width or self.width, height or self.height), Color(bg))

    # overlay image with l at specified offset or with specified gravity
    def overlay(self, l, pos=(0,0)):
        if type(pos) in [list, tuple]:
            pos=Geometry(0,0,pos[0],pos[1]) # see http://www.graphicsmagick.org/Magick++/Geometry.html
        else:
            pos=gravities[pos]
        self.image.composite(l, pos, CompositeOperator.OverCompositeOp)

    # Draw a border in fg color on edge of the image
    def border(self, width):
        self.image.strokeWidth(width)
        self.image.strokeColor(self.fg)
        self.image.fillColor("transparent")
        self.image.draw(DrawableRectangle(0, 0, self.width-1, self.height-1))

    # Write text to image
    def text(
            self,
            text,                    # text to be written, may contain tabs and linefeeds.
            left=0, top=0,           # text box offset in image
            width=None, height=None, # text box size
            box=None,                # bounding box, alternative way of defining left, top, width and height
            gravity = 'nw',          # align text to nw, n, ne, w, c, e, sw, s, or se of the text box
            wrap = False,            # wrap long lines to fit
            clip = True,             # clip text to fit frame (False will render partial characters)
            point = 20,              # pointsize
            fg=None,                 # foreground, default to self.fg
            bg="transparent",        # background color
            font = __font__          # font
        ):

        # convert text to list of lines
        text=[s.expandtabs() for s in text.splitlines()]

        if box:
            left, top, width, height = self.box(*box)
        else:
            if height is None: height is self.height
            if width is None: width is self.width

        # write text to a layer
        l = self.layer(width, height, bg)
        l.font(font)
        l.fontPointsize(point)
        tm = TypeMetric()
        l.fontTypeMetrics("M",tm)

        # the y offset is based on font and gravity
        if gravity in ("nw","n","ne"): yoffset = tm.ascent()
        elif gravity in ("sw","s","se"): yoffset = -tm.descent()
        else: yoffset=0

        maxcols = int(width // tm.textWidth())
        maxlines = int(height // (tm.textHeight()+1))

        if wrap:
            # wrap text to fit... this fails for characters wider than 'M'
            def wrapt(t):
                t = t.rstrip(' ')
                while len(t) > maxcols:
                    i = t[:maxcols].rfind(' ')
                    if (i < 0):
                        yield t[:maxcols]
                        t = t[maxcols:]
                    else:
                        yield t[:i]
                        t = t[i+1:]
                    t = t.rstrip(' ')
                yield t
            text = [w for t in text for w in wrapt(t)]

        if clip:
            text = text[:maxlines]
            text = [s[:maxcols] for s in text] # does nothing if wrapped

        if text:
            # If text remains, write it to the layer with gravity
            l.strokeWidth(0)
            l.fillColor(fg or self.fg)
            # XXX can this be done with Image.annotate()?
            d = DrawableList()
            d.append(DrawableGravity(gravities[gravity]))
            d.append(DrawableText(0, yoffset, '\n'.join(text)))
            l.draw(d)

            self.overlay(l, (left, top))

    # Load an image file and scale/stretch.
    def read(
            self,
            filename,       # a filename, '-' for stdin, prefix with FMT: to force format
            margin=0,       # pixels to leave around edge of image
            stretch=False   # stretch image to fit image
        ):

        if filename == '-':
            try: fh = sys.stdin.buffer # python 3
            except: fh = sys.stdin     # python 2
        else:
            fh = open(filename, mode='rb')

        l=Image(Blob(fh.read()))
        g=Geometry(self.width-(margin*2), self.height-(margin*2))
        if stretch: g.aspect(True)
        l.scale(g)
        self.overlay(l,'c')

    # Write the image to a file or stdout. Format is determined from file
    # extent or leading "FMT:" tag (e.g "PNG:data").
    def write(self, filename):
        self.image.write(filename)

    # Return image raw RGB data
    def rgb(self):
        blob=Blob()
        self.image.write(blob, "RGB", 8)
        return blob.data