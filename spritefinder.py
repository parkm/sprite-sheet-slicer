import wx
from threading import Thread

class Pixel():
    def __init__(self, img, x, y):
        self.x = x
        self.y = y

        # Is this pixel inside the image?
        if self.x >= 0 and self.y >= 0 and self.x < img.Width and self.y < img.Height:
            self.invisible = (img.GetAlpha(x, y) <= 0)
            self.outOfBounds = False
        else:
            self.invisible = None
            self.outOfBounds = True

        self.img = img

    # Returns neighbors from the 4 cardinal compass directions.
    def getCardinalNeighbors(self):
        return [
            Pixel(self.img, self.x+1, self.y),
            Pixel(self.img, self.x-1, self.y),
            Pixel(self.img, self.x, self.y+1),
            Pixel(self.img, self.x, self.y-1),
        ]

    # Returns neighbors from the corner directions.
    def getCornerNeighbors(self):
        return [
            Pixel(self.img, self.x+1, self.y-1),
            Pixel(self.img, self.x+1, self.y+1),
            Pixel(self.img, self.x-1, self.y+1),
            Pixel(self.img, self.x-1, self.y-1),
        ]

# Finds a sprite bounding box from a pixel. Returns wx.Rect
def findFromPixel(img, x, y):
    start = Pixel(img, x, y)

    left = start.x
    top = start.y
    right = start.x+1
    bottom = start.y+1

    unvisited = []
    visited = set() # Used for quick lookups.

    unvisited.extend(start.getCardinalNeighbors())
    unvisited.extend(start.getCornerNeighbors())

    lastPixel = None # Last visited pixel

    while unvisited:
        pixel = unvisited.pop()
        x = pixel.x
        y = pixel.y

        if (pixel.outOfBounds) or (pixel.invisible) or ((x, y) in visited):
            continue

        visited.add((x, y))

        if   x > right:  right  = x
        elif x < left:   left   = x
        if   y > bottom: bottom = y
        elif y < top:    top    = y

        # Figures out if we should use cardinal or corner directions.
        neighbors = pixel.getCardinalNeighbors()
        if all(p.invisible or p.outOfBounds or ((p.x, p.y) in visited) for p in neighbors):
            # All cardinal neighbor pixels are fully transparent, non-existent, or have been visited. So attempt to use corners.
            corners = pixel.getCornerNeighbors()
            if lastPixel is not None and all(p.invisible or p.outOfBounds for p in corners):
                # All corners are also fully transparent or don't exist. Go back to the last pixel and use its corners.
                # TODO: This should probably also get the last pixel's cardinal neighbors?
                unvisited.extend(lastPixel.getCornerNeighbors())
            else:
                unvisited.extend(corners)
        else:
            unvisited.extend(neighbors)

        lastPixel = pixel

    offset = 1 # All selections seem to be off by 1 pixel for the right and bottom.
    return wx.Rect(left, top, right-left + offset, bottom-top + offset)

# Sets alpha to 0 on all pixels in a selection.
def clearImageSection(img, rect):
    for y in range(rect.Y, rect.Y+rect.Height):
        for x in range(rect.X, rect.X+rect.Width):
            img.SetAlpha(x, y, 0)

# Finds the bounding boxes of sprites in an image. Returns list of wx.Rect
def find(img):
    img = img.Copy()
    spriteBounds = []
    for y in range(img.Height):
        for x in range(img.Width):
            hasAlpha = (img.GetAlpha(x, y) > 0)
            if hasAlpha:
                bounding = findFromPixel(img, x, y)
                spriteBounds.append(bounding)
                clearImageSection(img, bounding)
    return spriteBounds

onSpritesFoundEvent, EVT_SPRITES_FOUND = wx.lib.newevent.NewEvent()
onSpriteFinderUpdateEvent, EVT_SPRITE_FINDER_UPDATE= wx.lib.newevent.NewEvent()
onSpriteFinderAbortEvent, EVT_SPRITE_FINDER_ABORT = wx.lib.newevent.NewEvent()

class SpriteFinderThread(Thread):
    def __init__(self, window, img):
        Thread.__init__(self)
        self.cwImage = img
        self.window = window
        self.abortStatus = False

    def run(self):
        img = self.cwImage.Copy()
        spriteBounds = []
        imgPixels = float(img.Width * img.Height)
        for y in range(img.Height):
            for x in range(img.Width):
                hasAlpha = (img.GetAlpha(x, y) > 0)
                if hasAlpha:
                    if self.abortStatus == True:
                        wx.PostEvent(self.window, onSpriteFinderAbortEvent())
                        return

                    bounding = findFromPixel(img, x, y)
                    spriteBounds.append(bounding)
                    clearImageSection(img, bounding)

                    ratio = (x + (y * img.Width)) / imgPixels
                    wx.PostEvent(self.window, onSpriteFinderUpdateEvent(ratio=ratio))

        wx.PostEvent(self.window, onSpritesFoundEvent(spriteBounds=spriteBounds))

    def abort(self): self.abortStatus = True

class FinderModal(wx.Dialog):
    def __init__(self, parent, doc):
        wx.Dialog.__init__(self, parent=parent, title='Find Sprites', size=(320, 100))
        self.doc = doc
        self.img = doc.cwImage

        panel = wx.Panel(self, style=wx.RAISED_BORDER)
        self.infoText = wx.StaticText(panel, label='Finding sprites...')
        self.progressBar = wx.Gauge(panel)

        cancelButton = wx.Button(self, label='Cancel')
        cancelButton.Bind(wx.EVT_BUTTON, self.onCancelButton)

        self.Bind(wx.EVT_CLOSE, self.onCancelButton)
        self.Bind(EVT_SPRITES_FOUND, self.onSpritesFound)
        self.Bind(EVT_SPRITE_FINDER_UPDATE, self.onSpriteFinderUpdate)
        self.Bind(EVT_SPRITE_FINDER_ABORT, self.onSpriteFinderAbort)

        panelSizer = wx.BoxSizer(wx.VERTICAL)
        panelSizer.Add(self.infoText)
        panelSizer.Add(self.progressBar, 0, wx.EXPAND)
        panel.SetSizer(panelSizer)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(panel, 1, wx.EXPAND)
        sizer.Add(cancelButton)
        self.SetSizer(sizer)

        self.finderThread = SpriteFinderThread(self, self.img)
        self.finderThread.start()

    def onCancelButton(self, e):
        self.infoText.SetLabel('Aborting...')
        self.finderThread.abort()

    def onSpritesFound(self, e):
        self.doc.addSlicesFromSpriteBounds(e.spriteBounds)
        self.Destroy()

    def onSpriteFinderAbort(self, e):
        self.Destroy()

    def onSpriteFinderUpdate(self, e):
        self.progressBar.SetValue(e.ratio * 100)
