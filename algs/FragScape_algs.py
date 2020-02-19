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

from PyQt5.QtCore import QCoreApplication, QVariant
from qgis.core import QgsProcessing, QgsProcessingAlgorithm, QgsProcessingException
from qgis.core import (Qgis,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterExpression,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingProvider,
                       QgsProcessingParameterMultipleLayers,
                       QgsProcessingUtils,
                       QgsProcessingParameterNumber,
                       QgsProcessingParameterMatrix,
                       QgsProcessingParameterBoolean,
                       QgsProcessingParameterCrs,
                       QgsProcessingParameterVectorDestination,
                       QgsProcessingParameterFile,
                       QgsProcessingParameterString,
                       QgsProcessingParameterEnum,
                       QgsProperty,
                       QgsWkbTypes,
                       QgsCoordinateReferenceSystem,
                       QgsProcessingMultiStepFeedback)
from qgis.core import QgsField, QgsFields, QgsFeature, QgsFeatureSink

from processing.algs.gdal.rasterize import rasterize
import xml.etree.ElementTree as ET

from ..qgis_lib_mc import utils, qgsTreatments, qgsUtils, feedbacks
from ..steps import params
            
NB_DIGITS = 5
            
class FragScapeVectorAlgorithm(QgsProcessingAlgorithm):
    
    def group(self):
        return "Vector"
    
    def groupId(self):
        return "fsVect"
        
    def name(self):
        return self.ALG_NAME
        
    def createInstance(self):
        assert(False)
        
    def displayName(self):
        assert(False)
        
    def shortHelpString(self):
        assert(False)
        
    def tr(self, string):
        return QCoreApplication.translate('Processing', string)
            

class RasterizeFixAllTouch(rasterize):

    ALG_NAME = 'rasterizefixalltouch'

    def createInstance(self):
        return RasterizeFixAllTouch()
        
    def name(self):
        return self.ALG_NAME
        
    def displayName(self):
        return self.tr('Rasterize (with ALL_TOUCH fix)')
        
    def group(self):
        return "Auxiliary algorithms"
        
    def groupId(self):
        return 'aux'
        
    def shortHelpString(self):
        return self.tr('Wrapper for gdal:rasterize algorithm allowing to use ALL_TOUCH option (every pixel touching input geometry are rasterized).')

    def initAlgorithm(self, config=None):
        super().initAlgorithm(config)
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.ALL_TOUCH,
                description = 'ALL_TOUCH option',
                defaultValue=False,
                optional=True))
    
# Apply rasterization on field 'field' of vector layer 'in_path'.
# Output raster layer in 'out_path'.
# Resolution set to 25 if not given.
# Extent can be given through 'extent_path'. If not, it is extracted from input layer.
# Output raster layer is loaded in QGIS if 'load_flag' is True.
def applyRasterizationFixAllTouch(in_path,out_path,extent,resolution,
                   field=None,burn_val=None,out_type=Qgis.Float32,
                   nodata_val=qgsTreatments.nodata_val,all_touch=False,overwrite=False,
                   context=None,feedback=None):
    TYPES = ['Byte', 'Int16', 'UInt16', 'UInt32', 'Int32', 'Float32',
         'Float64', 'CInt16', 'CInt32', 'CFloat32', 'CFloat64']
    if overwrite:
        qgsUtils.removeRaster(out_path)
    extra_param_name = 'EXTRA'
    if hasattr(rasterize,extra_param_name):
        res = qgsTreatments.applyRasterization(in_path,out_path,extent,resolution,
                field,burn_val,out_type,nodata_val,all_touch,overwrite,
                context,feedback)
    else:
        parameters = { 'ALL_TOUCH' : True,
                   'BURN' : burn_val,
                   'DATA_TYPE' : out_type,
                   'EXTENT' : extent,
                   'FIELD' : field,
                   'HEIGHT' : resolution,
                   'INPUT' : in_path,
                   'NODATA' : nodata_val,
                   'OUTPUT' : out_path,
                   'UNITS' : 1, 
                   'WIDTH' : resolution }
        res = qgsTreatments.applyProcessingAlg("FragScape","rasterizefixalltouch",parameters,context,feedback)
    return res

