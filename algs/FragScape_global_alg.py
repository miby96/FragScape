# -*- coding: utf-8 -*-
"""
/***************************************************************************
 FragScape
                                 A QGIS plugin
 Computes ecological continuities based on environments permeability
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2018-04-12
        git sha              : $Format:%H$
        copyright            : (C) 2018 by IRSTEA
        email                : mathieu.chailloux@irstea.fr
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

from PyQt5.QtCore import QCoreApplication, QVariant
from qgis.core import QgsProcessing, QgsProcessingAlgorithm, QgsProcessingException
from qgis.core import (QgsProcessingProvider,
                       QgsProcessingParameterVectorDestination,
                       QgsProcessingParameterFile, QgsProcessingParameterFileDestination)
#from qgis.core import QgsField, QgsFields, QgsFeature, QgsFeatureSink

import processing
import xml.etree.ElementTree as ET

from ..qgis_lib_mc import utils, qgsUtils, feedbacks
from ..FragScape_model import FragScapeModel

class FragScapeAlgorithm(QgsProcessingAlgorithm):

    # Algorithm parameters
    INPUT_CONFIG = "INPUT"
    LOG_FILE = "LOG"
    OUTPUT = "OUTPUT"
    
    def tr(self, string):
        return QCoreApplication.translate('Processing', string)
        
    def createInstance(self):
        return FragScapeAlgorithm()
        
    def name(self):
        return "FragScapeAlgorithm"
        
    def displayName(self):
        return self.tr("Run FragScape from configuration file")
        
    def shortHelpString(self):
        return self.tr("Executes complete process from XML configuration file")

    def initAlgorithm(self,config=None):
        self.addParameter(
            QgsProcessingParameterFile(
                self.INPUT_CONFIG,
                description=self.tr("Input configuration file")))
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.LOG_FILE,
                description=self.tr("Log file")))
        self.addParameter(
            QgsProcessingParameterVectorDestination(
                self.OUTPUT,
                description=self.tr("Output layer"),
                type=QgsProcessing.TypeVectorPolygon))
                
    def processAlgorithm(self,parameters,context,feedback):
        feedback.pushInfo("begin")
        print("coucou")
        utils.print_func = feedback.pushInfo
        # Parameters
        log_file = self.parameterAsFile(parameters,self.LOG_FILE,context)
        print("lof_file = " + str(log_file))
        if utils.fileExists(log_file):
            os.remove(log_file)
        with open(log_file,"w+") as f:
            f.write("FragScape from configuration file " + str(log_file) + "\n")
            #raise QgsProcessingException("Log file " + str(log_file) + " already exists")
        print("args ok")
        log_feedback = feedbacks.FileFeedback(log_file)
        print("args ok")
        log_feedback.pushInfo("test")
        config_file = self.parameterAsFile(parameters,self.INPUT_CONFIG,context)
        print("args ok : " + str(config_file))
        config_tree = ET.parse(config_file)
        print("args ok")
        config_root = config_tree.getroot()
        print("args ok")
        fragScapeModel = FragScapeModel(context,log_feedback)
        print("fs ok")
        fragScapeModel.fromXMLRoot(config_root)
        print("fs2 ok")
        fragScapeModel.landuseModel.applyItemsWithContext(context,log_feedback)
        print("s1 ok")
        fragScapeModel.fragmModel.applyItemsWithContext(context,log_feedback)
        print("s2 ok")
        res = fragScapeModel.reportingModel.runReportingWithContext(context,log_feedback)
        print("s3 ok")
        #qgsUtils.loadVectorLayer(res,loadProject=True)
        return {self.OUTPUT: res}