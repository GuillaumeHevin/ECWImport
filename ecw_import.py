# -*- coding: utf-8 -*-
"""
/***************************************************************************
 ECWImport
                                 A QGIS plugin
 Convert ECW into GeoTIFF file and import into a Raster layer
                              -------------------
        begin                : 2017-08-20
        git sha              : $Format:%H$
        copyright            : (C) 2017 by HEVIN Guillaume
        email                : hevin.guillaume@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *
# Initialize Qt resources from file resources.py
import resources
# Import the code for the dialog
from ecw_import_dialog import ECWImportDialog
from ecw_import_gdal import ECWImportGdal
from ecw_import_howtogdal import ECWImportHowToGdal
#import os.path
import os
import struct
import webbrowser
from subprocess import *

from osgeo import osr
import gdal
from gdalconst import *

class ECWImport:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'ECWImport_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)


        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&ECW Import')


    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('ECWImport', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        # Create the dialog (after translation) and keep reference
        self.dlg = ECWImportDialog()
        self.gdal = ECWImportGdal()
        self.htgdal = ECWImportHowToGdal()

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            #self.toolbar.addAction(action)
            try:
                self.iface.layerToolBar().addAction(action)
            except:
                self.toolbar = self.iface.addToolBar(u'ECW Import')
                self.toolbar.setObjectName(u'ECW Import')
                
                self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToRasterMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/ECWImport/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Import ECW file'),
            callback=self.run,
            parent=self.iface.mainWindow())


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginRasterMenu(
                self.tr(u'&ECW Import'),
                action)
            try:
                self.iface.layerToolBar().removeAction(action)
            except:
                self.iface.removeToolBarIcon(action)
                # remove the toolbar
                del self.toolbar


#############################
## Set Input & Output files## 
#############################  


     
    def select_input_file(self):
        if self.dlg.EditBrowse.text() == str():
            dialog = QFileDialog(self.dlg)
            dialog.setWindowTitle('Select .ecw file:')
            dialog.setNameFilter('*ecw')
            dialog.setFileMode(QFileDialog.ExistingFile)
            if dialog.exec_() == QDialog.Accepted:
                path = dialog.selectedFiles()[0]
            else:
                path = str()
                return
            #we can use : filename = QFileDialog.getOpenFileName(self.dlg, "Select .bln file:","", '*.bln') instead but it didn't remember the last directory openend on my computer (Ubuntu 16.04.2)
            self.dlg.EditBrowse.setText(path)
                    # set output name
            self.set_Output(path)
            self.getinfo(path)
            if self.dlg.All.isChecked():
                self.set_All_Window()
        else:
            None
            
    def set_Output(self,path):
        filename = str()
        l = -5
        letter = path[l]
        while letter != "/":
            filename += letter
            l -= 1
            letter = path[l]

        filename = filename[::-1]
        
        self.dlg.OutputFile.setText(filename)
        
    def Browse(self):
        self.dlg.EditBrowse.clear()
        self.select_input_file()




############################
########## RUN #############
############################        
        
    def run(self,*keep):
        """Run method that performs all the real work"""
        
        if keep[0] != True:
            self.clear_Everything()
        

        self.dlg.Browse.clicked.connect(self.Browse)
        
        
        self.dlg.Current.clicked.connect(self.set_Current_Window)
        self.dlg.Area.clicked.connect(self.set_Area_Window)
        self.dlg.All.clicked.connect(self.set_All_Window)
        
        ## Set True when it will have more format proposed
        self.dlg.ext.setEnabled(False)
        ext_name = ["GTiff"]
        self.dlg.ext.addItems(ext_name)
        
        
        self.dlg.gdal.clicked.connect(self.gdal_info)
        # show the dialog
        
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
                    
            path = self.dlg.EditBrowse.text()
            filenameout = self.dlg.OutputFile.text()
            
            
            # find work directory and name
            
            filename = str()
            try:
                while path[-1] != '/':
                     filename += path[-1]
                     path = path[:-1]
            except IndexError:
                #Sometimes when you whant to close the plugin, this Error show up here
                return
            
            path_dir = path[:-1]
            
            ecwfile = filename[::-1]
            
            #output file
            output = filenameout + ".tif"
            os.chdir(path_dir)           
            
            
            # Area limits of the file
            
            limW = float(self.dlg.LimW.text())
            limE = float(self.dlg.LimE.text())
            limN = float(self.dlg.LimN.text())
            limS = float(self.dlg.LimS.text())
            
            
            north = self.dlg.North.text()
            south = self.dlg.South.text()
            east = self.dlg.East.text()
            weast = self.dlg.Weast.text()
            
            if north == str() or south == str() or east == str() or weast == str():
                self.prob_notSet()
                
            try:    
                north = float(north)
                south = float(south)
                east = float(east)
                weast = float(weast)
            except ValueError:
                return
                
            
            if north < south or weast >= east:
                self.prob_set()
                return
            #Look if superior to limits
            prob = 0
            
            if north > limN or north < limS:
                north = limN
                prob = 1
            if south < limS or south > limN:
                south = limS
                prob = 1
            if east > limE or east < limW:
                east = limE
                prob = 1
            if weast < limW or weast > limE:
                weast = limW
                prob = 1
            
            if prob == 1:
                respond = self.prob_lim()
                if respond == 'No':
                    self.run(True)

            
            north = str(north)
            south = str(south)
            east = str(east)
            weast = str(weast)
            
               

            try : 
           
                ds = gdal.Open(ecwfile, gdal.GA_ReadOnly )
                #print ds
                ds = gdal.Translate(output,ds, projWin = [weast,north,east,south])
                ds = None                        
                
            ###### Open Raster#############3
                raster_path = path + output
                raster = QgsRasterLayer(raster_path, filenameout)
                QgsMapLayerRegistry.instance().addMapLayer(raster)
                
                
                end = self.Import_size(filenameout,raster_path)
                
                if end == 1:
                    return

            except AttributeError, ValueError :
                result = self.prob_noGdal()
                if result == 'Yes':
                    self.gdal_info()
                else:
                    return
                      
        
        
    def Import_size(self,filename,path):
        size = os.stat(path).st_size 
        size = size/1000
        size = round(size,0)
        ext = str()
        if size >= 1000000:
            size = size/1000000
            ext = ' Go'
        elif size > 1000 and ext == str() :
            size = size/1000
            size = round(size,0)
            ext = ' Mo'
        else:
            ext = ' ko'
            
        size = str(size) + ext
        
        msgBox = QMessageBox()
        msgBox.setText('Import of ' + filename + ' finish')
        msgBox.setWindowTitle("ECW Import")
        msgBox.setInformativeText('Size file is ' + size)
        ret = msgBox.exec_()
        
        if ret:
            return

############################@
#### Set Window GUI ########
############################                

    def getinfo(self,path):
        
        with open(path, mode='rb') as file: # b is important -> binary
            f = file.readline()
            f += file.readline()
        
        header1 = f[17:62]
        headerecw = struct.unpack('hddddsssss',header1)
        
        
        size = f[6:14]
        size = size[::-1]
        sizeecw = struct.unpack('ii',size)
        
        
        UTMf=f[73:78]
        UTMecw = struct.unpack('sssss',UTMf)
        
        
        unit = headerecw[0]
        Psx  = headerecw[1]
        Psy  = headerecw[2]
        Ox = headerecw[3]
        Oy = headerecw[4]
        
        Datum = headerecw[5]+headerecw[6]+headerecw[7]+headerecw[8]+headerecw[9]
        UTM = UTMecw[0]+UTMecw[1]+UTMecw[2]+UTMecw[3]+UTMecw[4]
        
        sizeV = sizeecw[0]
        sizeH = sizeecw[1]
        
        Limy = Oy+Psy*sizeV
        Limx = Ox+Psx*sizeH
        
        self.dlg.infoDatum.setText(Datum)
        self.dlg.infoUTM.setText(UTM)
        
        
        self.dlg.LimW.setText(str(round(Ox,1)))
        self.dlg.LimE.setText(str(round(Limx,1)))
        
        if Oy >= Limy:
            self.dlg.LimN.setText(str(round(Oy,1)))
            self.dlg.LimS.setText(str(round(Limy,1)))
        else:
            self.dlg.LimN.setText(str(round(Limy,1)))
            self.dlg.LimS.setText(str(round(Oy,1)))
            
        if unit == 1:
            Units = 'Meter'
        elif unit == 2:
            Units = 'Degrees'
        elif unit == 3:
            Units = 'Foot'
        else:
            Units = 'Unknow'
            
        self.dlg.infoUnit.setText(Units)




    def Current_Window(self):
        window = self.iface.mapCanvas().extent().asWktCoordinates()
        #print window
        east = str()
        south = str()
        north = str()
        weast = str()
        
        #Read numbers
        while window[0] != " ":
            weast += window[0]
            window = window[1:]
        
        window = window[1:]
        
        while window[0] != ",":
            south += window[0]
            window = window[1:]
        
        window = window[2:]
        
        while window[0] != " ":
            east += window[0]
            window = window[1:]
            
        window = window[1:]
        
        while len(window) != 0:
            north += window[0]
            window = window[1:]
        
        north = float(north)
        south = float(south)
        east = float(east)
        weast = float(weast)
        
        return(north,south,east,weast)
 
      
    def set_Current_Window(self):
        
        north,south,east,weast = self.Current_Window()
        
        self.dlg.North.setText(str(round(north,2)))
        self.dlg.South.setText(str(round(south,2)))
        self.dlg.East.setText(str(round(east,2)))
        self.dlg.Weast.setText(str(round(weast,2)))
        self.dlg.Area.setChecked(True)
        
    def set_Area_Window(self):
        self.dlg.North.clear()
        self.dlg.South.clear()
        self.dlg.East.clear()
        self.dlg.Weast.clear()
        
        self.dlg.North.setReadOnly(False)
        self.dlg.South.setReadOnly(False)
        self.dlg.East.setReadOnly(False)
        self.dlg.Weast.setReadOnly(False)
    
    def set_All_Window(self):
        self.dlg.North.setText(self.dlg.LimN.text())
        self.dlg.South.setText(self.dlg.LimS.text())
        self.dlg.East.setText(self.dlg.LimE.text())
        self.dlg.Weast.setText(self.dlg.LimW.text())
        
        self.dlg.North.setReadOnly(True)
        self.dlg.South.setReadOnly(True)
        self.dlg.East.setReadOnly(True)
        self.dlg.Weast.setReadOnly(True)
        
    def clear_Everything(self):
        
        self.dlg.North.clear()
        self.dlg.South.clear()
        self.dlg.East.clear()
        self.dlg.Weast.clear()
        self.dlg.ext.clear()
        
        self.dlg.infoDatum.clear()
        self.dlg.infoUTM.clear()
        self.dlg.infoUnit.clear()
        
        
        self.dlg.LimW.clear()
        self.dlg.LimE.clear()
        self.dlg.LimN.clear()
        self.dlg.LimS.clear()
        
        self.dlg.OutputFile.clear()
        self.dlg.EditBrowse.clear()
        
        self.dlg.Area.setChecked(True)
        
        
        
        
###########################
### GDAL info & Install ###
###########################
     
    def gdal_info(self):
        try:
            Version = gdal.VersionInfo()
            nbreVersion = str()
            
            if int(Version[:2]) < 201:
                self.gdal.Version.setStyleSheet('color: green')
            else:
                self.gdal.Version.setStyleSheet('color: red')
                
                
            while len(Version) >=1:
                if Version[0] == '0':
                    Version = Version[1:]
                else:
                    nbreVersion += Version[0] + '.'
                    Version = Version[1:]
                
            nbreVersion = nbreVersion[:-1]
            
        except AttributeError:
            nbreVersion = 'GDAL not Installed'
        
        # Find if ECW is available
        contability = 0
        
        for i in range(gdal.GetDriverCount()):
            driver = gdal.GetDriver(i).ShortName
            if driver == 'ECW':
                contability = 1
                break
        
        if contability == 1:
            #available
            self.gdal.ECWOk.setStyleSheet('color: green')
            self.gdal.ECWOk.setText('Yes')
        else:
            #Not Available
            self.gdal.ECWOk.setStyleSheet('color: red')
            self.gdal.ECWOk.setText('No')
            
            
            
        self.gdal.setWindowTitle("GDAL Version")
        self.gdal.Version.setText(nbreVersion)
        
        
        self.gdal.Ok.clicked.connect(self.close)
        self.gdal.Install.clicked.connect(self.install)
        
        self.gdal.exec_()

    def close(self):
        self.gdal.close()
        self.htgdal.close()
    def install(self):
        self.htgdal.setWindowTitle("Install ECW lybrary / GDAL")
        

        self.htgdal.GDAL.clicked.connect(self.DownGDAL)
        self.htgdal.Plugin.clicked.connect(self.DownPLUG)
        self.htgdal.maybe.clicked.connect(self.DownMAYBE)
        self.htgdal.ECW.clicked.connect(self.DownECW)
        
        self.htgdal.ERDAS_L.clicked.connect(self.DownERDAS)
        self.htgdal.ERDAS_M.clicked.connect(self.DownERDAS)
        self.htgdal.ERDAS_W.clicked.connect(self.DownERDAS)
        
        self.htgdal.exec_()
        
    def DownECW(self):
        webbrowser.open_new('https://s3-ap-southeast-2.amazonaws.com/adamogradybackups/libecwj2-3.3-2006-09-06.zip')
    def DownGDAL(self):
        webbrowser.open_new('http://trac.osgeo.org/gdal/wiki/DownloadSource')
    def DownPLUG(self):
        webbrowser.open_new('http://www.kyngchaos.com/software/archive')
    def DownERDAS(self):
        webbrowser.open_new('http://download.intergraph.com/download-portal')
    def DownMAYBE(self):
        webbrowser.open_new('https://trac.osgeo.org/gdal/wiki/ECW')
        
        
        
        
################################
###### Problem #################
################################
        
    def prob_lim(self):
        msgBox = QMessageBox()
        msgBox.setText("Limits set are bigger than the ecw limits")
        msgBox.setWindowTitle("ECW Import Problem")
        msgBox.setIcon(QMessageBox.Question)
        msgBox.setInformativeText("Do you whant to use ecw limits?")
        msgBox.addButton(QMessageBox.Yes)
        msgBox.addButton(QMessageBox.No)
        msgBox.setDefaultButton(QMessageBox.Yes)
        ret = msgBox.exec_()
        
        if ret == QMessageBox.Yes:
            return('Yes')
        else:
            return('No')
            
    def prob_notSet(self):
        msgBox = QMessageBox()
        msgBox.setText("At least one area limit is not set.")
        msgBox.setWindowTitle("ECW Import Problem")
        msgBox.setIcon(QMessageBox.Warning)
        msgBox.setInformativeText("You need to set all limits")
        ret = msgBox.exec_()
        
        if ret:
            self.run(True)
            
    def prob_set(self):
        msgBox = QMessageBox()
        msgBox.setText("There is a problem with your limits\n(South > North or East > Weast)")
        msgBox.setWindowTitle("ECW Import Problem")
        msgBox.setIcon(QMessageBox.Warning)
        msgBox.setInformativeText("Check again your Area limits")
        ret = msgBox.exec_()
        
        if ret:
            self.run(True)
            
    def prob_noGdal(self):
        msgBox = QMessageBox()
        msgBox.setText("You can't open ECW file")
        msgBox.setWindowTitle("GDAL or ECW Problem")
        msgBox.setIcon(QMessageBox.Critical)
        msgBox.setInformativeText("Do you whant to see how fix the problem?")
        msgBox.addButton(QMessageBox.Yes)
        msgBox.addButton(QMessageBox.No)
        msgBox.setDefaultButton(QMessageBox.Yes)
        ret = msgBox.exec_()
        
        if ret == QMessageBox.Yes:
            return('Yes')
        else:
            return('No')
        
        
        