class PrepareLanduseAlgorithm(FragScapeVectorAlgorithm):

    ALG_NAME = "prepareLanduse"

    INPUT = "INPUT"
    CLIP_LAYER = "CLIP_LAYER"
    SELECT_EXPR = "SELECT_EXPR"
    OUTPUT = "OUTPUT"
        
    def createInstance(self):
        return PrepareLanduseAlgorithm()
        
    def displayName(self):
        return self.tr("Prepare land cover data")
        
    def shortHelpString(self):
        return self.tr("This algorithms prepares land cover data by applying selection (from expression) and dissolving geometries")

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr("Input layer"),
                [QgsProcessing.TypeVectorAnyGeometry]))
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.CLIP_LAYER,
                description=self.tr("Clip layer"),
                types=[QgsProcessing.TypeVectorPolygon],
                optional=True))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SELECT_EXPR,
                self.tr("Selection expression"),
                "",
                self.INPUT))
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr("Output layer")))
                
    def processAlgorithm(self,parameters,context,feedback):
        # Dummy function to enable running an alg inside an alg
        # def no_post_process(alg, context, feedback):
            # pass
        input = self.parameterAsVectorLayer(parameters,self.INPUT,context)
        feedback.pushDebugInfo("input = " + str(input))
        if input is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))
        qgsUtils.normalizeEncoding(input)
        feedback.pushDebugInfo("input ok")
        clip_layer = self.parameterAsVectorLayer(parameters,self.CLIP_LAYER,context)
        expr = self.parameterAsExpression(parameters,self.SELECT_EXPR,context)
        if clip_layer is None:
            clipped = input
        else:
            clipped_path = params.mkTmpLayerPath('landuseClipped.gpkg')
            qgsTreatments.applyVectorClip(input,clip_layer,clipped_path,context,feedback)
            clipped = qgsUtils.loadVectorLayer(clipped_path)
            feedback.pushDebugInfo("clipped  = " + str(clipped))
        selected_path = params.mkTmpLayerPath('landuseSelection.gpkg')
        qgsTreatments.selectGeomByExpression(clipped,expr,selected_path,'landuseSelection')
        # selected = qgsUtils.loadVectorLayer(selected_path)
        # selected = qgsTreatments.extractByExpression(
           # clipped,expr,'memory:',
           # context=context,feedback=feedback)
        feedback.pushDebugInfo("selected = " + str(selected_path))
        output = parameters[self.OUTPUT]
        dissolved = qgsTreatments.dissolveLayer(selected_path,output,context=context,feedback=feedback)
        dissolved = None
        return {self.OUTPUT : dissolved}
        
        
class PrepareFragmentationAlgorithm(FragScapeVectorAlgorithm):

    ALG_NAME = "prepareFragm"

    INPUT = "INPUT"
    CLIP_LAYER = "CLIP_LAYER"
    SELECT_EXPR = "SELECT_EXPR"
    BUFFER = "BUFFER_EXPR"
    NAME = "NAME"
    OUTPUT = "OUTPUT"
        
    def createInstance(self):
        return PrepareFragmentationAlgorithm()
        
    def displayName(self):
        return self.tr("Prepare vector data")
        
    def shortHelpString(self):
        return self.tr("This algorithm prepares a vector layer by applying clip, selection and buffer")

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                description=self.tr("Input layer"),
                types=[QgsProcessing.TypeVectorLine]))
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.CLIP_LAYER,
                description=self.tr("Clip layer"),
                types=[QgsProcessing.TypeVectorPolygon],
                optional=True))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.SELECT_EXPR,
                description=self.tr("Selection expression"),
                parentLayerParameterName=self.INPUT,
                optional=True))
        self.addParameter(
            QgsProcessingParameterExpression(
                self.BUFFER,
                description=self.tr("Buffer expression"),
                parentLayerParameterName=self.INPUT,
                optional=True))
        self.addParameter(
            QgsProcessingParameterString(
                self.NAME,
                description=self.tr("Identifier"),
                optional=True))
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                description=self.tr("Output layer")))
                
    def processAlgorithm(self,parameters,context,feedback):
        # Parameters
        feedback.pushDebugInfo("parameters = " + str(parameters))
        input = self.parameterAsVectorLayer(parameters,self.INPUT,context)
        if input is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))
        qgsUtils.normalizeEncoding(input)
        clip = self.parameterAsVectorLayer(parameters,self.CLIP_LAYER,context)
        clip_flag = (clip is None)
        select_expr = self.parameterAsExpression(parameters,self.SELECT_EXPR,context)
        feedback.pushDebugInfo("select_expr : " + str(select_expr))
        buffer_expr = self.parameterAsExpression(parameters,self.BUFFER,context)
        name = self.parameterAsString(parameters,self.NAME,context)
        if not name:
            name = 'fragm'
        feedback.pushDebugInfo("buffer_expr : " + str(buffer_expr))
        if buffer_expr == "" and input.geometryType() != QgsWkbTypes.PolygonGeometry:
           feedback.pushDebugInfo("Empty buffer with non-polygon layer")
        output = parameters[self.OUTPUT]
        if clip is None:
            clipped = input
        else:
            clipped_path = params.mkTmpLayerPath(name + 'Clipped.gpkg')
            qgsTreatments.applyVectorClip(input,clip,clipped_path,context,feedback)
            clipped = qgsUtils.loadVectorLayer(clipped_path)
        if select_expr == "":
            selected = clipped
        else:
            selected_path = params.mkTmpLayerPath(name + 'Selected.gpkg')
            qgsTreatments.selectGeomByExpression(clipped,select_expr,selected_path,name)
            selected = selected_path
        if buffer_expr == "":
            buffered = selected
        else:
            buffer_expr_prep = QgsProperty.fromExpression(buffer_expr)
            buffered = qgsTreatments.applyBufferFromExpr(selected,buffer_expr_prep,output,context,feedback)
        if buffered == input:
            buffered = qgsUtils.pathOfLayer(buffered)
        return {self.OUTPUT : buffered}
        

        
