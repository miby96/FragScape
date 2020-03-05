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
try:
    from scipy import ndimage
    import numpy as np
except ModuleNotFoundError:
    pass

import time, sys

try:
    from osgeo import gdal
except ImportError:
    import gdal

from PyQt5.QtCore import QCoreApplication
from qgis.core import (QgsProcessing,
                       QgsProcessingUtils,
                       QgsProcessingException,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterRasterLayer,
                       QgsProcessingParameterNumber,
                       QgsProcessingOutputNumber,
                       QgsProcessingOutputRasterLayer,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterEnum,
                       QgsProcessingParameterFeatureSource)      

from ..qgis_lib_mc import utils, qgsUtils, qgsTreatments, feedbacks
from ..steps import params
from .FragScape_algs import MeffAlgUtils


class FragScapeRasterAlgorithm(QgsProcessingAlgorithm,MeffAlgUtils):
    
    def __init__(self):
        self.curr_suffix = ""
        QgsProcessingAlgorithm.__init__(self)
            
    def createInstance(self):
        assert(False)
    
    def displayName(self):
        assert(False)
        
    def shortHelpString(self):
        assert(False)
        
    def name(self):
        return self.ALG_NAME
    
    def group(self):
        return "Raster"
    
    def groupId(self):
        return "fsRast"
        
    def initAlgorithm(self, config=None, report_opt=True):
        self.report_opt = report_opt
        self.addParameter(QgsProcessingParameterRasterLayer(
            self.INPUT, "Input raster layer",
            optional=False))
        self.addParameter(QgsProcessingParameterNumber(
            self.CLASS, "Choose Landscape Class",
            type=QgsProcessingParameterNumber.Integer,
            defaultValue=1))
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.REPORTING,
                description=self.tr("Clip layer (boundary)"),
                types=[QgsProcessing.TypeVectorPolygon],
                optional=report_opt))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.UNIT,
                description=self.tr("Report areas unit"),
                options=self.getUnitOptions(),
                defaultValue=0))
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr("Output layer"),
                optional=True)),
        self.addOutput(QgsProcessingOutputNumber(
            self.OUTPUT_VAL, "Output layer"))
            
    def prepareInputs(self,parameters,context,feedback):
        input = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        cl = self.parameterAsInt(parameters, self.CLASS, context)
        report_layer = self.parameterAsVectorLayer(parameters,self.REPORTING,context)
        if not self.report_opt and not report_layer:
            raise QgsProcessingException("No reporting layer given")
        self.report_layer = report_layer
        feedback.pushDebugInfo("parameters = " + str(parameters))
        # feedback.pushDebugInfo("unit_init = " + str(parameters[self.UNIT]))
        unit = self.parameterAsEnum(parameters,self.UNIT,context)
        feedback.pushDebugInfo("unit = " + str(unit))
        self.unit_divisor = self.UNIT_DIVISOR[unit]
        feedback.pushDebugInfo("unit_divisor = " + str(self.unit_divisor))
        suffix = parameters[self.SUFFIX] if self.SUFFIX in parameters else ""
        output = self.parameterAsOutputLayer(parameters,self.OUTPUT,context)
        if not output:
            raise QgsProcessingException("No output layer given")
        # output = parameters[self.OUTPUT]
        # Input properties
        input_dpr = input.dataProvider()
        input_crs = input_dpr.crs()
        nodata = input_dpr.sourceNoDataValue(1)
        inputFilename = input.source()
        x_res = input.rasterUnitsPerPixelX() # Extract The X-Value
        y_res = input.rasterUnitsPerPixelY() # Extract The Y-Value
        pix_area = x_res * y_res
        feedback.pushDebugInfo("nodata = " + str(nodata))
        feedback.pushDebugInfo("Pixel area " + str(x_res) + " x " + str(y_res)
                                + " = " + str(pix_area))
        if math.isnan(nodata):
            input_type = input_dpr.dataType(1)
            unique_vals = qgsTreatments.getRasterUniqueVals(input,feedback)
            nodata = qgsUtils.getNDCandidate(input_type,unique_vals)
        # Clip input
        clip_flag = self.CLIP_FLAG not in parameters or parameters[self.CLIP_FLAG]
        if clip_flag and report_layer:
            input_clipped_path = QgsProcessingUtils.generateTempFilename(
                "input_clipped" + suffix + ".tif")
            clipped = qgsTreatments.clipRasterFromVector(inputFilename,report_layer,
                input_clipped_path,crop_cutline=True,nodata=nodata,
                data_type=0,context=context, feedback=feedback)
            clipped = input_clipped_path
            # clipped = qgsTreatments.clipRasterAllTouched(inputFilename,report_layer,
                # input_crs,out_path=input_clipped_path,nodata=nodata,
                # data_type=0,resolution=x_res,context=context, feedback=feedback)
        else:
            clipped = inputFilename   
        self.nodata = nodata
        self.cl = cl
        self.pix_area = pix_area
        self.input_clipped = clipped
        self.input_crs = input_crs
        self.resolution = x_res
        return (input, output)
        
    def labelAndPatchLen(self,input,feedback):
        feedback.pushDebugInfo("input = " + str(input))
        classes, array = qgsUtils.getRasterValsAndArray(input)
        if self.cl not in classes:
            utils.warn("Input layer " + str(input)
                + " has no cells with value " + str(self.cl))
            # labeled_array = np.empty
            labeled_array = np.zeros(array.shape)
            nb_patches = 0
            patches_len = []
        else:
            new_array = np.copy(array)
            feedback.pushDebugInfo("new_array1 = " + str(new_array))
            new_array[new_array!=self.cl] = 0
            new_array[array==self.cl] = 1
            feedback.pushDebugInfo("new_array2 = " + str(new_array))
            # 8-connexity ? TODO : investigate
            # struct = ndimage.generate_binary_structure(2,2)
            struct = ndimage.generate_binary_structure(2,1)
            labeled_array, nb_patches = ndimage.label(new_array,struct)
            feedback.pushDebugInfo("labeled_array = " + str(labeled_array))
            feedback.pushDebugInfo("nb_patches = " + str(nb_patches))
            if nb_patches == 0:
                feedback.reportError("No patches found",fatalError=True)
            labels = list(range(1,nb_patches+1))
            patches_len = ndimage.labeled_comprehension(new_array,
                labeled_array,labels,len,int,0)
            feedback.pushDebugInfo("patches_len = " + str(patches_len))
        nb_pix = len(array[array != self.nodata])
        feedback.pushDebugInfo("nb_pix = " + str(nb_pix))
        return (labeled_array, nb_patches, patches_len, nb_pix)
        
    def getGDALType(self,max_val):
        if max_val < 256:
            return gdal.GDT_Byte
        elif max_val < 65536:
            return gdal.GDT_UInt16
        else:
            return gdal.GDT_UInt32
  
    def getGDALTypeAndND(self,max_val):
        if max_val < 255:
            return gdal.GDT_Byte, 255
        elif max_val < 65535:
            return gdal.GDT_UInt16, 65536
        else:
            return gdal.GDT_UInt32, sys.maxsize


