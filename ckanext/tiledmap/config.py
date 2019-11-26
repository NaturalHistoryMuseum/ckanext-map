#!/usr/bin/env python
# encoding: utf-8
#
# This file is part of ckanext-map
# Created by the Natural History Museum in London, UK

config = {
    # Information about the base layer used for the maps.
    # We don't want to let users define this per dataset, as we need to ensure we have
    #  the right to use the tiles.
    u'tiledmap.tile_layer.url': u'http://{s}.tiles.mapbox.com/v4/mapbox.streets/'
                                u'{z}/{x}/{y}@2x.png?access_token='
                                u'pk.eyJ1IjoibmhtIiwiYSI6ImNpcjU5a3VuNDAwMDNpYm5vY251MW5'
                                u'oNTIifQ.JuGQ2xZ66FKOAOhYl2HdWQ',
    u'tiledmap.tile_layer.opacity': u'0.8',

    # Max/min zoom constraints
    u'tiledmap.zoom_bounds.min': u'3',
    u'tiledmap.zoom_bounds.max': u'18',

    # The tiled map autozooms to the dataset's features. The autozoom can be
    # constrained here to avoid too little or too much context.
    # TODO: Configure this per dataset?
    u'tiledmap.initial_zoom.min': u'3',
    u'tiledmap.initial_zoom.max': u'6',

    # The style parameters for the plot map. The colors can be defined per dataset (
    # with the defaults provided in the main config if present, or here otherwise),
    # but the marker size and resolution can only be set in the main config (if
    # present, or here otherwise) as they have a notable performance impact on larger
    # datasets.
    u'tiledmap.style.plot.fill_color': u'#EE0000',
    u'tiledmap.style.plot.line_color': u'#FFFFFF',
    u'tiledmap.style.plot.marker_size': u'8',
    u'tiledmap.style.plot.grid_resolution': u'4',

    # The style parameters for the grid map. The base color can be defined per dataset
    #  (with the defaults provided in the main config if present, or here otherwise),
    # but the marker size and grid resolution can only be set in the main config (if
    # present, or here otherwise) as they have a notable performance impact on larger
    # datasets.
    u'tiledmap.style.gridded.base_color': u'#F02323',
    u'tiledmap.style.gridded.marker_size': u'8',
    u'tiledmap.style.gridded.grid_resolution': u'8',

    # The style parameters for the heatmap. The intensity can be defined per dataset (
    # with the default provided in the main config if present, or here otherwise),
    # but the marker url and marker size can only be set in the main config (if
    # present, or here otherwise) as they have a notable performance impact on larger
    # datasets.
    u'tiledmap.style.heatmap.intensity': u'0.1',
    u'tiledmap.style.heatmap.gradient': u'#0000FF, #00FFFF, #00FF00, #FFFF00, #FFA500, '
                                        u'#FF0000',
    u'tiledmap.style.heatmap.marker_url': u'!markers!/alpharadiantdeg20px.png',
    u'tiledmap.style.heatmap.marker_size': u'20',

    # Templates used for hover and click information on the map.
    u'tiledmap.info_template': u'point_detail',
    u'tiledmap.quick_info_template': u'point_detail_hover'
    }
