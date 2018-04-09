#!/usr/bin/env python
# encoding: utf-8
#
# This file is part of ckanext-map
# Created by the Natural History Museum in London, UK

import re
import json
import urllib
import urlparse

from pylons import config
import paste.fixture
from sqlalchemy import create_engine
import nose
from mock import patch

import ckan
import ckan.tests as tests
import ckan.plugins as p
import ckan.config.middleware as middleware
import ckan.lib.create_test_data as ctd
from ckan.logic.action.create import package_create
from ckan.logic.action.delete import package_delete
from ckanext.datastore.logic.action import datastore_create, datastore_delete, datastore_upsert
from ckanext.tiledmap.config import config as tm_config

from nose.tools import assert_equal, assert_true, assert_false, assert_in

class TestTileFetching(tests.WsgiAppCase):
    '''Test cases for the Map plugin'''
    dataset = None
    resource = None
    context = None

    @classmethod
    @patch(u'ckan.lib.helpers.flash')
    def setup_class(cls, mock_flash):
        '''Prepare the test

        :param mock_flash: 

        '''
        # We need datastore for these tests.
        if not tests.is_datastore_supported():
            raise nose.SkipTest(u'Datastore not supported')

        # Setup a test app
        wsgiapp = middleware.make_app(config[u'global_conf'], **config)
        cls.app = paste.fixture.TestApp(wsgiapp)
        ctd.CreateTestData.create()
        cls.context = {u'model': ckan.model,
                       u'session': ckan.model.Session,
                       u'user': ckan.model.User.get(u'testsysadmin').name}

        # Load plugins
        p.load(u'tiledmap')
        p.load(u'datastore')

        # Set windshaft host/port as these settings do not have a default.
        # TODO: Test that calls fail if not set
        tm_config.update({
            u'tiledmap.windshaft.host': u'127.0.0.1',
            u'tiledmap.windshaft.port': u'4000'
        })

        # Copy tiledmap settings
        cls.config = dict(tm_config.items())

        # Setup a dummy datastore.
        cls.dataset = package_create(cls.context, {u'name': u'map-test-dataset'})
        cls.resource = datastore_create(cls.context, {
            u'resource': {
                u'package_id': cls.dataset[u'id']
            },
            u'fields': [
                {u'id': u'id', u'type': u'integer'},
                {u'id': u'latitude', u'type': u'numeric'},
                {u'id': u'longitude', u'type': u'numeric'},
                {u'id': u'some_field_1', u'type': u'text'},
                {u'id': u'some_field_2', u'type': u'text'}
            ],
            u'primary_key': u'id'
        })

        # Add some data. We add 4 records such that:
        # - The first three records have 'some_field_1' set to 'hello' ;
        # - The third record does not have a geom ;
        # - The fourth record has a geom, but 'some_field_1' is set to something elese.
        datastore_upsert(cls.context, {
            u'resource_id': cls.resource[u'resource_id'],
            u'method': u'upsert',
            u'records': [{
                u'id': u'1',
                u'latitude': -15,
                u'longitude': -11,
                u'some_field_1': u'hello',
                u'some_field_2': u'world'
            }, {
                u'id': 2,
                u'latitude': 48,
                u'longitude': 23,
                u'some_field_1': u'hello',
                u'some_field_2': u'again'
            }, {
                u'id': 3,
                u'latitude': None,
                u'longitude': None,
                u'some_field_1': u'hello',
                u'some_field_2': u'hello'
            }, {
                u'id': 4,
                u'latitude': 80,
                u'longitude': 80,
                u'some_field_1': u'all your bases',
                u'some_field_2': u'are belong to us'
            }]
        })

        # Create a tiledmap resource view. This process itself is fully tested in test_view_create.py.
        # This will also generate the geometry column - that part of the process is fully tested in test_actions
        data_dict = {
            u'description': u'',
            u'title': u'test',
            u'resource_id': cls.resource[u'resource_id'],
            u'plot_marker_color': u'#EE0000',
            u'enable_plot_map': u'True',
            u'overlapping_records_view': u'',
            u'longitude_field': u'longitude',
            u'heat_intensity': u'0.1',
            u'view_type': u'tiledmap',
            u'utf_grid_title': u'_id',
            u'plot_marker_line_color': u'#FFFFFF',
            u'latitude_field': u'latitude',
            u'enable_utf_grid': u'True',
            u'utf_grid_fields' : [u'some_field_1', u'some_field_2'],
            u'grid_base_color': u'#F02323',
            u'enable_heat_map': u'True',
            u'enable_grid_map': u'True'
        }

        resource_view_create = p.toolkit.get_action(u'resource_view_create')
        cls.resource_view = resource_view_create(cls.context, data_dict)

        # Create a resource that does not have spatial fields
        cls.non_spatial_resource = datastore_create(cls.context, {
            u'resource': {
                u'package_id': cls.dataset[u'id']
            },
            u'fields': [
                {u'id': u'id', u'type': u'integer'},
                {u'id': u'some_field', u'type': u'text'}
            ],
            u'primary_key': u'id'
        })



    @classmethod
    def teardown_class(cls):
        '''Clean up after the test'''
        datastore_delete(cls.context, {u'resource_id': cls.resource[u'resource_id']})
        package_delete(cls.context, {u'id': cls.dataset[u'id']})
        p.unload(u'tiledmap')
        p.unload(u'datastore')

    def teardown(self):
        ''' '''
        # Ensure all settings are reset to default.
        tm_config.update(TestTileFetching.config)

    def test_map_info(self):
        '''Test the map-info controller returns the expected data'''
        filters = u'some_field_1:hello'
        res = self.app.get('/map-info?resource_id={resource_id}&view_id={view_id}&filters={filters}&fetch_id={fetch_id}'.format(
            resource_id=TestTileFetching.resource[u'resource_id'],
            view_id=TestTileFetching.resource_view[u'id'],
            filters=urllib.quote_plus(filters),
            fetch_id=44
        ))
        values = json.loads(res.body)
        assert_true(values[u'geospatial'])
        assert_equal(values[u'geom_count'], 2)
        assert_equal(values[u'fetch_id'], u'44')
        assert_in(u'initial_zoom', values)
        assert_in(u'tile_layer', values)
        assert_equal(values[u'bounds'], [[-15, -11], [48, 23]])
        assert_in(u'map_style', values)
        assert_in(u'plot', values[u'map_styles'])
        assert_in(u'heatmap', values[u'map_styles'])
        assert_in(u'gridded', values[u'map_styles'])
        for control in [u'drawShape', u'mapType']:
            assert_in(control, values[u'control_options'])
            assert_in(u'position', values[u'control_options'][control])
        for plugin in [u'tooltipInfo', u'pointInfo']:
            assert_in(plugin, values[u'plugin_options'])
        assert_in(u'template', values[u'plugin_options'][u'pointInfo'])
        assert_in(u'template', values[u'plugin_options'][u'tooltipInfo'])
