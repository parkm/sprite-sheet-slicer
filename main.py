import wx
import wx.lib.scrolledpanel
import wx.lib.newevent
import json

class Selector():
    def __init__(self, x, y, w, h):
        self.rect = wx.Rect(x, y, w, h)

    # Returns True if point is inside rect.
    def contains(self, x, y, zoom):
        zoomedRect = wx.Rect(self.rect.X * zoom, self.rect.Y * zoom, self.rect.Width * zoom, self.rect.Height * zoom)
        return zoomedRect.ContainsXY(x, y)

class DrawPanel(wx.Panel):
    OnSelectionEvent, EVT_ON_SELECTION = wx.lib.newevent.NewEvent()
    def __init__(self, parent):
        wx.Panel.__init__(self, parent)

        self.Bind(wx.EVT_PAINT, self.onPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.onEraseBack)
        self.Bind(wx.EVT_MOTION, self.onMouseMove)
        self.Bind(wx.EVT_LEFT_DOWN, self.onMouseDown)
        self.Bind(wx.EVT_LEFT_UP, self.onMouseUp)
        self.Bind(wx.EVT_MOUSEWHEEL, self.onScroll)
        self.Bind(wx.EVT_KEY_DOWN, self.onKeyDown)
        self.Bind(wx.EVT_KEY_UP, self.onKeyUp)

        self.bitmap = wx.Bitmap('cindy.png')
        self.SetBackgroundColour('gray')

        self.currentSelection = wx.Rect()
        self.SetDoubleBuffered(True)

        self.resize = False

        self.selectors = []
        self.activeSelector = None

        self.zoom = 1.0
        self.SetSize((self.bitmap.Width, self.bitmap.Height))

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
        if self.newSelector:
            rect = self.newSelector.rect
            self.newSelector.rect.X /= self.zoom
            self.newSelector.rect.Y /= self.zoom
            self.newSelector.rect.Width /= self.zoom
            self.newSelector.rect.Height /= self.zoom
            self.currentSelection.X /= self.zoom
            self.currentSelection.Y /= self.zoom
            self.currentSelection.Width /= self.zoom
            self.currentSelection.Height /= self.zoom

            if (abs(rect.Width) < 1 and abs(rect.Height) < 1): return;

            # If width is negative then swap x and width.
            if rect.Width < 0:
                self.currentSelection.Width = abs(self.currentSelection.Width)
                self.currentSelection.X -= self.currentSelection.Width

            # If height is negative then swap y and height.
            if rect.Height < 0:
                self.currentSelection.Height = abs(self.currentSelection.Height)
                self.currentSelection.Y -= self.currentSelection.Height


            img = self.bitmap.ConvertToImage().GetSubImage(wx.Rect(self.currentSelection.X, self.currentSelection.Y, self.currentSelection.Width, self.currentSelection.Height))

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

            #self.newSelector.rect = wx.Rect(self.currentSelection.X, self.currentSelection.Y, self.currentSelection.Width, self.currentSelection.Height)
            self.newSelector.rect = wx.Rect(self.currentSelection.X + left, self.currentSelection.Y + top, self.currentSelection.Width - left - right, self.currentSelection.Height - top - bottom)
            self.selectors.append(self.newSelector)
            self.newSelector = None
            self.currentSelection = wx.Rect()
            self.Refresh()

            wx.PostEvent(self, DrawPanel.OnSelectionEvent())

    def onMouseDown(self, e):
        self.SetFocus()
        for sel in self.selectors:
            if sel.contains(e.X, e.Y, self.zoom):
                self.activeSelector = sel
                self.Refresh()
                return

        self.resize = True
        self.currentSelection.X = e.X
        self.currentSelection.Y = e.Y
        self.newSelector = Selector(self.currentSelection.X, self.currentSelection.Y, self.currentSelection.Width, self.currentSelection.Height)
        self.activeSelector = self.newSelector

    def onMouseMove(self, e):
        if self.resize:
            self.currentSelection.Width = e.X - self.currentSelection.X
            self.currentSelection.Height = e.Y - self.currentSelection.Y
            if self.newSelector:
                self.newSelector.rect = wx.Rect(self.currentSelection.X, self.currentSelection.Y, self.currentSelection.Width, self.currentSelection.Height)
            self.Refresh()

    def onPaint(self, e):
        dc = wx.PaintDC(self)
        dc.Clear()
        dc.SetUserScale(self.zoom, self.zoom)

        if self.activeSelector and self.currentSelection.IsEmpty():
            rect = self.activeSelector.rect
            self.drawSelectorBack(dc, rect.X, rect.Y, rect.Width, rect.Height)
        elif not self.currentSelection.IsEmpty():
            rect = self.activeSelector.rect
            self.drawSelectorBack(dc, rect.X/self.zoom, rect.Y/self.zoom, rect.Width/self.zoom, rect.Height/self.zoom)

        for selector in self.selectors:
            rect = selector.rect
            #self.drawSelectorBack(dc, rect.X/self.zoom, rect.Y/self.zoom, rect.Width/self.zoom, rect.Height/self.zoom)
            self.drawSelectorBack(dc, rect.X, rect.Y, rect.Width, rect.Height)

        dc.DrawBitmap(self.bitmap, 0, 0);

        if self.activeSelector and self.currentSelection.IsEmpty():
            rect = self.activeSelector.rect
            self.drawSelectorActive(dc, rect.X, rect.Y, rect.Width, rect.Height)
        elif not self.currentSelection.IsEmpty():
            rect = self.activeSelector.rect
            self.drawSelectorActive(dc, rect.X/self.zoom, rect.Y/self.zoom, rect.Width/self.zoom, rect.Height/self.zoom)

    def setZoom(self, amount):
        self.zoom = amount
        self.SetMinSize((self.bitmap.Width * self.zoom, self.bitmap.Height * self.zoom))
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
        img = self.bitmap.ConvertToImage()
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
    def __init__(self, parent):
        wx.Panel.__init__(self, parent)

        self.bitmap = wx.Bitmap('cindy.png')

        img = self.bitmap.ConvertToImage()
        self.slices = [img.GetSubImage(wx.Rect(11, 14, 43, 98)).ConvertToBitmap(), img.GetSubImage(wx.Rect(70, 15, 54, 97)).ConvertToBitmap()]

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

    def onPlayButton(self, e):
        self.timer.Start(1000/10)

    def onStopButton(self, e):
        self.frame = 0
        self.timer.Stop()
        self.drawPanel.Refresh()

    def onTimerUpdate(self, e):
        self.frame += 1
        if self.frame > len(self.slices)-1:
            self.frame = 0
        self.drawPanel.Refresh()

    def onEraseBack(self, e): pass # Do nothing, to avoid flashing on MSWin

    def onPaint(self, e):
        dc = wx.PaintDC(self.drawPanel)
        dc.Clear()

        dc.DrawBitmap(self.slices[self.frame], 0, 0);

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

        self.drawPanelSizer = wx.BoxSizer(wx.VERTICAL)
        self.drawPanelScroller = wx.lib.scrolledpanel.ScrolledPanel(self)
        self.drawPanel = DrawPanel(self.drawPanelScroller)
        self.drawPanel.Bind(DrawPanel.EVT_ON_SELECTION, self.test)

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

        animPanel = AnimPanel(self)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(leftPanel, 0, wx.EXPAND)
        sizer.Add(self.drawPanelScroller, 2, wx.EXPAND)
        sizer.Add(animPanel, 0, wx.EXPAND)
        self.SetSizer(sizer)

        self.Show(True)

        self.drawPanel.SetFocus()

    def test(self, e):
        print('hi')

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