class ApplyFragmentationAlgorithm(FragScapeVectorAlgorithm):

    ALG_NAME = "applyFragm"

    LANDUSE = "LANDUSE"
    FRAGMENTATION = "FRAGMENTATION"
    CRS = "CRS"
    OUTPUT = "OUTPUT"
        
    def createInstance(self):
        return ApplyFragmentationAlgorithm()
        
    def displayName(self):
        return self.tr("Integrates vector data to land cover")
        
    def shortHelpString(self):
        return self.tr("This algorithm builds a layer of patches from a land cover layer and fragmentation layers. Overlaying geometries are removed and remaining ones are cast to single geometry type.")

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.LANDUSE,
                self.tr("Land cover layer"),
                [QgsProcessing.TypeVectorPolygon]))
        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                self.FRAGMENTATION,
                self.tr("Fragmentation layers"),
                QgsProcessing.TypeVectorPolygon))
        self.addParameter(
            QgsProcessingParameterCrs(
                self.CRS,
                description=self.tr("Output CRS"),
                defaultValue=params.defaultCrs))
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr("Output layer")))
                
    def processAlgorithm(self,parameters,context,feedback):
        # Parameters
        landuse = self.parameterAsVectorLayer(parameters,self.LANDUSE,context)
        if landuse is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.LANDUSE))
        qgsUtils.normalizeEncoding(landuse)
        fragm_layers = self.parameterAsLayerList(parameters,self.FRAGMENTATION,context)
        output = self.parameterAsOutputLayer(parameters,self.OUTPUT,context)
        crs = self.parameterAsCrs(parameters,self.CRS,context)
        # output = parameters[self.OUTPUT]
        # Merge fragmentation layers
        fragm_path = params.mkTmpLayerPath("fragm.gpkg")
        fragm_layer = qgsTreatments.mergeVectorLayers(fragm_layers,crs,fragm_path)
        feedback.pushDebugInfo("fragm_layer = " + str(fragm_layer))
        if fragm_layer is None:
            raise QgsProcessingException("Fragmentation layers merge failed")
        # Apply difference
        diff_path = params.mkTmpLayerPath("diff.gpkg")
        diff_layer = qgsTreatments.applyDifference(
            landuse,fragm_layer,diff_path,
            context=context,feedback=feedback)
        if fragm_layer is None:
            raise QgsProcessingException("Difference landuse/fragmentation failed")
        # Multi to single part
        singleGeomLayer = qgsTreatments.multiToSingleGeom(
            diff_layer,output,
            context=context,feedback=feedback)
        if fragm_layer is None:
            raise QgsProcessingException("Multi to single part failed")
        return {self.OUTPUT : singleGeomLayer}
        
 
