#!/usr/bin/env python
# encoding: utf-8
#
# This file is part of ckanext-map
# Created by the Natural History Museum in London, UK

from sqlalchemy.exc import ProgrammingError, DataError, InternalError

from ckan.common import _
from ckan.lib.helpers import flash_error, flash_success
from ckan.logic.action.create import resource_view_create as ckan_resource_view_create
from ckan.logic.action.delete import resource_view_delete as ckan_resource_view_delete
from ckan.logic.action.update import resource_view_update as ckan_resource_view_update
from ckanext.dataspatial.lib.postgis import has_postgis_columns, create_postgis_columns, populate_postgis_columns

def resource_view_create(context, data_dict):
    '''Override ckan's resource_view_create so we can create geom fields when new tiled map views are added

    :param context: 
    :param data_dict: 

    '''
    # Invoke ckan resource_view_create
    r = ckan_resource_view_create(context, data_dict)
    if r[u'view_type'] == u'tiledmap':
        _create_update_resource(r, context, data_dict)
    return r


def resource_view_update(context, data_dict):
    '''Override ckan's resource_view_update so we can update geom fields when the tiled map view is edited

    :param context: 
    :param data_dict: 

    '''
    # Invoke ckan resource_view_update
    r = ckan_resource_view_update(context, data_dict)
    if r[u'view_type'] == u'tiledmap':
        _create_update_resource(r, context, data_dict)
    return r


def resource_view_delete(context, data_dict):
    '''

    :param context: 
    :param data_dict: 

    '''
    # TODO: We need to check if there any other tiled map view on the given resource. If not, we can drop the fields.
    r = ckan_resource_view_delete(context, data_dict)
    return r

def _create_update_resource(r, context, data_dict):
    '''Create/update geom field on the given resource

    :param r: 
    :param context: 
    :param data_dict: 

    '''
    options = dict(data_dict.items() + {u'populate': False}.items())
    if not has_postgis_columns(data_dict[u'resource_id']):
        try:
             create_postgis_columns(data_dict[u'resource_id'])
        except ProgrammingError as e:
            flash_error(_(u'The extension failed to initialze the database table to support geometries. You will' +
            u' not be able to use this view. Please inform an administrator.'))
            return
    try:
        populate_postgis_columns(
            data_dict[u'resource_id'],
            data_dict[u'latitude_field'],
            data_dict[u'longitude_field']
        )
except (DataError, InternalError) as e:
        flash_error(_(u'It was not possible to create the geometry data from the given latitude/longitude columns.' +
        u'Those columns must contain only decimal numbers, with latitude between -90 and +90 and longitude ' +
        u'between -180 and +180. Please correct the data or select different fields.'))
    else:
        flash_success(_(u'Successfully created the geometric data.'))
