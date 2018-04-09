#!/usr/bin/env python
# encoding: utf-8
#
# This file is part of ckanext-map
# Created by the Natural History Museum in London, UK

import json
import urllib

from ckanext.tiledmap.config import config
from ckanext.tiledmap.db import _get_engine

from ckan.lib.render import find_template
from ckan.plugins import toolkit


class MapController(toolkit.BaseController):
    '''Controller for getting map setting and information.
    
    This is implemented as a controller (rather than providing the data directly
    to the javascript module) because the map will generate new queries without
    page reloads.
    
    The map setting and information is available at `/map-info`.
    This request expects a 'resource_id' parameter, and accepts `filters` and
    `q` formatted as per resource view URLs.
    
    See ckanext.tiledmap.config for configuration options.


    '''

    def __before__(self, action, **params):
        '''Setup the request

        This will trigger a 400 error if the resource_id parameter is missing.
        '''
        # Run super
        super(MapController, self).__before__(action, **params)

        # Get request resource_id
        if not toolkit.request.params.get(u'resource_id'):
            toolkit.abort(400, toolkit._(u'Missing resource id'))

        self.resource_id = toolkit.request.params.get(u'resource_id')

        try:
            resource_show = toolkit.get_action(u'resource_show')
            self.resource = resource_show(None, {
                u'id': self.resource_id
                })
        except toolkit.ObjectNotFound:
            toolkit.abort(404, toolkit._(u'Resource not found'))
        except toolkit.NotAuthorized:
            toolkit.abort(401, toolkit._(u'Unauthorized to read resources'))
        resource_view_show = toolkit.get_action(u'resource_view_show')
        self.view_id = toolkit.request.params.get(u'view_id')
        self.view = resource_view_show(None, {
            u'id': self.view_id
            })

        # Read resource-dependent parameters
        self.info_title = self.view[u'utf_grid_title']
        try:
            self.info_fields = self.view[u'utf_grid_fields']
            if not isinstance(self.info_fields, list):
                self.info_fields = [self.info_fields]
        except KeyError:
            self.info_fields = []
        self.info_template = config[u'tiledmap.info_template']
        self.quick_info_template = config[u'tiledmap.quick_info_template']
        self.repeat_map = self.view[u'repeat_map']

        # Fields that need to be added to the query. Note that postgres query fails
        # with duplicate names
        self.query_fields = set(self.info_fields).union(set([self.info_title]))

    def map_info(self):
        '''Controller action that returns metadata about a given map.
        
        As a side effect this will set the content type to application/json


        :returns: A JSON encoded string representing the metadata

        '''
        # Specific parameters
        fetch_id = toolkit.request.params.get(u'fetch_id')
        tile_url_base = u'http://{host}:{port}/database/{database}/table/{table}'.format(
            host=config[u'tiledmap.windshaft.host'],
            port=config[u'tiledmap.windshaft.port'],
            database=_get_engine().url.database,
            table=self.resource_id
            )

        ## Ensure we have at least one map style
        if not self.view[u'enable_plot_map'] and not self.view[
            u'enable_grid_map'] and not self.view[u'enable_heat_map']:
            return json.dumps({
                u'geospatial': False,
                u'fetch_id': fetch_id
                })

        # Prepare result
        quick_info_template_name = u'{base}.{format}.mustache'.format(
            base=self.quick_info_template,
            format=str(self.resource[u'format']).lower()
            )
        if not find_template(quick_info_template_name):
            quick_info_template_name = self.quick_info_template + u'.mustache'
        info_template_name = u'{base}.{format}.mustache'.format(
            base=self.info_template,
            format=str(self.resource[u'format']).lower()
            )
        if not find_template(info_template_name):
            info_template_name = self.info_template + u'.mustache'

        quick_info_template = toolkit.render(quick_info_template_name, {
            u'title': self.info_title,
            u'fields': self.info_fields
            })
        info_template = toolkit.render(info_template_name, {
            u'title': self.info_title,
            u'fields': self.info_fields,
            u'overlapping_records_view': self.view[u'overlapping_records_view']
            })
        result = {
            u'geospatial': True,
            u'geom_count': 0,
            u'total_count': 0,
            u'bounds': ((83, -170), (-83, 170)),
            u'zoom_bounds': {
                u'min': int(config[u'tiledmap.zoom_bounds.min']),
                u'max': int(config[u'tiledmap.zoom_bounds.max'])
                },
            u'initial_zoom': {
                u'min': int(config[u'tiledmap.initial_zoom.min']),
                u'max': int(config[u'tiledmap.initial_zoom.max'])
                },
            u'tile_layer': {
                u'url': config[u'tiledmap.tile_layer.url'],
                u'opacity': float(config[u'tiledmap.tile_layer.opacity'])
                },
            u'repeat_map': self.repeat_map,
            u'map_styles': {
                },
            u'control_options': {
                u'fullScreen': {
                    u'position': u'topright'
                    },
                u'drawShape': {
                    u'draw': {
                        u'polyline': False,
                        u'marker': False,
                        u'circle': False,
                        u'country': True,
                        u'polygon': {
                            u'allowIntersection': False,
                            u'shapeOptions': {
                                u'stroke': True,
                                u'color': u'#F44',
                                u'weight': 5,
                                u'opacity': 0.5,
                                u'fill': True,
                                u'fillColor': u'#F44',
                                u'fillOpacity': 0.1
                                }
                            }
                        },
                    u'position': u'topleft'
                    },
                u'selectCountry': {
                    u'draw': {
                        u'fill': u'#F44',
                        u'fill-opacity': u'0.1',
                        u'stroke': u'#F44',
                        u'stroke-opacity': u'0.5'
                        }
                    },
                u'mapType': {
                    u'position': u'bottomleft'
                    },
                u'miniMap': {
                    u'position': u'bottomright',
                    u'tile_layer': {
                        u'url': config[u'tiledmap.tile_layer.url']
                        },
                    u'zoomLevelFixed': 1,
                    # 'zoomLevelOffset': -10,
                    u'toggleDisplay': True,
                    u'viewport': {
                        u'marker_zoom': 8,
                        u'rect': {
                            u'weight': 1,
                            u'color': u'#00F',
                            u'opacity': 1,
                            u'fill': False
                            },
                        u'marker': {
                            u'weight': 1,
                            u'color': u'#00F',
                            u'opacity': 1,
                            u'radius': 3,
                            u'fillColor': u'#00F',
                            u'fillOpacity': 0.2
                            }
                        }
                    }
                },
            u'plugin_options': {
                u'tooltipInfo': {
                    u'count_field': u'_tiledmap_count',
                    u'template': quick_info_template,
                    },
                u'tooltipCount': {
                    u'count_field': u'_tiledmap_count'
                    },
                u'pointInfo': {
                    u'template': info_template,
                    u'count_field': u'_tiledmap_count'
                    }
                },
            u'fetch_id': fetch_id
            }

        if self.view[u'enable_heat_map']:
            result[u'map_styles'][u'heatmap'] = {
                u'name': toolkit._(u'Heat Map'),
                u'icon': u'<i class="fa fa-fire"></i>',
                u'controls': [u'drawShape', u'mapType', u'fullScreen', u'miniMap'],
                u'has_grid': False,
                u'tile_source': {
                    u'url': tile_url_base + '/{z}/{x}/{y}.png',
                    u'params': {
                        u'intensity': config[u'tiledmap.style.heatmap.intensity'],
                        }
                    },
                }
            result[u'map_style'] = u'heatmap'

        if self.view[u'enable_grid_map']:
            result[u'map_styles'][u'gridded'] = {
                u'name': toolkit._(u'Grid Map'),
                u'icon': u'<i class="fa fa-th"></i>',
                u'controls': [u'drawShape', u'mapType', u'fullScreen', u'miniMap'],
                u'plugins': [u'tooltipCount'],
                u'has_grid': self.view[u'enable_utf_grid'],
                u'grid_resolution': int(config[u'tiledmap.style.plot.grid_resolution']),
                u'tile_source': {
                    u'url': tile_url_base + '/{z}/{x}/{y}.png',
                    u'params': {
                        u'base_color': config[u'tiledmap.style.gridded.base_color']
                        }
                    },
                u'grid_source': {
                    u'url': tile_url_base + '/{z}/{x}/{y}.grid.json',
                    u'params': {
                        u'interactivity': u','.join(self.query_fields)
                        }
                    }
                }
            result[u'map_style'] = u'gridded'

        if self.view[u'enable_plot_map']:
            result[u'map_styles'][u'plot'] = {
                u'name': toolkit._(u'Plot Map'),
                u'icon': u'<i class="fa fa-dot-circle-o"></i>',
                u'controls': [u'drawShape', u'mapType', u'fullScreen', u'miniMap'],
                u'plugins': [u'tooltipInfo', u'pointInfo'],
                u'has_grid': self.view[u'enable_utf_grid'],
                u'grid_resolution': int(config[u'tiledmap.style.plot.grid_resolution']),
                u'tile_source': {
                    u'url': tile_url_base + '/{z}/{x}/{y}.png',
                    u'params': {
                        u'fill_color': config[u'tiledmap.style.plot.fill_color'],
                        u'line_color': config[u'tiledmap.style.plot.line_color']
                        }
                    },
                u'grid_source': {
                    u'url': tile_url_base + '/{z}/{x}/{y}.grid.json',
                    u'params': {
                        u'interactivity': u','.join(self.query_fields)
                        }
                    }
                }
            result[u'map_style'] = u'plot'

        # Get query extent and count
        info = toolkit.get_action(u'datastore_query_extent')({}, {
            u'resource_id': self.resource_id,
            u'filters': self._get_request_filters(),
            u'limit': 1,
            u'q': urllib.unquote(toolkit.request.params.get(u'q', u'')),
            u'fields': u'_id'
            })
        result[u'total_count'] = info[u'total_count']
        result[u'geom_count'] = info[u'geom_count']
        if info[u'bounds']:
            result[u'bounds'] = info[u'bounds']

        toolkit.response.headers[u'Content-type'] = u'application/json'
        return json.dumps(result)

    def _get_request_filters(self):
        ''' '''
        filters = {}
        for f in urllib.unquote(toolkit.request.params.get(u'filters', u'')).split(u'|'):
            if f:
                (k, v) = f.split(u':', 1)
                if k not in filters:
                    filters[k] = []
                filters[k].append(v)
        return filters