class MeffAlgUtils:

    NB_DIGITS = 5
    
    INPUT = "INPUT"
    REPORTING = "REPORTING"
    CLASS = "CLASS"
    CRS = "CRS"
    INCLUDE_CBC = "INCLUDE_CBC"
    UNIT = "UNIT"
    OUTPUT = "OUTPUT"
    OUTPUT_VAL = "OUTPUT_VAL"
    
    SUM_AI = "sum_ai"
    SUM_AI_SQ = "sum_ai_sq"
    SUM_AI_SQ_CBC = "sum_ai_sq_cbc"
    DIVISOR = "divisor"

    # Output layer fields
    ID = "fid"
    NB_PATCHES = "nb_patches"
    REPORT_AREA = "report_area"
    INTERSECTING_AREA = "intersecting_area"
    # Main measures
    MESH_SIZE = "effective_mesh_size"
    CBC_MESH_SIZE = "CBC_effective_mesh_size"
    DIVI = "landscape_division"
    SPLITTING_INDEX = "splitting_index"
    # Auxiliary measures
    COHERENCE = "coherence"
    SPLITTING_DENSITY = "splitting_density"
    NET_PRODUCT = "net_product"
    CBC_NET_PRODUCT = "CBC_net_product"
    
    UNIT_DIVISOR = [1, 100, 10000, 1000000]
    
    DEFAULT_CRS = QgsCoordinateReferenceSystem("epsg:2154")
    
    def getUnitOptions(self):
        return [self.tr("m² (square meters)"),
            self.tr("dm² (square decimeters / ares)"),
            self.tr("hm² (square hectometers / hectares)"),
            self.tr("km² (square kilometers)")]
            
    def mkReportFields(self,include_cbc=False):
        report_id_field = QgsField(self.ID, QVariant.Int)
        mesh_size_field = QgsField(self.MESH_SIZE, QVariant.Double)
        nb_patches_field = QgsField(self.NB_PATCHES, QVariant.Int)
        report_area_field = QgsField(self.REPORT_AREA, QVariant.Double)
        intersecting_area_field = QgsField(self.INTERSECTING_AREA, QVariant.Double)
        div_field = QgsField(self.DIVI, QVariant.Double)
        split_index_field = QgsField(self.SPLITTING_INDEX, QVariant.Double)
        coherence_field = QgsField(self.COHERENCE, QVariant.Double)
        split_density_field = QgsField(self.SPLITTING_DENSITY, QVariant.Double)
        net_product_field = QgsField(self.NET_PRODUCT, QVariant.Double)
        unit_divisor_field = QgsField(self.DIVISOR, QVariant.Int)
        if include_cbc:
            cbc_mesh_size_field = QgsField(self.CBC_MESH_SIZE, QVariant.Double)
            cbc_net_product_field = QgsField(self.CBC_NET_PRODUCT, QVariant.Double)
        output_fields = QgsFields()
        output_fields.append(report_id_field)
        if include_cbc:
            output_fields.append(cbc_mesh_size_field)
        output_fields.append(mesh_size_field)
        output_fields.append(nb_patches_field)
        output_fields.append(report_area_field)
        output_fields.append(intersecting_area_field)
        output_fields.append(div_field)
        output_fields.append(split_index_field)
        output_fields.append(coherence_field)
        output_fields.append(split_density_field)
        output_fields.append(net_product_field)
        if include_cbc:
            output_fields.append(cbc_net_product_field)
        output_fields.append(unit_divisor_field)
        return output_fields
                
    def mkResFeat(self,include_cbc):
        if not self.report_layer or self.report_layer.featureCount() == 0:
            raise QgsProcessingException("Invalid reporting layer")
        for f in self.report_layer.getFeatures():
            report_feat = f
        output_fields = self.mkReportFields(include_cbc)
        res_feat = QgsFeature(output_fields)
        res_feat.setGeometry(report_feat.geometry())
        res_feat[self.ID] = report_feat.id()
        return res_feat
        
    def fillResFeat(self,res_feat,res_dict):
        divisor = float(res_dict[self.DIVISOR])
        report_area = float(res_dict[self.REPORT_AREA]) / divisor
        report_area_sq = report_area * report_area
        sum_ai = float(res_dict[self.SUM_AI])  / divisor
        sum_ai_sq = float(res_dict[self.SUM_AI_SQ]) / (divisor * divisor)
        utils.debug("divisor = " + str(divisor))
        utils.debug("sum_ai = " + str(sum_ai))
        utils.debug("sum_ai_sq = " + str(sum_ai_sq))
        utils.debug("report_area = " + str(report_area))
        utils.debug("report_area_sq = " + str(report_area_sq))
        res_feat[self.NB_PATCHES] = res_dict[self.NB_PATCHES]
        # Metrics
        res_feat[self.NET_PRODUCT] = round(sum_ai_sq,NB_DIGITS)
        res_feat[self.REPORT_AREA] = report_area
        res_feat[self.INTERSECTING_AREA] = sum_ai
        res_feat[self.COHERENCE] = sum_ai_sq / report_area_sq if report_area_sq > 0 else 0
        res_feat[self.SPLITTING_DENSITY] = report_area / sum_ai if sum_ai > 0 else 0
        res_feat[self.MESH_SIZE] = round(sum_ai_sq / report_area, NB_DIGITS) if report_area > 0 else 0
        res_feat[self.SPLITTING_INDEX] = report_area_sq / sum_ai_sq if sum_ai_sq > 0 else 0
        res_feat[self.DIVI] = 1 - res_feat[self.COHERENCE]
        res_feat[self.DIVISOR] = divisor
        # CBC Metrics
        if self.SUM_AI_SQ_CBC in res_dict:
            sum_ai_sq_cbc = float(res_dict[self.SUM_AI_SQ_CBC]) / (divisor * divisor)
            res_feat[self.CBC_NET_PRODUCT] = round(sum_ai_sq_cbc,NB_DIGITS)
            res_feat[self.CBC_MESH_SIZE] = round(sum_ai_sq_cbc / report_area,NB_DIGITS) if report_area > 0 else 0
            
        
    def mkResSink(self,parameters,res_feat,context,include_cbc=False):
        report_fields = self.mkReportFields(include_cbc)
        wkb_type = self.report_layer.wkbType()
        report_crs = self.report_layer.sourceCrs()
        sink, dest_id = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            report_fields,
            wkb_type,
            report_crs)
        sink.addFeature(res_feat)
        return dest_id
        
    def mkOutputs(self,parameters,res_dict,context):
        if self.report_layer:
            nb_feats = self.report_layer.featureCount()
            if nb_feats != 1:
                raise QgsProcessingException("Report layer has "
                    + str(nb_feats) + " features but only 1 was expected")
            include_cbc = self.SUM_AI_SQ_CBC in res_dict
            utils.debug("include_cbc = " + str(include_cbc))
            res_feat = self.mkResFeat(include_cbc)
            self.fillResFeat(res_feat,res_dict)
            dest_id = self.mkResSink(parameters,res_feat,context,include_cbc)
            res_layer = dest_id
            if include_cbc:
                res_val = res_feat[self.CBC_MESH_SIZE] / res_dict[self.DIVISOR]
            else:
                res_val = res_feat[self.MESH_SIZE] / res_dict[self.DIVISOR]
        else:
            res_layer = None
            if res_dict[self.REPORT_AREA] > 0:
                res_val = (res_dict[self.SUM_AI_SQ] / res_dict[self.REPORT_AREA]) / res_dict[self.DIVISOR]
            else:
                res_val = 0
        res_val = round(res_val, self.NB_DIGITS)
        return (res_layer, res_val)
    
    def tr(self, string):
        return QCoreApplication.translate('Processing', string)
        
    def name(self):
        return self.ALG_NAME


