import wx
import wx.lib.scrolledpanel
import wx.lib.newevent
import json
import os

class Document(wx.EvtHandler):
    onSliceAddEvent, EVT_ON_SLICE_ADD = wx.lib.newevent.NewEvent()
    onSliceRemoveEvent, EVT_ON_SLICE_REMOVE = wx.lib.newevent.NewEvent()
    onSliceSwapEvent, EVT_ON_SLICE_SWAP = wx.lib.newevent.NewEvent()
    def __init__(self, fileName):
        wx.EvtHandler.__init__(self)
        self.setCurrentWorkingGraphic(fileName)

        self.activeGroup = SpriteGroup()
        self.spriteGroups = [self.activeGroup]

    def addSlice(self, slice):
        self.activeGroup.addSlice(slice)
        wx.PostEvent(self, Document.onSliceAddEvent(slice=slice))

    def removeSlice(self, slice):
        self.activeGroup.removeSlice(slice)
        wx.PostEvent(self, Document.onSliceRemoveEvent(slice=slice))

    def swapSlice(self, sliceA, sliceB):
        indices = self.activeGroup.swapSlice(sliceA, sliceB)
        if indices == False: return
        wx.PostEvent(self, Document.onSliceSwapEvent(indexA=indices[0], indexB=indices[1]))

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

    def swapSlice(self, sliceA, sliceB):
        aIndex = self.slices.index(sliceA)
        bIndex = self.slices.index(sliceB)
        if aIndex < 0 or bIndex < 0: return False

        self.slices[aIndex] = sliceB
        self.slices[bIndex] = sliceA
        return (aIndex, bIndex)

class Slice():
    def __init__(self, doc, sliceRect):
        self.doc = doc
        self.rect = sliceRect
        self.bitmap = self.doc.cwImage.GetSubImage(self.rect).ConvertToBitmap()

