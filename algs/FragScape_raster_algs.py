# -*- coding: utf-8 -*-
"""
/***************************************************************************
 FragScape
                                 A QGIS plugin
 Computes effective mesh size
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

import math
import scipy
import numpy as np

from PyQt5.QtCore import QCoreApplication
from qgis.core import (QgsProcessing,
                       QgsProcessingUtils,
                       QgsProcessingException,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterRasterLayer,
                       QgsProcessingParameterNumber,
                       QgsProcessingOutputNumber,
                       QgsProcessingOutputRasterLayer,
                       QgsProcessingParameterFeatureSource)      

from ..qgis_lib_mc import qgsUtils, qgsTreatments                    
                       
def tr(string):
    return QCoreApplication.translate('Processing', string) 

class MeffRaster(QgsProcessingAlgorithm):

    ALG_NAME = "meffRaster"
    
    INPUT = "INPUT"
    CLASS = "CLASS"
    OUTPUT = "OUTPUT"
        
    def createInstance(self):
        return MeffRaster()
        
    def name(self):
        return self.ALG_NAME
        
    def displayName(self):
        return tr("Raster Effective Mesh Size")
        
    def shortHelpString(self):
        return tr("Computes effective mesh size on a raster layer")

    def initAlgorithm(self, config=None):
        '''Here we define the inputs and output of the algorithm, along
        with some other properties'''
        self.addParameter(QgsProcessingParameterRasterLayer(
            self.INPUT, "Input raster layer", optional=False))
        self.addParameter(QgsProcessingParameterNumber(
            self.CLASS, "Choose Landscape Class", type=QgsProcessingParameterNumber.Integer, defaultValue=1))
        self.addOutput(QgsProcessingOutputNumber(
            self.OUTPUT, "Output effective mesh size"))
        
    def processAlgorithm(self, parameters, context, feedback):
        '''Here is where the processing itself takes place'''
        
        # Retrieve the values of the parameters entered by the user
        input = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        cl = self.parameterAsInt(parameters, self.CLASS, context)
        output = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)        
                
        # Processing
        input_dpr = input.dataProvider()
        nodata = input_dpr.sourceNoDataValue(1)
        inputFilename = input.source()
        x_res = input.rasterUnitsPerPixelX() # Extract The X-Value
        y_res = input.rasterUnitsPerPixelY() # Extract The Y-Value
        pix_area = x_res * y_res
        feedback.pushDebugInfo("Pixel area " + str(x_res) + " x " + str(y_res)
                                + " = " + str(pix_area))
        classes, array = qgsUtils.getRasterValsAndArray(str(inputFilename)) # get classes and array
        if cl not in classes:
            raise QgsProcessingException("Input layer has no cells with value " + str(cl))
        new_array = np.copy(array)
        new_array[new_array!=cl] = 0
        # 8-connexity ? TODO : investigate
        struct = scipy.ndimage.generate_binary_structure(2,2)
        labeled_array, nb_patches = scipy.ndimage.label(new_array,struct)
        feedback.pushDebugInfo("nb_patches = " + str(nb_patches))

        res = []
        labels = list(range(1,nb_patches+1))
        feedback.pushDebugInfo("labels = " + str(labels))
        patches_len = scipy.ndimage.labeled_comprehension(new_array,labeled_array,labels,len,int,0)
        feedback.pushDebugInfo("patches_len = " + str(patches_len))
        
        sum_ai = 0
        sum_ai_sq = 0
        for patch_len in patches_len:
            ai = patch_len * pix_area
            sum_ai_sq += math.pow(ai,2)
            sum_ai += ai
        feedback.pushDebugInfo("sum_ai = " + str(sum_ai))
        feedback.pushDebugInfo("sum_ai_sq = " + str(sum_ai_sq))
        if sum_ai_sq == 0:
            feedback.reportError("Empty area for patches, please check your selection.")
        
        nb_pix = len(array[array != nodata])
        tot_area = nb_pix * pix_area
        #area_sq = math.pow(nb_pix,2)
        if nb_pix == 0:
            feedback.reportError("Unexpected error : empty area for input layer")
        
        res = float(sum_ai_sq) / float(tot_area)
        
        return {self.OUTPUT: res}
        
 

class MeffRasterCBC2(QgsProcessingAlgorithm):

    ALG_NAME = "meffRasterCBC2"
    
    INPUT = "INPUT"
    CLASS = "CLASS"
    REPORTING_LAYER = "REPORTING_LAYER"
    OUTPUT = "OUTPUT"
    OUTPUT_PATH = "OUTPUT_PATH"
        
    def createInstance(self):
        return MeffRasterCBC()
        
    def name(self):
        return self.ALG_NAME
        
    def displayName(self):
        return tr("Raster Effective Mesh Size (Cross-Boundary C2)")
        
    def shortHelpString(self):
        return tr("Computes effective mesh size on a raster layer")

    def initAlgorithm(self, config=None):
        '''Here we define the inputs and output of the algorithm, along
        with some other properties'''
        self.addParameter(QgsProcessingParameterRasterLayer(
            self.INPUT, "Input raster layer", optional=False))
        self.addParameter(QgsProcessingParameterNumber(
            self.CLASS, "Choose Landscape Class", type=QgsProcessingParameterNumber.Integer, defaultValue=1))
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.REPORTING_LAYER,
                description=tr("Reporting layer"),
                types=[QgsProcessing.TypeVectorPolygon],
                optional=True))
        self.addOutput(QgsProcessingOutputNumber(
            self.OUTPUT, "Output effective mesh size"))
        self.addOutput(QgsProcessingOutputRasterLayer(
            self.OUTPUT_PATH, "Output path"))
        
    def processAlgorithm(self, parameters, context, feedback):
        '''Here is where the processing itself takes place'''
        
        # Retrieve the values of the parameters entered by the user
        input = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        cl = self.parameterAsInt(parameters, self.CLASS, context)
        report_layer = self.parameterAsVectorLayer(parameters,self.REPORTING_LAYER,context)
        output = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)        
            
        # Processing
        input_dpr = input.dataProvider()
        nodata = input_dpr.sourceNoDataValue(1)
        inputFilename = input.source()
        x_res = input.rasterUnitsPerPixelX() # Extract The X-Value
        y_res = input.rasterUnitsPerPixelY() # Extract The Y-Value
        pix_area = x_res * y_res
        feedback.pushDebugInfo("Pixel area " + str(x_res) + " x " + str(y_res)
                                + " = " + str(pix_area))
        classes, array = qgsUtils.getRasterValsAndArray(str(inputFilename)) # get classes and array
        if cl not in classes:
            raise QgsProcessingException("Input layer has no cells with value " + str(cl))
        new_array = np.copy(array)
        new_array[new_array!=cl] = 0
        # 8-connexity ? TODO : investigate
        struct = scipy.ndimage.generate_binary_structure(2,2)
        labeled_array, nb_patches = scipy.ndimage.label(new_array,struct)
        feedback.pushDebugInfo("nb_patches = " + str(nb_patches))
        feedback.pushDebugInfo("new_array = " + str(labeled_array[labeled_array==52]))
        labels = list(range(1,nb_patches+1))
        feedback.pushDebugInfo("labels = " + str(labels))
        
        labeled_path = QgsProcessingUtils.generateTempFilename("labeled.tif")
        clipped_path = QgsProcessingUtils.generateTempFilename("labeled_clipped.tif")
        qgsUtils.exportRaster(labeled_array,inputFilename,labeled_path)
        clipped = qgsTreatments.clipRasterFromVector(labeled_path,report_layer,clipped_path,
            crop_cutline=False, context=context, feedback=feedback)
        clip_classes, clip_array = qgsUtils.getRasterValsAndArray(str(clipped_path))
        feedback.pushDebugInfo("clip_classes = " + str(clip_classes))
            
        # def labelFunc(patch):
            # idx = patch[0]
            # feedback.pushDebugInfo("patch = " + str(patch))
            # feedback.pushDebugInfo("idx = " + str(idx))
            # return (idx,len(patch))
            
        # dummy_type= np.dtype('O')
        # feedback.pushDebugInfo("dtype = " + str(dummy_type))
        # patches_len = scipy.ndimage.labeled_comprehension(
            # new_array,labeled_array,labels,labelFunc,dummy_type,None,pass_positions=False)
        # feedback.pushDebugInfo("patchess_len = " + str(patches_len))
        
        sum_ai_sq = 0
        for lbl in clip_classes:
            lbl_val = int(lbl)
            feedback.pushDebugInfo("lbl_val = " + str(lbl_val))
            patch = labeled_array[labeled_array==lbl_val]
            patch_len = len(patch)
            patch_cbc = clip_array[clip_array==lbl_val]
            cbc_len = len(patch_cbc)
            if patch_len != cbc_len:
                #feedback.pushDebugInfo("patch = " + str(patch))
                feedback.pushDebugInfo("patch_len = " + str(patch_len))
                #feedback.pushDebugInfo("patch_cbc = " + str(patch_cbc))
                feedback.pushDebugInfo("cbc_len = " + str(cbc_len))
            # Accumulators
            ai = patch_len * pix_area
            ai_cbc = cbc_len * pix_area
            sum_ai_sq += ai * ai_cbc
        feedback.pushDebugInfo("sum_ai_sq = " + str(sum_ai_sq))
            
        #qgsUtils.loadRasterLayer(clipped_path,loadProject=True)
        #res = 0
        return {self.OUTPUT : sum_ai_sq, self.OUTPUT_PATH : clipped_path}
            
            

class MeffRasterCBC(QgsProcessingAlgorithm):

    ALG_NAME = "meffRasterCBC2"
    
    INPUT = "INPUT"
    CLASS = "CLASS"
    REPORTING_LAYER = "REPORTING_LAYER"
    OUTPUT = "OUTPUT"
    OUTPUT_PATH = "OUTPUT_PATH"
        
    def createInstance(self):
        return MeffRasterCBC()
        
    def name(self):
        return self.ALG_NAME
        
    def displayName(self):
        return tr("Raster Effective Mesh Size (Cross-Boundary C)")
        
    def shortHelpString(self):
        return tr("Computes effective mesh size on a raster layer")

    def initAlgorithm(self, config=None):
        '''Here we define the inputs and output of the algorithm, along
        with some other properties'''
        self.addParameter(QgsProcessingParameterRasterLayer(
            self.INPUT, "Input raster layer", optional=False))
        self.addParameter(QgsProcessingParameterNumber(
            self.CLASS, "Choose Landscape Class", type=QgsProcessingParameterNumber.Integer, defaultValue=1))
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.REPORTING_LAYER,
                description=tr("Reporting layer"),
                types=[QgsProcessing.TypeVectorPolygon],
                optional=True))
        self.addOutput(QgsProcessingOutputNumber(
            self.OUTPUT, "Output effective mesh size"))
        self.addOutput(QgsProcessingOutputRasterLayer(
            self.OUTPUT_PATH, "Output path"))
        
    def processAlgorithm(self, parameters, context, feedback):
        '''Here is where the processing itself takes place'''
        
        # Retrieve the values of the parameters entered by the user
        input = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        cl = self.parameterAsInt(parameters, self.CLASS, context)
        report_layer = self.parameterAsVectorLayer(parameters,self.REPORTING_LAYER,context)
        output = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)        
            
        # Processing
        input_dpr = input.dataProvider()
        nodata = input_dpr.sourceNoDataValue(1)
        inputFilename = input.source()
        x_res = input.rasterUnitsPerPixelX() # Extract The X-Value
        y_res = input.rasterUnitsPerPixelY() # Extract The Y-Value
        pix_area = x_res * y_res
        feedback.pushDebugInfo("Pixel area " + str(x_res) + " x " + str(y_res)
                                + " = " + str(pix_area))
        classes, array = qgsUtils.getRasterValsAndArray(str(inputFilename)) # get classes and array
        if cl not in classes:
            raise QgsProcessingException("Input layer has no cells with value " + str(cl))
        new_array = np.copy(array)
        new_array[new_array!=cl] = 0
        # 8-connexity ? TODO : investigate
        struct = scipy.ndimage.generate_binary_structure(2,2)
        labeled_array, nb_patches = scipy.ndimage.label(new_array,struct)
        feedback.pushDebugInfo("nb_patches = " + str(nb_patches))
        feedback.pushDebugInfo("new_array = " + str(labeled_array[labeled_array==52]))
        labels = list(range(1,nb_patches+1))
        feedback.pushDebugInfo("labels = " + str(labels))
        
        labeled_path = QgsProcessingUtils.generateTempFilename("labeled.tif")
        clipped_path = QgsProcessingUtils.generateTempFilename("labeled_clipped.tif")
        qgsUtils.exportRaster(labeled_array,inputFilename,labeled_path)
        clipped = qgsTreatments.clipRasterFromVector(labeled_path,report_layer,clipped_path,
            crop_cutline=False, context=context, feedback=feedback)
        clip_classes, clip_array = qgsUtils.getRasterValsAndArray(str(clipped_path))
        feedback.pushDebugInfo("clip_classes = " + str(clip_classes))
        
        dummy_type= np.dtype('O')
        feedback.pushDebugInfo("dtype = " + str(dummy_type))
        patches_len = scipy.ndimage.labeled_comprehension(
            new_array,labeled_array,labels,len,int,0)
        feedback.pushDebugInfo("patchess_len = " + str(patches_len))
        patches_len_clipped = scipy.ndimage.labeled_comprehension(
            new_array,clip_array,clip_classes,len,int,0)
        feedback.pushDebugInfo("patches_len_clipped = " + str(patches_len_clipped))
        
        sum_ai_sq = 0
        for cpt, lbl in enumerate(clip_classes):
            lbl_val = int(lbl)
            feedback.pushDebugInfo("lbl_val = " + str(lbl_val))
            patch_len = patches_len[lbl_val-1]
            cbc_len = patches_len_clipped[cpt]
            if patch_len != cbc_len:
                #feedback.pushDebugInfo("patch = " + str(patch))
                feedback.pushDebugInfo("patch_len = " + str(patch_len))
                #feedback.pushDebugInfo("patch_cbc = " + str(patch_cbc))
                feedback.pushDebugInfo("cbc_len = " + str(cbc_len))
            # Accumulators
            ai = patch_len * pix_area
            ai_cbc = cbc_len * pix_area
            sum_ai_sq += ai * ai_cbc
        feedback.pushDebugInfo("sum_ai_sq = " + str(sum_ai_sq))
            
        #qgsUtils.loadRasterLayer(clipped_path,loadProject=True)
        #res = 0
        return {self.OUTPUT : sum_ai_sq, self.OUTPUT_PATH : clipped_path}
            
            