class MeffRaster(FragScapeRasterAlgorithm):

    ALG_NAME = "meffRaster"
            
    def createInstance(self):
        return MeffRaster()
        
    def displayName(self):
        return self.tr("Raster Effective Mesh Size")
        
    def shortHelpString(self):
        return self.tr("Computes effective mesh size on a raster layer")
        
    def processAlgorithm(self, parameters, context, feedback):
        # Retrieve the values of the parameters entered by the user
        self.prepareInputs(parameters,context,feedback)
        labeled_array, nb_patches, patches_len, nb_pix = self.labelAndPatchLen(
            self.input_clipped,feedback)
        
        # Computing
        sum_ai = 0
        sum_ai_sq = 0
        for patch_len in patches_len:
            ai = patch_len * self.pix_area
            sum_ai += ai
            sum_ai_sq += math.pow(ai,2)
        feedback.pushDebugInfo("sum_ai = " + str(sum_ai))
        feedback.pushDebugInfo("sum_ai_sq = " + str(sum_ai_sq))
        if sum_ai_sq == 0:
            feedback.reportError("Empty area for patches, please check your selection.")
        report_area = nb_pix * self.pix_area
        feedback.pushDebugInfo("report_area = " + str(report_area))
        
        res_dict = { self.REPORT_AREA : report_area,
            self.SUM_AI : sum_ai,
            self.SUM_AI_SQ : sum_ai_sq,
            self.NB_PATCHES : nb_patches,
            self.DIVISOR : self.unit_divisor
        }
        res_layer, res_val = self.mkOutputs(parameters,res_dict,context)
        return {self.OUTPUT : res_layer, self.OUTPUT_VAL : res_val}


