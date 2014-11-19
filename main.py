import wx
import json
from wx import glcanvas
from OpenGL.GL import *

class Selector():
    def __init__(self, x, y, w, h):
        self.rect = wx.Rect(x, y, w, h)

    # Returns True if point is inside rect.
    def contains(self, x, y):
        return self.rect.ContainsXY(x, y)

class DrawPanel(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent)

        self.Bind(wx.EVT_PAINT, self.onPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.onEraseBack)
        self.Bind(wx.EVT_MOTION, self.onMouseMove)
        self.Bind(wx.EVT_LEFT_DOWN, self.onMouseDown)
        self.Bind(wx.EVT_LEFT_UP, self.onMouseUp)
        self.Bind(wx.EVT_KEY_DOWN, self.onKeyDown)

        self.bitmap = wx.Bitmap('cindy.png')
        self.SetBackgroundColour('gray')

        self.currentSelection = wx.Rect()
        self.SetDoubleBuffered(True)

        self.resize = False

        self.selectors = []
        self.activeSelector = None

    def onKeyDown(self, e):
        keyCode = e.GetKeyCode()
        if keyCode == wx.WXK_DELETE:
            if self.activeSelector:
                self.selectors.remove(self.activeSelector)
                self.activeSelector = None
                self.Refresh()
        e.Skip()

    def onMouseUp(self, e):
        self.resize = False
        if self.newSelector:
            rect = self.newSelector.rect
            if (abs(rect.Width) < 1 and abs(rect.Height) < 1): return;

            # If width is negative then swap x and width.
            if rect.Width < 0:
                self.currentSelection.Width = abs(self.currentSelection.Width)
                self.currentSelection.X -= self.currentSelection.Width

            # If height is negative then swap y and height.
            if rect.Height < 0:
                self.currentSelection.Height = abs(self.currentSelection.Height)
                self.currentSelection.Y -= self.currentSelection.Height

            self.newSelector.rect = wx.Rect(self.currentSelection.X, self.currentSelection.Y, self.currentSelection.Width, self.currentSelection.Height)
            self.selectors.append(self.newSelector)
            self.newSelector = None
            self.currentSelection = wx.Rect()

    def onMouseDown(self, e):
        self.SetFocus()
        for sel in self.selectors:
            if sel.contains(e.X, e.Y):
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

        if self.activeSelector:
            rect = self.activeSelector.rect
            self.drawSelectorBack(dc, rect.X, rect.Y, rect.Width, rect.Height)

        for selector in self.selectors:
            rect = selector.rect
            self.drawSelectorBack(dc, rect.X, rect.Y, rect.Width, rect.Height)

        dc.DrawBitmap(self.bitmap, 0, 0);

        if self.activeSelector:
            rect = self.activeSelector.rect
            dc.BeginDrawing()
            dc.SetPen(wx.Pen('red'))
            dc.SetBrush(wx.TRANSPARENT_BRUSH)
            # set x, y, w, h for rectangle
            dc.DrawRectangle(rect.X, rect.Y, rect.Width, rect.Height)
            dc.EndDrawing()

    def onEraseBack(self, e): pass # Do nothing, to avoid flashing on MSWin

    def drawSelectorBack(self, dc, x, y, w, h):
        dc.BeginDrawing()
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.SetBrush(wx.Brush(wx.Color(70, 70, 70, 0)))
        # set x, y, w, h for rectangle
        dc.DrawRectangle(x, y, w, h)
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


class MainWindow(wx.Frame):
    def __init__(self, parent, title):
        wx.Frame.__init__(self, parent, title=title, size=(640, 480))

        fileMenu = wx.Menu()
        helpMenu = wx.Menu()
        menuBar = wx.MenuBar()

        self.glInitialized = False
        attribList = (glcanvas.WX_GL_RGBA, glcanvas.WX_GL_DOUBLEBUFFER, glcanvas.WX_GL_DEPTH_SIZE, 24) # 24 bit
        #self.canvas = glcanvas.GLCanvas(self, attribList=attribList)

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
        #self.canvas.Bind(wx.EVT_ERASE_BACKGROUND, self.onBackgroundErase)
        #self.canvas.Bind(wx.EVT_SIZE, self.onResize)
        #self.canvas.Bind(wx.EVT_PAINT, self.onPaint)

        #pan = wx.Panel(self)
        #button = wx.Button(pan)
        self.drawPanel = DrawPanel(self)

        leftPanel = wx.Panel(self)
        leftPanelSizer = wx.BoxSizer(wx.VERTICAL)

        sliceButton = wx.Button(leftPanel, label='slice')
        sliceButton.Bind(wx.EVT_BUTTON, self.onSliceButton)
        exportButton = wx.Button(leftPanel, label='export')
        exportButton.Bind(wx.EVT_BUTTON, self.onExportButton)

        leftPanelSizer.Add(sliceButton, 0, wx.EXPAND)
        leftPanelSizer.Add(exportButton, 0, wx.EXPAND)
        leftPanel.SetSizer(leftPanelSizer)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(leftPanel, 0, wx.EXPAND)
        sizer.Add(self.drawPanel, 2, wx.EXPAND)
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

    def onBackgroundErase(self, e):
        pass # Do nothing, to avoid flashing on MSWin

    def onResize(self, e):
        if self.canvas.GetContext():
            # Make sure the frame is shown before calling SetCurrent.
            self.Show()
            self.canvas.SetCurrent()

            size = self.canvas.GetClientSize()
            self.updateGLView(size.width, size.height)
            self.canvas.Refresh(False)
        e.Skip()

    def onPaint(self, e):
        self.canvas.SetCurrent()

        # Initialize OpenGL
        if not self.glInitialized:
            self.initGL()
            self.glInitialized = True

        self.renderGL()
        self.canvas.SwapBuffers()
        e.Skip()

    def updateGLView(self, width, height):
        glViewport(0, 0, width, height)

        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, width, height, 0, -1, 1)

        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

    def initGL(self):
        glClearColor(1, 1, 1, 1)
        size = self.canvas.GetClientSize()
        self.updateGLView(size.width, size.height)

    def drawLine(self, x1, y1, x2, y2):
        glBegin(GL_LINES)
        glVertex(x1, y1)
        glVertex(x2, y2)
        glEnd()

    def renderGL(self):
        glClear(GL_COLOR_BUFFER_BIT)

        canvasSize = self.canvas.GetClientSize()

        # Draw grid
        glColor(0.5, 0.5, 0.5)
        for x in range(1, canvasSize.width/32 + 1):
            self.drawLine(x*32, 0, x*32, canvasSize.height)

        for y in range(1, canvasSize.height/32 + 1):
            self.drawLine(0, y*32, canvasSize.width, y*32)


app = wx.App(False)

frame = MainWindow(None, 'spri')
app.MainLoop()
app.Destroy()