class ResultsDiffAlgorithm(MeffAlgUtils,QgsProcessingAlgorithm):

    ALG_NAME = 'diffResults'
    
    LAYER_A = "LAYER_A"
    LAYER_B = "LAYER_B"
    
    PREFIX = "B_"

    def createInstance(self):
        return ResultsDiffAlgorithm()
        
    def name(self):
        return self.ALG_NAME
        
    def displayName(self):
        return self.tr('Compare results layer')
        
    def shortHelpString(self):
        msg = "Compare 2 results layers produced by FragScape (step 4)"
        msg += " by applying difference between indicators values (layer_b - layer_a)"
        return self.tr(msg)
        
    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.LAYER_A,
                self.tr("Layer A"),
                [QgsProcessing.TypeVectorPolygon]))
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.LAYER_B,
                self.tr("Layer B"),
                [QgsProcessing.TypeVectorPolygon]))
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr("Output layer")))
                
    def processAlgorithm(self,parameters,context,feedback):
        layer_a = self.parameterAsVectorLayer(parameters,self.LAYER_A,context)
        layer_b = self.parameterAsVectorLayer(parameters,self.LAYER_B,context)
        if layer_a is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.LAYER_A))
        if layer_b is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.LAYER_B))
        a_crs, b_crs = layer_a.sourceCrs(), layer_b.sourceCrs()
        if a_crs.authid() != b_crs.authid():
            raise QgsProcessingException("Different CRS for layers (" +
                str(a_crs) + " vs " + str(b_crs))
        nb_feats_a, nb_feats_b = layer_a.featureCount(), layer_b.featureCount()
        if nb_feats_a != nb_feats_b:
            raise QgsProcessingException("Layers do not have same number of features (" + str(nb_feats_a) + " vs " + str(nb_feats_b) + ")")
        a_fields, b_fields = layer_a.fields().names(), layer_b.fields().names()
        include_cbc_a = self.CBC_MESH_SIZE in a_fields
        include_cbc_b = self.CBC_MESH_SIZE in b_fields
        include_cbc = include_cbc_a and include_cbc_b
        # Fields
        if self.DIVISOR not in a_fields or self.DIVISOR not in b_fields:
            raise QgsProcessingException("Missing field 'divisor'")
        qgs_fields = self.mkReportFields(include_cbc=include_cbc)
        fields_names = [f.name() for f in qgs_fields]
        diff_fields = [self.NB_PATCHES, self.DIVI,
            self.SPLITTING_INDEX,self.COHERENCE,self.SPLITTING_DENSITY]
        diff_fields_divisor = [self.MESH_SIZE, self.REPORT_AREA, 
            self.INTERSECTING_AREA, self.NET_PRODUCT]
        diff_fields_divisor_sq = [self.NET_PRODUCT]
        same_fields = [self.ID]
        if include_cbc:
            diff_fields_divisor.append(self.CBC_MESH_SIZE)
            diff_fields_divisor_sq.append(self.CBC_NET_PRODUCT)
        # Join layers A and B
        predicates = [2] # 2 <=> join on equal geometries
        joined_path = QgsProcessingUtils.generateTempFilename("joined.gpkg")
        joined = qgsTreatments.joinByLoc(layer_a,layer_b,predicates=predicates,
            out_path=joined_path,fields=fields_names,prefix=self.PREFIX,
            context=context,feedback=feedback)
        joined_layer = qgsUtils.loadVectorLayer(joined_path)
        if nb_feats_a != joined_layer.featureCount():
            raise QgsProcessingException("Join by location failed, geometries do not match exactly")
        # Output computation
        wkb_type = layer_a.wkbType()
        sink, dest_id = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            qgs_fields,
            wkb_type,
            a_crs)
        for feat in joined_layer.getFeatures():
            # new_feat = QgsFeature(fields)
            new_feat = QgsFeature(qgs_fields)
            new_feat.setGeometry(feat.geometry())
            for fname in same_fields:
                new_feat[fname] = feat[fname]
            for fname in diff_fields:
                a_val, b_val = feat[fname], feat[self.PREFIX + fname]
                new_feat[fname] = b_val - a_val
            for fname in diff_fields_divisor + diff_fields_divisor_sq:
                if self.DIVISOR in a_fields and self.DIVISOR in b_fields:
                    a_divi = feat[self.DIVISOR]
                    b_divi = feat[self.PREFIX + self.DIVISOR]
                else:
                    a_divi = 1
                    b_divi = 1
                a_val, b_val = feat[fname], feat[self.PREFIX + fname]
                # a_divi_sq, b_divi_sq = a_divi * a_divi, b_divi * b_divi
                factor = a_divi / b_divi
                if fname in diff_fields_divisor_sq:
                    factor = factor * factor
                factor_sq = factor * factor
                if a_divi == b_divi:
                    feedback.pushDebugInfo("a_divi == b_divi")
                    new_feat[fname] = b_val - a_val
                    new_feat[self.DIVISOR] = a_divi
                elif a_divi < b_divi:
                    # a_val_round = round(a_val / (b_divi / a_divi), self.NB_DIGITS)
                    a_val_round = round(a_val * factor, self.NB_DIGITS)
                    feedback.pushDebugInfo("a_val_round = " + str(a_val_round))
                    new_feat[fname] = b_val - a_val_round
                    new_feat[self.DIVISOR] = b_divi
                else:
                    # b_val_round = round(b_val / (a_divi / b_divi), self.NB_DIGITS)
                    b_val_round = round(b_val / factor, self.NB_DIGITS)
                    feedback.pushDebugInfo("b_val_round = " + str(b_val_round))
                    new_feat[fname] = b_val_round - a_val
                    new_feat[self.DIVISOR] = a_divi
            sink.addFeature(new_feat)
        return { self.OUTPUT : dest_id }
        
                
