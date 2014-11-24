import wx
import wx.lib.scrolledpanel
import wx.lib.newevent
import json

class Document():
    def __init__(self, fileName):
        self.setCurrentWorkingGraphic(fileName)

        self.activeGroup = SpriteGroup()
        self.spriteGroups = [self.activeGroup]

    def setCurrentWorkingGraphic(self, fileName):
        self.cwBitmap = wx.Bitmap(fileName)
        self.cwImage = self.cwBitmap.ConvertToImage()

class Selector():
    def __init__(self, rect, slice):
        self.rect = rect
        self.slice = slice

    # Returns True if point is inside rect.
    def contains(self, x, y, zoom):
        zoomedRect = wx.Rect(self.rect.X * zoom, self.rect.Y * zoom, self.rect.Width * zoom, self.rect.Height * zoom)
        return zoomedRect.ContainsXY(x, y)

class SpriteGroup():
    def __init__(self):
        self.slices = []

    def addSlice(self, slice):
        self.slices.append(slice)

    def removeSlice(self, slice):
        self.slices.remove(slice)

class Slice():
    def __init__(self, doc, sliceRect):
        self.doc = doc
        self.rect = sliceRect
        self.bitmap = self.doc.cwImage.GetSubImage(self.rect).ConvertToBitmap()

