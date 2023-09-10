import win32com.client as win32

class PPTGen():
    def __init__(self, config):

        pptApp = win32.gencache.EnsureDispatch('PowerPoint.Application')
        pptApp.Visible = True
        self.ppt = pptApp.Presentations.Add()

        self.slideCtr = 0

    def addSlide(self):
        
        self.slideCtr = self.slideCtr + 1
        slide = self.ppt.Slides.Add(self.ppt.Slides.Count + 1, win32.constants.ppLayoutBlank)
        return slide
    
    def savePPT(self, pptName):
        return
    