class FragScapeMeffVectorAlgorithm(FragScapeVectorAlgorithm,MeffAlgUtils):
    
    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr("Input layer"),
                [QgsProcessing.TypeVectorPolygon]))
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.REPORTING,
                self.tr("Reporting layer"),
                [QgsProcessing.TypeVectorPolygon]))
        self.addParameter(
            QgsProcessingParameterCrs(
                self.CRS,
                description=self.tr("Output CRS"),
                defaultValue=params.defaultCrs))
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.INCLUDE_CBC,
                self.tr("Include Cross-boundary connection metrics")))
        self.addParameter(
            QgsProcessingParameterEnum(
                self.UNIT,
                description=self.tr("Report areas unit"),
                options=self.getUnitOptions()))
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr("Output layer")))
                
    def prepareInputs(self,parameters,context,feedback):
        input = self.parameterAsVectorLayer(parameters, self.INPUT, context)
        report_layer = self.parameterAsVectorLayer(parameters,self.REPORTING,context)
        if input is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))
        reporting = self.parameterAsVectorLayer(parameters,self.REPORTING,context)
        if reporting is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.REPORTING))
        self.report_layer = reporting
        self.crs = self.parameterAsCrs(parameters,self.CRS,context)
        unit = self.parameterAsEnum(parameters,self.UNIT,context)
        self.include_cbc = self.parameterAsBool(parameters,self.INCLUDE_CBC,context)
        self.unit_divisor = self.UNIT_DIVISOR[unit]
        return (input, reporting)