class DrawPanel(wx.Panel):
    def __init__(self, parent, doc):
        wx.Panel.__init__(self, parent)
        self.doc = doc

        self.Bind(wx.EVT_PAINT, self.onPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.onEraseBack)
        self.Bind(wx.EVT_MOTION, self.onMouseMove)
        self.Bind(wx.EVT_LEFT_DOWN, self.onMouseDown)
        self.Bind(wx.EVT_LEFT_UP, self.onMouseUp)
        self.Bind(wx.EVT_MOUSEWHEEL, self.onScroll)
        self.Bind(wx.EVT_KEY_DOWN, self.onKeyDown)
        self.Bind(wx.EVT_KEY_UP, self.onKeyUp)

        self.SetBackgroundColour(wx.Color(200, 200, 200))

        self.newSelection = wx.Rect()

        self.SetDoubleBuffered(True)

        self.resize = False

        self.selectors = []
        self.activeSelector = None

        self.zoom = 1.0
        self.SetSize((self.doc.cwBitmap.Width, self.doc.cwBitmap.Height))

        self.controlHeld = False # CTRL being held?

    def onScroll(self, e):
        if not self.controlHeld:
            e.Skip()
            return

        rot = e.GetWheelRotation()
        if rot > 0:
            self.setZoom(self.zoom + 0.1)
        else:
            self.setZoom(self.zoom - 0.1)
        self.Refresh()

    def onKeyDown(self, e):
        keyCode = e.GetKeyCode()
        if keyCode == wx.WXK_DELETE:
            if self.activeSelector:
                self.doc.activeGroup.removeSlice(self.activeSelector.slice)
                self.selectors.remove(self.activeSelector)
                self.activeSelector = None
                self.Refresh()
        if keyCode == wx.WXK_ADD or keyCode == wx.WXK_NUMPAD_ADD:
            self.setZoom(self.zoom + 0.1)
            self.Refresh()
        elif keyCode == wx.WXK_SUBTRACT or keyCode == wx.WXK_NUMPAD_SUBTRACT:
            self.setZoom(self.zoom - 0.1)
            self.Refresh()
        elif keyCode == wx.WXK_CONTROL:
            self.controlHeld = True
        e.Skip()

    def onKeyUp(self, e):
        keyCode = e.GetKeyCode();
        if keyCode == wx.WXK_CONTROL:
            self.controlHeld = False
        e.Skip()

    def onMouseUp(self, e):
        self.resize = False
        if not self.newSelection.IsEmpty():
            rect = self.newSelection
            self.newSelection.X /= self.zoom
            self.newSelection.Y /= self.zoom
            self.newSelection.Width /= self.zoom
            self.newSelection.Height /= self.zoom

            if (abs(rect.Width) < 1 and abs(rect.Height) < 1): return;

            # If width is negative then swap x and width.
            if rect.Width < 0:
                self.newSelection.Width = abs(self.newSelection.Width)
                self.newSelection.X -= self.newSelection.Width

            # If height is negative then swap y and height.
            if rect.Height < 0:
                self.newSelection.Height = abs(self.newSelection.Height)
                self.newSelection.Y -= self.newSelection.Height

            img = self.doc.cwImage.GetSubImage(wx.Rect(self.newSelection.X, self.newSelection.Y, self.newSelection.Width, self.newSelection.Height))

            # Returns the amount of pixels you must add/subtract to crop out the alpha.
            def getCropAmount(yFirst, reverse):
                out = 0
                firstRange = range(img.Height if yFirst else img.Width)
                if reverse: firstRange = reversed(firstRange)
                for i in firstRange:
                    transparent = None
                    for j in range(img.Width if yFirst else img.Height):
                        if yFirst:
                            y = i
                            x = j
                        else:
                            x = i
                            y = j
                        transparent = (img.GetAlpha(x, y) <= 0)
                        if not transparent: break
                    if not transparent: break
                    out += 1
                return out
            left = getCropAmount(False, False)
            top = getCropAmount(True, False)
            right = getCropAmount(False, True)
            bottom = getCropAmount(True, True)

            self.newSelection = wx.Rect(self.newSelection.X + left, self.newSelection.Y + top, self.newSelection.Width - left - right, self.newSelection.Height - top - bottom)

            slice = Slice(self.doc, self.newSelection)
            self.activeSelector = Selector(self.newSelection, slice)
            self.selectors.append(self.activeSelector)
            self.doc.activeGroup.addSlice(slice)

            self.newSelection = wx.Rect()
            self.Refresh()

    def onMouseDown(self, e):
        self.SetFocus()
        for i, sel in enumerate(self.selectors):
            if sel.contains(e.X, e.Y, self.zoom):
                self.activeSelector = sel
                self.Refresh()
                return

        self.resize = True
        self.newSelection.X = e.X
        self.newSelection.Y = e.Y

    def onMouseMove(self, e):
        if self.resize:
            self.newSelection.Width = e.X - self.newSelection.X
            self.newSelection.Height = e.Y - self.newSelection.Y
            self.Refresh()

    def onPaint(self, e):
        dc = wx.PaintDC(self)
        dc.Clear()
        dc.SetUserScale(self.zoom, self.zoom)

        if self.activeSelector and self.newSelection.IsEmpty():
            rect = self.activeSelector.rect
            self.drawSelectorBack(dc, rect.X, rect.Y, rect.Width, rect.Height)
        elif not self.newSelection.IsEmpty():
            rect = self.newSelection
            self.drawSelectorBack(dc, rect.X/self.zoom, rect.Y/self.zoom, rect.Width/self.zoom, rect.Height/self.zoom)

        for sel in self.selectors:
            rect = sel.rect
            self.drawSelectorBack(dc, rect.X, rect.Y, rect.Width, rect.Height)

        dc.DrawBitmap(self.doc.cwBitmap, 0, 0);

        if self.activeSelector and self.newSelection.IsEmpty():
            rect = self.activeSelector.rect
            self.drawSelectorActive(dc, rect.X, rect.Y, rect.Width, rect.Height)
        elif not self.newSelection.IsEmpty():
            rect = self.newSelection
            self.drawSelectorActive(dc, rect.X/self.zoom, rect.Y/self.zoom, rect.Width/self.zoom, rect.Height/self.zoom)

    def setZoom(self, amount):
        self.zoom = amount
        self.SetMinSize((self.doc.cwBitmap.Width * self.zoom, self.doc.cwBitmap.Height * self.zoom))
        self.GetParent().FitInside()

    def scaleRect(self, rect, scale):
        rect.X *= scale
        rect.Y *= scale
        rect.Width *= scale
        rect.Height *= scale

    def onEraseBack(self, e): pass # Do nothing, to avoid flashing on MSWin

    def drawSelectorBack(self, dc, x, y, w, h):
        dc.BeginDrawing()
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.SetBrush(wx.Brush(wx.Color(90, 200, 90, 0)))
        # set x, y, w, h for rectangle
        dc.DrawRectangle(x, y, w, h)
        dc.EndDrawing()

    def drawSelectorActive(self, dc, x, y, w, h):
        dc.BeginDrawing()
        dc.SetPen(wx.Pen('red'))
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        # set x, y, w, h for rectangle
        dc.DrawRectangle(x-1, y-1, w+2, h+2)
        dc.EndDrawing()

    def sliceAndSave(self):
        img = self.doc.cwImage
        img = img.GetSubImage(self.activeSelector.rect)
        img.SaveFile('slice.png', wx.BITMAP_TYPE_PNG)

    def export(self):
        out = {'frames': {}}
        for i, sel in enumerate(self.selectors):
            rect = sel.rect
            out['frames'][str(i)] = {
                'frame': {
                    'x': rect.X,
                    'y': rect.Y,
                    'w': rect.Width,
                    'h': rect.Height,
                }
            }
        return out