class SpriteSheetPanel(wx.Panel):
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
        self.leftMouseHeld = False

        self.mouseX = 0
        self.mouseY = 0
        # Mouse position when control key was last pressed.
        self.controlMouseX = 0
        self.controlMouseY = 0

        self.gridSelection = False
        self.gridWidth = 64
        self.gridHeight = 64
        self.horCells = 4
        self.verCells = 2

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
                self.doc.removeSlice(self.activeSelector.slice)
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
            self.controlMouseX = self.mouseX
            self.controlMouseY = self.mouseY
            self.controlHeld = True
        elif keyCode == wx.WXK_SPACE:
            if self.gridSelection:
                for y in range(0, self.verCells):
                    for x in range(0, self.horCells):
                        self.createSelection(wx.Rect(self.mouseX + (x * self.gridWidth), self.mouseY + (y * self.gridHeight), self.gridWidth, self.gridHeight))
                        self.gridSelection = False
                        self.Refresh()
        e.Skip()

    def onKeyUp(self, e):
        keyCode = e.GetKeyCode();
        if keyCode == wx.WXK_CONTROL:
            self.controlHeld = False
        e.Skip()

    # Creates a selection: creates slice and adds to slice group, adds selector and crops.
    def createSelection(self, rect):
        if (abs(rect.Width) < 1 and abs(rect.Height) < 1):
            return False

        # If width is negative then swap x and width.
        if rect.Width < 0:
            rect.Width = abs(rect.Width)
            rect.X -= rect.Width

        # If height is negative then swap y and height.
        if rect.Height < 0:
            rect.Height = abs(rect.Height)
            rect.Y -= rect.Height

        if rect.X + rect.Width > self.doc.cwImage.Width or rect.Y + rect.Height > self.doc.cwImage.Height:
            return False

        img = self.doc.cwImage.GetSubImage(rect)

        # Returns the amount of pixels you must add/subtract to crop out the alpha.
        def getCropAmount(yFirst, reverse):
            out = 0
            firstRange = range(img.Height if yFirst else img.Width)
            if reverse: firstRange = reversed(firstRange)
            for i in firstRange:
                transparent = False
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
            if (yFirst and out >= img.Height) or (not yFirst and out >= img.Width):
                out = 0
            return out
        left = getCropAmount(False, False)
        top = getCropAmount(True, False)
        right = getCropAmount(False, True)
        bottom = getCropAmount(True, True)

        rect = wx.Rect(rect.X + left, rect.Y + top, rect.Width - left - right, rect.Height - top - bottom)

        slice = Slice(self.doc, rect)
        self.activeSelector = Selector(rect, slice)
        self.selectors.append(self.activeSelector)

        self.doc.addSlice(slice)

        return True

    def onMouseUp(self, e):
        self.resize = False
        if not self.newSelection.IsEmpty():
            self.newSelection.X /= self.zoom
            self.newSelection.Y /= self.zoom
            self.newSelection.Width /= self.zoom
            self.newSelection.Height /= self.zoom

            self.createSelection(self.newSelection)

            self.newSelection = wx.Rect()
            self.Refresh()

        self.leftMouseHeld = False

    def onMouseDown(self, e):
        self.SetFocus()

        self.leftMouseHeld = True
        if self.gridSelection: return

        for i, sel in enumerate(self.selectors):
            if sel.contains(e.X, e.Y, self.zoom):
                self.activeSelector = sel
                self.Refresh()
                return

        self.resize = True
        self.newSelection.X = e.X
        self.newSelection.Y = e.Y

    def onMouseMove(self, e):
        if self.gridSelection:
            if self.controlHeld:
                self.gridWidth = e.X / self.zoom - self.controlMouseX
                self.gridHeight = e.Y / self.zoom - self.controlMouseY
            elif self.leftMouseHeld:
                self.mouseX = e.X / self.zoom
                self.mouseY = e.Y / self.zoom
            self.Refresh()

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

        if self.gridSelection:
            for x in range(0, self.horCells):
                for y in range(0, self.verCells):
                    dc.BeginDrawing()
                    dc.SetPen(wx.Pen(wx.Color(20,20,80)))
                    dc.SetBrush(wx.Brush(wx.Color(70,70,150)))
                    dc.DrawRectangle(self.mouseX + (x * self.gridWidth), self.mouseY + (y * self.gridHeight), self.gridWidth, self.gridHeight)
                    dc.EndDrawing()

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
        self.animSpeed = 500

        self.drawPanel = wx.Panel(self)
        self.drawPanel.Bind(wx.EVT_PAINT, self.onPaint)
        self.drawPanel.Bind(wx.EVT_ERASE_BACKGROUND, self.onEraseBack)
        self.drawPanel.SetSize((128, 128))

        self.playButton = wx.Button(self, label='play')
        self.stopButton = wx.Button(self, label='stop')

        self.playButton.Bind(wx.EVT_BUTTON, self.onPlayButton)
        self.stopButton.Bind(wx.EVT_BUTTON, self.onStopButton)

        animSpeedPanel = wx.Panel(self)
        self.animSpeedLabel = wx.StaticText(animSpeedPanel, label='ms')
        self.animSpeedInput = wx.TextCtrl(animSpeedPanel, size=(32, -1), value=str(self.animSpeed))
        animSpeedPanelSizer = wx.BoxSizer(wx.HORIZONTAL)
        animSpeedPanelSizer.AddStretchSpacer()
        animSpeedPanelSizer.Add(self.animSpeedInput, 0)
        animSpeedPanelSizer.Add(self.animSpeedLabel, 0)
        animSpeedPanelSizer.AddStretchSpacer()
        animSpeedPanel.SetSizer(animSpeedPanelSizer)

        self.animSpeedInput.Bind(wx.EVT_TEXT, self.onAnimSpeedChange)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.drawPanel, 2, wx.EXPAND)
        sizer.Add(animSpeedPanel, 0, wx.EXPAND)
        sizer.Add(self.playButton, 0, wx.EXPAND)
        sizer.Add(self.stopButton, 0, wx.EXPAND)
        self.SetSizer(sizer)

        self.animWidth = 128
        self.animHeight = 128

    def onAnimSpeedChange(self, e):
        try:
            self.animSpeed = int(self.animSpeedInput.Value)
            self.timer.Stop()
            self.frame = 0
            self.timer.Start(self.animSpeed)
        except ValueError: return

    def onPlayButton(self, e):
        self.timer.Start(self.animSpeed)

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

