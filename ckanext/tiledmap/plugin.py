#!/usr/bin/env python
# encoding: utf-8
#
# This file is part of ckanext-map
# Created by the Natural History Museum in London, UK

import re
from sqlalchemy.sql import select
from sqlalchemy import Table, Column, MetaData, Numeric
from sqlalchemy.exc import DataError
from sqlalchemy import func, or_, not_, cast
import ckan.plugins as p
from ckan.common import json
import ckan.plugins.toolkit as toolkit
import ckanext.tiledmap.logic.action as map_action
import ckanext.tiledmap.logic.auth as map_auth
from ckanext.tiledmap.config import config as plugin_config
from ckanext.tiledmap.lib.helpers import mustache_wrapper, dwc_field_title
from ckanext.tiledmap.db import _get_engine
from ckanext.datastore.interfaces import IDatastore
from ckan.common import _

import ckan.logic as logic
get_action = logic.get_action

import ckan.lib.navl.dictization_functions as df
ignore_empty = p.toolkit.get_validator(u'ignore_empty')
Invalid = df.Invalid
Missing = df.Missing


class TiledMapPlugin(p.SingletonPlugin):
    '''Windshaft map plugin
    
    This plugin replaces the recline preview template to use a custom map engine.
    The plugin provides controller routes to server tiles and grid from the winsdhaft
    backend. See MapController for configuration options.


    '''
    p.implements(p.IConfigurer)
    p.implements(p.IRoutes, inherit=True)
    p.implements(p.IActions)
    p.implements(p.IAuthFunctions)
    p.implements(p.ITemplateHelpers)
    p.implements(p.IResourceView, inherit=True)
    p.implements(p.IConfigurable)

    ## IConfigurer
    def update_config(self, config):
        '''Add our template directories to the list of available templates

        :param config: 

        '''
        p.toolkit.add_template_directory(config, u'theme/templates')
        p.toolkit.add_public_directory(config, u'theme/public')
        p.toolkit.add_resource(u'theme/public', u'ckanext-tiledmap')

    ## IRoutes
    def before_map(self, map):
        '''Add routes to our tile/grid serving functionality

        :param map: 

        '''
        map.connect('/map-tile/{z}/{x}/{y}.png', controller=u'ckanext.tiledmap.controllers.map:MapController', action=u'tile')
        map.connect('/map-grid/{z}/{x}/{y}.grid.json', controller=u'ckanext.tiledmap.controllers.map:MapController', action=u'grid')
        map.connect('/map-info', controller=u'ckanext.tiledmap.controllers.map:MapController', action=u'map_info')

        return map

    ## IActions
    def get_actions(self):
        '''Add actions to override resource create/update/delete actions'''
        return {
            u'resource_view_create': map_action.resource_view_create,
            u'resource_view_update': map_action.resource_view_update,
            u'resource_view_delete': map_action.resource_view_delete
        }

    ## IAuthFunctions
    def get_auth_functions(self):
        '''Add auth functions for access to geom column creation actions'''
        return {
            u'create_geom_columns': map_auth.create_geom_columns,
            u'update_geom_columns': map_auth.update_geom_columns
        }

    ## ITemplateHelpers
    def get_helpers(self):
        '''Add a template helper for formating mustache templates server side'''
        return {
            u'mustache': mustache_wrapper,
            u'dwc_field_title': dwc_field_title
        }

    ## IConfigurable
    def configure(self, config):
        '''

        :param config: 

        '''
        plugin_config.update(config)

    ## IResourceView
    def info(self):
        ''' '''
        return {
            u'name': u'tiledmap',
            u'title': u'Tiled map',
            u'schema': {
                u'latitude_field': [self._is_datastore_field, self._is_latitude_field],
                u'longitude_field': [self._is_datastore_field, self._is_longitude_field],
                u'repeat_map': [self._boolean_validator],
                u'enable_plot_map': [self._boolean_validator],
                u'enable_grid_map': [self._boolean_validator],
                u'enable_heat_map': [self._boolean_validator],
                u'plot_marker_color': [self._color_validator],
                u'plot_marker_line_color': [self._color_validator],
                u'grid_base_color': [self._color_validator],
                u'heat_intensity': [self._float_01_validator],
                u'enable_utf_grid': [self._boolean_validator],
                u'utf_grid_title': [self._is_datastore_field],
                u'utf_grid_fields': [ignore_empty, self._is_datastore_field],
                u'overlapping_records_view': [self._is_view_id],
            },
            u'icon': u'compass',
            u'iframed': True,
            u'filterable': True,
            u'preview_enabled': False,
            u'full_page_edit': False
        }

    def view_template(self, context, data_dict):
        '''

        :param context: 
        :param data_dict: 

        '''
        return u'tiledmap_view.html'

    def form_template(self, context, data_dict):
        '''

        :param context: 
        :param data_dict: 

        '''
        return u'tiledmap_form.html'

    def can_view(self, data_dict):
        '''Specificy which resources can be viewed by this plugin

        :param data_dict: 

        '''
        # Check that the Windshaft server is configured
        if ((plugin_config.get(u'tiledmap.windshaft.host', None) is None) or
           (plugin_config.get(u'tiledmap.windshaft.port', None) is None)):
            return False
        # Check that we have a datastore for this resource
        if data_dict[u'resource'].get(u'datastore_active'):
            return True
        return False

    def setup_template_variables(self, context, data_dict):
        '''Setup variables available to templates

        :param context: 
        :param data_dict: 

        '''
        #TODO: Apply variables to appropriate view.
        datastore_fields = self._get_datastore_fields(data_dict[u'resource'][u'id'], context)
        views = p.toolkit.get_action(u'resource_view_list')(context, {u'id': data_dict[u'resource'][u'id']})
        if u'id' in data_dict[u'resource_view']:
            views = [v for v in views if v[u'id'] != data_dict[u'resource_view'][u'id']]
        views = [{u'text': _(u'(None)'), u'value': u''}] + [{u'text': v[u'title'], u'value': v[u'id']} for v in views]
        return {
            u'resource_json': json.dumps(data_dict[u'resource']),
            u'resource_view_json': json.dumps(data_dict[u'resource_view']),
            u'map_fields': [{u'text': f, u'value': f} for f in datastore_fields],
            u'available_views': views,
            u'defaults': plugin_config,
            u'is_new': not(u'id' in data_dict[u'resource_view'])
        }

    def _is_datastore_field(self, key, data, errors, context):
        '''Check that a field is indeed a datastore field

        :param key: 
        :param data: 
        :param errors: 
        :param context: 

        '''
        if isinstance(data[key], list):
            if not set(data[key]).issubset(self._get_datastore_fields(context[u'resource'].id, context)):
                raise p.toolkit.Invalid(u'"{0}" is not a valid parameter'.format(data[key]))
        elif not data[key] in self._get_datastore_fields(context[u'resource'].id, context):
            raise p.toolkit.Invalid(u'"{0}" is not a valid parameter'.format(data[key]))

    def _get_datastore_fields(self, rid, context):
        '''

        :param rid: 
        :param context: 

        '''
        if not hasattr(self, u'_datastore_fields'):
            self._datastore_fields = {}
        if not (rid in self._datastore_fields):
            data = {u'resource_id': rid, u'limit': 0}
            fields = toolkit.get_action(u'datastore_search')(context, data)[u'fields']
            self._datastore_fields[rid] = [f[u'id'] for f in fields]

        return self._datastore_fields[rid]

    def _boolean_validator(self, value, context):
        '''Validate a field as a boolean. Assuming missing value means false

        :param value: 
        :param context: 

        '''
        if isinstance(value, bool):
            return value
        elif (isinstance(value, str) or isinstance(value, unicode)) and value.lower() in [u'true', u'yes', u't', u'y', u'1']:
            return True
        elif (isinstance(value, str) or isinstance(value, unicode)) and value.lower() in [u'false', u'no', u'f', u'n', u'0']:
            return False
        elif isinstance(value, Missing):
            return False
        else:
            raise p.toolkit.Invalid(_(u'Value must a true/false value (ie. true/yes/t/y/1 or false/no/f/n/0)'))

    def _color_validator(self, value, context):
        '''Validate a value is a CSS hex color

        :param value: 
        :param context: 

        '''
        if re.match(u'^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$', value):
            if value[0] != u'#':
                return u'#' + value
            else:
                return value
        else:
            raise p.toolkit.Invalid(_(u'Colors must be formed of three or six RGB hex value, optionally preceded by a # sign (eg. #E55 or #F4A088)'))

    def _float_01_validator(self, value, context):
        '''Validate value is a float number between 0 and 1

        :param value: 
        :param context: 

        '''
        try:
            value = float(value)
        except:
            raise p.toolkit.Invalid(_(u'Must be a decimal number, between 0 and 1'))
        if value < 0 or value > 1:
            raise p.toolkit.Invalid(_(u'Must be a decimal number, between 0 and 1'))

        return value

    def _is_view_id(self, value, context):
        '''Ensure this is a view id on the current resource

        :param value: 
        :param context: 

        '''
        if value:
            views = p.toolkit.get_action(u'resource_view_list')(context, {u'id': context[u'resource'].id})
            if value not in [v[u'id'] for v in views]:
                raise p.toolkit.Invalid(_(u'Must be a view on the current resource'))

        return value

    def _is_latitude_field(self, value, context):
        '''Ensure this field can be used for latitudes

        :param value: 
        :param context: 

        '''
        # We can't use datastore_search for this, as we need operators
        db = _get_engine()
        metadata = MetaData()
        table = Table(context[u'resource'].id, metadata, Column(value, Numeric))

        query = select([func.count(1).label(u'count')], from_obj=table)
        query = query.where(not_(table.c[value] == None))
        query = query.where(or_(cast(table.c[value], Numeric) < -90, cast(table.c[value], Numeric) > 90))
        with db.begin() as connection:
            try:
                query_result = connection.execute(query)
            except DataError as e:
                raise p.toolkit.Invalid(_(u'Latitude field must contain numeric data'))

            row = query_result.fetchone()
            query_result.close()
            if row[u'count'] > 0:
                raise p.toolkit.Invalid(_(u'Latitude field must be between -90 and 90'))
        return value

    def _is_longitude_field(self, value, context):
        '''Ensure this field can be used for longitudes

        :param value: 
        :param context: 

        '''
        # We can't use datastore_search for this, as we need operators
        db = _get_engine()
        metadata = MetaData()
        table = Table(context[u'resource'].id, metadata, Column(value, Numeric))

        query = select([func.count(1).label(u'count')], from_obj=table)
        query = query.where(not_(table.c[value] == None))
        query = query.where(or_(cast(table.c[value], Numeric) < -180, cast(table.c[value], Numeric) > 180))
        with db.begin() as connection:
            try:
                query_result = connection.execute(query)
            except DataError as e:
                raise p.toolkit.Invalid(_(u'Longitude field must contain numeric data'))

            row = query_result.fetchone()
            query_result.close()
            if row[u'count'] > 0:
                raise p.toolkit.Invalid(_(u'Longitude field must be between -180 and 180'))
        return value
