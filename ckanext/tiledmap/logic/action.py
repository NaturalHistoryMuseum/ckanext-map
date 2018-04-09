#!/usr/bin/env python
# encoding: utf-8
#
# This file is part of ckanext-map
# Created by the Natural History Museum in London, UK

from ckanext.dataspatial.lib.postgis import (create_postgis_columns, has_postgis_columns,
                                             populate_postgis_columns)
from sqlalchemy.exc import DataError, InternalError, ProgrammingError

from ckan.lib.helpers import flash_error, flash_success
from ckan.plugins import toolkit


@toolkit.chained_action
def resource_view_create(prev_func, context, data_dict):
    '''Override ckan's resource_view_create so we can create geom fields when new
    tiled map views are added

    :param prev_func: the function being overridden
    :param context: 
    :param data_dict: 

    '''
    # Invoke ckan resource_view_create
    r = prev_func(context, data_dict)
    if r[u'view_type'] == u'tiledmap':
        _create_update_resource(r, context, data_dict)
    return r


@toolkit.chained_action
def resource_view_update(prev_func, context, data_dict):
    '''Override ckan's resource_view_update so we can update geom fields when the
    tiled map view is edited

    :param prev_func: the function being overridden
    :param context: 
    :param data_dict: 

    '''
    # Invoke ckan resource_view_update
    r = prev_func(context, data_dict)
    if r[u'view_type'] == u'tiledmap':
        _create_update_resource(r, context, data_dict)
    return r


@toolkit.chained_action
def resource_view_delete(prev_func, context, data_dict):
    '''

    :param context: 
    :param data_dict: 

    '''
    # TODO: We need to check if there any other tiled map view on the given resource.
    # If not, we can drop the fields.
    r = prev_func(context, data_dict)
    return r


def _create_update_resource(r, context, data_dict):
    '''Create/update geom field on the given resource

    :param r: 
    :param context: 
    :param data_dict: 

    '''
    options = dict(data_dict.items() + {
        u'populate': False
        }.items())
    if not has_postgis_columns(data_dict[u'resource_id']):
        try:
            create_postgis_columns(data_dict[u'resource_id'])
        except ProgrammingError as e:
            flash_error(toolkit._(
                u'The extension failed to initialise the database table to support '
                u'geometries. You will not be able to use this view. Please inform an '
                u'administrator.'))
            return
    try:
        populate_postgis_columns(
            data_dict[u'resource_id'],
            data_dict[u'latitude_field'],
            data_dict[u'longitude_field']
            )
    except (DataError, InternalError) as e:
        flash_error(toolkit._(
            u'It was not possible to create the geometry data from the given '
            u'latitude/longitude columns.' +
            u'Those columns must contain only decimal numbers, with latitude between '
            u'-90 and +90 and longitude between -180 and +180. Please correct the data '
            u'or select different fields.'))
    else:
        flash_success(toolkit._(u'Successfully created the geometric data.'))