class SliceGroupPanel(wx.Panel):
    def __init__(self, parent, doc):
        wx.Panel.__init__(self, parent)
        self.doc = doc

        self.list = wx.ListCtrl(self, style=wx.LC_REPORT|wx.BORDER_SUNKEN|wx.LC_SINGLE_SEL)
        self.list.InsertColumn(0, 'slice')
        self.list.InsertColumn(1, 'name')
        self.list.SetColumnWidth(0, wx.LIST_AUTOSIZE_USEHEADER)
        self.list.SetColumnWidth(1, wx.LIST_AUTOSIZE)

        self.doc.Bind(Document.EVT_ON_SLICE_ADD, self.onDocAddSlice)
        self.doc.Bind(Document.EVT_ON_SLICE_REMOVE, self.onDocRemoveSlice)
        self.doc.Bind(Document.EVT_ON_SLICE_SWAP, self.onDocSwapSlice)

        buttonPanel = wx.Panel(self)
        buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
        upButton = wx.BitmapButton(buttonPanel, wx.ID_UP, wx.ArtProvider.GetBitmap(wx.ART_GO_UP))
        upButton.Bind(wx.EVT_BUTTON, self.onUpButton)
        downButton = wx.BitmapButton(buttonPanel, wx.ID_DOWN, wx.ArtProvider.GetBitmap(wx.ART_GO_DOWN))
        downButton.Bind(wx.EVT_BUTTON, self.onDownButton)

        buttonSizer.Add(upButton)
        buttonSizer.Add(downButton)
        buttonPanel.SetSizer(buttonSizer)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.list, 2, wx.EXPAND)
        sizer.Add(buttonPanel)
        self.SetSizer(sizer)

        self.slices = []

        self.imageListScale = 0.5
        self.imageListSize = wx.Size(0, 0)

    def onDocAddSlice(self, e):
        self.addSlice(e.slice)
        e.Skip()
    def onDocRemoveSlice(self, e):
        self.removeSlice(e.slice)
        e.Skip()
    def onDocSwapSlice(self, e):
        tmpBitmap = self.imageList.GetBitmap(e.indexA)
        tmpSlice = self.slices[e.indexA]

        # Swap slices array.
        self.slices[e.indexA] = self.slices[e.indexB]
        self.slices[e.indexB] = tmpSlice

        # Swap image list bitmaps.
        self.imageList.Replace(e.indexA, self.imageList.GetBitmap(e.indexB))
        self.imageList.Replace(e.indexB, tmpBitmap)

        # Update image list items.
        self.list.SetStringItem(e.indexA, 0, '', e.indexA)
        self.list.SetStringItem(e.indexB, 0, '', e.indexB)

    # Creates and assigns a new imageList from the size specified. Adds sliced bitmaps.
    def createImageList(self, size):
        self.imageListSize = wx.Size(size.GetWidth() * self.imageListScale, size.GetHeight() * self.imageListScale)
        self.imageList = wx.ImageList(self.imageListSize.GetWidth(), self.imageListSize.GetHeight(), len(self.slices))

        # Add the images from the slices. Resize them to fit with the new imageList size.
        for slice in self.slices:
            image = slice.bitmap.ConvertToImage()
            image = image.Scale(image.Width * self.imageListScale, image.Height * self.imageListScale, wx.IMAGE_QUALITY_HIGH)
            image = image.Resize(self.imageListSize, (0, 0))
            self.imageList.Add(image.ConvertToBitmap())

        self.list.AssignImageList(self.imageList, wx.IMAGE_LIST_SMALL)

    # Returns the largest width and height found from all sliced bitmaps.
    def getLargestSize(self):
        width = 0
        height = 0
        for slice in self.slices:
            bitmap = slice.bitmap
            if bitmap.Width > width: width = bitmap.Width
            if bitmap.Height > height: height = bitmap.Height
        return wx.Size(width, height)

    def addSlice(self, slice):
        self.slices.append(slice)

        largestSize = self.getLargestSize()
        self.createImageList(largestSize)

        index = len(self.slices)-1
        self.list.InsertStringItem(index, '', index)
        self.list.SetStringItem(index, 1, str(index))

    def removeSlice(self, slice):
        self.list.DeleteAllItems()
        self.slices.remove(slice)

        # Find largest size again, in case we deleted the largest slice.
        largestSize = self.getLargestSize()
        self.createImageList(largestSize)

        for i in range(len(self.slices)):
            self.list.InsertStringItem(i, '', long(i))
            self.list.SetStringItem(i, 1, str(i))

    def onUpButton(self, e):
        selectedIndex = self.list.GetFirstSelected()
        if (selectedIndex <= 0): return
        self.doc.swapSlice(self.slices[selectedIndex-1], self.slices[selectedIndex])
        self.list.Select(selectedIndex-1)

    def onDownButton(self, e):
        selectedIndex = self.list.GetFirstSelected()
        if (selectedIndex >= len(self.slices)-1): return
        self.doc.swapSlice(self.slices[selectedIndex+1], self.slices[selectedIndex])
        self.list.Select(selectedIndex+1)

