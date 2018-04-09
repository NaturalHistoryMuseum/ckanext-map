#!/usr/bin/env python
# encoding: utf-8
#
# This file is part of ckanext-map
# Created by the Natural History Museum in London, UK

import ckan.plugins as p


def map_auth(context, data_dict, privilege=u'resource_update'):
    '''

    :param context: 
    :param data_dict: 
    :param privilege:  (Default value = u'resource_update')

    '''
    if not u'id' in data_dict:
        data_dict[u'id'] = data_dict.get(u'resource_id')
    user = context.get(u'user')

    authorized = p.toolkit.check_access(privilege, context, data_dict)

    if not authorized:
        return {
            u'success': False,
            u'msg': p.toolkit._(u'User {0} not authorized to update resource {1}'
                    .format(str(user), data_dict[u'id']))
        }
    else:
        return {u'success': True}


def create_geom_columns(context, data_dict):
    '''

    :param context: 
    :param data_dict: 

    '''
    return map_auth(context, data_dict)


def update_geom_columns(context, data_dict):
    '''

    :param context: 
    :param data_dict: 

    '''
    return map_auth(context, data_dict)
