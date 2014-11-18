import wx
from wx import glcanvas
from OpenGL.GL import *

class DrawPanel(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent)
        self.Bind(wx.EVT_PAINT, self.onPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.onEraseBack)
        self.Bind(wx.EVT_MOTION, self.onMouseMove)
        self.Bind(wx.EVT_LEFT_DOWN, self.onMouseDown)
        self.Bind(wx.EVT_LEFT_UP, self.onMouseUp)
        self.bitmap = wx.Bitmap('cindy.png')
        self.SetBackgroundColour('gray')

        self.selX = 100
        self.selY = 100
        self.selW = 150
        self.selH = 150
        self.SetDoubleBuffered(True)

        self.resize = False

    def onMouseUp(self, e):
        self.resize = False

    def onMouseDown(self, e):
        self.resize = True
        self.selX = e.X
        self.selY = e.Y

    def onMouseMove(self, e):
        if self.resize:
            self.selW = e.X - self.selX
            self.selH = e.Y - self.selY
            self.Refresh()

    def onPaint(self, e):
        dc = wx.PaintDC(self)
        dc.Clear()

        dc.BeginDrawing()
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.SetBrush(wx.Brush(wx.Color(70, 70, 70, 0)))
        # set x, y, w, h for rectangle
        dc.DrawRectangle(self.selX, self.selY, self.selW, self.selH)
        dc.EndDrawing()

        dc.DrawBitmap(self.bitmap, 0, 0);

        dc.BeginDrawing()
        dc.SetPen(wx.Pen('red'))
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        # set x, y, w, h for rectangle
        dc.DrawRectangle(self.selX, self.selY, self.selW, self.selH)
        dc.EndDrawing()

    def onEraseBack(self, e): pass # Do nothing, to avoid flashing on MSWin

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
        testo = wx.Panel(self)
        wx.Button(testo, label='push')
        frame = DrawPanel(self)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(testo, 0, wx.EXPAND)
        sizer.Add(frame, 2, wx.EXPAND)
        self.SetSizer(sizer)

        self.Show(True)

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
