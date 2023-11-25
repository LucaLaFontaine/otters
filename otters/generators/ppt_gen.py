import win32com.client as win32
from datetime import date
from dateutil.relativedelta import relativedelta, MO, SU
class PPTGen():
    def __init__(self, parent):
        self.parent = parent
        pptApp = win32.gencache.EnsureDispatch('PowerPoint.Application')
        pptApp.Visible = True
        self.ppt = pptApp.Presentations.Add()
        

        # Slides should be a class
        self.slideCtr = 0

    def addSlide(self):
        
        self.slideCtr = self.slideCtr + 1
        slide = self.ppt.Slides.Add(self.ppt.Slides.Count + 1, win32.constants.ppLayoutBlank)
        return slide
    
    def savePPT(self, pptTitle):

        # Microsoft doesn't support forwards slashes lol
        pptTitle = pptTitle.replace('/', r'\\')
        self.ppt.SaveAs(pptTitle)

    
    def ExPSStyleName(self):
        self.folderPath = self.parent.reportFolder
        twoSundaysAgo = (date.today() + relativedelta(weekday=SU(-2))).strftime("%b%d")
        lastSunday = (date.today() + relativedelta(weekday=SU(-1))).strftime("%b%d")
        self.pptTitle = '{}{} - Excellent Plant Shutdown Performance ({}-{})'.format(self.folderPath, self.parent.plant, twoSundaysAgo, lastSunday)

        return self.pptTitle
        
           