class AnimPanel(wx.Panel):
    def __init__(self, parent, doc):
        wx.Panel.__init__(self, parent)

        self.doc = doc

        img = self.doc.cwImage

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.onTimerUpdate, self.timer)
        self.frame = 0

        self.drawPanel = wx.Panel(self)
        self.drawPanel.Bind(wx.EVT_PAINT, self.onPaint)
        self.drawPanel.Bind(wx.EVT_ERASE_BACKGROUND, self.onEraseBack)
        self.drawPanel.SetSize((128, 128))

        self.playButton = wx.Button(self, label='play')
        self.stopButton = wx.Button(self, label='stop')

        self.playButton.Bind(wx.EVT_BUTTON, self.onPlayButton)
        self.stopButton.Bind(wx.EVT_BUTTON, self.onStopButton)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.drawPanel, 2, wx.EXPAND)
        sizer.Add(self.playButton, 0, wx.EXPAND)
        sizer.Add(self.stopButton, 0, wx.EXPAND)
        self.SetSizer(sizer)

        self.animWidth = 128
        self.animHeight = 128

    def onPlayButton(self, e):
        self.timer.Start(1000/2)

    def onStopButton(self, e):
        self.frame = 0
        self.timer.Stop()
        self.drawPanel.Refresh()

    def onTimerUpdate(self, e):
        self.frame += 1
        if self.frame > len(self.doc.activeGroup.slices)-1:
            self.frame = 0
        self.drawPanel.Refresh()

    def onEraseBack(self, e): pass # Do nothing, to avoid flashing on MSWin

    def onPaint(self, e):
        dc = wx.PaintDC(self.drawPanel)
        dc.Clear()

        if len(self.doc.activeGroup.slices) > 0:
            slice = self.doc.activeGroup.slices[self.frame].bitmap
            dc.DrawBitmap(slice, (self.animWidth/2) - (slice.Width/2), (self.animHeight/2) - (slice.Height/2));

class MainWindow(wx.Frame):
    def __init__(self, parent, title):
        wx.Frame.__init__(self, parent, title=title, size=(640, 480))

        fileMenu = wx.Menu()
        helpMenu = wx.Menu()
        menuBar = wx.MenuBar()

        # File Menu
        menuOpen = fileMenu.Append(wx.ID_OPEN, '&Open', 'Open a file') # The ampersand is the acceleration key.
        menuSave = fileMenu.Append(wx.ID_SAVE, '&Save', 'Save current file')
        fileMenu.AppendSeparator()
        menuExit = fileMenu.Append(wx.ID_EXIT, 'E&xit', 'Terminate program')
        # Help Menu
        menuAbout = helpMenu.Append(wx.ID_ABOUT, '&About', 'Info goes here')

        menuBar.Append(fileMenu, '&File')
        menuBar.Append(helpMenu, '&Help')
        self.SetMenuBar(menuBar)

        self.Bind(wx.EVT_MENU, self.onAbout, menuAbout)
        self.Bind(wx.EVT_MENU, self.onExit, menuExit)

        self.doc = Document('cindy.png')

        self.drawPanelSizer = wx.BoxSizer(wx.VERTICAL)
        self.drawPanelScroller = wx.lib.scrolledpanel.ScrolledPanel(self)
        self.drawPanel = DrawPanel(self.drawPanelScroller, self.doc)

        self.drawPanelSizer.Add(self.drawPanel, 0, wx.FIXED_MINSIZE)
        self.drawPanelScroller.SetSizer(self.drawPanelSizer)
        self.drawPanelScroller.SetupScrolling()

        leftPanel = wx.Panel(self)
        leftPanelSizer = wx.BoxSizer(wx.VERTICAL)

        sliceButton = wx.Button(leftPanel, label='slice')
        sliceButton.Bind(wx.EVT_BUTTON, self.onSliceButton)
        exportButton = wx.Button(leftPanel, label='export')
        exportButton.Bind(wx.EVT_BUTTON, self.onExportButton)

        leftPanelSizer.Add(sliceButton, 0, wx.EXPAND)
        leftPanelSizer.Add(exportButton, 0, wx.EXPAND)
        leftPanel.SetSizer(leftPanelSizer)

        self.drawPanelScroller.SetBackgroundColour(wx.Color(40, 40, 40))

        self.animPanel = AnimPanel(self, self.doc)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(leftPanel, 0, wx.EXPAND)
        sizer.Add(self.drawPanelScroller, 2, wx.EXPAND)
        sizer.Add(self.animPanel, 0, wx.EXPAND)
        self.SetSizer(sizer)

        self.Show(True)

        self.drawPanel.SetFocus()

    def onSliceButton(self, e):
        self.drawPanel.sliceAndSave()

    def onExportButton(self, e):
        file = open('out.json', 'w')
        file.write(json.dumps(self.drawPanel.export()))
        file.close()

    def onAbout(self, e):
        dlg = wx.MessageDialog(self, 'This is where the about stuff goes', 'About geo', wx.OK)
        dlg.ShowModal()
        dlg.Destroy()

    def onExit(self, e):
        self.Close(True)

app = wx.App(False)

frame = MainWindow(None, 'spri')
app.MainLoop()
app.Destroy()