class MainWindow(wx.Frame):
    def __init__(self, parent, title):
        wx.Frame.__init__(self, parent, title=title, size=(640, 480))

        fileMenu = wx.Menu()
        helpMenu = wx.Menu()
        menuBar = wx.MenuBar()

        # File Menu
        # The ampersand is the acceleration key.
        menuExportJson = fileMenu.Append(wx.ID_FILE1, 'Export to &JSON', 'Export slices to JSON.')
        menuExportPng = fileMenu.Append(wx.ID_FILE2, 'Export to &PNG', 'Export slices to PNG images.')
        fileMenu.AppendSeparator()
        menuExit = fileMenu.Append(wx.ID_EXIT, 'E&xit', 'Terminate program')
        # Help Menu
        menuAbout = helpMenu.Append(wx.ID_ABOUT, '&About', 'Info goes here')

        menuBar.Append(fileMenu, '&File')
        menuBar.Append(helpMenu, '&Help')
        self.SetMenuBar(menuBar)

        self.Bind(wx.EVT_MENU, self.onAbout, menuAbout)
        self.Bind(wx.EVT_MENU, self.onExit, menuExit)
        self.Bind(wx.EVT_MENU, self.onExportJsonButton, menuExportJson)
        self.Bind(wx.EVT_MENU, self.onExportSliceButton, menuExportPng)

        self.doc = Document('cindy.png')

        self.sheetPanelSizer = wx.BoxSizer(wx.VERTICAL)
        self.sheetPanelScroller = wx.lib.scrolledpanel.ScrolledPanel(self)
        self.sheetPanel = SpriteSheetPanel(self.sheetPanelScroller, self.doc)

        self.sheetPanelSizer.Add(self.sheetPanel, 0, wx.FIXED_MINSIZE)
        self.sheetPanelScroller.SetSizer(self.sheetPanelSizer)
        self.sheetPanelScroller.SetupScrolling()

        self.sheetPanelScroller.SetBackgroundColour(wx.Color(40, 40, 40))

        rightPanelSizer = wx.BoxSizer(wx.VERTICAL)
        rightPanel = wx.Panel(self)
        self.animPanel = AnimPanel(rightPanel, self.doc)

        self.sliceGroupPanel = SliceGroupPanel(rightPanel, self.doc)

        rightPanelSizer.Add(self.animPanel, 0, wx.EXPAND)
        rightPanelSizer.Add(self.sliceGroupPanel , 2, wx.EXPAND)
        rightPanel.SetSizer(rightPanelSizer)

        toolbar = self.CreateToolBar()
        self.gridWidth = wx.TextCtrl(toolbar, value=str(self.sheetPanel.gridWidth), size=(32, -1))
        self.gridHeight = wx.TextCtrl(toolbar, value=str(self.sheetPanel.gridHeight), size=(32, -1))
        self.gridColumns = wx.TextCtrl(toolbar, value=str(self.sheetPanel.horCells), size=(24, -1))
        self.gridRows = wx.TextCtrl(toolbar, value=str(self.sheetPanel.verCells), size=(24, -1))
        self.gridButton = wx.Button(toolbar, label='grid')

        self.gridWidth.Bind(wx.EVT_TEXT, self.onGridWidthChange)
        self.gridHeight.Bind(wx.EVT_TEXT, self.onGridHeightChange)
        self.gridColumns.Bind(wx.EVT_TEXT, self.onGridColumnChange)
        self.gridRows.Bind(wx.EVT_TEXT, self.onGridRowChange)
        self.gridButton.Bind(wx.EVT_BUTTON, self.onGridButton)

        toolbar.AddControl(self.gridButton)
        toolbar.AddSeparator()
        toolbar.AddControl(wx.StaticText(toolbar, label='size'))
        toolbar.AddControl(self.gridWidth)
        toolbar.AddControl(wx.StaticText(toolbar, label='x'))
        toolbar.AddControl(self.gridHeight)
        toolbar.AddSeparator()
        toolbar.AddControl(wx.StaticText(toolbar, label='cells'))
        toolbar.AddControl(self.gridColumns)
        toolbar.AddControl(wx.StaticText(toolbar, label='x'))
        toolbar.AddControl(self.gridRows)
        toolbar.Realize()

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.sheetPanelScroller, 2, wx.EXPAND)
        sizer.Add(rightPanel, 0, wx.EXPAND)
        self.SetSizer(sizer)

        self.Show(True)

        self.sheetPanel.SetFocus()

    def onGridButton(self, e):
        self.sheetPanel.gridSelection = not self.sheetPanel.gridSelection
        self.sheetPanel.Refresh()

    def onGridColumnChange(self, e):
        try:
            self.sheetPanel.horCells = int(self.gridColumns.Value)
            self.sheetPanel.Refresh()
        except ValueError: return

    def onGridRowChange(self, e):
        try:
            self.sheetPanel.verCells = int(self.gridRows.Value)
            self.sheetPanel.Refresh()
        except ValueError: return

    def onGridWidthChange(self, e):
        try:
            self.sheetPanel.gridWidth = int(self.gridWidth.Value)
            self.sheetPanel.Refresh()
        except ValueError: return

    def onGridHeightChange(self, e):
        try:
            self.sheetPanel.gridHeight = int(self.gridHeight.Value)
            self.sheetPanel.Refresh()
        except ValueError: return

    def onExportSliceButton(self, e):
        dlg = wx.FileDialog(self, 'Export Slices', './', '', '*.png', wx.SAVE)
        if dlg.ShowModal() == wx.ID_OK:
            filePaths = []
            warnOverwrite = False
            for i in range(len(self.doc.activeGroup.slices)):
                filePath = os.path.join(dlg.GetDirectory(), str(i) + '_' + dlg.GetFilename())
                filePaths.append(filePath)
                if (os.path.exists(filePath)):
                    warnOverwrite = True

            write = True
            if (warnOverwrite):
                warn = wx.MessageDialog(self, 'This will overwrite data for multiple files.', 'Warning')
                write = (warn.ShowModal() == wx.ID_OK)
                warn.Destroy()

            if (write):
                for i, slice in enumerate(self.doc.activeGroup.slices):
                    filePath = os.path.join(dlg.GetDirectory(), filePaths[i])
                    slice.bitmap.ConvertToImage().SaveFile(filePath, wx.BITMAP_TYPE_PNG)

        dlg.Destroy()

    def onExportJsonButton(self, e):
        dlg = wx.FileDialog(self, 'Export JSON', './', '', '*.json', wx.SAVE)
        if dlg.ShowModal() == wx.ID_OK:
            filePath = os.path.join(dlg.GetDirectory(), dlg.GetFilename())
            write = True
            if (os.path.exists(filePath)):
                warn = wx.MessageDialog(self, "This will overwrite the current file's data.", 'Warning')
                write = (warn.ShowModal() == wx.ID_OK)
                warn.Destroy()

            if (write):
                with open(filePath, 'w') as file:
                    file.write(json.dumps(self.sheetPanel.export()))

        dlg.Destroy()

    def onAbout(self, e):
        dlg = wx.MessageDialog(self, 'This is where the about stuff goes', 'About this', wx.OK)
        dlg.ShowModal()
        dlg.Destroy()

    def onExit(self, e):
        self.Close(True)

app = wx.App(False)

frame = MainWindow(None, 'spri')
app.MainLoop()
app.Destroy()