class MeffRasterReport(FragScapeRasterAlgorithm):

    ALG_NAME = "meffRasterReport"
            
    def createInstance(self):
        return MeffRasterReport()
    
    def displayName(self):
        return self.tr("Raster Effective Mesh Size per feature")
        
    def shortHelpString(self):
        return self.tr("Computes effective mesh size on a raster layer")
        
    def initAlgorithm(self, config=None):
        super().initAlgorithm(config=config,report_opt=False)
        # self.addOutput(QgsProcessingOutputNumber(
            # self.OUTPUT_VAL, "Output effective mesh size"))
        
    def processAlgorithm(self, parameters, context, feedback):
        (input, output) = self.prepareInputs(parameters,context,feedback)
        output_layer = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        nb_feats = self.report_layer.featureCount()
        crs = self.report_layer.sourceCrs()
        feedback.pushDebugInfo("nb_feats = " + str(nb_feats))
        if nb_feats == 0:
            raise QgsProcessingException("Empty reporting layer")
        progress_step = 100.0 / nb_feats
        multi_feedback = feedbacks.ProgressMultiStepFeedback(nb_feats, feedback)
        report_layers = []
        parameters = { self.INPUT : self.input_clipped,
            self.CLASS : self.cl,
            self.REPORTING : self.report_layer,
            self.UNIT : parameters[self.UNIT],
            self.OUTPUT : output,
            self.SUFFIX : "Global" }
        # Iterate on feature
        if nb_feats > 1:
            for count, report_feat in enumerate(self.report_layer.getFeatures()):
                multi_feedback.setCurrentStep(count)
                report_id = report_feat.id()
                self.report_layer.selectByIds([report_id])
                select_path = params.mkTmpLayerPath("reportingSelection"
                    + str(report_id) + ".gpkg")
                qgsTreatments.saveSelectedFeatures(self.report_layer,select_path,context,multi_feedback)
                report_computed_path = params.mkTmpLayerPath("reportingComputed"
                    + str(report_id) + ".gpkg")
                parameters[self.REPORTING] = select_path
                parameters[self.OUTPUT] = report_computed_path
                parameters[self.SUFFIX] = str(report_id)
                qgsTreatments.applyProcessingAlg('FragScape','meffRaster',
                    parameters, context,multi_feedback)
                report_layers.append(report_computed_path)
            feedback.pushDebugInfo("report_layers = " + str(report_layers))
            qgsTreatments.mergeVectorLayers(report_layers,crs,output)
        # Global
        else:
            parameters[self.CLIP_FLAG] = False
            qgsTreatments.applyProcessingAlg('FragScape','meffRaster',
                parameters, context,multi_feedback)
        multi_feedback.setCurrentStep(nb_feats)
        return {self.OUTPUT: output}
        
        