class MeffVectorGlobal(FragScapeMeffVectorAlgorithm):

    ALG_NAME = "meffVectorGlobal"
    
    # OUTPUT_GLOBAL_MEFF = "GLOBAL_MEFF"
        
    def createInstance(self):
        return MeffVectorGlobal()
        
    def displayName(self):
        return self.tr("Vector Effective Mesh Size (Global)")
        
    def shortHelpString(self):
        return self.tr("Computes effective mesh size from patch layer and boundary of reporting layer (features are dissolved if needed)")
                
    def processAlgorithm(self,parameters,context,feedback):
        feedback.pushDebugInfo("Start " + str(self.name()))
        # Parameters
        source, boundary = self.prepareInputs(parameters, context, feedback)
        # CRS reprojection
        source_crs = source.crs().authid()
        boundary_crs = boundary.crs().authid()
        feedback.pushDebugInfo("source_crs = " + str(source_crs))
        feedback.pushDebugInfo("boundary_crs = " + str(boundary_crs))
        feedback.pushDebugInfo("crs = " + str(self.crs.authid()))
        source_name = boundary.sourceName()
        if source_crs != self.crs.authid():
            source_path = params.mkTmpLayerPath(source_name + "_source_reproject.gpkg")
            qgsTreatments.applyReprojectLayer(source,self.crs,source_path,context,feedback)
            source = qgsUtils.loadVectorLayer(source_path)
        if boundary_crs != self.crs.authid():
            boundary_path = params.mkTmpLayerPath(source_name + "_boundary_reproject.gpkg")
            qgsTreatments.applyReprojectLayer(boundary,self.crs,boundary_path,context,feedback)
            boundary = qgsUtils.loadVectorLayer(boundary_path)
        # Clip by boundary
        intersected_path = params.mkTmpLayerPath(source_name + "_source_intersected.gpkg")
        qgsTreatments.selectIntersection(source,boundary,context,feedback)
        qgsTreatments.saveSelectedFeatures(source,intersected_path,context,feedback)
        selected_path = intersected_path
        source = qgsUtils.loadVectorLayer(selected_path)
        # Dissolve
        if boundary.featureCount() > 1:
            dissolved_path = params.mkTmpLayerPath(source_name + "_boundary_dissolved.gpkg")
            qgsTreatments.dissolveLayer(boundary,dissolved_path,context,feedback)
            boundary = qgsUtils.loadVectorLayer(dissolved_path)
            self.report_layer = boundary
        # Algorithm
        # progress step
        nb_feats = source.featureCount()
        feedback.pushDebugInfo("nb_feats = " + str(nb_feats))
        if nb_feats == 0:
            utils.warn("Empty input layer : " + qgsUtils.pathOfLayer(source))
            progress_step = 100.0
            #raise QgsProcessingException("Empty layer : " + qgsUtils.pathOfLayer(source))
        else:
            progress_step = 100.0 / nb_feats
        curr_step = 0
        # Reporting area
        for report_feat in boundary.getFeatures():
            report_geom = report_feat.geometry()
        report_area = report_geom.area()
        sum_ai = 0
        feedback.pushDebugInfo("report_area = " + str(report_area))
        if report_area == 0:
            raise QgsProcessingException("Empty reporting area")
        else:
            feedback.pushDebugInfo("ok")
        net_product = 0
        cbc_net_product = 0
        intersecting_area = 0
        for f in source.getFeatures():
            f_geom = f.geometry()
            f_area = f_geom.area()
            sum_ai += f_area
            intersection = f_geom.intersection(report_geom)
            intersection_area = intersection.area()
            intersecting_area += intersection_area
            net_product += intersection_area * intersection_area
            cbc_net_product += f_area * intersection_area
            # Progress update
            curr_step += 1
            feedback.setProgress(int(curr_step * progress_step))
        report_area_sq = report_area * report_area
        # Outputs
        res_dict = { self.REPORT_AREA : report_area,
            self.SUM_AI : sum_ai,
            self.SUM_AI_SQ : net_product,
            self.NB_PATCHES : nb_feats,
            self.DIVISOR : self.unit_divisor,
        }
        if self.include_cbc:
            res_dict[self.SUM_AI_SQ_CBC] = cbc_net_product
        res_layer, res_val = self.mkOutputs(parameters,res_dict,context)
        return {self.OUTPUT: res_layer, self.OUTPUT_VAL : res_val}

   

