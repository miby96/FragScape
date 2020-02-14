# -*- coding: utf-8 -*-
"""
/***************************************************************************
 FragScape
                                 A QGIS plugin
 This plugin computes mesh effective size
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2018-11-05
        git sha              : $Format:%H$
        copyright            : (C) 2018 by Mathieu Chailloux
        email                : mathieu@chailloux.org
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

import os
import sys
import traceback
from io import StringIO
import xml.etree.ElementTree as ET

from PyQt5 import uic
from PyQt5 import QtWidgets
from PyQt5.QtCore import QTranslator, qVersion, QCoreApplication

from qgis.gui import QgsFileWidget
from qgis.core import QgsApplication, QgsProcessingContext

from .qgis_lib_mc import utils, qgsUtils, feedbacks, config_parsing, log, qgsTreatments
from .algs.FragScape_algs_provider import FragScapeAlgorithmsProvider
from .algs.FragScape_global_alg import FragScapeAlgorithm
from .steps import params, landuse, fragm, reporting
from . import tabs
from .FragScape_model import FragScapeModel

#from FragScapeAbout_dialog import FragScapeAboutDialog
from .FragScape_dialog_base import Ui_FragScapeDialogBase
from .FragScapeAbout_dialog_base import Ui_FragScapeAbout

class FragScapeAboutDialog(QtWidgets.QDialog,Ui_FragScapeAbout):

    def __init__(self,parent=None):
        super(FragScapeAboutDialog,self).__init__(parent)
        self.setupUi(self)

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'FragScape_dialog_base.ui'))


# class FragScapeDialog(QtWidgets.QDialog, Ui_FragScapeDialogBase):
class FragScapeDialog(QtWidgets.QDialog, FORM_CLASS):

    def __init__(self, parent=None):
        """Constructor."""
        super(FragScapeDialog, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.provider = FragScapeAlgorithmsProvider()
        fsGlobalAlg = FragScapeAlgorithm()
        fsGlobalAlg.initAlgorithm()
        self.provider.alglist.append(fsGlobalAlg)
        self.setupUi(self)

    def initTabs(self):
        global progressFeedback
        logConnector = log.LogConnector(self)
        logConnector.initGui()
        self.feedback =  feedbacks.ProgressFeedback(self)
        feedbacks.progressFeedback = self.feedback
        utils.debug("progressFeedback = " + str(feedbacks.progressFeedback))
        self.context = QgsProcessingContext()
        self.context.setFeedback(feedbacks.progressFeedback)
        self.fsModel = FragScapeModel(self.context,feedbacks.progressFeedback)
        self.paramsConnector = params.ParamsConnector(self,self.fsModel.paramsModel)
        params.params = self.paramsConnector.model
        self.landuseConnector = landuse.LanduseConnector(self,self.fsModel.landuseModel)
        self.fragmConnector = fragm.FragmConnector(self,self.fsModel.fragmModel)
        self.reportingConnector = reporting.ReportingConnector(self,self.fsModel.reportingModel)
        tabConnector = tabs.TabConnector(self)
        self.connectors = {"Params" : self.paramsConnector,
                           "Log" : logConnector,
                           "Landuse" : self.landuseConnector,
                           "Fragm" : self.fragmConnector,
                           "Reporting" : self.reportingConnector,
                           "Progress" : feedbacks.progressFeedback,
                           "Tabs" : tabConnector}
        self.recomputeParsers()
        
    def initGui(self):
        QgsApplication.processingRegistry().addProvider(self.provider)
        self.switchLangEn()
        for k, tab in self.connectors.items():
            tab.initGui()
        
    def modeIsVector(self): 
        return self.paramsConnector.modeIsVector()
        
    def getVectorWidgets(self):
        widgets = []
        return widgets
    def getRasterWidgets(self):
        widgets = [self.rasterResolution]
        return widgets
        
    # Exception hook, i.e. function called when exception raised.
    # Displays traceback and error message in log tab.
    # Ignores CustomException : exception raised from FragScape and already displayed.
    def exceptionHook(self,excType, excValue, tracebackobj):
        utils.debug("bioDispHook")
        if excType == utils.CustomException:
            utils.debug("Ignoring custom exception : " + str(excValue))
        else:
            tbinfofile = StringIO()
            traceback.print_tb(tracebackobj, None, tbinfofile)
            tbinfofile.seek(0)
            tbinfo = tbinfofile.read()
            errmsg = str(excType.__name__) + " : " + str(excValue)
            separator = '-' * 80
            #sections = [separator, errmsg, separator]
            #utils.debug(str(sections))
            msg = separator + "\n" + errmsg + "\n" + separator
            #msg = '\n'.join(sections)
            utils.debug(str(msg))
            #final_msg = tbinfo + "\n" + msg
            utils.warn("Traceback : " + tbinfo)
            utils.error_msg(msg,prefix="Unexpected error")
        self.mTabWidget.setCurrentWidget(self.logTab)
        #feedbacks.progressConnector.clear()
        
    # Connects view and model components for each tab.
    # Connects global elements such as project file and language management.
    def connectComponents(self):
        for k, tab in self.connectors.items():
            tab.connectComponents()
        # Main tab connectors
        self.saveProjectAs.clicked.connect(self.saveModelAsAction)
        self.saveProject.clicked.connect(self.saveModel)
        self.openProject.clicked.connect(self.loadModelAction)
        self.langEn.clicked.connect(self.switchLangEn)
        self.langFr.clicked.connect(self.switchLangFr)
        self.aboutButton.clicked.connect(self.openHelpDialog)
        feedbacks.progressFeedback.connectComponents()
        sys.excepthook = self.exceptionHook
        
    # Initialize or re-initialize global variables.
    def initializeGlobals(self):
        pass  
        
    def unload(self):
        self.fsModel = None
        QgsApplication.processingRegistry().removeProvider(self.provider)
        
    def initLog(self):
        utils.print_func = self.txtLog.append
        
        # Switch language to english.
    def switchLang(self,lang):
        utils.debug("switchLang " + str(lang))
        plugin_dir = os.path.dirname(__file__)
        lang_path = os.path.join(plugin_dir,'i18n','FragScape_' + lang + '.qm')
        if os.path.exists(lang_path):
            self.translator = QTranslator()
            self.translator.load(lang_path)
            if qVersion() > '4.3.3':
                utils.debug("Installing translator " + str(lang_path))
                QCoreApplication.installTranslator(self.translator)
            else:
                utils.internal_error("Unexpected qVersion : " + str(qVersion()))
        else:
            utils.warn("No translation file : " + str(en_path))
        self.retranslateUi(self)
        utils.curr_language = lang
        self.connectors["Tabs"].loadHelpFile()
        
    def switchLangEn(self):
        self.switchLang("en")
        self.langEn.setChecked(True)
        self.langFr.setChecked(False)
        
    def switchLangFr(self):
        self.switchLang("fr")
        self.langEn.setChecked(False)
        self.langFr.setChecked(True)
        
    def openHelpDialog(self):
        utils.debug("openHelpDialog")
        about_dlg = FragScapeAboutDialog(self)
        about_dlg.show()
        
    
    # Recompute self.parsers in case they have been reloaded
    def recomputeParsers(self):
        self.parsers = [self.paramsConnector,
                        self.landuseConnector,
                        self.fragmConnector.model,
                        self.reportingConnector]
        
        # Return XML string describing project
    def toXML(self):
        xmlStr = self.fsModel.toXML()
        return xmlStr

    # Save project to 'fname'
    def saveModelAs(self,fname):
        self.recomputeParsers()
        xmlStr = self.fsModel.toXML()
        self.paramsConnector.setProjectFile(fname)
        utils.writeFile(fname,xmlStr)
        utils.info("FragScape model saved into file '" + fname + "'")
        
    def saveModelAsAction(self):
        fname = qgsUtils.saveFileDialog(parent=self,msg="Sauvegarder le projet sous",filter="*.xml")
        if fname:
            self.saveModelAs(fname)
        
    # Save project to projectFile if existing
    def saveModel(self):
        fname = self.fsModel.paramsModel.projectFile
        utils.checkFileExists(fname,"Project ")
        self.saveModelAs(fname)
   
    # Load project from 'fname' if existing
    def loadModel(self,fname):
        utils.debug("loadModel " + str(fname))
        utils.checkFileExists(fname)
        config_parsing.setConfigParsers(self.parsers)
        self.paramsConnector.setProjectFile(fname)
        config_parsing.parseConfig(fname)
        utils.info("FragScape model loaded from file '" + fname + "'")
        
    def loadModelAction(self):
        fname =qgsUtils.openFileDialog(parent=self,msg="Ouvrir le projet",filter="*.xml")
        if fname:
            self.loadModel(fname)