class MeffRasterCBC(FragScapeRasterAlgorithm):

    ALG_NAME = "meffRasterCBC"
        
    def createInstance(self):
        return MeffRasterCBC()
        
    def displayName(self):
        return self.tr("Raster Effective Mesh Size (Cross-Boundary Connection)")
        
    def shortHelpString(self):
        return self.tr("Computes effective mesh size on a raster layer")
        
    def initAlgorithm(self,config=None):
        super().initAlgorithm(config=config,report_opt=False)
        
    def computeFeature(self,parameters,context,feedback,clip_flag=True):
        step_feedback = feedbacks.ProgressMultiStepFeedback(6,feedback)
        clipped_path = QgsProcessingUtils.generateTempFilename(
            "labeled_clipped" + self.curr_suffix + ".tif")
        clipped = qgsTreatments.clipRasterFromVector(self.labeled_path,self.report_layer,
            clipped_path,crop_cutline=True,nodata=self.nodata,data_type=self.label_out_type,
            context=context,feedback=step_feedback)
        # clipped = qgsTreatments.clipRasterAllTouched(self.labeled_path,self.report_layer,
            # self.input_crs,out_path=clipped_path,nodata=self.nodata,
            # data_type=self.label_out_type,resolution=self.resolution,
            # context=context,feedback=step_feedback)
        step_feedback.setCurrentStep(1)
        clip_report = qgsTreatments.getRasterUniqueValsReport(clipped,context,step_feedback)
        step_feedback.pushDebugInfo("clip_report = " + str(clip_report))
        step_feedback.setCurrentStep(2)
        if clip_flag:
            input_clipped_path = QgsProcessingUtils.generateTempFilename(
                "input_clipped_clipped" + self.curr_suffix + ".tif")
            input_clipped = qgsTreatments.clipRasterFromVector(self.input_clipped,self.report_layer,
                input_clipped_path,crop_cutline=True,data_type=0,nodata=255,
                context=context,feedback=step_feedback)
        else:
            input_clipped_path = self.input_clipped
        # input_clipped = qgsTreatments.clipRasterAllTouched(self.input_clipped,self.report_layer,
            # self.input_crs,out_path=input_clipped_path,nodata=self.nodata,
            # data_type=0,resolution=self.resolution,
            # context=context,feedback=step_feedback)
        step_feedback.setCurrentStep(3)
        input_clip_report = qgsTreatments.getRasterUniqueValsReport(
            input_clipped_path,context,step_feedback)
        step_feedback.pushDebugInfo("input_clip_report = " + str(input_clip_report))
        clip_classes, clip_array = qgsUtils.getRasterValsAndArray(str(clipped_path))
        clip_labels = [int(cl) for cl in clip_classes]
        step_feedback.setCurrentStep(4)
        if 0 in clip_labels:
            clip_labels.remove(0)
        nb_patches_clipped = len(clip_labels)
        # feedback.pushDebugInfo("nb_patches = " + str(nb_patches))
        # feedback.pushDebugInfo("nb labels = " + str(len(labels)))
        step_feedback.pushDebugInfo("nb clip labels = " + str(len(clip_labels)))
        
        # Patches length
        if clip_labels:
            patches_len2 = ndimage.labeled_comprehension(
                clip_array,clip_array,clip_labels,len,int,0)
            step_feedback.pushDebugInfo("patches_len2 = " + str(patches_len2))
            step_feedback.pushDebugInfo("nb patches_len2 = " + str(len(patches_len2)))
        step_feedback.setCurrentStep(5)
        
        sum_ai = 0
        sum_ai_sq = 0
        sum_ai_sq_cbc = 0
        for cpt, lbl in enumerate(clip_labels):
            lbl_val = int(lbl)
            cbc_len = self.patches_len[lbl_val - 1]
            patch_len = patches_len2[cpt]
            if cbc_len < patch_len:
                utils.internal_error("CBC len " + str(cbc_len)
                    + " < patch_len " + str(patch_len))
            ai = patch_len * self.pix_area
            ai_cbc = cbc_len * self.pix_area
            sum_ai_sq += ai * ai
            sum_ai_sq_cbc += ai * ai_cbc
            sum_ai += ai
        step_feedback.pushDebugInfo("sum_ai = " + str(sum_ai))
        step_feedback.pushDebugInfo("sum_ai_sq = " + str(sum_ai_sq))
        step_feedback.pushDebugInfo("sum_ai_sq_cbc = " + str(sum_ai_sq_cbc))
        step_feedback.pushDebugInfo("unit_divisor = " + str(self.unit_divisor))
        if sum_ai_sq == 0:
            step_feedback.reportError("Empty area for patches, please check your selection.")
        
        nb_pix_old = len(clip_array[clip_array != self.nodata])
        nb_pix2 = input_clip_report['TOTAL_PIXEL_COUNT']
        nb_pix_nodata2 = input_clip_report['NODATA_PIXEL_COUNT']
        nb_pix = nb_pix2 - nb_pix_nodata2
        nb_0 = len(clip_array[clip_array == 0])
        nb_not_0 = len(clip_array[clip_array != 0])
        step_feedback.pushDebugInfo("nb_pix = " + str(nb_pix))
        step_feedback.pushDebugInfo("nb_pix_old = " + str(nb_pix_old))
        step_feedback.pushDebugInfo("nb_pix2 = " + str(nb_pix2))
        step_feedback.pushDebugInfo("nb_pix_nodata2 = " + str(nb_pix_nodata2))
        step_feedback.pushDebugInfo("nb_0 = " + str(nb_0))
        step_feedback.pushDebugInfo("nb_not_0 = " + str(nb_not_0))
        tot_area = nb_pix * self.pix_area
        step_feedback.pushDebugInfo("tot_area = " + str(tot_area))
        #area_sq = math.pow(nb_pix,2)
        if nb_pix == 0:
            step_feedback.reportError("Unexpected error : empty area for input layer")
        res_dict = { self.REPORT_AREA : tot_area,
            self.SUM_AI : sum_ai,
            self.SUM_AI_SQ : sum_ai_sq,
            self.SUM_AI_SQ_CBC : sum_ai_sq_cbc,
            self.NB_PATCHES : nb_patches_clipped,
            self.DIVISOR : self.unit_divisor,
        }
        res = self.mkOutputs(parameters,res_dict,context)
        step_feedback.setCurrentStep(6)
        return res
        
        
    def processAlgorithm(self, parameters, context, feedback):        
        # Retrieve the values of the parameters entered by the user
        input, output = self.prepareInputs(parameters,context,feedback)
        init_layer = self.report_layer
        # Processing
        input_dpr = input.dataProvider()
        nodata = self.nodata
        # inputFilename = input.source()
        inputFilename = self.input_clipped
        pix_area = self.pix_area
        feedback.pushDebugInfo("nodata = " + str(nodata))
        # Export label
        feedback.pushDebugInfo("input = " + str(inputFilename))
        labeled_array, nb_patches, patches_len, nb_pix = self.labelAndPatchLen(inputFilename,feedback)
        self.patches_len = patches_len
        max_label = nb_patches + 1
        labels = list(range(1,max_label))
        label_out_type, label_nodata = self.getGDALTypeAndND(max_label)
        self.label_out_type = label_out_type
        self.nodata = label_nodata
        labeled_path = QgsProcessingUtils.generateTempFilename("labeled.tif")
        self.labeled_path = labeled_path
        # if math.isnan(nodata):
            # out_nodata = -1
            # out_type = 6
        # else:
            # out_nodata = nodata
            # out_type = 0
        out_nodata = -1
        # type = 0 <=> input data type
        # type = 6 <=> Int32
        out_type = 6
        qgsUtils.exportRaster(labeled_array,inputFilename,labeled_path,
            nodata=label_nodata,type=label_out_type)
        
        output_layer = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        feedback.pushDebugInfo("report_layer = " + str(self.report_layer))
        nb_feats = self.report_layer.featureCount()
        crs = self.report_layer.sourceCrs()
        # TODO : reproject
        feedback.pushDebugInfo("nb_feats = " + str(nb_feats))
        if nb_feats == 0:
            raise QgsProcessingException("Empty reporting layer")
        multi_feedback = feedbacks.ProgressMultiStepFeedback(nb_feats + 1, feedback)
        report_layers = []
        params_copy = dict(parameters)
        # Feats
        if nb_feats > 1:
            for count, report_feat in enumerate(self.report_layer.getFeatures()):
                multi_feedback.setCurrentStep(count)
                report_id = report_feat.id()
                init_layer.selectByIds([report_id])
                select_path = params.mkTmpLayerPath("reportingFeature"
                    + str(report_id) + ".gpkg")
                qgsTreatments.saveSelectedFeatures(init_layer,select_path,context,multi_feedback)
                report_computed_path = params.mkTmpLayerPath("reportingComputed"
                    + str(report_id) + ".gpkg")
                params_copy[self.OUTPUT] = report_computed_path
                self.report_layer = qgsUtils.loadVectorLayer(select_path)
                feedback.pushDebugInfo("report_layer = " + str(self.report_layer.sourceName()))
                self.curr_suffix = str(report_id)
                report_feat_res_layer, global_val = self.computeFeature(
                    params_copy,context,multi_feedback)
                self.curr_suffix = ""
                # parameters = { self.INPUT : input,
                    # self.CLASS : self.cl,
                    # self.REPORTING : select_path,
                    # self.UNIT : parameters[self.UNIT],
                    # self.OUTPUT : report_computed_path }
                # qgsTreatments.applyProcessingAlg('FragScape','meffRaster',
                    # parameters, context,multi_feedback)
                report_layers.append(report_feat_res_layer)
            feedback.pushDebugInfo("report_layers = " + str(report_layers))
            qgsTreatments.mergeVectorLayers(report_layers,crs,output_layer)
        # Global
        dissolved_path = params.mkTmpLayerPath('reportingDissolved.gpkg')
        qgsTreatments.dissolveLayer(init_layer,dissolved_path,context,feedback)
        self.report_layer = qgsUtils.loadVectorLayer(dissolved_path)
        if nb_feats == 1:
            params_copy[self.OUTPUT] = output_layer
        else:
            global_out_path = params.mkTmpLayerPath('reportingResultsGlobalCBC.gpkg')
            params_copy[self.OUTPUT] = global_out_path
        global_layer, global_val = self.computeFeature(
            params_copy,context,feedback,clip_flag=False)
        
        # if nb_feats > 1:
            # out_layer = output_layer
        # else:
            # out_layer = global_layer
        # Global (dissolve)
        # if nb_feats > 1:
            # dissolved_path = params.mkTmpLayerPath('reportingDissolved.gpkg')
            # qgsTreatments.dissolveLayer(init_layer,dissolved_path,context,feedback)
            # self.report_layer = qgsUtils.loadVectorLayer(dissolved_path)
            # global_out_path = params.mkTmpLayerPath('reportingResultsGlobalCBC.gpkg')
            # params_copy[self.OUTPUT] = global_out_path
            # global_layer, global_val = self.computeFeature(
                # params_copy,context,feedback,clip_flag=False)
        return {self.OUTPUT : output_layer, self.OUTPUT_VAL : global_val}

    
    
            