class MeffVectorReport(FragScapeMeffVectorAlgorithm):

    ALG_NAME = "meffVectorReport"
        
    def createInstance(self):
        return MeffVectorReport()
        
    def displayName(self):
        return self.tr("Vector Effective Mesh Size per feature")
        
    def shortHelpString(self):
        return self.tr("Computes effective mesh size from patch layer for each feature of reporting layer.")
                
    def processAlgorithm(self,parameters,context,feedback):
        source, reporting = self.prepareInputs(parameters, context, feedback)
        output = parameters[self.OUTPUT]
        # Algorithm
        # progress step
        nb_feats = reporting.featureCount()
        feedback.pushDebugInfo("nb_feats = " + str(nb_feats))
        if nb_feats == 0:
            raise QgsProcessingException("Empty layer")
        curr_step = 0
        # gna gna
        multi_feedback = feedbacks.ProgressMultiStepFeedback(nb_feats, feedback)
        report_layers = []
        for count, report_feat in enumerate(reporting.getFeatures()):
            multi_feedback.setCurrentStep(count)
            report_id = report_feat.id()
            reporting.selectByIds([report_id])
            select_path = params.mkTmpLayerPath("reportingSelection" + str(report_feat.id()) + ".gpkg")
            qgsTreatments.saveSelectedFeatures(reporting,select_path,context,multi_feedback)
            report_computed_path = params.mkTmpLayerPath("reportingComputed" + str(report_feat.id()) + ".gpkg")
            parameters = { MeffVectorGlobal.INPUT : source,
                           MeffVectorGlobal.REPORTING : select_path,
                           MeffVectorGlobal.CRS : self.crs,
                           MeffVectorGlobal.INCLUDE_CBC : self.include_cbc,
                           MeffVectorGlobal.UNIT : parameters[self.UNIT],
                           MeffVectorGlobal.OUTPUT : report_computed_path }
            qgsTreatments.applyProcessingAlg('FragScape',
                                             MeffVectorGlobal.ALG_NAME,
                                             parameters,context,multi_feedback)
            report_layers.append(report_computed_path)
        qgsTreatments.mergeVectorLayers(report_layers,self.crs,output)
        return {self.OUTPUT: output}

